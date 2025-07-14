import streamlit as st
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import av
import numpy as np
import wave
import os
import uuid

st.title("音声録音・保存＋オウム返しサンプル")

if "recording" not in st.session_state:
    st.session_state["recording"] = False

class AudioRecorder(AudioProcessorBase):
    def __init__(self):
        self.frames = []
    def recv_audio(self, frame: av.AudioFrame) -> av.AudioFrame:
        pcm = frame.to_ndarray()
        print("[DEBUG] recv_audio called", pcm.shape, pcm.dtype)  # デバッグ用
        # int16型でない場合は変換
        if pcm.dtype != np.int16:
            print("[DEBUG] pcm dtype is not int16, converting...")
            pcm = pcm.astype(np.int16)
        if st.session_state["recording"]:
            self.frames.append(pcm)
        # オウム返し（明示的に新しいAudioFrameを返す）
        return av.AudioFrame.from_ndarray(pcm, layout=frame.layout.name)

def save_wav(frames, out_dir="audio_chunks"):
    if not frames:
        print("[DEBUG] save_wav: frames is empty!")
        return None
    audio = np.concatenate(frames)
    print(f"[DEBUG] save_wav: audio shape={audio.shape}, dtype={audio.dtype}")
    os.makedirs(out_dir, exist_ok=True)
    session_id = str(uuid.uuid4())
    wav_path = os.path.join(out_dir, f"{session_id}.wav")
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        wf.writeframes(audio.tobytes())
    print(f"[DEBUG] save_wav: saved to {wav_path}")
    return wav_path

def toggle_recording():
    st.session_state["recording"] = not st.session_state["recording"]
    if st.session_state["recording"]:
        if recorder_ctx and recorder_ctx.audio_processor:
            print("[DEBUG] toggle_recording: frames reset")
            recorder_ctx.audio_processor.frames = []  # 録音開始時にリセット
        st.toast("録音開始", icon=":material/mic:")
    else:
        st.toast("録音停止", icon=":material/mic_off:")

recorder_ctx = webrtc_streamer(
    key="sendrecv-audio",
    mode=WebRtcMode.SENDRECV,
    audio_receiver_size=256,
    audio_processor_factory=AudioRecorder,
    media_stream_constraints={"audio": True, "video": False},
)

st.button(
    "録音 " + ("停止" if st.session_state["recording"] else "開始"),
    on_click=toggle_recording,
    type="primary" if st.session_state["recording"] else "secondary",
    disabled=recorder_ctx.audio_receiver is None
)

# 録音停止時に保存ボタンを表示
if recorder_ctx and recorder_ctx.audio_processor and not st.session_state["recording"]:
    if st.button("音声ファイルに変換・保存"):
        frames = recorder_ctx.audio_processor.frames
        wav_path = save_wav(frames)
        if wav_path:
            with open(wav_path, "rb") as f:
                st.download_button("録音データをダウンロード", f, file_name=wav_path.split("/")[-1], mime="audio/wav")
            st.success(f"保存しました: {wav_path}")
            recorder_ctx.audio_processor.frames = []
        else:
            st.warning("録音データがありません") 