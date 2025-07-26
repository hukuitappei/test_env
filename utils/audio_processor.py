import pyaudio
import numpy as np
import wave
import os
import time
from typing import Tuple, List, Optional, Dict, Any
from scipy import signal
import librosa
from .settings_manager import load_settings

def monitor_audio_level(device_index: Optional[int] = None) -> Tuple[float, List[float]]:
    """音声レベルを監視"""
    settings = load_settings()
    chunk_size = settings['audio']['chunk_size']
    sample_rate = settings['audio']['sample_rate']
    channels = settings['audio']['channels']
    
    try:
        p = pyaudio.PyAudio()
        
        # デバイスが指定されていない場合はデフォルトデバイスを使用
        if device_index is None:
            device_index = p.get_default_input_device_info()['index']
        
        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=chunk_size
        )
        
        levels = []
        for _ in range(10):  # 10回測定
            data = stream.read(chunk_size, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            level = np.sqrt(np.mean(audio_data**2))
            levels.append(level)
            time.sleep(0.1)
        
        stream.close()
        p.terminate()
        
        avg_level = np.mean(levels)
        return avg_level, levels
        
    except Exception as e:
        print(f"音声レベル監視エラー: {e}")
        return 0.0, []

def record_audio_with_device(duration: Optional[int] = None, gain: Optional[float] = None, device_index: Optional[int] = None) -> Tuple[Optional[List[bytes]], Optional[int]]:
    """指定されたデバイスで音声を録音"""
    settings = load_settings()
    
    if duration is None:
        duration = settings['audio']['duration']
    if gain is None:
        gain = settings['audio']['gain']
    
    chunk_size = settings['audio']['chunk_size']
    sample_rate = settings['audio']['sample_rate']
    channels = settings['audio']['channels']
    
    try:
        p = pyaudio.PyAudio()
        
        # デバイスが指定されていない場合はデフォルトデバイスを使用
        if device_index is None:
            device_index = p.get_default_input_device_info()['index']
        
        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=chunk_size
        )
        
        frames = []
        for _ in range(0, int(sample_rate / chunk_size * duration)):
            data = stream.read(chunk_size, exception_on_overflow=False)
            # ゲインを適用
            audio_data = np.frombuffer(data, dtype=np.int16)
            audio_data = (audio_data * gain).astype(np.int16)
            frames.append(audio_data.tobytes())
        
        stream.close()
        p.terminate()
        
        return frames, sample_rate
        
    except Exception as e:
        print(f"録音エラー: {e}")
        return None, None

def auto_record_with_level_monitoring(device_index: Optional[int] = None, duration: Optional[int] = None, gain: Optional[float] = None) -> Tuple[Optional[List[bytes]], Optional[int]]:
    """音声レベル監視付き自動録音"""
    settings = load_settings()
    
    if duration is None:
        duration = settings['audio']['duration']
    if gain is None:
        gain = settings['audio']['gain']
    
    chunk_size = settings['audio']['chunk_size']
    sample_rate = settings['audio']['sample_rate']
    channels = settings['audio']['channels']
    threshold = settings['ui']['auto_recording_threshold']
    delay = settings['ui']['auto_recording_delay']
    
    try:
        p = pyaudio.PyAudio()
        
        if device_index is None:
            device_index = p.get_default_input_device_info()['index']
        
        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=chunk_size
        )
        
        # 音声レベル監視
        print("音声レベルを監視中...")
        while True:
            data = stream.read(chunk_size, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            level = np.sqrt(np.mean(audio_data**2))
            
            if level > threshold:
                print(f"音声検出: レベル {level:.1f}")
                time.sleep(delay)  # 指定された時間待機
                break
        
        # 録音開始
        print("録音開始...")
        frames = []
        for _ in range(0, int(sample_rate / chunk_size * duration)):
            data = stream.read(chunk_size, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            audio_data = (audio_data * gain).astype(np.int16)
            frames.append(audio_data.tobytes())
        
        stream.close()
        p.terminate()
        
        return frames, sample_rate
        
    except Exception as e:
        print(f"自動録音エラー: {e}")
        return None, None

def analyze_audio_quality(frames: List[bytes], rate: int) -> Optional[Dict[str, Any]]:
    """音声品質を分析"""
    try:
        # フレームを結合してnumpy配列に変換
        audio_data = b''.join(frames)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # RMS（平均二乗根）
        rms = np.sqrt(np.mean(audio_array**2))
        
        # 最大振幅
        max_amplitude = np.max(np.abs(audio_array))
        
        # 無音比率（閾値以下の部分の割合）
        threshold = 100  # 無音とみなす閾値
        silent_samples = np.sum(np.abs(audio_array) < threshold)
        silent_ratio = (silent_samples / len(audio_array)) * 100
        
        return {
            'rms': rms,
            'max_amplitude': max_amplitude,
            'silent_ratio': silent_ratio
        }
        
    except Exception as e:
        print(f"音声品質分析エラー: {e}")
        return None

def preprocess_audio(audio_file_path: str) -> str:
    """音声ファイルの前処理"""
    try:
        # 音声ファイルを読み込み
        y, sr = librosa.load(audio_file_path, sr=None)
        
        # ノイズ除去（簡単なフィルタリング）
        y_filtered = signal.wiener(y)
        
        # 音量正規化
        y_normalized = librosa.util.normalize(y_filtered)
        
        # 処理済みファイルを保存
        processed_path = audio_file_path.replace('.wav', '_processed.wav')
        librosa.output.write_wav(processed_path, y_normalized, sr)
        
        return processed_path
        
    except Exception as e:
        print(f"音声前処理エラー: {e}")
        return audio_file_path

def save_audio_file(frames: List[bytes], rate: int, filename: str) -> bool:
    """音声ファイルを保存"""
    try:
        # ディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)  # モノラル
            wf.setsampwidth(2)  # 16bit
            wf.setframerate(rate)
            wf.writeframes(b''.join(frames))
        
        return True
        
    except Exception as e:
        print(f"音声ファイル保存エラー: {e}")
        return False

def get_audio_duration(frames: List[bytes], rate: int) -> float:
    """音声の長さを計算"""
    total_bytes = sum(len(frame) for frame in frames)
    total_samples = total_bytes // 2  # 16bit = 2 bytes
    return total_samples / rate

def convert_audio_format(input_path: str, output_path: str, target_format: str = 'wav') -> bool:
    """音声フォーマットを変換"""
    try:
        import librosa
        import soundfile as sf
        
        # 音声ファイルを読み込み
        y, sr = librosa.load(input_path, sr=None)
        
        # 新しいフォーマットで保存
        sf.write(output_path, y, sr, format=target_format.upper())
        
        return True
        
    except Exception as e:
        print(f"音声フォーマット変換エラー: {e}")
        return False 