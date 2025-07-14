# 音声で入力する（WebRTC方式）

import streamlit as st
import time
import os
from dotenv import load_dotenv
import openai
import whisper
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import av
import numpy as np
import wave
import uuid

# .envからAPIキーを読み込む
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

st.title("音声で入力する（WebRTC自動文字起こし＆要約）")
st.write("録音開始→10秒ごとに自動で文字起こし＆要約します。録音停止ボタンで手動停止も可能です。\n（WebRTC方式：ブラウザから直接録音できます）")

# 録音状態管理
if 'recording' not in st.session_state:
    st.session_state['recording'] = False
if 'transcripts' not in st.session_state:
    st.session_state['transcripts'] = []
if 'summaries' not in st.session_state:
    st.session_state['summaries'] = []
if 'audio_buffer' not in st.session_state:
    st.session_state['audio_buffer'] = []
if 'last_process_time' not in st.session_state:
    st.session_state['last_process_time'] = time.time()
if 'audio_level' not in st.session_state:
    st.session_state['audio_level'] = 0.0

class AudioRecorder(AudioProcessorBase):
    def __init__(self):
        self.frames = []
        self.level = 0.0
    def recv_audio(self, frame: av.AudioFrame) -> av.AudioFrame:
        pcm = frame.to_ndarray()
        if st.session_state['recording']:
            self.frames.append(pcm)
        rms = np.sqrt(np.mean(np.square(pcm.astype(np.float32))))
        self.level = rms
        st.session_state['audio_level'] = float(rms)
        return frame

recorder_ctx = webrtc_streamer(
    key="audio-webrtc",
    mode=WebRtcMode.SENDRECV,
    audio_receiver_size=1024,
    audio_processor_factory=AudioRecorder,
    media_stream_constraints={"audio": True, "video": False},
)

col1, col2 = st.columns(2)
with col1:
    if st.button("録音開始", disabled=st.session_state['recording']):
        st.session_state['recording'] = True
        st.session_state['transcripts'] = []
        st.session_state['summaries'] = []
        st.session_state['audio_buffer'] = []
        st.session_state['last_process_time'] = time.time()
        if recorder_ctx and recorder_ctx.audio_processor:
            recorder_ctx.audio_processor.frames = []
with col2:
    if st.button("録音停止", disabled=not st.session_state['recording']):
        st.session_state['recording'] = False

# 録音中インジケータと音量メーターの表示
if recorder_ctx and recorder_ctx.state.playing:
    if st.session_state['recording']:
        st.markdown("<h2 style='color:red;'>● 録音中</h2>", unsafe_allow_html=True)
    else:
        st.markdown("<h2 style='color:gray;'>録音停止中</h2>", unsafe_allow_html=True)
    audio_level = st.session_state.get("audio_level", 0.0)
    st.progress(min(int(audio_level * 100), 100), text=f"音声入力レベル: {audio_level:.2f}")

# 10秒ごとに録音バッファを処理
if recorder_ctx and recorder_ctx.audio_processor and st.session_state['recording']:
    now = time.time()
    # 10秒ごと、またはバッファが十分たまったら処理
    if (now - st.session_state['last_process_time'] > 10) and len(recorder_ctx.audio_processor.frames) > 0:
        frames = recorder_ctx.audio_processor.frames
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
        # Whisperで文字起こし
        model = whisper.load_model("base")
        result = model.transcribe(temp_path, language="ja")
        text = result["text"]
        st.session_state['transcripts'].append(text)
        st.subheader("文字起こし結果（最新）")
        st.write(text)
        # OpenAIで要約
        if openai.api_key:
            summary_prompt = f"以下の日本語の会話を要約してください。\n{text}"
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": "あなたは日本語の要約アシスタントです。"},
                          {"role": "user", "content": summary_prompt}]
            )
            summary = None
            if response and hasattr(response, 'choices') and response.choices and hasattr(response.choices[0], 'message') and hasattr(response.choices[0].message, 'content'):
                summary = response.choices[0].message.content
            if summary:
                summary = summary.strip()
                st.session_state['summaries'].append(summary)
                st.subheader("要約（最新）")
                st.write(summary)
            else:
                st.warning("要約の取得に失敗しました。")
        else:
            st.warning("OpenAI APIキーが設定されていません。要約はスキップされます。")
        # バッファとタイマーをリセット
        recorder_ctx.audio_processor.frames = []
        st.session_state['last_process_time'] = now
        st.rerun()

# 履歴表示
if st.session_state['transcripts']:
    st.subheader("文字起こし履歴")
    for i, t in enumerate(st.session_state['transcripts'], 1):
        st.write(f"{i}. {t}")
if st.session_state['summaries']:
    st.subheader("要約履歴")
    for i, s in enumerate(st.session_state['summaries'], 1):
        st.write(f"{i}. {s}")