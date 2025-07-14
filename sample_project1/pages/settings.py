import streamlit as st
import streamlit.components.v1 as components
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import av
import numpy as np
import wave
import uuid
import os

st.header('設定')
st.write('マイクデバイス選択や音量調整などを行えます。')
# マイクデバイス一覧取得・選択（JSで取得し、選択したIDをsession_stateに保存）
mic_selector_html = '''
<div>
  <label for="micSelect">マイクデバイス:</label>
  <select id="micSelect"></select>
  <button id="saveMic">選択</button>
  <span id="micStatus"></span>
</div>
<script>
async function getMicList() {
  let devices = await navigator.mediaDevices.enumerateDevices();
  let mics = devices.filter(d => d.kind === 'audioinput');
  let select = document.getElementById('micSelect');
  select.innerHTML = '';
  mics.forEach(m => {
    let opt = document.createElement('option');
    opt.value = m.deviceId;
    opt.text = m.label || 'マイク-' + m.deviceId.substring(0, 6);
    select.appendChild(opt);
  });
}
getMicList();
document.getElementById('saveMic').onclick = function() {
  let select = document.getElementById('micSelect');
  let deviceId = select.value;
  let label = select.options[select.selectedIndex].text;
  window.parent.postMessage({mic_device_id: deviceId, mic_device_label: label}, '*');
  document.getElementById('micStatus').innerText = '選択しました: ' + label;
};
</script>
'''
components.html(mic_selector_html, height=100)
# 音量調整
volume = st.slider("音量調整（録音時のゲイン）", 0, 200, 100, 1, key='volume')
# サンプリングレート選択
sample_rate = st.selectbox("サンプリングレート", [16000, 22050, 44100], index=0, key='sample_rate')

# --- 音量調整テスト用 録音・再生UI ---
st.subheader("音量調整テスト（録音・再生）")
st.caption("録音ボタンでテスト録音し、録音後に再生できます。音量スライダーの値が録音ゲインに反映されます。")

if "test_audio_level" not in st.session_state:
    st.session_state["test_audio_level"] = 0.0
if "test_audio_data" not in st.session_state:
    st.session_state["test_audio_data"] = None

class TestAudioRecorder(AudioProcessorBase):
    def __init__(self):
        self.frames = []
        self.level = 0.0
    def recv_audio(self, frame: av.AudioFrame) -> av.AudioFrame:
        print("test audio frame received")  # デバッグ用
        pcm = frame.to_ndarray().astype(np.float32)
        # 音量ゲイン適用
        gain = st.session_state.get('volume', 100) / 100.0
        pcm = pcm * gain
        self.frames.append(pcm.astype(np.int16))
        rms = np.sqrt(np.mean(np.square(pcm)))
        self.level = rms
        st.session_state["test_audio_level"] = float(rms)
        return av.AudioFrame.from_ndarray(pcm.astype(np.int16), layout=frame.layout.name)

test_recorder = webrtc_streamer(
    key="test_audio",
    mode=WebRtcMode.SENDONLY,
    audio_receiver_size=1024,
    audio_processor_factory=TestAudioRecorder,
    media_stream_constraints={"audio": True, "video": False},
)

if test_recorder and test_recorder.state.playing:
    st.markdown('<span style="color:red;font-weight:bold;">● 録音中</span>', unsafe_allow_html=True)
    audio_level = st.session_state.get("test_audio_level", 0.0)
    st.progress(min(int(audio_level * 100), 100), text=f"音声入力レベル: {audio_level:.2f}")

# 録音データの保存と再生
if test_recorder and test_recorder.audio_processor:
    if st.button("テスト録音データを保存"):
        session_id = str(uuid.uuid4())
        temp_dir = "audio_chunks"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"test_{session_id}.wav")
        frames = test_recorder.audio_processor.frames
        if frames:
            audio = np.concatenate(frames)
            with wave.open(temp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16bit
                wf.setframerate(st.session_state.get('sample_rate', 16000))
                wf.writeframes(audio.tobytes())
            st.session_state["test_audio_data"] = temp_path
            st.success("テスト録音データを保存しました")
        else:
            st.warning("録音データがありません。録音後にボタンを押してください。")

# 再生ボタン
if st.session_state.get("test_audio_data"):
    st.audio(st.session_state["test_audio_data"], format="audio/wav")
    if st.button("テスト録音データを削除"):
        try:
            os.remove(st.session_state["test_audio_data"])
        except Exception:
            pass
        st.session_state["test_audio_data"] = None 