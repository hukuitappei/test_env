import streamlit as st
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import av
import numpy as np
import wave
import uuid
import os

st.title("最小構成：音声録音＆保存（WebRTC）")

if "recording" not in st.session_state:
    st.session_state["recording"] = False
if "audio_saved" not in st.session_state:
    st.session_state["audio_saved"] = False
if "audio_path" not in st.session_state:
    st.session_state["audio_path"] = None
if "recv_audio_count" not in st.session_state:
    st.session_state["recv_audio_count"] = 0
if "last_frame_count" not in st.session_state:
    st.session_state["last_frame_count"] = 0
if "audio_meta" not in st.session_state:
    st.session_state["audio_meta"] = {}

class AudioRecorder(AudioProcessorBase):
    def __init__(self):
        self.frames = []
        self.meta = None
    def recv_audio(self, frame: av.AudioFrame) -> av.AudioFrame:
        pcm = frame.to_ndarray()
        # メタ情報を最初のフレームから取得
        if self.meta is None:
            channels = 1 if pcm.ndim == 1 else pcm.shape[1]
            sampwidth = pcm.dtype.itemsize
            framerate = frame.sample_rate if hasattr(frame, 'sample_rate') else 48000
            self.meta = {
                'channels': channels,
                'sampwidth': sampwidth,
                'framerate': framerate,
                'dtype': str(pcm.dtype)
            }
            st.session_state["audio_meta"] = self.meta
        if st.session_state["recording"]:
            self.frames.append(pcm)
        st.session_state["recv_audio_count"] += 1
        return frame

recorder_ctx = webrtc_streamer(
    key="minimal-audio",
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
        st.session_state["recv_audio_count"] = 0
        st.session_state["last_frame_count"] = 0
        st.session_state["audio_meta"] = {}
        if recorder_ctx and recorder_ctx.audio_processor:
            recorder_ctx.audio_processor.frames = []
            recorder_ctx.audio_processor.meta = None
with col2:
    if st.button("録音停止", disabled=not st.session_state["recording"]):
        st.session_state["recording"] = False
        if recorder_ctx and recorder_ctx.audio_processor:
            st.session_state["last_frame_count"] = len(recorder_ctx.audio_processor.frames)
            st.info(f"録音停止時のフレーム数: {st.session_state['last_frame_count']}")

# デバッグ表示
st.markdown("---")
st.subheader("[デバッグ情報]")
if recorder_ctx:
    st.write(f"WebRTC state: {getattr(recorder_ctx.state, 'status', recorder_ctx.state)}")
    if recorder_ctx.audio_processor:
        st.write(f"AudioProcessor.framesの長さ: {len(recorder_ctx.audio_processor.frames)}")
        st.write(f"recv_audio呼び出し回数: {st.session_state['recv_audio_count']}")
        st.write(f"Audio meta: {st.session_state['audio_meta']}")
    else:
        st.write("AudioProcessor未初期化")
else:
    st.write("recorder_ctx未初期化")

# 録音停止時に保存
if recorder_ctx and recorder_ctx.audio_processor and not st.session_state["recording"] and not st.session_state["audio_saved"]:
    frames = recorder_ctx.audio_processor.frames
    meta = recorder_ctx.audio_processor.meta or st.session_state["audio_meta"]
    if frames and meta:
        session_id = str(uuid.uuid4())
        temp_dir = "audio_chunks"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{session_id}.wav")
        audio = np.concatenate(frames)
        with wave.open(temp_path, "wb") as wf:
            wf.setnchannels(meta['channels'])
            wf.setsampwidth(meta['sampwidth'])
            wf.setframerate(meta['framerate'])
            wf.writeframes(audio.tobytes())
        st.session_state["audio_saved"] = True
        st.session_state["audio_path"] = temp_path
        st.success(f"保存完了: {temp_path}")
        # framesをリセット
        recorder_ctx.audio_processor.frames = []
        recorder_ctx.audio_processor.meta = None
    else:
        st.warning("録音データがありません。録音開始→録音停止の順で操作してください。")
        st.session_state["audio_saved"] = True

if st.session_state["audio_path"]:
    st.info(f"保存ファイル: {st.session_state['audio_path']}") 