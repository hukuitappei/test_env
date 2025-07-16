import streamlit as st
import whisper
import tempfile
import os
from datetime import datetime
import wave
import pyaudio

st.set_page_config(page_title="音声録音＆文字起こし", page_icon="🎤", layout="centered")
st.title("🎤 音声録音＆文字起こし（Streamlit版）")

# 音声認識エンジンの初期化
@st.cache_resource
def get_whisper_model():
    return whisper.load_model("base")

whisper_model = get_whisper_model()

# 録音機能
def record_audio(duration=10):
    """指定時間録音する関数"""
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    
    st.info(f"🎤 {duration}秒間録音します...")
    frames = []
    
    for i in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    return frames, RATE

# 録音データをWAVファイルに保存
def save_audio(frames, rate, filename):
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))

# 文字起こし機能
def transcribe_audio(audio_file_path):
    """音声ファイルを文字起こしする関数"""
    try:
        result = whisper_model.transcribe(audio_file_path, language="ja")
        return result["text"]
    except Exception as e:
        return f"音声認識エラー: {e}"

# メインUI
st.markdown("---")

# 録音時間の設定
duration = st.slider("録音時間（秒）", min_value=1, max_value=60, value=5, step=1)

# 録音ボタン
if st.button("🎤 録音開始", type="primary"):
    try:
        # 録音実行
        frames, rate = record_audio(duration)
        
        # ファイル保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recordings/recording_{timestamp}.wav"
        save_audio(frames, rate, filename)
        
        st.success(f"✅ 録音完了！保存ファイル: {filename}")
        
        # 文字起こし実行
        st.info("🔍 文字起こし中...")
        transcription = transcribe_audio(filename)
        
        # 結果表示
        st.markdown("### 📝 文字起こし結果")
        st.text_area("結果", transcription, height=150)
        
        # ファイル情報
        file_size = os.path.getsize(filename)
        st.info(f"📁 ファイル情報: {filename} ({file_size:,} bytes)")
        
    except Exception as e:
        st.error(f"録音エラー: {e}")
        st.info("マイクへのアクセスが許可されているか確認してください。")

# 既存ファイルの文字起こし
st.markdown("---")
st.subheader("📁 既存ファイルの文字起こし")

uploaded_file = st.file_uploader("音声ファイルをアップロード", type=['wav', 'mp3', 'm4a'])

if uploaded_file is not None:
    # 一時ファイルとして保存
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_file_path = tmp_file.name
    
    try:
        st.info("🔍 文字起こし中...")
        transcription = transcribe_audio(tmp_file_path)
        
        st.markdown("### 📝 文字起こし結果")
        st.text_area("結果", transcription, height=150)
        
    except Exception as e:
        st.error(f"文字起こしエラー: {e}")
    finally:
        # 一時ファイルを削除
        os.unlink(tmp_file_path)

# 保存されたファイル一覧
st.markdown("---")
st.subheader("📂 保存されたファイル")

wav_files = [f for f in os.listdir('recordings') if f.endswith('.wav')]
if wav_files:
    for file in sorted(wav_files, reverse=True):
        file_path = os.path.join('recordings', file)
        file_size = os.path.getsize(file_path)
        st.write(f"• {file} ({file_size:,} bytes)")
else:
    st.info("まだ録音ファイルがありません")

# 使用方法
st.markdown("---")
st.subheader("📖 使用方法")
st.markdown("""
1. **録音**: 録音時間を設定して「録音開始」ボタンを押す
2. **文字起こし**: 録音後、自動で文字起こしが実行される
3. **ファイルアップロード**: 既存の音声ファイルも文字起こし可能
4. **保存**: 録音ファイルは自動で保存される
""") 