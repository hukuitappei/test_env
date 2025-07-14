# 音声で入力する

######## Streamlitの設定 ########
import streamlit as st
import time
import os
from dotenv import load_dotenv
import openai
import pyaudio
import wave
import whisper

# .envからAPIキーを読み込む
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

st.title("音声で入力する（自動文字起こし＆要約）")
st.write("マイクに話しかけてください。録音開始→10秒ごとに自動で文字起こし＆要約します。\n録音停止ボタンで手動停止も可能です。")

# 録音関係の設定
p = pyaudio.PyAudio()
devices = []
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    max_input_channels = info['maxInputChannels']
    if isinstance(max_input_channels, str):
        try:
            max_input_channels = int(max_input_channels)
        except Exception:
            max_input_channels = 0
    if max_input_channels > 0:
        devices.append({
            'id': i,
            'name': info['name'],
            'channels': max_input_channels
        })

if 'selected_device_id' not in st.session_state:
    st.session_state['selected_device_id'] = devices[0]['id'] if devices else None

device_options = [f"ID {d['id']}: {d['name']} (Channels: {d['channels']})" for d in devices]
selected_option = st.selectbox("使用するマイクデバイスを選択してください", device_options, index=0)
selected_index = device_options.index(selected_option)
selected_device_id = devices[selected_index]['id']
st.session_state['selected_device_id'] = selected_device_id

# 録音状態管理
if 'recording' not in st.session_state:
    st.session_state['recording'] = False
if 'transcripts' not in st.session_state:
    st.session_state['transcripts'] = []
if 'summaries' not in st.session_state:
    st.session_state['summaries'] = []

# 録音UI
col1, col2 = st.columns(2)
with col1:
    if st.button("録音開始", disabled=st.session_state['recording']):
        st.session_state['recording'] = True
        st.session_state['transcripts'] = []
        st.session_state['summaries'] = []
with col2:
    if st.button("録音停止", disabled=not st.session_state['recording']):
        st.session_state['recording'] = False

if st.session_state['recording']:
    st.markdown("<h2 style='color:red;'>● 録音中...</h2>", unsafe_allow_html=True)
else:
    st.markdown("<h2 style='color:gray;'>録音停止中</h2>", unsafe_allow_html=True)

# 録音・文字起こし・要約の自動ループ
if st.session_state['recording']:
    chunk = 1024
    format = pyaudio.paInt16
    channels = 1
    rate = 44100
    record_seconds = 10
    output_filename = "output.wav"
    st.info("10秒ごとに自動で録音・文字起こし・要約します。録音停止ボタンで終了できます。")
    # 10秒録音
    try:
        stream = p.open(format=format,
                        channels=channels,
                        rate=rate,
                        input=True,
                        input_device_index=selected_device_id,
                        frames_per_buffer=chunk)
        frames = []
        for i in range(0, int(rate / chunk * record_seconds)):
            data = stream.read(chunk)
            frames.append(data)
        stream.stop_stream()
        stream.close()
        wf = wave.open(output_filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(format))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        st.success(f"録音完了: {output_filename}")
        # Whisperで文字起こし
        model = whisper.load_model("base")
        result = model.transcribe(output_filename, language="ja")
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
        # 10秒ごとに自動で繰り返す
        st.rerun()
    except Exception as e:
        st.error(f"録音・文字起こし・要約中にエラーが発生しました: {e}")

# 履歴表示
if st.session_state['transcripts']:
    st.subheader("文字起こし履歴")
    for i, t in enumerate(st.session_state['transcripts'], 1):
        st.write(f"{i}. {t}")
if st.session_state['summaries']:
    st.subheader("要約履歴")
    for i, s in enumerate(st.session_state['summaries'], 1):
        st.write(f"{i}. {s}")