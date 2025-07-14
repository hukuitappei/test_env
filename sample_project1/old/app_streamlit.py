import os
import streamlit as st
from datetime import datetime
import uuid
import json
import shutil
import base64
import streamlit.components.v1 as components
from utils.transcribe_utils import transcribe_audio_file
from dotenv import load_dotenv
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import av
import numpy as np
import wave

# .envから環境変数を読み込む
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ページ切り替え用セッションステート
if 'page' not in st.session_state:
    st.session_state['page'] = 'main'
if 'mic_device_id' not in st.session_state:
    st.session_state['mic_device_id'] = ''
if 'mic_device_label' not in st.session_state:
    st.session_state['mic_device_label'] = ''

# 設定ページへの遷移ボタン
if st.session_state['page'] == 'main':
    if st.button('設定', key='to_settings'):
        st.session_state['page'] = 'settings'

if st.session_state['page'] == 'settings':
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
    test_recorder_html = f'''
    <style>
    #testRecordButton {{
      background-color: #2196F3;
      color: white;
      border: none;
      padding: 10px 24px;
      font-size: 16px;
      border-radius: 8px;
      margin-bottom: 8px;
    }}
    #testRecordButton.recording {{
      background-color: #e53935;
    }}
    #testStatus {{
      font-weight: bold;
      color: #2196F3;
    }}
    #testStatus.recording {{
      color: #e53935;
    }}
    #testVolumeMeter {{
      width: 200px;
      height: 20px;
      background: #eee;
      border-radius: 10px;
      margin-top: 8px;
    }}
    </style>
    <div id="testRecorder">
      <button id="testRecordButton">● 録音開始/停止</button>
      <audio id="testAudioPlayback" controls style="display:none;"></audio>
      <br/>
      <span id="testStatus">待機中</span>
      <canvas id="testVolumeMeter"></canvas>
    </div>
    <script>
    let testChunks = [];
    let testRecorder;
    let testAudioURL = '';
    let testStream;
    let testIsRecording = false;
    let testAudioContext, testAnalyser, testDataArray, testSource, testGainNode;
    const testRecordButton = document.getElementById('testRecordButton');
    const testAudioPlayback = document.getElementById('testAudioPlayback');
    const testStatus = document.getElementById('testStatus');
    const testVolumeMeter = document.getElementById('testVolumeMeter');
    let testSelectedMic = "{st.session_state.get('mic_device_id','')}";
    let testGainValue = {st.session_state.get('volume', 100)} / 100.0;
    function drawTestVolume() {{
      if (!testAnalyser) return;
      requestAnimationFrame(drawTestVolume);
      testAnalyser.getByteTimeDomainData(testDataArray);
      let sum = 0;
      for (let i = 0; i < testDataArray.length; i++) {{
        let v = (testDataArray[i] - 128) / 128.0;
        sum += v * v;
      }}
      let volume = Math.sqrt(sum / testDataArray.length);
      let ctx = testVolumeMeter.getContext('2d');
      ctx.clearRect(0, 0, testVolumeMeter.width, testVolumeMeter.height);
      ctx.fillStyle = testIsRecording ? '#e53935' : '#2196F3';
      ctx.fillRect(0, 0, testVolumeMeter.width * volume, testVolumeMeter.height);
    }}
    testRecordButton.onclick = async function() {{
      if (!testIsRecording) {{
        let constraints = {{ audio: {{sampleRate: {st.session_state.get('sample_rate', 16000)}}} }};
        if (testSelectedMic) {{
          constraints.audio.deviceId = {{exact: testSelectedMic}};
        }}
        testStream = await navigator.mediaDevices.getUserMedia(constraints);
        testAudioContext = new (window.AudioContext || window.webkitAudioContext)();
        testSource = testAudioContext.createMediaStreamSource(testStream);
        testGainNode = testAudioContext.createGain();
        testGainNode.gain.value = testGainValue;
        testAnalyser = testAudioContext.createAnalyser();
        testSource.connect(testGainNode).connect(testAnalyser);
        testAnalyser.fftSize = 256;
        testDataArray = new Uint8Array(testAnalyser.fftSize);
        drawTestVolume();
        // 録音
        let dest = testAudioContext.createMediaStreamDestination();
        testGainNode.connect(dest);
        testRecorder = new MediaRecorder(dest.stream);
        testRecorder.ondataavailable = e => testChunks.push(e.data);
        testRecorder.onstop = e => {{
          const blob = new Blob(testChunks, {{ type: 'audio/wav' }});
          testChunks = [];
          testAudioURL = window.URL.createObjectURL(blob);
          testAudioPlayback.src = testAudioURL;
          testAudioPlayback.style.display = 'block';
          // base64変換
          var reader = new FileReader();
          reader.readAsDataURL(blob);
          reader.onloadend = function() {{
            var base64data = reader.result;
            // クエリパラメータにbase64を埋め込む
            let url = new URL(window.location.href);
            url.searchParams.set('test_wav_base64', base64data);
            window.location.href = url.toString();
          }}
        }};
        testRecorder.start();
        testIsRecording = true;
        testRecordButton.classList.add('recording');
        testStatus.classList.add('recording');
        testStatus.innerText = '録音中';
        testRecordButton.innerText = '■ 録音停止';
      }} else {{
        testRecorder.stop();
        testStream.getTracks().forEach(track => track.stop());
        if (testAudioContext) testAudioContext.close();
        testIsRecording = false;
        testRecordButton.classList.remove('recording');
        testStatus.classList.remove('recording');
        testStatus.innerText = '待機中';
        testRecordButton.innerText = '● 録音開始/停止';
        let ctx = testVolumeMeter.getContext('2d');
        ctx.clearRect(0, 0, testVolumeMeter.width, testVolumeMeter.height);
      }}
    }};
    testVolumeMeter.width = 200;
    testVolumeMeter.height = 20;
    </script>
    '''
    components.html(test_recorder_html, height=200)

    # Python側でtest_wav_base64をquery_paramsから受信し、st.audioで再生
    test_wav_data = st.query_params.get('test_wav_base64', [None])[0]
    if test_wav_data and test_wav_data.startswith("data:audio/wav;base64,"):
        st.success("テスト録音データを再生できます")
        st.audio(test_wav_data, format="audio/wav")
        # 文字起こし実行ボタン
        if st.button("テスト録音データで文字起こし実行", key="test_transcribe_btn"):
            import uuid, base64, os
            from utils.transcribe_utils import transcribe_audio_file
            session_id = "test_" + str(uuid.uuid4())
            chunk_index = 0
            b64 = test_wav_data.split(",")[1]
            wav_bytes = base64.b64decode(b64)
            temp_dir = "audio_chunks"
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"{session_id}_chunk{chunk_index}.wav")
            with open(temp_path, "wb") as f:
                f.write(wav_bytes)
            # 文字起こし
            trans_dir = "transcriptions"
            text = transcribe_audio_file(temp_path, session_id, chunk_index, trans_dir)
            if text:
                st.success("文字起こし結果:")
                st.text_area("テスト録音の文字起こしテキスト", text, height=200, key="test_transcribe_text")
            else:
                st.error("文字起こしに失敗しました")

    # --- コマンド辞書管理 ---
    st.subheader("コマンド辞書管理")
    COMMAND_DICT_PATH = os.path.join("settings", 'command_dictionary.json')
    def load_dict(path):
        if not os.path.exists(path):
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    def save_dict(path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    cmd_dict = load_dict(COMMAND_DICT_PATH)
    new_word = st.text_input("新しいコマンド単語を追加", key="cmd_add_settings")
    if st.button("追加", key="cmd_add_btn_settings") and new_word:
        if new_word in cmd_dict:
            st.warning("既に登録されています")
        else:
            cmd_dict.append(new_word)
            save_dict(COMMAND_DICT_PATH, cmd_dict)
            st.success("登録しました")
    if cmd_dict:
        st.write(cmd_dict)
    else:
        st.info("コマンド辞書は空です")

    # --- 設定画面で自動録音開始オプション ---
    st.subheader("自動録音設定")
    if 'auto_record_on_settings' not in st.session_state:
        st.session_state['auto_record_on_settings'] = False
    auto_record = st.checkbox("設定画面に入ったら自動で録音を開始する", value=st.session_state['auto_record_on_settings'], key='auto_record_on_settings')

    # --- 設定画面で自動録音UI ---
    if auto_record:
        st.info("設定画面に入ったので自動で録音UIを表示しています。録音ボタンを押してください。")
        auto_recorder_html = '''
        <style>
        #recordButton_settings {{
          background-color: #2196F3;
          color: white;
          border: none;
          padding: 10px 24px;
          font-size: 16px;
          border-radius: 8px;
          margin-bottom: 8px;
        }}
        #recordButton_settings.recording {{
          background-color: #e53935;
        }}
        #status_settings {{
          font-weight: bold;
          color: #2196F3;
        }}
        #status_settings.recording {{
          color: #e53935;
        }}
        #volumeMeter_settings {{
          width: 200px;
          height: 20px;
          background: #eee;
          border-radius: 10px;
          margin-top: 8px;
        }}
        </style>
        <div id=\"recorder_settings\">\n          <button id=\"recordButton_settings\">● 録音開始/停止</button>\n          <audio id=\"audioPlayback_settings\" controls style=\"display:none;\"></audio>\n          <br/>\n          <span id=\"status_settings\">待機中</span>\n          <canvas id=\"volumeMeter_settings\"></canvas>\n        </div>\n        <script>\n        let chunks = [];\n        let recorder;\n        let audioURL = '';\n        let stream;\n        let isRecording = false;\n        let audioContext, analyser, dataArray, source;\n        const recordButton = document.getElementById('recordButton_settings');\n        const audioPlayback = document.getElementById('audioPlayback_settings');\n        const status = document.getElementById('status_settings');\n        const volumeMeter = document.getElementById('volumeMeter_settings');\n        function drawVolume() {{\n          if (!analyser) return;\n          requestAnimationFrame(drawVolume);\n          analyser.getByteTimeDomainData(dataArray);\n          let sum = 0;\n          for (let i = 0; i < dataArray.length; i++) {{\n            let v = (dataArray[i] - 128) / 128.0;\n            sum += v * v;\n          }}\n          let volume = Math.sqrt(sum / dataArray.length);\n          let ctx = volumeMeter.getContext('2d');\n          ctx.clearRect(0, 0, volumeMeter.width, volumeMeter.height);\n          ctx.fillStyle = isRecording ? '#e53935' : '#2196F3';\n          ctx.fillRect(0, 0, volumeMeter.width * volume, volumeMeter.height);\n        }}\n        recordButton.onclick = async function() {{\n          if (!isRecording) {{\n            stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});\n            recorder = new MediaRecorder(stream);\n            recorder.ondataavailable = e => chunks.push(e.data);\n            recorder.onstop = e => {{\n              const blob = new Blob(chunks, {{ type: 'audio/wav' }});\n              chunks = [];\n              audioURL = window.URL.createObjectURL(blob);\n              audioPlayback.src = audioURL;\n              audioPlayback.style.display = 'block';
              // base64変換\n              var reader = new FileReader();\n              reader.readAsDataURL(blob);\n              reader.onloadend = function() {{\n                var base64data = reader.result;\n                // クエリパラメータにbase64を埋め込む\n                let url = new URL(window.location.href);\n                url.searchParams.set('wav_base64', base64data);\n                window.location.href = url.toString();\n              }}\n            }};\n            // 音量メーター\n            audioContext = new (window.AudioContext || window.webkitAudioContext)();\n            analyser = audioContext.createAnalyser();\n            source = audioContext.createMediaStreamSource(stream);\n            source.connect(analyser);\n            analyser.fftSize = 256;\n            dataArray = new Uint8Array(analyser.fftSize);\n            drawVolume();\n            isRecording = true;\n            recordButton.classList.add('recording');
              status.classList.add('recording');\n            status.innerText = '録音中';\n            recordButton.innerText = '■ 録音停止';\n          }} else {{\n            recorder.stop();
            stream.getTracks().forEach(track => track.stop());\n            if (audioContext) audioContext.close();\n            isRecording = false;\n            recordButton.classList.remove('recording');\n            status.classList.remove('recording');\n            status.innerText = '待機中';\n            recordButton.innerText = '● 録音開始/停止';\n            let ctx = volumeMeter.getContext('2d');\n            ctx.clearRect(0, 0, volumeMeter.width, volumeMeter.height);\n          }}\n        }};\n        volumeMeter.width = 200;\n        volumeMeter.height = 20;\n        // ページ表示時に自動で録音ボタンをクリック\n        window.onload = function() {{\n          setTimeout(function() {{\n            recordButton.click();\n          }}, 500);\n        }};\n        </script>\n        '''
        components.html(auto_recorder_html, height=200)

    # 戻るボタンは常に表示
    if st.button('戻る', key='to_main'):
        st.session_state['page'] = 'main'
        st.rerun()
    st.stop()

# JSからのマイクデバイス選択受信
mic_device_id = st.session_state.get('mic_device_id', '')
mic_device_label = st.session_state.get('mic_device_label', '')

# --- pages/recorder.py ---
st.header("1. 音声録音＆文字起こし（streamlit-webrtc版）")
st.write("下の録音ボタンで音声を録音し、録音後に[録音データを保存して文字起こし]ボタンを押してください。\n\n**設定画面でマイクや音量を調整できます。**")

class AudioRecorder(AudioProcessorBase):
    def __init__(self):
        self.frames = []
    def recv_audio(self, frame: av.AudioFrame) -> av.AudioFrame:
        pcm = frame.to_ndarray()
        self.frames.append(pcm)
        return frame

recorder = webrtc_streamer(
    key="audio",
    mode=WebRtcMode.SENDONLY,
    audio_receiver_size=1024,
    audio_processor_factory=AudioRecorder,
    media_stream_constraints={"audio": True, "video": False},
)

if recorder and recorder.audio_processor:
    if st.button("録音データを保存して文字起こし"):
        session_id = str(uuid.uuid4())
        temp_dir = "audio_chunks"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{session_id}.wav")
        frames = recorder.audio_processor.frames
        if frames:
            audio = np.concatenate(frames)
            with wave.open(temp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16bit
                wf.setframerate(48000)
                wf.writeframes(audio.tobytes())
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

# --- 文字起こしファイル一覧・要約・辞書管理などはそのまま下に残す ---

# Python側でwav_base64をquery_paramsから受信し、session_stateに保存
wav_data = None
if 'wav_base64' not in st.session_state:
    wav_data = st.query_params.get('wav_base64', [None])[0]
    if wav_data:
        st.session_state['wav_base64'] = wav_data
else:
    wav_data = st.session_state['wav_base64']

# 受信したbase64データをWAVファイルとして保存
if wav_data and wav_data.startswith("data:audio/wav;base64,"):
    b64 = wav_data.split(",")[1]
    wav_bytes = base64.b64decode(b64)
    session_id = str(uuid.uuid4())
    chunk_index = 0
    UPLOAD_FOLDER = "audio_chunks"
    TRANSCRIPTION_FOLDER = "transcriptions"
    session_upload_dir = os.path.join(UPLOAD_FOLDER, session_id)
    os.makedirs(session_upload_dir, exist_ok=True)
    filename = f"{session_id}_chunk{chunk_index}.wav"
    filepath = os.path.join(session_upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(wav_bytes)
    st.success(f"録音データを保存しました: {filename}")
    # 録音内容の再生
    st.audio(wav_data, format="audio/wav")
    if st.button("録音データを保存して文字起こし"):
        # transcribe_audio_fileを(text, error_message)タプルで返すように修正
        from utils.transcribe_utils import transcribe_audio_file
        try:
            result = transcribe_audio_file(filepath, session_id, chunk_index, TRANSCRIPTION_FOLDER, return_error=True)
        except TypeError:
            # 古いシグネチャの場合は従来通り
            text = transcribe_audio_file(filepath, session_id, chunk_index, TRANSCRIPTION_FOLDER)
            result = (text, None)
        text, error_message = result
        if text:
            st.success("文字起こし結果:")
            st.text_area("テキスト", text, height=200)
            # 保存
            out_dir = os.path.join(TRANSCRIPTION_FOLDER, session_id)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"{session_id}_chunk{chunk_index}.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
        else:
            st.error("文字起こしに失敗しました")
            if error_message:
                st.error(f"詳細: {error_message}")

# --- 文字起こしファイル一覧 ---
st.header("2. 文字起こしファイル一覧")
trans_files = []
for root, _, files in os.walk("transcriptions"):
    for file in files:
        if file.endswith('.txt'):
            rel_path = os.path.relpath(os.path.join(root, file), "transcriptions")
            trans_files.append(rel_path)
selected_trans_text = ""
if trans_files:
    selected = st.selectbox("表示するファイルを選択", trans_files, key="trans_select")
    if selected:
        with open(os.path.join("transcriptions", selected), "r", encoding="utf-8") as f:
            selected_trans_text = f.read()
        st.text_area("内容", selected_trans_text, height=200, key="trans_text_area")
else:
    st.info("文字起こしファイルがありません")

# --- 要約機能（OpenAI APIキーが必要） ---
st.header("3. 要約機能（OpenAI APIキーが必要）")
def get_openai_api_key():
    if OPENAI_API_KEY:
        return OPENAI_API_KEY
    return st.text_input("OpenAI APIキー", type="password")

openai_api_key = get_openai_api_key()
# 文字起こしテキストがあれば自動で要約欄に渡す
if selected_trans_text:
    default_summary_text = selected_trans_text
else:
    default_summary_text = ""
if openai_api_key:
    import openai
    openai.api_key = openai_api_key
    text_to_summarize = st.text_area("要約したいテキストを入力または上記からコピペ", value=default_summary_text, key="summary_input")
    if st.button("要約実行") and text_to_summarize:
        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": f"以下のテキストを日本語で3行以内に要約してください。元の言語が日本語以外でも必ず日本語で要約してください。\n{text_to_summarize}\n要約："}],
                max_tokens=256,
                temperature=0.3
            )
            content = response.choices[0].message.content
            summary = content.strip() if content else "(要約が取得できませんでした)"
            st.success("要約結果:")
            st.text_area("要約", summary, height=100, key="summary_output")
        except Exception as e:
            st.error(f"要約に失敗しました: {e}")

# --- コマンド辞書・単語辞書管理 ---
# st.header("4. コマンド辞書・単語辞書管理")
# dict_tab = st.tabs(["単語辞書"])
# 
# with dict_tab[0]:
#     st.subheader("単語辞書")
#     WORD_DICT_PATH = os.path.join("settings", 'word_dictionary.json')
#     def load_dict(path):
#         if not os.path.exists(path):
#             return []
#         with open(path, 'r', encoding='utf-8') as f:
#             return json.load(f)
#     def save_dict(path, data):
#         with open(path, 'w', encoding='utf-8') as f:
#             json.dump(data, f, ensure_ascii=False, indent=2)
#     word_dict = load_dict(WORD_DICT_PATH)
#     new_word2 = st.text_input("新しい単語を追加", key="word_add")
#     if st.button("追加", key="word_add_btn") and new_word2:
#         if new_word2 in word_dict:
#             st.warning("既に登録されています")
#         else:
#             word_dict.append(new_word2)
#             save_dict(WORD_DICT_PATH, word_dict)
#             st.success("登録しました")
#     if word_dict:
#         st.write(word_dict)
#     else:
#         st.info("単語辞書は空です")

st.caption("© Tech Mentor Streamlit版") 