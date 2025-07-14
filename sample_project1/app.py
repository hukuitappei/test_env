import streamlit as st
from utils.transcribe_utils import transcribe_audio_file
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import av
import numpy as np
import wave
import uuid
import os

st.title("Tech Mentor 音声文字起こしアプリ")
st.write("下の録音ボタンで音声を録音し、録音後に[録音データを保存して文字起こし]ボタンを押してください。\n\n録音・文字起こしはこのメインページから直接利用できます。\n\n設定や要約・辞書管理はサイドバーからどうぞ。\n")

# 音量情報を格納するためのStreamlitセッション変数
if "audio_level" not in st.session_state:
    st.session_state["audio_level"] = 0.0

class AudioRecorder(AudioProcessorBase):
    def __init__(self):
        self.frames = []
        self.level = 0.0
    def recv_audio(self, frame: av.AudioFrame) -> av.AudioFrame:
        print("audio frame received")  # デバッグ用
        pcm = frame.to_ndarray()
        self.frames.append(pcm)
        # 音量（RMS値）を計算
        rms = np.sqrt(np.mean(np.square(pcm.astype(np.float32))))
        self.level = rms
        st.session_state["audio_level"] = float(rms)
        return frame

recorder = webrtc_streamer(
    key="audio",
    mode=WebRtcMode.SENDRECV,  # ← SENDRECVに変更
    audio_receiver_size=1024,
    audio_processor_factory=AudioRecorder,
    media_stream_constraints={"audio": True, "video": False},
)

# 録音中インジケータと音量メーターの表示
if recorder and recorder.state.playing:
    st.markdown('<span style="color:red;font-weight:bold;">● 録音中</span>', unsafe_allow_html=True)
    # 音量メーター
    audio_level = st.session_state.get("audio_level", 0.0)
    st.progress(min(int(audio_level * 100), 100), text=f"音声入力レベル: {audio_level:.2f}")

if recorder and recorder.audio_processor:
    if st.button("録音データを保存して文字起こし"):
        # 録音データをリセット
        recorder.audio_processor.frames = []
        session_id = str(uuid.uuid4())
        temp_dir = "audio_chunks"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{session_id}.wav")
        frames = recorder.audio_processor.frames
        print(f"framesの長さ: {len(frames)}")  # デバッグ用
        if frames:
            audio = np.concatenate(frames)
            print(f"audio shape: {audio.shape}")  # デバッグ用
            with wave.open(temp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16bit
                wf.setframerate(48000)
                wf.writeframes(audio.tobytes())
            print(f"保存したwavファイル: {temp_path}")  # デバッグ用
            st.success("録音データを保存しました")
            # ここで文字起こし処理を呼び出す
            text, error_message = transcribe_audio_file(temp_path, session_id, 0, "transcriptions", return_error=True)
            if text:
                st.success("文字起こし結果:")
                st.text_area("テキスト", text, height=200)
            else:
                st.error("文字起こしに失敗しました")
                if error_message:
                    st.error(f"詳細: {error_message}")
        else:
            st.warning("録音データがありません。録音後にボタンを押してください。")



