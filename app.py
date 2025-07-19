import streamlit as st
import whisper
import tempfile
import os
from datetime import datetime
import wave
import pyaudio
import time
import numpy as np
from scipy import signal
import librosa
import sys
import json

# LLM関連のライブラリ（オプション）
try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

st.set_page_config(page_title="音声録音＆文字起こし", page_icon="🎤", layout="wide")
st.title("🎤 音声録音＆文字起こし（統合版）")

# 設定ファイルのパス
SETTINGS_FILE = "settings/app_settings.json"

# デフォルト設定
DEFAULT_SETTINGS = {
    "audio": {
        "chunk_size": 1024,
        "format": "paInt16",
        "channels": 1,
        "sample_rate": 44100,
        "gain": 2.0,
        "duration": 5
    },
    "whisper": {
        "model_size": "base",
        "language": "ja",
        "temperature": 0.0,
        "compression_ratio_threshold": 2.4,
        "logprob_threshold": -1.0,
        "no_speech_threshold": 0.6,
        "condition_on_previous_text": True,
        "initial_prompt": "これは日本語の音声です。"
    },
    "device": {
        "selected_device_index": None,
        "selected_device_name": None,
        "auto_select_default": True,
        "test_device_on_select": True
    },
    "ui": {
        "show_advanced_options": False,
        "auto_save_recordings": True,
        "show_quality_analysis": True,
        "show_level_monitoring": True,
        "auto_start_recording": False,  # 音声レベルが一定以上になったら自動で録音を開始するかどうか
        "auto_recording_threshold": 300,  # 自動録音を開始する音声レベルのしきい値（大きいほど音が大きい）
        "auto_recording_delay": 1.0  # 音声検出から録音開始までの待ち時間（秒）
    },
    "troubleshooting": {
        "retry_count": 3,
        "timeout_seconds": 10,
        "enable_error_recovery": True,
        "log_errors": True
    },
    "llm": {
        "api_key": "",
        "provider": "openai",
        "model": "gpt-3.5-turbo",
        "temperature": 0.3,
        "max_tokens": 1000,
        "enabled": False
    }
}

def load_settings():
    """設定を読み込み"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # 新しい設定項目を追加
                for category, default_values in DEFAULT_SETTINGS.items():
                    if category not in settings:
                        settings[category] = default_values
                    else:
                        for key, default_value in default_values.items():
                            if key not in settings[category]:
                                settings[category][key] = default_value
                return settings
        else:
            return DEFAULT_SETTINGS.copy()
    except Exception as e:
        st.error(f"設定読み込みエラー: {e}")
        return DEFAULT_SETTINGS.copy()

# 設定を読み込み
settings = load_settings()

# 設定から値を取得
CHUNK = settings['audio']['chunk_size']
FORMAT = pyaudio.paInt16  # 設定から取得する場合は変換が必要
CHANNELS = settings['audio']['channels']
RATE = settings['audio']['sample_rate']

# デフォルトマイクの自動選択機能
def auto_select_default_microphone():
    """デフォルトマイクを自動選択"""
    devices = get_microphone_devices()
    if devices:
        # デフォルトデバイスを探す
        default_device = None
        for device in devices:
            if device['is_default']:
                default_device = device
                break
        
        # デフォルトデバイスが見つからない場合は最初のデバイスを使用
        if not default_device:
            default_device = devices[0]
        
        # 設定に保存
        settings['device']['selected_device_index'] = default_device['index']
        settings['device']['selected_device_name'] = default_device['name']
        
        # セッション状態にも保存
        st.session_state['selected_device'] = default_device
        
        return default_device
    return None

# アプリ起動時のマイク選択は関数定義後に実行

# recordingsディレクトリの作成
os.makedirs('recordings', exist_ok=True)

# Whisperモデルの読み込み
@st.cache_resource
def get_whisper_model(model_size=None):
    if model_size is None:
        model_size = settings['whisper']['model_size']
    
    with st.spinner(f"Whisperモデル({model_size})を読み込み中..."):
        try:
            model = whisper.load_model(model_size)
            st.success(f"Whisperモデル({model_size})の読み込み完了")
            return model
        except Exception as e:
            st.error(f"Whisperモデルの読み込みエラー: {e}")
            return None

# 全オーディオデバイス情報取得
def get_all_audio_devices():
    """すべてのオーディオデバイス情報を取得"""
    p = pyaudio.PyAudio()
    devices = []
    
    try:
        device_count = p.get_device_count()
        st.write(f"**総デバイス数**: {device_count}")
        
        for i in range(device_count):
            try:
                device_info = p.get_device_info_by_index(i)
                devices.append({
                    'index': i,
                    'name': device_info['name'],
                    'max_input_channels': int(device_info['maxInputChannels']),
                    'max_output_channels': int(device_info['maxOutputChannels']),
                    'default_sample_rate': int(device_info['defaultSampleRate']),
                    'host_api': device_info['hostApi'],
                    'is_input': int(device_info['maxInputChannels']) > 0,
                    'is_output': int(device_info['maxOutputChannels']) > 0
                })
            except Exception as e:
                st.error(f"デバイス {i} の情報取得エラー: {e}")
                
    except Exception as e:
        st.error(f"デバイス情報取得エラー: {e}")
    finally:
        p.terminate()
    
    return devices

# デフォルトデバイス情報取得
def get_default_devices():
    """デフォルトデバイス情報を取得"""
    p = pyaudio.PyAudio()
    defaults = {}
    
    try:
        # デフォルト入力デバイス
        try:
            default_input = p.get_default_input_device_info()
            defaults['input'] = {
                'index': default_input['index'],
                'name': default_input['name']
            }
        except Exception as e:
            defaults['input'] = {'error': str(e)}
        
        # デフォルト出力デバイス
        try:
            default_output = p.get_default_output_device_info()
            defaults['output'] = {
                'index': default_output['index'],
                'name': default_output['name']
            }
        except Exception as e:
            defaults['output'] = {'error': str(e)}
            
    except Exception as e:
        st.error(f"デフォルトデバイス取得エラー: {e}")
    finally:
        p.terminate()
    
    return defaults

# デバイスアクセステスト（エラーハンドリング強化）
def test_device_access(device_index):
    """デバイスへのアクセステスト"""
    p = pyaudio.PyAudio()
    
    try:
        # デバイス情報取得
        device_info = p.get_device_info_by_index(device_index)
        
        # ストリーム作成テスト
        if int(device_info['maxInputChannels']) > 0:
            try:
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK
                )
                stream.close()
                return True, "アクセス可能"
            except Exception as e:
                error_msg = str(e)
                if "Errno -9999" in error_msg:
                    return False, "ホストエラー: デバイスが他のアプリで使用中または権限不足"
                elif "Errno -9998" in error_msg:
                    return False, "ストリームエラー: デバイスが利用できない"
                elif "Errno -9997" in error_msg:
                    return False, "デバイスエラー: デバイスが存在しない"
                else:
                    return False, f"アクセスエラー: {error_msg}"
        else:
            return False, "入力チャンネルなし"
            
    except Exception as e:
        return False, f"デバイス情報取得エラー: {e}"
    finally:
        p.terminate()

# マイクデバイス情報取得（録音用）
def get_microphone_devices():
    """利用可能なマイクデバイスを取得"""
    p = pyaudio.PyAudio()
    devices = []
    
    try:
        for i in range(p.get_device_count()):
            try:
                device_info = p.get_device_info_by_index(i)
                if int(device_info['maxInputChannels']) > 0:
                    devices.append({
                        'index': i,
                        'name': device_info['name'],
                        'channels': int(device_info['maxInputChannels']),
                        'sample_rate': int(device_info['defaultSampleRate']),
                        'is_default': device_info['name'] == p.get_default_input_device_info()['name']
                    })
            except Exception as e:
                st.warning(f"デバイス {i} の情報取得エラー: {e}")
    except Exception as e:
        st.error(f"デバイス情報取得エラー: {e}")
    finally:
        p.terminate()
    
    return devices

# マイクレベル監視
def monitor_audio_level(device_index=None):
    """リアルタイム音声レベル監視"""
    p = pyaudio.PyAudio()
    
    try:
        # デバイス情報表示
        if device_index is not None:
            device_info = p.get_device_info_by_index(device_index)
            st.write(f"**監視デバイス**: {device_info['name']}")
        
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=CHUNK)
        
        # レベル監視用のプレースホルダー
        level_placeholder = st.empty()
        chart_placeholder = st.empty()
        
        # レベル履歴
        levels = []
        
        st.write("🎤 マイクレベルを監視中... 話してみてください")
        
        for i in range(50):  # 5秒間監視
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_array = np.frombuffer(data, dtype=np.int16)
                # NaNや負の値を防ぐ
                audio_squared = audio_array.astype(np.float64) ** 2
                rms = np.sqrt(np.mean(audio_squared)) if np.any(audio_squared >= 0) else 0.0
                levels.append(rms)
                
                # レベル表示
                level_placeholder.metric("現在の音声レベル", f"{rms:.1f}")
                
                # チャート表示
                if len(levels) > 10:
                    try:
                        import pandas as pd
                        chart_data = pd.DataFrame({
                            'レベル': levels[-10:],
                            '時間': range(len(levels[-10:]))
                        })
                        chart_placeholder.line_chart(chart_data.set_index('時間'))
                    except ImportError:
                        # pandasがない場合は簡易表示
                        chart_placeholder.write(f"レベル履歴: {levels[-5:]}")
                
                time.sleep(0.1)
                
            except Exception as e:
                st.error(f"レベル監視エラー: {e}")
                break
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # 平均レベルを返す
        avg_level = np.mean(levels) if levels else 0
        return avg_level, levels
        
    except Exception as e:
        st.error(f"レベル監視エラー: {e}")
        return 0, []

# 改良版録音機能（選択されたデバイスで）
def record_audio_with_device(duration=None, gain=None, device_index=None):
    """選択されたデバイスで録音"""
    # 設定から値を取得
    if duration is None:
        duration = settings['audio']['duration']
    if gain is None:
        gain = settings['audio']['gain']
    
    st.write("録音開始...")
    
    try:
        p = pyaudio.PyAudio()
        st.write("PyAudio初期化完了")
        
        # デバイス情報表示
        if device_index is not None:
            device_info = p.get_device_info_by_index(device_index)
            st.write(f"**録音デバイス**: {device_info['name']}")
            st.write(f"デバイスID: {device_index}")
        
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=CHUNK)
        
        st.write("ストリーム開始完了")
        st.info(f"🎤 {duration}秒間録音します... (ゲイン: {gain}x)")
        
        frames = []
        progress_bar = st.progress(0)
        level_placeholder = st.empty()
        
        for i in range(0, int(RATE / CHUNK * duration)):
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                
                # 音声レベルを上げる
                audio_array = np.frombuffer(data, dtype=np.int16)
                amplified_array = np.clip(audio_array * gain, -32768, 32767).astype(np.int16)
                amplified_data = amplified_array.tobytes()
                
                frames.append(amplified_data)
                
                # プログレス更新
                progress = (i + 1) / int(RATE / CHUNK * duration)
                progress_bar.progress(progress)
                
                # リアルタイムレベル表示
                audio_squared = audio_array.astype(np.float64) ** 2
                rms = np.sqrt(np.mean(audio_squared)) if np.any(audio_squared >= 0) else 0.0
                level_placeholder.metric("録音レベル", f"{rms:.1f}")
                
            except Exception as e:
                st.error(f"録音フレーム {i} でエラー: {e}")
                break
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        progress_bar.empty()
        level_placeholder.empty()
        st.write(f"録音完了。フレーム数: {len(frames)}")
        
        return frames, RATE
        
    except Exception as e:
        st.error(f"録音エラー: {e}")
        return None, None

def auto_record_with_level_monitoring(device_index=None, duration=None, gain=None):
    """音声レベルを監視しながら自動録音（音が大きくなったら自動で録音を始める）"""
    if device_index is None:
        device_index = settings['device']['selected_device_index']
    if duration is None:
        duration = settings['audio']['duration']
    if gain is None:
        gain = settings['audio']['gain']
    
    p = pyaudio.PyAudio()
    stream = None
    
    try:
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK
        )
        
        # 音声レベル監視（音が大きくなるまで待つ）
        st.info("🎤 音声を検出中... 話し始めてください")
        
        threshold = settings['ui']['auto_recording_threshold']
        delay_seconds = settings['ui']['auto_recording_delay']
        
        # 音声レベルがしきい値を超えるまで待機
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            level = np.sqrt(np.mean(audio_data**2))
            
            if level > threshold:
                st.success(f"🎤 音声を検出しました！ {delay_seconds}秒後に録音を開始します...")
                time.sleep(delay_seconds)
                break
            
            time.sleep(0.1)
        
        # 録音開始
        st.info("🎤 録音中...")
        frames = []
        
        for _ in range(int(RATE / CHUNK * duration)):
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            
            # ゲイン適用（音を大きくする）
            if gain != 1.0:
                audio_data = (audio_data * gain).astype(np.int16)
            
            frames.append(audio_data.tobytes())
        
        st.success("✅ 録音完了！")
        return frames, RATE
        
    except Exception as e:
        st.error(f"自動録音エラー: {e}")
        return None, None
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
        p.terminate()

# 音声ファイル分析
def analyze_audio_quality(frames, rate):
    """録音された音声の品質を分析"""
    if not frames:
        return None
    
    try:
        # 音声データを結合
        audio_data = b''.join(frames)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # 分析
        rms = np.sqrt(np.mean(audio_array**2))
        max_amplitude = np.max(np.abs(audio_array))
        min_amplitude = np.min(np.abs(audio_array))
        
        # 無音部分の検出
        silence_threshold = 100
        silent_frames = np.sum(np.abs(audio_array) < silence_threshold)
        silent_ratio = silent_frames / len(audio_array) * 100
        
        return {
            'rms': rms,
            'max_amplitude': max_amplitude,
            'min_amplitude': min_amplitude,
            'silent_ratio': silent_ratio,
            'has_audio': rms > 100 and silent_ratio < 90
        }
        
    except Exception as e:
        st.error(f"音声分析エラー: {e}")
        return None

# 音声前処理機能
def preprocess_audio(audio_file_path):
    """音声ファイルの前処理（ノイズ除去、正規化など）"""
    try:
        # 音声ファイルを読み込み
        y, sr = librosa.load(audio_file_path, sr=None)
        
        # ノイズ除去（スペクトルサブトラクション）
        # 最初の1秒をノイズとして使用
        noise_sample = y[:sr]
        noise_spectrum = np.abs(np.fft.fft(noise_sample))
        
        # スペクトルサブトラクション
        y_spectrum = np.abs(np.fft.fft(y))
        cleaned_spectrum = y_spectrum - 0.1 * noise_spectrum[:len(y_spectrum)]
        cleaned_spectrum = np.maximum(cleaned_spectrum, 0)
        
        # 逆フーリエ変換
        cleaned_audio = np.real(np.fft.ifft(cleaned_spectrum))
        
        # 音量正規化
        cleaned_audio = librosa.util.normalize(cleaned_audio)
        
        # 一時ファイルとして保存
        temp_path = audio_file_path.replace('.wav', '_cleaned.wav')
        with wave.open(temp_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes((cleaned_audio * 32767).astype(np.int16).tobytes())
        
        return temp_path
    except Exception as e:
        st.warning(f"音声前処理エラー: {e}（元のファイルを使用します）")
        return audio_file_path

# ファイル保存
def save_audio_file(frames, rate, filename):
    try:
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(b''.join(frames))
        
        file_size = os.path.getsize(filename)
        st.success(f"✅ 録音完了！保存ファイル: {filename} ({file_size:,} bytes)")
        return True
        
    except Exception as e:
        st.error(f"ファイル保存エラー: {e}")
        return False

# 文字起こし機能（高精度版）
def transcribe_audio_high_quality(audio_file_path):
    """高精度な文字起こし機能"""
    if whisper_model is None:
        return "Whisperモデルが読み込まれていません"
    
    try:
        # 音声前処理
        cleaned_audio_path = preprocess_audio(audio_file_path)
        
        # プログレス表示
        with st.spinner("文字起こし中（高精度設定）..."):
            # 設定からパラメータを取得
            whisper_params = settings['whisper']
            
            # 高精度設定で文字起こし
            result = whisper_model.transcribe(
                cleaned_audio_path,
                language=whisper_params['language'],
                task="transcribe",
                verbose=False,
                # 高精度設定
                temperature=whisper_params['temperature'],
                compression_ratio_threshold=whisper_params['compression_ratio_threshold'],
                logprob_threshold=whisper_params['logprob_threshold'],
                no_speech_threshold=whisper_params['no_speech_threshold'],
                condition_on_previous_text=whisper_params['condition_on_previous_text'],
                initial_prompt=whisper_params['initial_prompt']
            )
            
            # 前処理ファイルを削除
            if cleaned_audio_path != audio_file_path:
                try:
                    os.unlink(cleaned_audio_path)
                except:
                    pass
            
            return result["text"]
    except Exception as e:
        st.error(f"文字起こしエラー: {e}")
        return f"音声認識エラー: {e}"

# 文字起こし機能（通常版）
def transcribe_audio(audio_file_path):
    """通常の文字起こし機能"""
    if whisper_model is None:
        return "Whisperモデルが読み込まれていません"
    
    try:
        # プログレス表示
        with st.spinner("文字起こし中..."):
            result = whisper_model.transcribe(
                audio_file_path, 
                language=settings['whisper']['language']
            )
            return result["text"]
    except Exception as e:
        st.error(f"文字起こしエラー: {e}")
        return f"音声認識エラー: {e}"

# 複数モデルでの比較機能
def compare_transcriptions(audio_file_path):
    """複数のモデルで文字起こしを比較"""
    models_to_compare = ["tiny", "base", "small"]
    results = {}
    
    for model_name in models_to_compare:
        try:
            with st.spinner(f"{model_name}モデルで文字起こし中..."):
                model = whisper.load_model(model_name)
                result = model.transcribe(
                    audio_file_path,
                    language=settings['whisper']['language'],
                    temperature=settings['whisper']['temperature']
                )
                results[model_name] = result["text"]
        except Exception as e:
            results[model_name] = f"エラー: {e}"
    
    return results

def send_to_llm(transcription_text, task="summarize"):
    """文字起こし結果をLLMに送信"""
    if not settings['llm']['enabled']:
        return "LLM機能が無効になっています。設定画面で有効にしてください。"
    
    api_key = settings['llm']['api_key']
    provider = settings['llm']['provider']
    model = settings['llm']['model']
    temperature = settings['llm']['temperature']
    max_tokens = settings['llm']['max_tokens']
    
    # 環境変数からAPIキーを取得
    if not api_key:
        env_api_key = os.getenv(f"{provider.upper()}_API_KEY", "")
        if env_api_key:
            api_key = env_api_key
        else:
            return "APIキーが設定されていません。設定画面でAPIキーを設定してください。"
    
    try:
        if provider == "openai" and openai:
            client = openai.OpenAI(api_key=api_key)
            
            if task == "summarize":
                prompt = f"以下の文字起こし結果を要約してください：\n\n{transcription_text}"
            elif task == "analyze":
                prompt = f"以下の文字起こし結果を分析し、キーポイントを抽出してください：\n\n{transcription_text}"
            else:
                prompt = f"以下の文字起こし結果について、{task}してください：\n\n{transcription_text}"
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
            
        elif provider == "anthropic" and anthropic:
            client = anthropic.Anthropic(api_key=api_key)
            
            if task == "summarize":
                prompt = f"以下の文字起こし結果を要約してください：\n\n{transcription_text}"
            elif task == "analyze":
                prompt = f"以下の文字起こし結果を分析し、キーポイントを抽出してください：\n\n{transcription_text}"
            else:
                prompt = f"以下の文字起こし結果について、{task}してください：\n\n{transcription_text}"
            
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            # Anthropicのレスポンス構造を正しく処理
            if response.content and len(response.content) > 0:
                content_block = response.content[0]
                if hasattr(content_block, 'text'):
                    return content_block.text  # type: ignore
                else:
                    return "テキスト形式でないレスポンスです"
            else:
                return "レスポンスが空です"
            
        elif provider == "google" and genai:
            # Google Generative AIの正しい使用方法
            genai.configure(api_key=api_key)  # type: ignore
            model_genai = genai.GenerativeModel(model)  # type: ignore
            
            if task == "summarize":
                prompt = f"以下の文字起こし結果を要約してください：\n\n{transcription_text}"
            elif task == "analyze":
                prompt = f"以下の文字起こし結果を分析し、キーポイントを抽出してください：\n\n{transcription_text}"
            else:
                prompt = f"以下の文字起こし結果について、{task}してください：\n\n{transcription_text}"
            
            response = model_genai.generate_content(prompt)
            return response.text
            
        else:
            return f"{provider}のライブラリがインストールされていません。pip install {provider} でインストールしてください。"
            
    except Exception as e:
        return f"LLM処理エラー: {e}"

# Whisperモデルの読み込み（設定から）
whisper_model = get_whisper_model(settings['whisper']['model_size'])

# アプリ起動時にマイクを選択
if 'selected_device' not in st.session_state:
    # 保存された設定からマイクを復元
    if settings['device']['selected_device_index'] is not None:
        devices = get_microphone_devices()
        saved_device = None
        for device in devices:
            if device['index'] == settings['device']['selected_device_index']:
                saved_device = device
                break
        
        if saved_device:
            st.session_state['selected_device'] = saved_device
        else:
            # 保存されたデバイスが見つからない場合はデフォルトマイクを選択
            auto_select_default_microphone()
    else:
        # 設定がない場合はデフォルトマイクを自動選択
        auto_select_default_microphone()

# メインUI
st.markdown("---")

# ヘッダー部分に設定ボタンを追加
col1, col2 = st.columns([4, 1])
with col1:
    st.markdown("### 🎤 録音・文字起こし")
with col2:
    if st.button("⚙️ 設定", help="詳細設定を開く", type="secondary"):
        st.session_state['show_settings'] = True

# 設定画面の表示
if st.session_state.get('show_settings', False):
    st.markdown("---")
    st.subheader("⚙️ 詳細設定")
    
    # 設定タブ
    settings_tab1, settings_tab2, settings_tab3, settings_tab4, settings_tab5, settings_tab6, settings_tab7, settings_tab8, settings_tab9, settings_tab10 = st.tabs([
        "🎤 録音設定", "🤖 Whisper設定", "🔧 デバイス設定", "🎨 UI設定", "🔧 トラブルシューティング", "💻 システム診断", "📖 使用方法", "🔍 マイク情報", "📁 ファイル管理", "🤖 LLM設定"
    ])
    
    with settings_tab1:
        st.markdown("### 🎤 録音設定")
        st.info("💡 **録音設定**: マイクで音を録音するときの設定です。音の質や録音時間を調整できます。")
        
        col1, col2 = st.columns(2)
        
        with col1:
            settings['audio']['chunk_size'] = st.number_input(
                "チャンクサイズ", 
                min_value=512, 
                max_value=4096, 
                value=settings['audio']['chunk_size'], 
                step=512,
                help="音を録音するときのデータの塊の大きさ（大きいほど安定するけど遅くなる）"
            )
            settings['audio']['sample_rate'] = st.selectbox(
                "サンプルレート", 
                [8000, 16000, 22050, 44100, 48000], 
                index=[8000, 16000, 22050, 44100, 48000].index(settings['audio']['sample_rate']),
                help="1秒間に何回音を測るか（大きいほど音質が良くなるけどファイルが大きくなる）"
            )
            settings['audio']['channels'] = st.selectbox(
                "チャンネル数", 
                [1, 2], 
                index=settings['audio']['channels']-1,
                help="録音する音の種類（1=モノラル、2=ステレオ。ステレオは左右の音を録音）"
            )
        
        with col2:
            settings['audio']['gain'] = st.slider(
                "音声ゲイン", 
                min_value=1.0, 
                max_value=5.0, 
                value=settings['audio']['gain'], 
                step=0.1,
                help="録音する音を大きくする倍率（1.0=そのまま、2.0=2倍の音量）"
            )
            settings['audio']['duration'] = st.slider(
                "録音時間（秒）", 
                min_value=1, 
                max_value=60, 
                value=settings['audio']['duration'], 
                step=1,
                help="録音ボタンを押してから何秒間録音するか"
            )
    
    with settings_tab2:
        st.markdown("### 🤖 Whisper設定")
        st.info("💡 **Whisper設定**: 音声を文字に変換するAI（Whisper）の設定です。精度や速度を調整できます。")
        
        col1, col2 = st.columns(2)
        
        with col1:
            settings['whisper']['model_size'] = st.selectbox(
                "モデルサイズ", 
                ["tiny", "base", "small", "medium", "large"], 
                index=["tiny", "base", "small", "medium", "large"].index(settings['whisper']['model_size']),
                help="AIの大きさ（小さい=速いけど精度低い、大きい=遅いけど精度高い）"
            )
            settings['whisper']['language'] = st.selectbox(
                "言語", 
                ["ja", "en", "auto"], 
                index=["ja", "en", "auto"].index(settings['whisper']['language']),
                help="録音した音声の言語（ja=日本語、en=英語、auto=自動判定）"
            )
            settings['whisper']['temperature'] = st.slider(
                "温度", 
                min_value=0.0, 
                max_value=1.0, 
                value=settings['whisper']['temperature'], 
                step=0.1,
                help="AIの創造性（0.0=正確、1.0=創造的。音声認識では0.0がおすすめ）"
            )
        
        with col2:
            settings['whisper']['initial_prompt'] = st.text_area(
                "初期プロンプト", 
                value=settings['whisper']['initial_prompt'], 
                height=100,
                help="AIに最初に教える情報（例：「これは日本語の音声です」）"
            )
            settings['whisper']['condition_on_previous_text'] = st.checkbox(
                "前のテキストを考慮", 
                value=settings['whisper']['condition_on_previous_text'],
                help="前の録音の内容を参考にして文字起こしの精度を上げるかどうか"
            )
    
    with settings_tab3:
        st.markdown("### 🔧 デバイス設定")
        st.info("💡 **デバイス設定**: どのマイクを使うか、マイクのテストや設定を行います。")
        
        # 現在選択されているデバイスの表示
        if 'selected_device' in st.session_state:
            current_device = st.session_state['selected_device']
            st.success(f"**現在選択中**: {current_device['name']} (ID: {current_device['index']})")
            st.write(f"チャンネル数: {current_device['channels']}, サンプルレート: {current_device['sample_rate']} Hz")
        else:
            st.warning("マイクデバイスが選択されていません")
        
        st.markdown("---")
        st.markdown("#### 🎤 マイクデバイス選択")
        
        devices = get_microphone_devices()
        
        if devices:
            st.write(f"**見つかったマイクデバイス数: {len(devices)}**")
            
            # デバイス一覧表示
            for device in devices:
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    device_name = device['name']
                    if device['is_default']:
                        device_name += " (デフォルト)"
                    if device['index'] == settings['device']['selected_device_index']:
                        device_name += " (設定済み)"
                    st.write(f"**{device_name}**")
                    st.write(f"デバイスID: {device['index']}")
                
                with col2:
                    st.write(f"チャンネル数: {device['channels']}")
                    st.write(f"サンプルレート: {device['sample_rate']} Hz")
                
                with col3:
                    if st.button(f"選択", key=f"settings_select_{device['index']}"):
                        # 設定とセッション状態を更新
                        settings['device']['selected_device_index'] = device['index']
                        settings['device']['selected_device_name'] = device['name']
                        st.session_state['selected_device'] = device
                        st.success(f"選択されました: {device['name']}")
                        st.rerun()
            
            st.markdown("---")
            st.markdown("#### 🔍 デバイステスト")
            
            # 現在選択されているデバイスでテスト
            if 'selected_device' in st.session_state:
                selected_device = st.session_state['selected_device']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🔍 アクセステスト", key="settings_test_access"):
                        success, message = test_device_access(selected_device['index'])
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
                
                with col2:
                    if st.button("🎤 レベル監視テスト", key="settings_test_level"):
                        try:
                            avg_level, levels = monitor_audio_level(selected_device['index'])
                            st.write(f"平均音声レベル: {avg_level:.1f}")
                            
                            if avg_level < 100:
                                st.warning("⚠️ 音声レベルが低いです")
                            elif avg_level < 500:
                                st.info("ℹ️ 音声レベルは適切です")
                            else:
                                st.success("✅ 音声レベルは良好です")
                        except Exception as e:
                            st.error(f"レベル監視エラー: {e}")
            
            st.markdown("---")
            st.markdown("#### ⚙️ 自動選択設定")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔄 デフォルトマイクを自動選択"):
                    default_device = auto_select_default_microphone()
                    if default_device:
                        st.success(f"デフォルトマイクを選択しました: {default_device['name']}")
                        st.rerun()
                    else:
                        st.error("デフォルトマイクの選択に失敗しました")
            
            with col2:
                if st.button("🗑️ 選択をクリア"):
                    if 'selected_device' in st.session_state:
                        del st.session_state['selected_device']
                    settings['device']['selected_device_index'] = None
                    settings['device']['selected_device_name'] = None
                    st.success("マイク選択をクリアしました")
                    st.rerun()
        else:
            st.error("マイクデバイスが見つかりません")
    
    with settings_tab4:
        st.markdown("### 🎨 UI設定")
        
        # 基本表示設定
        st.markdown("#### 📺 表示設定")
        col1, col2 = st.columns(2)
        
        with col1:
            settings['ui']['show_advanced_options'] = st.checkbox(
                "詳細オプションを表示", 
                value=settings['ui']['show_advanced_options'],
                help="難しい設定項目も表示するかどうか"
            )
            settings['ui']['auto_save_recordings'] = st.checkbox(
                "録音を自動保存", 
                value=settings['ui']['auto_save_recordings'],
                help="録音が終わったら自動でファイルに保存するかどうか"
            )
        
        with col2:
            settings['ui']['show_quality_analysis'] = st.checkbox(
                "音声品質分析を表示", 
                value=settings['ui']['show_quality_analysis'],
                help="録音の音質を分析して結果を表示するかどうか"
            )
            settings['ui']['show_level_monitoring'] = st.checkbox(
                "レベル監視を表示", 
                value=settings['ui']['show_level_monitoring'],
                help="マイクの音の大きさを測る機能を表示するかどうか"
            )
        
        # 自動録音設定
        st.markdown("---")
        st.markdown("#### 🤖 自動録音設定")
        
        settings['ui']['auto_start_recording'] = st.checkbox(
            "自動録音を有効にする", 
            value=settings['ui']['auto_start_recording'],
            help="音が大きくなったら自動で録音を始めるかどうか（話し始めると自動で録音が始まります）"
        )
        
        if settings['ui']['auto_start_recording']:
            col1, col2 = st.columns(2)
            
            with col1:
                settings['ui']['auto_recording_threshold'] = st.slider(
                    "音声検出レベル", 
                    min_value=100, 
                    max_value=1000, 
                    value=settings['ui']['auto_recording_threshold'], 
                    step=50,
                    help="このレベル以上の音が聞こえたら録音を開始します（大きいほど大きな音が必要）"
                )
            
            with col2:
                settings['ui']['auto_recording_delay'] = st.slider(
                    "録音開始までの待ち時間（秒）", 
                    min_value=0.5, 
                    max_value=3.0, 
                    value=settings['ui']['auto_recording_delay'], 
                    step=0.1,
                    help="音を検出してから録音を始めるまでの時間（短いほど素早く録音開始）"
                )
            
            st.info("💡 **自動録音の使い方**: 録音ボタンを押すと、音声を検出するまで待機します。話し始めると自動で録音が始まります！")
    
    with settings_tab5:
        st.markdown("### 🔧 トラブルシューティング設定")
        col1, col2 = st.columns(2)
        
        with col1:
            settings['troubleshooting']['retry_count'] = st.number_input("リトライ回数", min_value=1, max_value=10, value=settings['troubleshooting']['retry_count'])
            settings['troubleshooting']['timeout_seconds'] = st.number_input("タイムアウト（秒）", min_value=5, max_value=60, value=settings['troubleshooting']['timeout_seconds'])
        
        with col2:
            settings['troubleshooting']['enable_error_recovery'] = st.checkbox("エラー回復を有効", value=settings['troubleshooting']['enable_error_recovery'])
            settings['troubleshooting']['log_errors'] = st.checkbox("エラーログを記録", value=settings['troubleshooting']['log_errors'])
    
    with settings_tab6:
        st.markdown("### 💻 システム診断")
        
        # システム情報
        st.markdown("#### システム情報")
        import platform
        st.write(f"**OS**: {platform.system()} {platform.release()}")
        st.write(f"**Python**: {platform.python_version()}")
        st.write("**PyAudio**: インストール済み")
        
        # デバイス情報
        st.markdown("#### オーディオデバイス情報")
        all_devices = get_all_audio_devices()
        st.write(f"**総デバイス数**: {len(all_devices)}")
        
        input_devices = [d for d in all_devices if d['is_input']]
        st.write(f"**入力デバイス数**: {len(input_devices)}")
        
        # デフォルトデバイス
        defaults = get_default_devices()
        if 'input' in defaults and 'error' not in defaults['input']:
            st.write(f"**デフォルト入力**: {defaults['input']['name']} (ID: {defaults['input']['index']})")
        else:
            st.error("デフォルト入力デバイスが設定されていません")
    
    with settings_tab7:
        st.markdown("### 📖 使用方法")
        
        st.markdown("""
        #### 🎯 主な機能
        
        1. **マイクデバイス選択**: 利用可能なマイクデバイスから選択
        2. **レベル監視**: 選択されたマイクの音声レベルを確認
        3. **音声ゲイン機能**: 録音時に音声レベルを自動で上げる
        4. **音声品質分析**: 録音後の音声レベルと無音比率を分析
        5. **高精度文字起こし**: ノイズ除去、音量正規化、最適化されたパラメータ
        6. **複数モデル比較**: 異なるモデルサイズでの結果を比較
        
        #### 🔧 使用手順
        
        1. **マイク選択**: 設定画面の「🔧 デバイス設定」でマイクを選択
        2. **レベル監視**: メイン画面で「🎤 選択されたマイクでレベル監視」で音声レベルを確認
        3. **録音設定**: 設定画面の「🎤 録音設定」で録音時間とゲインを調整
        4. **録音実行**: メイン画面で「🎤 選択されたマイクで録音開始」で録音
        5. **品質確認**: 録音品質分析で結果を確認
        6. **文字起こし**: 通常精度または高精度で文字起こし
        
        #### 💡 トラブルシューティング
        
        - **マイクが認識されない場合**: デバイスマネージャーでマイクが有効になっているか確認
        - **音声レベルが低い場合**: ゲインを上げる、マイクに近づく
        - **無音部分が多い場合**: 録音時間を短くする、静かな環境で録音
        - **文字起こしが空の場合**: 音声レベルを確認、より明確に話す
        - **PyAudioエラー（Errno -9999）**: 他のアプリがマイクを使用していないか確認、権限設定を確認
        
        #### 🎤 精度向上のポイント
        
        - **高精度設定**: ノイズ除去、音量正規化、最適化されたパラメータ
        - **モデルサイズ**: 大きいモデルほど高精度（ただし重い）
        - **音声品質**: 静かな環境、クリアな発音で録音
        - **複数モデル比較**: 異なるモデルでの結果を比較して最適なものを選択
        
        #### ⚙️ 設定の活用
        
        - **録音設定**: チャンクサイズ、サンプルレート、ゲインを調整
        - **Whisper設定**: モデルサイズ、言語、温度を調整
        - **デバイス設定**: マイク選択、アクセステスト、自動選択
        - **UI設定**: 表示オプション、自動保存、品質分析
        - **トラブルシューティング設定**: リトライ回数、タイムアウト、エラー回復
        
        **注意事項:**
        - 初回起動時はWhisperモデルのダウンロードに時間がかかります
        - 高精度設定は処理時間が長くなります
        - マイクへのアクセス許可が必要です
        - 設定は「💾 設定を保存」で保存されます
                """)

    with settings_tab8:
        st.markdown("### 🔍 マイク情報")
        
        # システム情報
        st.markdown("#### 💻 システム情報")
        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Pythonバージョン**: {sys.version}")
            st.write("**PyAudio**: インストール済み")
            st.write(f"**現在のディレクトリ**: {os.getcwd()}")

        with col2:
            st.write(f"**Whisperモデル**: {settings['whisper']['model_size']}")
            st.write(f"**サンプルレート**: {RATE} Hz")
            st.write(f"**チャンクサイズ**: {CHUNK}")

        # 全オーディオデバイス情報
        st.markdown("---")
        st.markdown("#### 🔍 全オーディオデバイス情報")

        all_devices = get_all_audio_devices()
        
        if all_devices:
            st.write(f"**総デバイス数**: {len(all_devices)}")
            
            # 入力デバイスのみ表示
            input_devices = [d for d in all_devices if d['is_input']]
            st.write(f"**入力デバイス数**: {len(input_devices)}")
            
            for device in input_devices:
                with st.expander(f"デバイス {device['index']}: {device['name']}"):
                    st.write(f"**デバイスID**: {device['index']}")
                    st.write(f"**名前**: {device['name']}")
                    st.write(f"**入力チャンネル**: {device['max_input_channels']}")
                    st.write(f"**出力チャンネル**: {device['max_output_channels']}")
                    st.write(f"**サンプルレート**: {device['default_sample_rate']} Hz")
                    st.write(f"**ホストAPI**: {device['host_api']}")
                    
                    # アクセステスト
                    if st.button(f"🔍 アクセステスト", key=f"settings_test_{device['index']}"):
                        success, message = test_device_access(device['index'])
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
        else:
            st.error("デバイス情報の取得に失敗しました")

        # デフォルトデバイス情報
        st.markdown("---")
        st.markdown("#### 🎯 デフォルトデバイス情報")

        defaults = get_default_devices()
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**デフォルト入力デバイス**")
            if 'input' in defaults and 'error' not in defaults['input']:
                st.write(f"名前: {defaults['input']['name']}")
                st.write(f"ID: {defaults['input']['index']}")
            else:
                st.error("デフォルト入力デバイスが設定されていません")
                if 'input' in defaults:
                    st.write(f"エラー: {defaults['input']['error']}")

        with col2:
            st.write("**デフォルト出力デバイス**")
            if 'output' in defaults and 'error' not in defaults['output']:
                st.write(f"名前: {defaults['output']['name']}")
                st.write(f"ID: {defaults['output']['index']}")
            else:
                st.error("デフォルト出力デバイスが設定されていません")
                if 'output' in defaults:
                    st.write(f"エラー: {defaults['output']['error']}")

    with settings_tab9:
        st.markdown("### 📁 ファイル管理")
        
        # 録音ファイル一覧
        st.markdown("#### 🎤 録音ファイル一覧")
        
        recordings_dir = "recordings"
        if os.path.exists(recordings_dir):
            files = [f for f in os.listdir(recordings_dir) if f.endswith('.wav')]
            
            if files:
                st.write(f"**録音ファイル数**: {len(files)}")
                
                for file in sorted(files, reverse=True):
                    file_path = os.path.join(recordings_dir, file)
                    file_size = os.path.getsize(file_path)
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    with st.expander(f"📁 {file} ({file_size:,} bytes, {file_time.strftime('%Y-%m-%d %H:%M:%S')})"):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.write(f"**ファイル名**: {file}")
                            st.write(f"**サイズ**: {file_size:,} bytes")
                            st.write(f"**作成日時**: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        with col2:
                            if st.button("🔍 文字起こし", key=f"settings_transcribe_{file}"):
                                transcription = transcribe_audio(file_path)
                                st.markdown("**文字起こし結果:**")
                                st.text_area("結果", transcription, height=100, key=f"settings_result_{file}")
                                
                                # LLMへのデータ渡しボタン
                                if st.button("🤖 LLMに送信", key=f"settings_llm_send_{file}"):
                                    if transcription:
                                        llm_result = send_to_llm(transcription, "summarize")
                                        st.markdown("### 🤖 LLM処理結果")
                                        st.text_area("LLM結果", llm_result, height=150, key=f"settings_llm_result_{file}")
                                    else:
                                        st.error("文字起こし結果がありません")
                        
                        with col3:
                            if st.button("🗑️ 削除", key=f"settings_delete_{file}"):
                                try:
                                    os.remove(file_path)
                                    st.success("ファイルを削除しました")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"削除エラー: {e}")
            else:
                st.info("録音ファイルがありません")
        else:
            st.info("recordingsディレクトリが存在しません")

        # 設定ファイル管理
        st.markdown("---")
        st.markdown("#### ⚙️ 設定ファイル管理")
        
        if os.path.exists(SETTINGS_FILE):
            file_size = os.path.getsize(SETTINGS_FILE)
            file_time = datetime.fromtimestamp(os.path.getmtime(SETTINGS_FILE))
            
            st.write(f"**設定ファイル**: {SETTINGS_FILE}")
            st.write(f"**サイズ**: {file_size:,} bytes")
            st.write(f"**更新日時**: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📥 設定をエクスポート", key="settings_export"):
                    try:
                        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                            settings_data = f.read()
                        
                        st.download_button(
                            label="📥 設定ファイルをダウンロード",
                            data=settings_data,
                            file_name="app_settings.json",
                            mime="application/json"
                        )
                    except Exception as e:
                        st.error(f"エクスポートエラー: {e}")
            
            with col2:
                if st.button("🗑️ 設定をリセット", key="settings_reset"):
                    try:
                        os.remove(SETTINGS_FILE)
                        st.success("設定ファイルを削除しました。次回起動時にデフォルト設定が適用されます。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"リセットエラー: {e}")
        else:
            st.info("設定ファイルが存在しません（デフォルト設定を使用中）")

    with settings_tab10:
        st.markdown("### 🤖 LLM設定")
        
        # LLM機能の有効化
        llm_enabled = st.checkbox("LLM機能を有効にする", value=settings['llm']['enabled'])
        settings['llm']['enabled'] = llm_enabled
        
        if llm_enabled:
            st.markdown("---")
            
            # プロバイダー選択
            provider = st.selectbox(
                "LLMプロバイダー",
                ["openai", "anthropic", "google"],
                index=["openai", "anthropic", "google"].index(settings['llm']['provider'])
            )
            settings['llm']['provider'] = provider
            
            # APIキー設定
            st.markdown("#### 🔑 APIキー設定")
            
            # 環境変数からの読み込み
            env_api_key = os.getenv(f"{provider.upper()}_API_KEY", "")
            if env_api_key:
                st.info(f"✅ 環境変数 {provider.upper()}_API_KEY からAPIキーが読み込まれています")
                api_key = env_api_key
            else:
                st.warning(f"⚠️ 環境変数 {provider.upper()}_API_KEY が設定されていません")
                api_key = st.text_input(
                    f"{provider.upper()} APIキー",
                    value=settings['llm']['api_key'],
                    type="password",
                    help=f"{provider.upper()}のAPIキーを入力してください"
                )
                settings['llm']['api_key'] = api_key
            
            # モデル設定
            st.markdown("---")
            st.markdown("#### 🎛️ モデル設定")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if provider == "openai":
                    model = st.selectbox(
                        "モデル",
                        ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"],
                        index=["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"].index(settings['llm']['model'])
                    )
                elif provider == "anthropic":
                    model = st.selectbox(
                        "モデル",
                        ["claude-3-sonnet-20240229", "claude-3-opus-20240229", "claude-3-haiku-20240307"],
                        index=["claude-3-sonnet-20240229", "claude-3-opus-20240229", "claude-3-haiku-20240307"].index(settings['llm']['model'])
                    )
                else:  # google
                    model = st.selectbox(
                        "モデル",
                        ["gemini-pro", "gemini-pro-vision"],
                        index=["gemini-pro", "gemini-pro-vision"].index(settings['llm']['model'])
                    )
                settings['llm']['model'] = model
                
                temperature = st.slider(
                    "温度 (Temperature)",
                    min_value=0.0,
                    max_value=2.0,
                    value=settings['llm']['temperature'],
                    step=0.1,
                    help="値が高いほど創造的、低いほど決定論的になります"
                )
                settings['llm']['temperature'] = temperature
            
            with col2:
                max_tokens = st.number_input(
                    "最大トークン数",
                    min_value=100,
                    max_value=4000,
                    value=settings['llm']['max_tokens'],
                    step=100,
                    help="生成するテキストの最大長"
                )
                settings['llm']['max_tokens'] = max_tokens
            
            # APIキーテスト
            st.markdown("---")
            st.markdown("#### 🧪 APIキーテスト")
            
            if st.button("🔍 APIキーをテスト"):
                if api_key:
                    try:
                        # 簡単なテストリクエスト
                        if provider == "openai" and openai:
                            openai.api_key = api_key
                            # 新しいOpenAI API形式
                            client = openai.OpenAI(api_key=api_key)
                            response = client.chat.completions.create(
                                model=model,
                                messages=[{"role": "user", "content": "こんにちは"}],
                                max_tokens=10,
                                temperature=temperature
                            )
                            st.success("✅ OpenAI APIキーが正常に動作しています")
                        elif provider == "anthropic" and anthropic:
                            client = anthropic.Anthropic(api_key=api_key)
                            response = client.messages.create(
                                model=model,
                                max_tokens=10,
                                messages=[{"role": "user", "content": "こんにちは"}]
                            )
                            st.success("✅ Anthropic APIキーが正常に動作しています")
                        elif provider == "google" and genai:
                            # Google Generative AIの正しい使用方法
                            genai.configure(api_key=api_key)  # type: ignore
                            model_genai = genai.GenerativeModel(model)  # type: ignore
                            response = model_genai.generate_content("こんにちは")
                            st.success("✅ Google APIキーが正常に動作しています")
                        else:
                            st.error(f"❌ {provider}のライブラリがインストールされていません")
                    except Exception as e:
                        st.error(f"❌ APIキーテストに失敗しました: {e}")
                else:
                    st.error("❌ APIキーが設定されていません")
            
            # 使用方法
            st.markdown("---")
            st.markdown("#### 📖 使用方法")
            
            st.info("""
            **APIキーの設定方法:**
            
            1. **環境変数での設定（推奨）:**
               - `.env`ファイルを作成し、以下を記載:
               ```
               OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
               ```
               - または、システムの環境変数に設定
            
            2. **UIでの設定:**
               - 上記のAPIキー入力欄に直接入力
            
            **対応プロバイダー:**
            - OpenAI (GPT-3.5, GPT-4)
            - Anthropic (Claude)
            - Google (Gemini)
            """)
        else:
            st.info("LLM機能を有効にすると、文字起こし結果をLLMに送信して要約や分析を行うことができます。")

    # 設定保存・キャンセルボタン
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("💾 設定を保存"):
            try:
                # 現在選択されているマイク情報も保存
                if 'selected_device' in st.session_state:
                    selected_device = st.session_state['selected_device']
                    settings['device']['selected_device_index'] = selected_device['index']
                    settings['device']['selected_device_name'] = selected_device['name']
                
                os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
                with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, ensure_ascii=False, indent=2)
                st.success("設定を保存しました")
                st.session_state['show_settings'] = False
                st.rerun()
            except Exception as e:
                st.error(f"設定保存エラー: {e}")
    
    with col2:
        if st.button("🔄 デフォルトに戻す"):
            settings = DEFAULT_SETTINGS.copy()
            st.success("設定をデフォルトに戻しました")
    
    with col3:
        if st.button("❌ キャンセル"):
            st.session_state['show_settings'] = False
            st.rerun()

# 設定情報表示（サイドバー）
if settings['ui']['show_advanced_options']:
    st.sidebar.markdown("### ⚙️ 現在の設定")
    st.sidebar.write(f"**モデル**: {settings['whisper']['model_size']}")
    st.sidebar.write(f"**サンプルレート**: {RATE} Hz")
    st.sidebar.write(f"**チャンクサイズ**: {CHUNK}")
    st.sidebar.write(f"**ゲイン**: {settings['audio']['gain']}x")
    
    if st.sidebar.button("🔄 設定を再読み込み"):
        settings = load_settings()
        st.rerun()

# 設定画面が開いている場合はメインコンテンツを非表示
if not st.session_state.get('show_settings', False):
    # タブ作成
    tab1, tab2 = st.tabs(["🎤 録音", "📝 文字起こし"])

    with tab1:
        # 現在選択されているマイクの表示
        if 'selected_device' in st.session_state:
            selected = st.session_state['selected_device']
            st.info(f"**現在選択中のマイク**: {selected['name']} (ID: {selected['index']})")
            st.write(f"チャンネル数: {selected['channels']}, サンプルレート: {selected['sample_rate']} Hz")
        else:
            st.warning("⚠️ マイクデバイスが選択されていません。設定画面でマイクを選択してください。")

        # レベル監視ボタン
        if settings['ui']['show_level_monitoring']:
            st.markdown("---")
            st.subheader("🔍 マイクレベル監視")

            # 選択されたデバイスでレベル監視
            if 'selected_device' in st.session_state:
                selected_device = st.session_state['selected_device']
                
                if st.button("🎤 選択されたマイクでレベル監視", type="secondary"):
                    try:
                        avg_level, levels = monitor_audio_level(selected_device['index'])
                        
                        st.write(f"平均音声レベル: {avg_level:.1f}")
                        
                        if avg_level < 100:
                            st.warning("⚠️ 音声レベルが低いです。マイクの音量を上げるか、より近くで話してください。")
                        elif avg_level < 500:
                            st.info("ℹ️ 音声レベルは適切です。")
                        else:
                            st.success("✅ 音声レベルは良好です。")
                            
                    except Exception as e:
                        st.error(f"レベル監視エラー: {e}")
            else:
                st.info("⚠️ 録音するマイクデバイスを選択してください")

        # 録音ボタン
        st.markdown("---")
        st.subheader("🎤 録音")

        if 'selected_device' in st.session_state:
            selected_device = st.session_state['selected_device']
            
            # 録音ボタンの選択
            if settings['ui']['auto_start_recording']:
                # 自動録音ボタン
                if st.button("🤖 自動録音開始（音声検出）", type="primary"):
                    if whisper_model is None:
                        st.error("Whisperモデルが読み込まれていません。ページを再読み込みしてください。")
                    else:
                        try:
                            # 自動録音実行
                            frames, rate = auto_record_with_level_monitoring(selected_device['index'])
                            
                            if frames and rate:
                                st.success("録音データ取得成功")
                                
                                # 音声品質分析
                                if settings['ui']['show_quality_analysis']:
                                    quality = analyze_audio_quality(frames, rate)
                                    
                                    if quality:
                                        st.markdown("### 📊 録音品質分析")
                                        col1, col2, col3 = st.columns(3)
                                        
                                        with col1:
                                            st.metric("RMS", f"{quality['rms']:.1f}")
                                            if quality['rms'] < 100:
                                                st.warning("音声レベルが低い")
                                            else:
                                                st.success("音声レベル良好")
                                        
                                        with col2:
                                            st.metric("最大振幅", quality['max_amplitude'])
                                        
                                        with col3:
                                            st.metric("無音比率", f"{quality['silent_ratio']:.1f}%")
                                            if quality['silent_ratio'] > 70:
                                                st.warning("無音部分が多い")
                                            else:
                                                st.success("音声が検出されている")
                                
                                # ファイル保存
                                if settings['ui']['auto_save_recordings']:
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    device_name = selected_device['name'].replace(" ", "_").replace("(", "").replace(")", "")
                                    filename = f"recordings/recording_{device_name}_{timestamp}.wav"
                                    
                                    if save_audio_file(frames, rate, filename):
                                        # 文字起こし精度選択
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            if st.button("🔍 通常精度で文字起こし"):
                                                transcription = transcribe_audio(filename)
                                                st.markdown("### 📝 文字起こし結果（通常精度）")
                                                st.text_area("結果", transcription, height=150)
                                        
                                        with col2:
                                            if st.button("🎯 高精度で文字起こし"):
                                                transcription = transcribe_audio_high_quality(filename)
                                                st.markdown("### 📝 文字起こし結果（高精度）")
                                                st.text_area("結果", transcription, height=150)
                                        
                                        # 複数モデル比較
                                        if st.button("🔄 複数モデルで比較"):
                                            st.markdown("### 📊 複数モデル比較結果")
                                            results = compare_transcriptions(filename)
                                            
                                            for model_name, text in results.items():
                                                st.markdown(f"**{model_name}モデル:**")
                                                st.text_area(f"{model_name}結果", text, height=100, key=f"compare_{model_name}")
                                        
                                        # ファイル情報
                                        file_size = os.path.getsize(filename)
                                        st.info(f"📁 ファイル情報: {filename} ({file_size:,} bytes)")
                                    else:
                                        st.error("ファイル保存に失敗しました")
                                else:
                                    st.info("自動保存が無効になっています。設定で有効にしてください。")
                            else:
                                st.error("録音データの取得に失敗しました")
                                
                        except Exception as e:
                            st.error(f"録音エラー: {e}")
                            st.info("マイクへのアクセスが許可されているか確認してください。")
            else:
                # 通常録音ボタン
                if st.button("🎤 選択されたマイクで録音開始", type="primary"):
                    if whisper_model is None:
                        st.error("Whisperモデルが読み込まれていません。ページを再読み込みしてください。")
                    else:
                        try:
                            # 録音実行
                            frames, rate = record_audio_with_device(settings['audio']['duration'], settings['audio']['gain'], selected_device['index'])
                            
                            if frames and rate:
                                st.success("録音データ取得成功")
                                
                                # 音声品質分析
                                if settings['ui']['show_quality_analysis']:
                                    quality = analyze_audio_quality(frames, rate)
                                    
                                    if quality:
                                        st.markdown("### 📊 録音品質分析")
                                        col1, col2, col3 = st.columns(3)
                                        
                                        with col1:
                                            st.metric("RMS", f"{quality['rms']:.1f}")
                                            if quality['rms'] < 100:
                                                st.warning("音声レベルが低い")
                                            else:
                                                st.success("音声レベル良好")
                                        
                                        with col2:
                                            st.metric("最大振幅", quality['max_amplitude'])
                                        
                                        with col3:
                                            st.metric("無音比率", f"{quality['silent_ratio']:.1f}%")
                                            if quality['silent_ratio'] > 70:
                                                st.warning("無音部分が多い")
                                            else:
                                                st.success("音声が検出されている")
                                
                                # ファイル保存
                                if settings['ui']['auto_save_recordings']:
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    device_name = selected_device['name'].replace(" ", "_").replace("(", "").replace(")", "")
                                    filename = f"recordings/recording_{device_name}_{timestamp}.wav"
                                    
                                    if save_audio_file(frames, rate, filename):
                                        # 文字起こし精度選択
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            if st.button("🔍 通常精度で文字起こし"):
                                                transcription = transcribe_audio(filename)
                                                st.markdown("### 📝 文字起こし結果（通常精度）")
                                                st.text_area("結果", transcription, height=150)
                                        
                                        with col2:
                                            if st.button("🎯 高精度で文字起こし"):
                                                transcription = transcribe_audio_high_quality(filename)
                                                st.markdown("### 📝 文字起こし結果（高精度）")
                                                st.text_area("結果", transcription, height=150)
                                        
                                        # 複数モデル比較
                                        if st.button("🔄 複数モデルで比較"):
                                            st.markdown("### 📊 複数モデル比較結果")
                                            results = compare_transcriptions(filename)
                                            
                                            for model_name, text in results.items():
                                                st.markdown(f"**{model_name}モデル:**")
                                                st.text_area(f"{model_name}結果", text, height=100, key=f"compare_{model_name}")
                                        
                                        # ファイル情報
                                        file_size = os.path.getsize(filename)
                                        st.info(f"📁 ファイル情報: {filename} ({file_size:,} bytes)")
                                    else:
                                        st.error("ファイル保存に失敗しました")
                                else:
                                    st.info("自動保存が無効になっています。設定で有効にしてください。")
                            else:
                                st.error("録音データの取得に失敗しました")
                                
                        except Exception as e:
                            st.error(f"録音エラー: {e}")
                            st.info("マイクへのアクセスが許可されているか確認してください。")
        else:
            st.info("⚠️ 録音するマイクデバイスを選択してください")

    with tab2:
        # 文字起こし
        st.subheader("📝 文字起こし")
        
        # 既存ファイルの文字起こし
        st.markdown("### 📁 ファイルアップロード")
        uploaded_file = st.file_uploader("音声ファイルをアップロード", type=['wav', 'mp3', 'm4a'])

        if uploaded_file is not None:
            # 一時ファイルとして保存
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            try:
                # 文字起こし精度選択
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔍 通常精度で文字起こし", key="upload_normal"):
                        transcription = transcribe_audio(tmp_file_path)
                        st.markdown("### 📝 文字起こし結果（通常精度）")
                        st.text_area("結果", transcription, height=150, key="upload_result_normal")
                        
                        # LLMへのデータ渡しボタン
                        if st.button("🤖 LLMに送信", key="llm_send_normal"):
                            if transcription:
                                llm_result = send_to_llm(transcription, "summarize")
                                st.markdown("### 🤖 LLM処理結果")
                                st.text_area("LLM結果", llm_result, height=150, key="llm_result_normal")
                            else:
                                st.error("文字起こし結果がありません")
                
                with col2:
                    if st.button("🎯 高精度で文字起こし", key="upload_high"):
                        transcription = transcribe_audio_high_quality(tmp_file_path)
                        st.markdown("### 📝 文字起こし結果（高精度）")
                        st.text_area("結果", transcription, height=150, key="upload_result_high")
                        
                        # LLMへのデータ渡しボタン
                        if st.button("🤖 LLMに送信", key="llm_send_high"):
                            if transcription:
                                llm_result = send_to_llm(transcription, "summarize")
                                st.markdown("### 🤖 LLM処理結果")
                                st.text_area("LLM結果", llm_result, height=150, key="llm_result_high")
                            else:
                                st.error("文字起こし結果がありません")
                
            except Exception as e:
                st.error(f"文字起こしエラー: {e}")
            finally:
                # 一時ファイルを削除
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass
        
        # 録音ファイルからの文字起こし
        st.markdown("---")
        st.markdown("### 🎤 録音ファイルからの文字起こし")
        
        recordings_dir = "recordings"
        if os.path.exists(recordings_dir):
            files = [f for f in os.listdir(recordings_dir) if f.endswith('.wav')]
            
            if files:
                st.write(f"**録音ファイル数**: {len(files)}")
                
                for file in sorted(files, reverse=True):
                    file_path = os.path.join(recordings_dir, file)
                    file_size = os.path.getsize(file_path)
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    with st.expander(f"📁 {file} ({file_size:,} bytes, {file_time.strftime('%Y-%m-%d %H:%M:%S')})"):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.write(f"**ファイル名**: {file}")
                            st.write(f"**サイズ**: {file_size:,} bytes")
                            st.write(f"**作成日時**: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        with col2:
                            if st.button("🔍 文字起こし", key=f"transcribe_{file}"):
                                transcription = transcribe_audio(file_path)
                                st.markdown("**文字起こし結果:**")
                                st.text_area("結果", transcription, height=100, key=f"result_{file}")
                                
                                # LLMへのデータ渡しボタン
                                if st.button("🤖 LLMに送信", key=f"llm_send_{file}"):
                                    if transcription:
                                        llm_result = send_to_llm(transcription, "summarize")
                                        st.markdown("### 🤖 LLM処理結果")
                                        st.text_area("LLM結果", llm_result, height=150, key=f"llm_result_{file}")
                                    else:
                                        st.error("文字起こし結果がありません")
                        
                        with col3:
                            if st.button("🗑️ 削除", key=f"delete_{file}"):
                                try:
                                    os.remove(file_path)
                                    st.success("ファイルを削除しました")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"削除エラー: {e}")
            else:
                st.info("録音ファイルがありません")
        else:
            st.info("recordingsディレクトリが存在しません")

