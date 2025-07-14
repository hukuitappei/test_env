import streamlit as st
from utils.transcribe_utils import transcribe_audio_file
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import av
import numpy as np
import wave
import uuid
import os

st.title("Tech Mentor 音声文字起こしアプリ")
st.write("下の録音開始/停止ボタンで音声を録音し、録音停止時に自動で保存・再生・文字起こしを行います。\n\n録音・文字起こしはこのメインページから直接利用できます。\n\n設定や要約・辞書管理はサイドバーからどうぞ。\n")

# 録音状態管理
if "recording" not in st.session_state:
    st.session_state["recording"] = False
if "audio_saved" not in st.session_state:
    st.session_state["audio_saved"] = False
if "audio_path" not in st.session_state:
    st.session_state["audio_path"] = None
if "transcribed_text" not in st.session_state:
    st.session_state["transcribed_text"] = None
if "transcribe_error" not in st.session_state:
    st.session_state["transcribe_error"] = None
if "audio_level" not in st.session_state:
    st.session_state["audio_level"] = 0.0

class AudioRecorder(AudioProcessorBase):
    def __init__(self):
        self.frames = []
        self.level = 0.0
    def recv_audio(self, frame: av.AudioFrame) -> av.AudioFrame:
        pcm = frame.to_ndarray()
        if st.session_state["recording"]:
            self.frames.append(pcm)
        rms = np.sqrt(np.mean(np.square(pcm.astype(np.float32))))
        self.level = rms
        st.session_state["audio_level"] = float(rms)
        return frame

recorder_ctx = webrtc_streamer(
    key="audio",
    mode=WebRtcMode.SENDRECV,
    audio_receiver_size=1024,
    audio_processor_factory=AudioRecorder,
    media_stream_constraints={"audio": True, "video": False},
)

col1, col2 = st.columns(2)
with col1:
    if st.button("録音開始", disabled=st.session_state["recording"]):
        st.session_state["recording"] = True
        st.session_state["audio_saved"] = False
        st.session_state["audio_path"] = None
        st.session_state["transcribed_text"] = None
        st.session_state["transcribe_error"] = None
        if recorder_ctx and recorder_ctx.audio_processor:
            recorder_ctx.audio_processor.frames = []
with col2:
    if st.button("録音停止", disabled=not st.session_state["recording"]):
        st.session_state["recording"] = False

# 録音中インジケータと音量メーターの表示
if recorder_ctx and recorder_ctx.state.playing:
    if st.session_state["recording"]:
        st.markdown('<span style="color:red;font-weight:bold;">● 録音中</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="color:gray;font-weight:bold;">録音停止中</span>', unsafe_allow_html=True)
    audio_level = st.session_state.get("audio_level", 0.0)
    st.progress(min(int(audio_level * 100), 100), text=f"音声入力レベル: {audio_level:.2f}")

# 録音停止時に保存・再生・文字起こし
if recorder_ctx and recorder_ctx.audio_processor and not st.session_state["recording"] and not st.session_state["audio_saved"]:
    frames = recorder_ctx.audio_processor.frames
    if frames:
        session_id = str(uuid.uuid4())
        temp_dir = "audio_chunks"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{session_id}.wav")
        audio = np.concatenate(frames)
        with wave.open(temp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(audio.tobytes())
        st.session_state["audio_saved"] = True
        st.session_state["audio_path"] = temp_path
        # 再生
        with open(temp_path, "rb") as f:
            st.audio(f.read(), format="audio/wav")
        # 文字起こし
        text, error_message = transcribe_audio_file(temp_path, session_id, 0, "transcriptions", return_error=True)
        if text:
            st.session_state["transcribed_text"] = text
            st.session_state["transcribe_error"] = None
        else:
            st.session_state["transcribed_text"] = None
            st.session_state["transcribe_error"] = error_message
        # framesをリセット
        recorder_ctx.audio_processor.frames = []
    else:
        st.warning("録音データがありません。録音開始→録音停止の順で操作してください。")
        st.session_state["audio_saved"] = True  # 空でも一度だけ警告

# 結果表示
if st.session_state["audio_path"]:
    st.success("録音データを保存しました")
    with open(st.session_state["audio_path"], "rb") as f:
        st.audio(f.read(), format="audio/wav")
if st.session_state["transcribed_text"]:
    st.success("文字起こし結果:")
    st.text_area("テキスト", st.session_state["transcribed_text"], height=200)
if st.session_state["transcribe_error"]:
    st.error("文字起こしに失敗しました")
    st.error(f"詳細: {st.session_state['transcribe_error']}")



