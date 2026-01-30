"""
스마트 미러 메모 재생 UI
- 터치/클릭 기반 인터페이스
- 음성 메모 재생
- 영상 메모 재생
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import List, Optional
import threading
import cv2
from PIL import Image, ImageTk

# 오디오 재생
try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Warning: pygame not installed. Audio playback disabled.")

# 메모 모듈
from memo_module import MemoManager


class MemoPlayerUI:
    """메모 재생 UI 클래스"""
    
    def __init__(self, memo_dir: str = None):
        # 저장 경로 설정
        if memo_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            memo_dir = os.path.join(script_dir, "memos")
        
        self.memo_dir = memo_dir
        self.memo_manager = MemoManager(memo_dir)
        
        # UI 초기화
        self.root = tk.Tk()
        self.root.title("📝 스마트 미러 메모")
        self.root.geometry("400x600")
        self.root.configure(bg="#1a1a2e")
        
        # 스타일 설정
        self._setup_styles()
        
        # UI 구성
        self._create_widgets()
        
        # 메모 목록 로드
        self.refresh_memos()
        
        # 재생 상태
        self._is_playing_audio = False
        self._video_window: Optional[tk.Toplevel] = None
    
    def _setup_styles(self):
        """UI 스타일 설정"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 프레임 스타일
        style.configure("Dark.TFrame", background="#1a1a2e")
        
        # 라벨 스타일
        style.configure("Title.TLabel",
                       background="#1a1a2e",
                       foreground="#eee",
                       font=("맑은 고딕", 20, "bold"))
        
        style.configure("Subtitle.TLabel",
                       background="#1a1a2e",
                       foreground="#888",
                       font=("맑은 고딕", 10))
        
        # 버튼 스타일
        style.configure("Play.TButton",
                       font=("맑은 고딕", 12),
                       padding=10)
        
        style.configure("Delete.TButton",
                       font=("맑은 고딕", 10),
                       padding=5)
    
    def _create_widgets(self):
        """UI 위젯 생성"""
        # 헤더
        header_frame = ttk.Frame(self.root, style="Dark.TFrame")
        header_frame.pack(fill=tk.X, padx=20, pady=20)
        
        title_label = ttk.Label(header_frame, text="📝 메모 목록", style="Title.TLabel")
        title_label.pack(side=tk.LEFT)
        
        # 새로고침 버튼
        refresh_btn = tk.Button(header_frame, text="🔄", 
                               command=self.refresh_memos,
                               bg="#16213e", fg="white",
                               font=("맑은 고딕", 14),
                               bd=0, padx=10, pady=5)
        refresh_btn.pack(side=tk.RIGHT)
        
        # 메모 개수 표시
        self.count_label = ttk.Label(header_frame, text="", style="Subtitle.TLabel")
        self.count_label.pack(side=tk.RIGHT, padx=10)
        
        # 메모 목록 스크롤 영역
        list_frame = ttk.Frame(self.root, style="Dark.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        # 캔버스 + 스크롤바
        self.canvas = tk.Canvas(list_frame, bg="#1a1a2e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        
        self.memo_list_frame = ttk.Frame(self.canvas, style="Dark.TFrame")
        
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.memo_list_frame, anchor="nw")
        
        # 스크롤 영역 업데이트
        self.memo_list_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # 마우스 휠 스크롤
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
    
    def _on_frame_configure(self, event):
        """프레임 크기 변경 시 스크롤 영역 업데이트"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _on_canvas_configure(self, event):
        """캔버스 크기 변경 시 내부 프레임 너비 조정"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _on_mousewheel(self, event):
        """마우스 휠 스크롤"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def refresh_memos(self):
        """메모 목록 새로고침"""
        # 기존 위젯 삭제
        for widget in self.memo_list_frame.winfo_children():
            widget.destroy()
        
        # 메모 목록 가져오기
        memos = self.memo_manager.get_all_memos()
        counts = self.memo_manager.get_memo_count()
        
        # 개수 표시 업데이트
        self.count_label.config(text=f"🎤 {counts['voice']} | 🎥 {counts['video']}")
        
        if not memos:
            no_memo_label = tk.Label(self.memo_list_frame,
                                    text="저장된 메모가 없습니다.\n\n음성 명령으로 메모를 추가하세요:\n• \"음성 메모\"\n• \"영상 메모\"",
                                    bg="#1a1a2e", fg="#666",
                                    font=("맑은 고딕", 12),
                                    justify=tk.CENTER)
            no_memo_label.pack(pady=50)
            return
        
        # 메모 아이템 생성
        for memo in memos:
            self._create_memo_item(memo)
    
    def _create_memo_item(self, memo: dict):
        """메모 아이템 위젯 생성"""
        # 아이템 프레임
        item_frame = tk.Frame(self.memo_list_frame, bg="#16213e", padx=15, pady=12)
        item_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # 아이콘 + 정보
        icon = "🎤" if memo["type"] == "voice" else "🎥"
        type_text = "음성 메모" if memo["type"] == "voice" else "영상 메모"
        
        # 시간 포맷
        time_str = memo["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        
        # 파일 크기 포맷
        size_kb = memo["size"] / 1024
        if size_kb > 1024:
            size_str = f"{size_kb/1024:.1f} MB"
        else:
            size_str = f"{size_kb:.1f} KB"
        
        # 왼쪽 영역 (아이콘 + 정보)
        left_frame = tk.Frame(item_frame, bg="#16213e")
        left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        icon_label = tk.Label(left_frame, text=icon, 
                             bg="#16213e", fg="white",
                             font=("맑은 고딕", 24))
        icon_label.pack(side=tk.LEFT, padx=(0, 10))
        
        info_frame = tk.Frame(left_frame, bg="#16213e")
        info_frame.pack(side=tk.LEFT, fill=tk.X)
        
        type_label = tk.Label(info_frame, text=type_text,
                             bg="#16213e", fg="white",
                             font=("맑은 고딕", 12, "bold"))
        type_label.pack(anchor=tk.W)
        
        time_label = tk.Label(info_frame, text=time_str,
                             bg="#16213e", fg="#888",
                             font=("맑은 고딕", 9))
        time_label.pack(anchor=tk.W)
        
        size_label = tk.Label(info_frame, text=size_str,
                             bg="#16213e", fg="#666",
                             font=("맑은 고딕", 8))
        size_label.pack(anchor=tk.W)
        
        # 오른쪽 영역 (버튼들)
        btn_frame = tk.Frame(item_frame, bg="#16213e")
        btn_frame.pack(side=tk.RIGHT)
        
        # 재생 버튼
        play_btn = tk.Button(btn_frame, text="▶",
                            command=lambda m=memo: self._play_memo(m),
                            bg="#0f3460", fg="white",
                            font=("맑은 고딕", 14),
                            bd=0, padx=15, pady=8)
        play_btn.pack(side=tk.LEFT, padx=5)
        
        # 삭제 버튼
        delete_btn = tk.Button(btn_frame, text="🗑",
                              command=lambda m=memo: self._delete_memo(m),
                              bg="#e94560", fg="white",
                              font=("맑은 고딕", 12),
                              bd=0, padx=10, pady=8)
        delete_btn.pack(side=tk.LEFT)
        
        # 호버 효과
        def on_enter(e):
            item_frame.configure(bg="#0f3460")
            for child in item_frame.winfo_children():
                self._update_bg_recursive(child, "#0f3460")
        
        def on_leave(e):
            item_frame.configure(bg="#16213e")
            for child in item_frame.winfo_children():
                self._update_bg_recursive(child, "#16213e")
        
        item_frame.bind("<Enter>", on_enter)
        item_frame.bind("<Leave>", on_leave)
    
    def _update_bg_recursive(self, widget, bg_color):
        """위젯과 자식들의 배경색 업데이트"""
        try:
            if isinstance(widget, (tk.Frame, tk.Label)):
                widget.configure(bg=bg_color)
            for child in widget.winfo_children():
                self._update_bg_recursive(child, bg_color)
        except:
            pass
    
    def _play_memo(self, memo: dict):
        """메모 재생"""
        if memo["type"] == "voice":
            self._play_audio(memo["filepath"])
        else:
            self._play_video(memo["filepath"])
    
    def _play_audio(self, filepath: str):
        """음성 메모 재생"""
        if not PYGAME_AVAILABLE:
            messagebox.showerror("오류", "pygame이 설치되지 않아 오디오를 재생할 수 없습니다.")
            return
        
        try:
            if self._is_playing_audio:
                pygame.mixer.music.stop()
                self._is_playing_audio = False
            
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            self._is_playing_audio = True
            
            # 재생 완료 감지
            def check_playing():
                if pygame.mixer.music.get_busy():
                    self.root.after(100, check_playing)
                else:
                    self._is_playing_audio = False
            
            check_playing()
            
        except Exception as e:
            messagebox.showerror("오류", f"오디오 재생 실패: {e}")
    
    def _play_video(self, filepath: str):
        """영상 메모 재생"""
        if self._video_window:
            self._video_window.destroy()
        
        # 새 창 생성
        self._video_window = tk.Toplevel(self.root)
        self._video_window.title("🎥 영상 메모 재생")
        self._video_window.configure(bg="black")
        
        # 비디오 라벨
        video_label = tk.Label(self._video_window, bg="black")
        video_label.pack()
        
        # 닫기 버튼
        close_btn = tk.Button(self._video_window, text="✕ 닫기",
                             command=self._video_window.destroy,
                             bg="#e94560", fg="white",
                             font=("맑은 고딕", 12),
                             bd=0, padx=20, pady=10)
        close_btn.pack(pady=10)
        
        # 비디오 재생 스레드
        def play_video():
            cap = cv2.VideoCapture(filepath)
            if not cap.isOpened():
                messagebox.showerror("오류", "영상을 열 수 없습니다.")
                return
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            delay = int(1000 / fps) if fps > 0 else 33
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                if not self._video_window or not self._video_window.winfo_exists():
                    break
                
                # BGR -> RGB 변환
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # PIL 이미지로 변환
                img = Image.fromarray(frame_rgb)
                
                # 크기 조정
                img.thumbnail((640, 480))
                
                # Tkinter 이미지로 변환
                photo = ImageTk.PhotoImage(image=img)
                
                # 라벨 업데이트
                try:
                    video_label.configure(image=photo)
                    video_label.image = photo
                    self._video_window.update()
                except:
                    break
                
                cv2.waitKey(delay)
            
            cap.release()
        
        # 별도 스레드에서 재생
        threading.Thread(target=play_video, daemon=True).start()
    
    def _delete_memo(self, memo: dict):
        """메모 삭제"""
        type_text = "음성 메모" if memo["type"] == "voice" else "영상 메모"
        
        if messagebox.askyesno("삭제 확인", f"이 {type_text}를 삭제하시겠습니까?"):
            if self.memo_manager.delete_memo(memo["filepath"]):
                self.refresh_memos()
            else:
                messagebox.showerror("오류", "메모 삭제에 실패했습니다.")
    
    def run(self):
        """UI 실행"""
        self.root.mainloop()
    
    def destroy(self):
        """UI 종료"""
        if self._video_window:
            self._video_window.destroy()
        self.root.destroy()


# 테스트용
if __name__ == "__main__":
    print("=== Smart Mirror Memo Player UI ===")
    print(f"Pygame: {'Available' if PYGAME_AVAILABLE else 'Not Available'}")
    
    ui = MemoPlayerUI()
    ui.run()
