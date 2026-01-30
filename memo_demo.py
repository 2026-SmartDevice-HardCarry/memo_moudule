"""
스마트 미러 메모 데모
- 카메라 피드 + 녹화 상태 표시
- 음성 명령으로 메모 시작/중지
- 키보드 단축키 지원
"""

import cv2
import time
import os
import sys
import threading

# 메모 모듈
from memo_module import SmartMirrorMemo, SPEECH_RECOGNITION_AVAILABLE, PYAUDIO_AVAILABLE


def main():
    print("=" * 50)
    print("    스마트 미러 메모 데모")
    print("=" * 50)
    print()
    print(f"음성 인식: {'✓ 사용 가능' if SPEECH_RECOGNITION_AVAILABLE else '✗ 사용 불가'}")
    print(f"오디오 녹음: {'✓ 사용 가능' if PYAUDIO_AVAILABLE else '✗ 사용 불가'}")
    print()
    
    # 메모 모듈 초기화
    memo = SmartMirrorMemo()
    
    # 콜백 설정
    recording_status = {"mode": None, "start_time": None}
    
    def on_recording_start(mode):
        recording_status["mode"] = mode
        recording_status["start_time"] = time.time()
        mode_text = "🎤 음성 메모" if mode == "voice" else "🎥 영상 메모"
        print(f"\n[녹화 시작] {mode_text}")
    
    def on_recording_stop(mode, filepath):
        recording_status["mode"] = None
        recording_status["start_time"] = None
        if filepath:
            print(f"[녹화 완료] {filepath}")
    
    memo.on_recording_start = on_recording_start
    memo.on_recording_stop = on_recording_stop
    
    # 카메라 초기화
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: 카메라를 열 수 없습니다.")
        return
    
    # 프레임 크기 가져오기
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print()
    print("─" * 50)
    print("  조작 방법")
    print("─" * 50)
    print("  음성 명령:")
    print("    • \"음성 메모\" - 음성 녹음 시작")
    print("    • \"영상 메모\" - 영상 녹화 시작")
    print("    • \"중지\" - 녹화 중지")
    print()
    print("  키보드 단축키:")
    print("    • V - 음성 메모 시작")
    print("    • R - 영상 메모 시작")
    print("    • S - 녹화 중지")
    print("    • P - 메모 재생 UI 열기")
    print("    • Q - 종료")
    print("─" * 50)
    print()
    
    # 메모 시스템 시작 (음성 명령 대기)
    memo.start()
    
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("프레임을 읽을 수 없습니다.")
                break
            
            # 좌우 반전 (거울 모드)
            frame = cv2.flip(frame, 1)
            
            # 영상 녹화 중이면 프레임 저장
            if memo.get_recording_mode() == "video":
                memo.write_video_frame(frame)
            
            # 상태 표시 오버레이
            overlay = frame.copy()
            
            # 녹화 상태 표시
            if recording_status["mode"]:
                mode = recording_status["mode"]
                elapsed = time.time() - recording_status["start_time"]
                
                # 녹화 표시 (빨간 원)
                cv2.circle(overlay, (30, 30), 15, (0, 0, 255), -1)
                
                # 녹화 시간
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                time_text = f"{minutes:02d}:{seconds:02d}"
                
                if mode == "voice":
                    status_text = f"🎤 음성 녹음 중... {time_text}"
                else:
                    status_text = f"🎥 영상 녹화 중... {time_text}"
                
                # 텍스트 배경
                cv2.rectangle(overlay, (50, 10), (350, 50), (0, 0, 0), -1)
                cv2.putText(overlay, status_text, (60, 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            else:
                # 대기 상태
                cv2.rectangle(overlay, (10, 10), (300, 50), (0, 0, 0), -1)
                cv2.putText(overlay, "Ready - Say 'memo' to start", (20, 38),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # 도움말 표시 (하단)
            help_y = frame_height - 30
            cv2.rectangle(overlay, (0, help_y - 10), (frame_width, frame_height), (0, 0, 0), -1)
            cv2.putText(overlay, "V:Voice | R:Video | S:Stop | P:Player | Q:Quit",
                       (10, help_y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            
            # 오버레이 적용 (투명도)
            alpha = 0.7
            frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
            
            # 화면 표시
            cv2.imshow("Smart Mirror Memo Demo", frame)
            
            # 키 입력 처리
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == ord('Q'):
                break
            elif key == ord('v') or key == ord('V'):
                if not memo.is_recording():
                    memo.start_voice_memo()
            elif key == ord('r') or key == ord('R'):
                if not memo.is_recording():
                    memo.start_video_memo((frame_width, frame_height))
            elif key == ord('s') or key == ord('S'):
                if memo.is_recording():
                    memo.stop_recording()
            elif key == ord('p') or key == ord('P'):
                # 메모 재생 UI 열기 (별도 스레드)
                def open_player():
                    try:
                        from memo_player_ui import MemoPlayerUI
                        player = MemoPlayerUI()
                        player.run()
                    except Exception as e:
                        print(f"Player error: {e}")
                
                threading.Thread(target=open_player, daemon=True).start()
    
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단됨")
    
    finally:
        # 정리
        print("\n정리 중...")
        memo.stop()
        cap.release()
        cv2.destroyAllWindows()
        
        # 저장된 메모 목록 출력
        memos = memo.get_memos()
        if memos:
            print("\n" + "=" * 50)
            print("    저장된 메모 목록")
            print("=" * 50)
            for m in memos[:5]:  # 최근 5개만 표시
                icon = "🎤" if m["type"] == "voice" else "🎥"
                print(f"  {icon} {m['filename']}")
            if len(memos) > 5:
                print(f"  ... 외 {len(memos) - 5}개")
            print()
        
        print("데모 종료")


if __name__ == "__main__":
    main()
