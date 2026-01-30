"""
스마트 미러 메모 모듈
- 음성 명령으로 메모 시작/중지
- 음성 메모 녹음 (WAV)
- 영상 메모 녹화 (MP4)
"""

import os
import threading
import time
import wave
from datetime import datetime
from typing import Callable, Optional, List
import cv2
import numpy as np

# 음성 인식 관련
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    print("Warning: speech_recognition not installed. Voice commands disabled.")

# 오디오 녹음 관련
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("Warning: pyaudio not installed. Audio recording disabled.")


class VoiceRecognizer:
    """음성 명령 인식 클래스"""
    
    # 지원하는 음성 명령
    COMMANDS = {
        "voice_memo": ["음성 메모", "음성 녹음", "보이스 메모", "voice memo"],
        "video_memo": ["영상 메모", "영상 녹화", "비디오 메모", "비디오 녹화", "video memo"],
        "stop": ["중지", "스탑", "그만", "stop", "끝"]
    }
    
    def __init__(self, callback: Optional[Callable[[str], None]] = None):
        """
        Args:
            callback: 명령 인식 시 호출될 콜백 함수. 명령 타입을 인자로 받음.
        """
        self.callback = callback
        self.is_listening = False
        self._listen_thread: Optional[threading.Thread] = None
        
        if SPEECH_RECOGNITION_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            # 주변 소음에 맞게 조정
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        else:
            self.recognizer = None
            self.microphone = None
    
    def start_listening(self):
        """음성 명령 감지 시작"""
        if not SPEECH_RECOGNITION_AVAILABLE:
            print("Speech recognition not available.")
            return
        
        if self.is_listening:
            return
        
        self.is_listening = True
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        print("Voice command listening started...")
    
    def stop_listening(self):
        """음성 명령 감지 중지"""
        self.is_listening = False
        if self._listen_thread:
            self._listen_thread.join(timeout=2)
        print("Voice command listening stopped.")
    
    def _listen_loop(self):
        """백그라운드에서 음성 명령 감지"""
        while self.is_listening:
            try:
                with self.microphone as source:
                    # 3초 동안 음성 대기
                    audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=5)
                
                try:
                    # Google Speech Recognition (무료, 인터넷 필요)
                    text = self.recognizer.recognize_google(audio, language="ko-KR")
                    print(f"인식된 음성: {text}")
                    
                    # 명령어 매칭
                    command = self._match_command(text)
                    if command and self.callback:
                        self.callback(command)
                        
                except sr.UnknownValueError:
                    pass  # 음성을 인식하지 못함
                except sr.RequestError as e:
                    print(f"Speech recognition error: {e}")
                    
            except sr.WaitTimeoutError:
                pass  # 타임아웃, 계속 대기
            except Exception as e:
                print(f"Voice recognition error: {e}")
                time.sleep(0.5)
    
    def _match_command(self, text: str) -> Optional[str]:
        """텍스트에서 명령어 매칭"""
        text_lower = text.lower()
        for cmd_type, keywords in self.COMMANDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return cmd_type
        return None


class AudioRecorder:
    """음성 메모 녹음 클래스"""
    
    def __init__(self, save_dir: str = "memos"):
        self.save_dir = save_dir
        self.is_recording = False
        self._record_thread: Optional[threading.Thread] = None
        self._frames: List[bytes] = []
        self._current_file: Optional[str] = None
        
        # 오디오 설정
        self.format = pyaudio.paInt16 if PYAUDIO_AVAILABLE else None
        self.channels = 1
        self.rate = 44100
        self.chunk = 1024
        
        # 저장 폴더 생성
        os.makedirs(save_dir, exist_ok=True)
    
    def start_recording(self) -> Optional[str]:
        """음성 녹음 시작. 저장될 파일 경로 반환."""
        if not PYAUDIO_AVAILABLE:
            print("PyAudio not available. Cannot record audio.")
            return None
        
        if self.is_recording:
            print("Already recording audio.")
            return self._current_file
        
        # 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_file = os.path.join(self.save_dir, f"voice_memo_{timestamp}.wav")
        
        self.is_recording = True
        self._frames = []
        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()
        
        print(f"Audio recording started: {self._current_file}")
        return self._current_file
    
    def stop_recording(self) -> Optional[str]:
        """음성 녹음 중지. 저장된 파일 경로 반환."""
        if not self.is_recording:
            return None
        
        self.is_recording = False
        if self._record_thread:
            self._record_thread.join(timeout=2)
        
        # WAV 파일 저장
        if self._frames and self._current_file:
            self._save_wav()
            print(f"Audio saved: {self._current_file}")
            return self._current_file
        
        return None
    
    def _record_loop(self):
        """백그라운드에서 오디오 녹음"""
        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )
            
            while self.is_recording:
                data = stream.read(self.chunk, exception_on_overflow=False)
                self._frames.append(data)
            
            stream.stop_stream()
            stream.close()
            audio.terminate()
            
        except Exception as e:
            print(f"Audio recording error: {e}")
            self.is_recording = False
    
    def _save_wav(self):
        """녹음된 오디오를 WAV 파일로 저장"""
        try:
            audio = pyaudio.PyAudio()
            with wave.open(self._current_file, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(audio.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(self._frames))
            audio.terminate()
        except Exception as e:
            print(f"Error saving WAV: {e}")


class VideoRecorder:
    """영상 메모 녹화 클래스"""
    
    def __init__(self, save_dir: str = "memos"):
        self.save_dir = save_dir
        self.is_recording = False
        self._current_file: Optional[str] = None
        self._video_writer: Optional[cv2.VideoWriter] = None
        self._audio_recorder: Optional[AudioRecorder] = None
        
        # 비디오 설정
        self.fps = 30.0
        self.frame_size = (640, 480)
        
        # 저장 폴더 생성
        os.makedirs(save_dir, exist_ok=True)
    
    def start_recording(self, frame_size: tuple = None) -> Optional[str]:
        """영상 녹화 시작. 저장될 파일 경로 반환."""
        if self.is_recording:
            print("Already recording video.")
            return self._current_file
        
        if frame_size:
            self.frame_size = frame_size
        
        # 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_file = os.path.join(self.save_dir, f"video_memo_{timestamp}.mp4")
        
        # VideoWriter 초기화
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self._video_writer = cv2.VideoWriter(
            self._current_file,
            fourcc,
            self.fps,
            self.frame_size
        )
        
        # 오디오 녹음도 시작 (별도 파일로)
        audio_file = self._current_file.replace('.mp4', '_audio.wav')
        self._audio_recorder = AudioRecorder(self.save_dir)
        self._audio_recorder._current_file = audio_file
        if PYAUDIO_AVAILABLE:
            self._audio_recorder.start_recording()
        
        self.is_recording = True
        print(f"Video recording started: {self._current_file}")
        return self._current_file
    
    def write_frame(self, frame: np.ndarray):
        """프레임 기록"""
        if self.is_recording and self._video_writer:
            # 프레임 크기 조정
            if frame.shape[1] != self.frame_size[0] or frame.shape[0] != self.frame_size[1]:
                frame = cv2.resize(frame, self.frame_size)
            self._video_writer.write(frame)
    
    def stop_recording(self) -> Optional[str]:
        """영상 녹화 중지. 저장된 파일 경로 반환."""
        if not self.is_recording:
            return None
        
        self.is_recording = False
        
        # 비디오 저장
        if self._video_writer:
            self._video_writer.release()
            self._video_writer = None
        
        # 오디오 저장
        if self._audio_recorder:
            self._audio_recorder.stop_recording()
            self._audio_recorder = None
        
        print(f"Video saved: {self._current_file}")
        return self._current_file


class MemoManager:
    """메모 파일 관리 클래스"""
    
    def __init__(self, memo_dir: str = "memos"):
        self.memo_dir = memo_dir
        os.makedirs(memo_dir, exist_ok=True)
    
    def get_all_memos(self) -> List[dict]:
        """모든 메모 목록 반환"""
        memos = []
        
        if not os.path.exists(self.memo_dir):
            return memos
        
        for filename in os.listdir(self.memo_dir):
            filepath = os.path.join(self.memo_dir, filename)
            if not os.path.isfile(filepath):
                continue
            
            # 오디오 파일 제외 (영상의 오디오 트랙)
            if "_audio.wav" in filename:
                continue
            
            memo_type = None
            if filename.startswith("voice_memo") and filename.endswith(".wav"):
                memo_type = "voice"
            elif filename.startswith("video_memo") and filename.endswith(".mp4"):
                memo_type = "video"
            
            if memo_type:
                # 파일명에서 타임스탬프 추출
                try:
                    timestamp_str = filename.split("_")[2] + "_" + filename.split("_")[3].split(".")[0]
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                except (IndexError, ValueError):
                    timestamp = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                memos.append({
                    "filename": filename,
                    "filepath": filepath,
                    "type": memo_type,
                    "timestamp": timestamp,
                    "size": os.path.getsize(filepath)
                })
        
        # 최신순 정렬
        memos.sort(key=lambda x: x["timestamp"], reverse=True)
        return memos
    
    def delete_memo(self, filepath: str) -> bool:
        """메모 삭제"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                
                # 영상 메모의 경우 오디오 파일도 삭제
                audio_path = filepath.replace('.mp4', '_audio.wav')
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                
                print(f"Memo deleted: {filepath}")
                return True
        except Exception as e:
            print(f"Error deleting memo: {e}")
        return False
    
    def get_memo_count(self) -> dict:
        """메모 개수 반환"""
        memos = self.get_all_memos()
        return {
            "total": len(memos),
            "voice": sum(1 for m in memos if m["type"] == "voice"),
            "video": sum(1 for m in memos if m["type"] == "video")
        }


class SmartMirrorMemo:
    """스마트 미러 메모 통합 클래스"""
    
    def __init__(self, save_dir: str = None):
        # 저장 경로 설정 (스크립트 위치 기준)
        if save_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            save_dir = os.path.join(script_dir, "memos")
        
        self.save_dir = save_dir
        
        # 모듈 초기화
        self.voice_recognizer = VoiceRecognizer(callback=self._on_voice_command)
        self.audio_recorder = AudioRecorder(save_dir)
        self.video_recorder = VideoRecorder(save_dir)
        self.memo_manager = MemoManager(save_dir)
        
        # 상태
        self.current_mode: Optional[str] = None  # "voice" or "video"
        self.is_active = False
        
        # 콜백
        self.on_recording_start: Optional[Callable[[str], None]] = None
        self.on_recording_stop: Optional[Callable[[str, str], None]] = None
    
    def start(self):
        """메모 시스템 시작 (음성 명령 대기)"""
        self.is_active = True
        self.voice_recognizer.start_listening()
        print("Smart Mirror Memo system started.")
    
    def stop(self):
        """메모 시스템 중지"""
        self.is_active = False
        self.stop_recording()
        self.voice_recognizer.stop_listening()
        print("Smart Mirror Memo system stopped.")
    
    def _on_voice_command(self, command: str):
        """음성 명령 처리"""
        print(f"Voice command received: {command}")
        
        if command == "voice_memo":
            self.start_voice_memo()
        elif command == "video_memo":
            self.start_video_memo()
        elif command == "stop":
            self.stop_recording()
    
    def start_voice_memo(self):
        """음성 메모 시작"""
        if self.current_mode:
            print(f"Already recording {self.current_mode}. Stop first.")
            return
        
        self.current_mode = "voice"
        filepath = self.audio_recorder.start_recording()
        
        if self.on_recording_start:
            self.on_recording_start("voice")
        
        return filepath
    
    def start_video_memo(self, frame_size: tuple = None):
        """영상 메모 시작"""
        if self.current_mode:
            print(f"Already recording {self.current_mode}. Stop first.")
            return
        
        self.current_mode = "video"
        filepath = self.video_recorder.start_recording(frame_size)
        
        if self.on_recording_start:
            self.on_recording_start("video")
        
        return filepath
    
    def write_video_frame(self, frame: np.ndarray):
        """영상 프레임 기록 (영상 녹화 중일 때)"""
        if self.current_mode == "video" and self.video_recorder.is_recording:
            self.video_recorder.write_frame(frame)
    
    def stop_recording(self) -> Optional[str]:
        """현재 녹화 중지"""
        if not self.current_mode:
            return None
        
        filepath = None
        mode = self.current_mode
        
        if self.current_mode == "voice":
            filepath = self.audio_recorder.stop_recording()
        elif self.current_mode == "video":
            filepath = self.video_recorder.stop_recording()
        
        self.current_mode = None
        
        if self.on_recording_stop:
            self.on_recording_stop(mode, filepath)
        
        return filepath
    
    def is_recording(self) -> bool:
        """녹화 중인지 확인"""
        return self.current_mode is not None
    
    def get_recording_mode(self) -> Optional[str]:
        """현재 녹화 모드 반환"""
        return self.current_mode
    
    def get_memos(self) -> List[dict]:
        """저장된 메모 목록 반환"""
        return self.memo_manager.get_all_memos()
    
    def delete_memo(self, filepath: str) -> bool:
        """메모 삭제"""
        return self.memo_manager.delete_memo(filepath)


# 테스트용
if __name__ == "__main__":
    print("=== Smart Mirror Memo Module Test ===")
    print(f"Speech Recognition: {'Available' if SPEECH_RECOGNITION_AVAILABLE else 'Not Available'}")
    print(f"PyAudio: {'Available' if PYAUDIO_AVAILABLE else 'Not Available'}")
    
    memo = SmartMirrorMemo()
    
    def on_start(mode):
        print(f"[CALLBACK] Recording started: {mode}")
    
    def on_stop(mode, filepath):
        print(f"[CALLBACK] Recording stopped: {mode} -> {filepath}")
    
    memo.on_recording_start = on_start
    memo.on_recording_stop = on_stop
    
    print("\nStarting memo system...")
    memo.start()
    
    print("\nSay '음성 메모' or '영상 메모' to start recording.")
    print("Say '중지' to stop recording.")
    print("Press Ctrl+C to exit.\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        memo.stop()
