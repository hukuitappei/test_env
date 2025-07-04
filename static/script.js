const recordButton = document.getElementById('recordButton');
const stopButton = document.getElementById('stopButton');
const statusDiv = document.getElementById('status');
const transcriptionResultDiv = document.getElementById('transcriptionResult');
const recordingTimeSpan = document.getElementById('recordingTime');
const audioWaveCanvas = document.getElementById('audioWave');
const autoRecordToggle = document.getElementById('autoRecordToggle');
const transcriptionListUl = document.getElementById('transcriptionList');
const troubleReportForm = document.getElementById('troubleReportForm');
const errorMessageDiv = document.getElementById('errorMessage');
const troubleToggleBtn = document.getElementById('troubleToggleBtn');
const troubleText = document.getElementById('troubleText');
const troubleSendBtn = document.getElementById('troubleSendBtn');
const volumeBar = document.getElementById('volumeBar');
const volumeWarning = document.getElementById('volumeWarning');

const canvasContext = audioWaveCanvas.getContext('2d');

let mediaRecorder;
let audioChunks = [];
let recordingInterval;
let session_id = null; // ユニークなセッションID
let chunk_index = 0; // 各セッションでのチャンク番号
let recordingStartTime;
let recordingTimer;
let audioContext; // for audio visualization
let analyser; // for audio visualization
let dataArray; // for audio visualization
let source; // for audio visualization
let animationFrameId; // for audio visualization
let lowVolumeStart = null;
const LOW_VOLUME_THRESHOLD = 0.08; // 0~1の範囲で調整
const LOW_VOLUME_DURATION = 1000; // ms

const MAX_RECORDING_CHUNK_DURATION = 300 * 1000; // 5分 = 300秒 = 300,000ミリ秒

// Socket.IO クライアントを初期化
const socket = io();

// マイク選択用のセレクトボックスを取得
const micSelect = document.getElementById('micSelect');
let selectedDeviceId = null;

let pendingUploads = 0;

socket.on('connect', () => {
    console.log('Connected to Socket.IO');
    statusDiv.textContent = '準備完了';
    loadSettings(); // 設定を読み込む
    loadTranscriptions(); // 過去のメモを読み込む
});

socket.on('disconnect', () => {
    console.log('Disconnected from Socket.IO');
    statusDiv.textContent = '接続切れ';
    displayErrorMessage('サーバーとの接続が切れました。ページをリロードしてください。');
});

socket.on('transcription_status', (data) => {
    if (data.status === 'processing_chunk') {
        statusDiv.textContent = `文字起こし中 (チャンク ${data.chunk_index})...`;
    } else if (data.status === 'chunk_completed') {
        statusDiv.textContent = `文字起こし完了 (チャンク ${data.chunk_index}).`;
        // 各チャンクの文字起こし結果をリアルタイム表示（結合前のもの）
        const p = document.createElement('p');
        p.textContent = `チャンク ${data.chunk_index}: ${data.text}`;
        transcriptionResultDiv.appendChild(p);
        transcriptionResultDiv.scrollTop = transcriptionResultDiv.scrollHeight; // スクロール
    } else if (data.status === 'chunk_failed') {
        statusDiv.textContent = `文字起こし失敗 (チャンク ${data.chunk_index}).`;
        displayErrorMessage(`文字起こしに失敗しました (チャンク ${data.chunk_index})。`);
    } else if (data.status === 'combining_results') {
        statusDiv.textContent = '文字起こし結果を結合中...';
    } else if (data.status === 'final_completed') {
        statusDiv.textContent = `最終文字起こし完了: ${data.final_filename}`;
        displayErrorMessage('最終文字起こしが完了し、ファイルが保存されました！', false);
        loadTranscriptions(); // 新しい文字起こしが完了したらリストを更新
    } else if (data.status === 'final_failed') {
        statusDiv.textContent = '最終文字起こし失敗。';
        displayErrorMessage(`最終文字起こしに失敗しました: ${data.error || '不明なエラー'}。`);
    }
});

if (recordButton) recordButton.addEventListener('click', () => {
    startRecording();
});

if (stopButton) stopButton.addEventListener('click', () => {
    stopRecording();
});

// 利用可能なマイク一覧を取得してセレクトボックスに追加
async function populateMicList() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        return;
    }
    const devices = await navigator.mediaDevices.enumerateDevices();
    const audioInputs = devices.filter(device => device.kind === 'audioinput');
    if (micSelect) micSelect.innerHTML = '';
    audioInputs.forEach(device => {
        const option = document.createElement('option');
        option.value = device.deviceId;
        option.text = device.label || `マイク${micSelect.length + 1}`;
        if (micSelect) micSelect.appendChild(option);
    });
    if (audioInputs.length > 0) {
        selectedDeviceId = audioInputs[0].deviceId;
    }
}

if (micSelect) micSelect.addEventListener('change', (e) => {
    selectedDeviceId = e.target.value;
});

// 録音開始
async function startRecording() {
    try {
        // 選択されたマイクで録音
        const constraints = selectedDeviceId ? { audio: { deviceId: { exact: selectedDeviceId } } } : { audio: true };
        const stream = await navigator.mediaDevices.getUserMedia(constraints);

        // 新しい録音セッションを開始
        session_id = uuidv4();
        chunk_index = 0;
        audioChunks = []; // Clear for new session
        transcriptionResultDiv.innerHTML = ''; // Clear previous results

        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm; codecs=opus' });

        mediaRecorder.ondataavailable = event => {
            audioChunks.push(event.data);
            if (event.data.size > 0) {
                // チャンクデータをサーバーに送信
                const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
                sendAudioChunk(audioBlob, session_id, chunk_index);
                audioChunks = []; // 送信後クリア
                chunk_index++;
            }
        };

        mediaRecorder.onstop = () => {
            console.log('Recording stopped.');
            // ストリームを停止してマイクを解放
            stream.getTracks().forEach(track => track.stop());
            stopRecordingTimer();
            stopAudioWave();
            updateButtonStates(false); // 停止時のボタン状態に更新
        };

        // 5分ごとに ondataavailable イベントをトリガー
        mediaRecorder.start(MAX_RECORDING_CHUNK_DURATION); // 5分ごとにデータを取得

        startRecordingTimer();
        startAudioWave(stream);
        updateButtonStates(true); // 録音開始時のボタン状態に更新
        statusDiv.textContent = '録音中...';
        displayErrorMessage('', false); // エラーメッセージをクリア

    } catch (error) {
        console.error('Error accessing microphone:', error);
        displayErrorMessage('マイクが見つかりません。マイクへのアクセスを許可してください。');
        statusDiv.textContent = 'エラー';
    }
}

// 録音停止
function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        statusDiv.textContent = 'アップロード中...';
        // アップロード完了を待ってからファイナライズ
        waitForAllUploadsThenFinalize();
    }
}

// 音声チャンクをサーバーに送信
async function sendAudioChunk(audioBlob, sessionId, chunkIndex) {
    pendingUploads++;
    const formData = new FormData();
    formData.append('audio_chunk', audioBlob, `chunk_${chunkIndex}.webm`);
    formData.append('session_id', sessionId);
    formData.append('chunk_index', chunkIndex);
    try {
        const response = await fetch('/upload_audio_chunk', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!response.ok) {
            displayErrorMessage(`音声チャンクのアップロードに失敗しました: ${data.error}`);
        }
    } catch (error) {
        console.error('Error uploading audio chunk:', error);
        displayErrorMessage('音声チャンクのアップロード中にエラーが発生しました。');
    } finally {
        pendingUploads--;
    }
}

function waitForAllUploadsThenFinalize() {
    const check = () => {
        if (pendingUploads === 0) {
            fetch('/finalize_recording', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ session_id: session_id }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    statusDiv.textContent = data.error;
                } else {
                    statusDiv.textContent = '記録完了!';
                }
            })
            .catch(error => {
                console.error('Error finalizing recording:', error);
                displayErrorMessage('録音終了処理中にエラーが発生しました。');
            });
        } else {
            setTimeout(check, 200);
        }
    };
    check();
}

// UUID v4 を生成するシンプルな関数
function uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// 録音時間の更新
function startRecordingTimer() {
    recordingStartTime = Date.now();
    recordingTimer = setInterval(() => {
        const elapsedTime = Date.now() - recordingStartTime;
        const minutes = Math.floor(elapsedTime / 60000);
        const seconds = Math.floor((elapsedTime % 60000) / 1000);
        recordingTimeSpan.textContent = 
            `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }, 1000);
}

function stopRecordingTimer() {
    clearInterval(recordingTimer);
    recordingTimeSpan.textContent = '00:00';
}

// 音声波形表示
function startAudioWave(stream) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);
    analyser.fftSize = 2048;
    dataArray = new Uint8Array(analyser.frequencyBinCount);

    canvasContext.clearRect(0, 0, audioWaveCanvas.width, audioWaveCanvas.height);
    draw();
}

function draw() {
    animationFrameId = requestAnimationFrame(draw);

    analyser.getByteTimeDomainData(dataArray);

    // 音量計算（RMS）
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
        const v = (dataArray[i] - 128) / 128.0;
        sum += v * v;
    }
    const rms = Math.sqrt(sum / dataArray.length);

    // 音量バーの幅・色を更新
    if (volumeBar) {
        const percent = Math.min(1, rms * 2); // 0~1
        volumeBar.style.width = (percent * 100) + '%';
        if (percent < 0.2) {
            volumeBar.style.background = '#ff5555';
        } else if (percent < 0.5) {
            volumeBar.style.background = '#ffd700';
        } else {
            volumeBar.style.background = '#61afef';
        }
    }

    // 音量が小さい場合の警告
    if (rms < LOW_VOLUME_THRESHOLD) {
        if (!lowVolumeStart) lowVolumeStart = Date.now();
        if (Date.now() - lowVolumeStart > LOW_VOLUME_DURATION) {
            if (volumeWarning) volumeWarning.style.display = 'block';
        }
    } else {
        lowVolumeStart = null;
        if (volumeWarning) volumeWarning.style.display = 'none';
    }

    // 既存の波形描画
    canvasContext.fillStyle = 'rgb(40, 44, 52)';
    canvasContext.fillRect(0, 0, audioWaveCanvas.width, audioWaveCanvas.height);
    canvasContext.lineWidth = 2;
    canvasContext.strokeStyle = 'rgb(255, 0, 0)';
    canvasContext.beginPath();
    const sliceWidth = audioWaveCanvas.width * 1.0 / dataArray.length;
    let x = 0;
    for(let i = 0; i < dataArray.length; i++) {
        const v = dataArray[i] / 128.0;
        const y = v * audioWaveCanvas.height / 2;
        if(i === 0) {
            canvasContext.moveTo(x, y);
        } else {
            canvasContext.lineTo(x, y);
        }
        x += sliceWidth;
    }
    canvasContext.lineTo(audioWaveCanvas.width, audioWaveCanvas.height/2);
    canvasContext.stroke();
}

function stopAudioWave() {
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
    }
    if (audioContext) {
        audioContext.close();
        audioContext = null;
        analyser = null;
        source = null;
    }
    canvasContext.clearRect(0, 0, audioWaveCanvas.width, audioWaveCanvas.height);
}

// ボタンの状態を更新
function updateButtonStates(isRecording) {
    if (isRecording) {
        if (recordButton) recordButton.disabled = true;
        if (stopButton) stopButton.disabled = false;
        if (recordButton) recordButton.style.backgroundColor = 'red';
        if (stopButton) stopButton.style.backgroundColor = ''; // デフォルトに戻す
    } else {
        if (recordButton) recordButton.disabled = false;
        if (stopButton) stopButton.disabled = true;
        if (recordButton) recordButton.style.backgroundColor = 'green';
        if (stopButton) stopButton.style.backgroundColor = '';
    }
}

// エラーメッセージの表示
function displayErrorMessage(message, isError = true) {
    if (errorMessageDiv) errorMessageDiv.textContent = message;
    if (errorMessageDiv) errorMessageDiv.style.display = message ? 'block' : 'none';
    if (errorMessageDiv) errorMessageDiv.style.backgroundColor = isError ? '#dc3545' : '#28a745'; // 赤 (エラー) または緑 (成功)
}

// 設定の読み込みと保存
async function loadSettings() {
    try {
        const response = await fetch('/settings');
        if (response.ok) {
            const data = await response.json();
            settings = data.settings; // Assuming settings are nested under 'settings' key
            if (autoRecordToggle) {
                autoRecordToggle.checked = settings.autoRecord || false;
                if (autoRecordToggle.checked) {
                    startRecording();
                }
            }
        } else if (response.status === 501) {
            // Not Implemented: 初回起動などで設定がない場合、デフォルト値を設定
            settings = { autoRecord: false };
            if (autoRecordToggle) autoRecordToggle.checked = false;
        } else {
            displayErrorMessage(`設定の読み込みに失敗しました: ${response.statusText}`);
        }
    } catch (error) {
        console.error('Error loading settings:', error);
        displayErrorMessage('設定の読み込み中にエラーが発生しました。');
    }
}

async function saveSettings() {
    try {
        const newSettings = {
            autoRecord: autoRecordToggle ? autoRecordToggle.checked : false
        };
        const response = await fetch('/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(newSettings),
        });
        if (!response.ok) {
            const errorData = await response.json();
            displayErrorMessage(`設定の保存に失敗しました: ${errorData.message}`);
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        displayErrorMessage('設定の保存中にエラーが発生しました。');
    }
}

if (autoRecordToggle) autoRecordToggle.addEventListener('change', saveSettings);

// 過去の文字起こしリストの読み込み
async function loadTranscriptions() {
    try {
        const response = await fetch('/list_transcriptions');
        if (response.ok) {
            const data = await response.json();
            transcriptionListUl.innerHTML = '';
            if (data.transcriptions && data.transcriptions.length > 0) {
                data.transcriptions.forEach(path => {
                    const li = document.createElement('li');
                    const link = document.createElement('a');
                    link.href = 'javascript:void(0)';
                    // パスからファイル名のみ抽出
                    const parts = path.split(/[/\\]/);
                    const filename = parts[parts.length - 1];
                    let displayName = filename;
                    // 1. 結合済みファイル: YYYYMMDD_HHMMSS_タグ.txt → YYYY-MM-DD_タグ.txt
                    const matchCombined = filename.match(/(\d{8})_(\d{6})_(.+)\.txt$/);
                    if (matchCombined) {
                        const y = matchCombined[1].slice(0,4);
                        const m = matchCombined[1].slice(4,6);
                        const d = matchCombined[1].slice(6,8);
                        const tag = matchCombined[3];
                        displayName = `${y}-${m}-${d}_${tag}.txt`;
                    } else {
                        // 2. チャンクファイル: sessionid_chunkN.txt → 日付_無題.txt（sessionidの先頭8桁を日付と仮定、なければ"無題"）
                        const matchChunk = filename.match(/([a-zA-Z0-9\-]{8,})_chunk\d+\.txt$/);
                        if (matchChunk) {
                            // sessionidの先頭8桁を日付に見立てる（なければ"無題"）
                            const sessionId = matchChunk[1];
                            let y = '----', m = '--', d = '--';
                            if (/\d{8}/.test(sessionId.slice(0,8))) {
                                y = sessionId.slice(0,4);
                                m = sessionId.slice(4,6);
                                d = sessionId.slice(6,8);
                            }
                            displayName = `${y}-${m}-${d}_無題.txt`;
                        }
                    }
                    link.textContent = displayName;
                    link.addEventListener('click', () => displayTranscriptionContent(path));
                    li.appendChild(link);
                    transcriptionListUl.appendChild(li);
                });
            } else {
                const li = document.createElement('li');
                li.textContent = '過去のメモはありません。';
                transcriptionListUl.appendChild(li);
            }
        } else {
            displayErrorMessage(`文字起こしリストの取得に失敗しました: ${response.statusText}`);
        }
    } catch (error) {
        console.error('Error loading transcriptions:', error);
        displayErrorMessage('過去のメモ一覧の取得中にエラーが発生しました。');
    }
}

// 文字起こしファイルの内容を表示＋要約
async function displayTranscriptionContent(filename) {
    try {
        const response = await fetch(`/transcriptions/${filename}`);
        if (response.ok) {
            const textContent = await response.text();
            transcriptionResultDiv.innerHTML = `<h2>${filename}</h2><pre>${textContent}</pre>`;
            // 要約API呼び出し
            const summaryDiv = document.getElementById('audioSummary');
            if (summaryDiv) {
                summaryDiv.textContent = '要約生成中...';
                try {
                    const res = await fetch('/summarize', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: textContent })
                    });
                    if (res.ok) {
                        const data = await res.json();
                        summaryDiv.textContent = data.summary || '要約がありません';
                    } else {
                        summaryDiv.textContent = '要約生成に失敗しました';
                    }
                } catch (e) {
                    summaryDiv.textContent = '要約生成中にエラーが発生しました';
                }
            }
        } else {
            displayErrorMessage(`ファイルの読み込みに失敗しました: ${response.statusText}`);
        }
    } catch (error) {
        console.error('Error displaying transcription content:', error);
        displayErrorMessage('文字起こし内容の表示中にエラーが発生しました。');
    }
}

// トラブル報告フォームの送信
if (troubleToggleBtn && troubleReportForm) {
    troubleToggleBtn.addEventListener('click', () => {
        if (troubleReportForm.style.display === 'none' || troubleReportForm.style.display === '') {
            troubleReportForm.style.display = 'block';
            troubleText.value = '';
        } else {
            troubleReportForm.style.display = 'none';
        }
    });
}

if (troubleSendBtn) {
    troubleSendBtn.addEventListener('click', async () => {
        const text = troubleText.value.trim();
        if (!text) {
            alert('内容を入力してください');
            return;
        }
        try {
            const res = await fetch('/log_trouble', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            if (res.ok) {
                alert('トラブル報告を送信しました');
                troubleReportForm.style.display = 'none';
            } else {
                alert('送信に失敗しました');
            }
        } catch (e) {
            alert('送信中にエラーが発生しました');
        }
    });
}

// 初期化時に設定と文字起こしリストを読み込む
document.addEventListener('DOMContentLoaded', () => {
    populateMicList();
    // socket.on('connect') で loadSettings と loadTranscriptions を呼んでいるので、ここでは不要
    updateButtonStates(false); // 初期状態では停止ボタンを無効化
});

// ユーザー辞書モーダルの制御
const openDictBtn = document.getElementById('open-dictionary-btn');
const closeDictBtn = document.getElementById('close-dictionary-btn');
const dictModal = document.getElementById('dictionary-modal');
const wordList = document.getElementById('word-dictionary-list');
const commandList = document.getElementById('command-dictionary-list');
const addWordInput = document.getElementById('add-word-input');
const addWordBtn = document.getElementById('add-word-btn');
const addCommandInput = document.getElementById('add-command-input');
const addCommandBtn = document.getElementById('add-command-btn');

function showDictionaryModal() {
  dictModal.style.display = 'block';
  loadWordDictionary();
  loadCommandDictionary();
}
function hideDictionaryModal() {
  dictModal.style.display = 'none';
}
if (openDictBtn) openDictBtn.onclick = showDictionaryModal;
if (closeDictBtn) closeDictBtn.onclick = hideDictionaryModal;

// 単語辞書取得・表示
function loadWordDictionary() {
  fetch('/api/word_dictionary').then(r=>r.json()).then(list => {
    wordList.innerHTML = '';
    list.forEach(word => {
      const li = document.createElement('li');
      li.textContent = word;
      const delBtn = document.createElement('button');
      delBtn.textContent = '削除';
      delBtn.onclick = () => deleteWord(word);
      li.appendChild(delBtn);
      wordList.appendChild(li);
    });
  });
}
function addWord() {
  const word = addWordInput.value.trim();
  if (!word) return;
  fetch('/api/word_dictionary', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({word})
  }).then(()=>{addWordInput.value='';loadWordDictionary();});
}
function deleteWord(word) {
  fetch('/api/word_dictionary', {
    method: 'DELETE',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({word})
  }).then(loadWordDictionary);
}
if (addWordBtn) addWordBtn.onclick = addWord;

// コマンド辞書取得・表示
function loadCommandDictionary() {
  fetch('/api/command_dictionary').then(r=>r.json()).then(list => {
    commandList.innerHTML = '';
    list.forEach(word => {
      const li = document.createElement('li');
      li.textContent = word;
      const delBtn = document.createElement('button');
      delBtn.textContent = '削除';
      delBtn.onclick = () => deleteCommand(word);
      li.appendChild(delBtn);
      commandList.appendChild(li);
    });
  });
}
function addCommand() {
  const word = addCommandInput.value.trim();
  if (!word) return;
  fetch('/api/command_dictionary', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({word})
  }).then(()=>{addCommandInput.value='';loadCommandDictionary();});
}
function deleteCommand(word) {
  fetch('/api/command_dictionary', {
    method: 'DELETE',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({word})
  }).then(loadCommandDictionary);
}
if (addCommandBtn) addCommandBtn.onclick = addCommand;

// トークン利用履歴の表示UI（web上に直接表示する部分）は削除
// renderTokenUsage, loadTokenUsage, window.addEventListener('DOMContentLoaded', loadTokenUsage) などを削除
// 設定モーダル内のrenderTokenUsageInのみ残す
// 設定モーダルUI・タブ切り替え
const settingsGearBtn = document.getElementById('settings-gear-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsModalBtn = document.getElementById('close-settings-modal');
const settingsContent = document.getElementById('settings-content');

function showSettingsModal() {
    settingsModal.style.display = 'block';
    renderSettingsTabs();
}
function hideSettingsModal() {
    settingsModal.style.display = 'none';
}
if (settingsGearBtn) settingsGearBtn.addEventListener('click', showSettingsModal);
if (closeSettingsModalBtn) closeSettingsModalBtn.addEventListener('click', hideSettingsModal);

function renderSettingsTabs() {
    settingsContent.innerHTML = `
        <div style="display:flex;gap:8px;margin-bottom:16px;">
            <button class="settings-tab-btn" data-tab="startup">起動設定</button>
            <button class="settings-tab-btn" data-tab="mic">マイク設定</button>
            <button class="settings-tab-btn" data-tab="shortcut">ショートカット</button>
            <button class="settings-tab-btn" data-tab="token">トークン履歴</button>
            <button class="settings-tab-btn" data-tab="dictionary">ユーザー辞書</button>
        </div>
        <div id="settings-tab-content"></div>
    `;
    const tabBtns = settingsContent.querySelectorAll('.settings-tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderSettingsTabContent(btn.dataset.tab);
        });
    });
    // デフォルトで起動設定タブ
    tabBtns[0].click();
}

function renderSettingsTabContent(tab) {
    const tabContent = document.getElementById('settings-tab-content');
    tabContent.innerHTML = '';
    if (tab === 'startup') {
        tabContent.innerHTML = `
            <div class="settings-section">
                <label for="autoRecordToggle">
                    <input type="checkbox" id="autoRecordToggle">
                    起動時に自動で記録を開始
                </label>
                <p>音声ファイルの分割長さ: 5分</p>
            </div>
        `;
        // 既存の設定値を反映
        const autoRecordToggle = tabContent.querySelector('#autoRecordToggle');
        if (autoRecordToggle) {
            if (localStorage.getItem('autoRecord') === 'true') autoRecordToggle.checked = true;
            autoRecordToggle.addEventListener('change', () => {
                localStorage.setItem('autoRecord', autoRecordToggle.checked ? 'true' : 'false');
            });
        }
    } else if (tab === 'mic') {
        // マイク設定
        renderMicSettings(tabContent);
    } else if (tab === 'shortcut') {
        // ショートカット設定
        const section = document.createElement('div');
        section.className = 'settings-section';
        tabContent.appendChild(section);
        // 既存のrenderShortcutSettingsをsection内に描画
        renderShortcutSettings(section);
    } else if (tab === 'token') {
        // トークン履歴
        const section = document.createElement('div');
        section.className = 'settings-section';
        tabContent.appendChild(section);
        renderTokenUsageIn(section);
    } else if (tab === 'dictionary') {
        // ユーザー辞書
        const section = document.createElement('div');
        section.className = 'settings-section';
        tabContent.appendChild(section);
        renderDictionarySection(section);
    }
}

// renderShortcutSettingsをモーダル用に拡張
function renderShortcutSettings(parent) {
    if (!parent) return; // parentがundefined/nullなら何もしない
    parent.innerHTML = `<h3>ショートカットキー設定</h3>
        <table class="dict-table" style="width:100%;margin-top:10px;">
            <thead><tr><th>操作</th><th>ショートカット</th><th>変更</th></tr></thead>
            <tbody id="shortcutSettingsTbody"></tbody>
        </table>`;
    const tbody = parent.querySelector('#shortcutSettingsTbody');
    tbody.innerHTML = '';
    const actions = [
        { key: 'startRecording', label: '録音開始' },
        { key: 'stopRecording', label: '録音停止' },
        { key: 'openDictionary', label: 'ユーザー辞書表示' },
        { key: 'summarize', label: '要約実行' },
    ];
    actions.forEach(act => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${act.label}</td><td><span>${shortcutToDisplay(shortcuts[act.key])}</span></td><td><button>変更</button></td>`;
        const btn = tr.querySelector('button');
        btn.addEventListener('click', () => {
            btn.textContent = 'キー入力待ち...';
            const onKey = (e) => {
                e.preventDefault();
                let combo = '';
                if (e.ctrlKey) combo += 'Ctrl+';
                if (e.altKey) combo += 'Alt+';
                if (e.shiftKey) combo += 'Shift+';
                combo += e.key.length === 1 ? e.key.toUpperCase() : e.key;
                shortcuts[act.key] = combo;
                saveShortcuts(shortcuts);
                renderShortcutSettings(parent);
                document.removeEventListener('keydown', onKey, true);
            };
            document.addEventListener('keydown', onKey, true);
        });
        tbody.appendChild(tr);
    });
}

// トークン履歴をモーダル用に描画
function renderTokenUsageIn(parent) {
    parent.innerHTML = `<h3>トークン利用履歴</h3>
        <div id="tokenUsageSummary"></div>
        <table id="tokenUsageTable" class="dict-table" style="width:100%;margin-top:10px;">
            <thead><tr><th>日時</th><th>モデル</th><th>入力</th><th>出力</th><th>合計</th><th>コスト($)</th></tr></thead>
            <tbody></tbody>
        </table>`;
    fetch('/api/token_usage').then(res => res.json()).then(usageData => {
        const summaryDiv = parent.querySelector('#tokenUsageSummary');
        summaryDiv.textContent = `合計トークン: ${usageData.total_tokens} / 合計コスト: $${usageData.total_cost.toFixed(4)}`;
        const tbody = parent.querySelector('#tokenUsageTable tbody');
        tbody.innerHTML = '';
        (usageData.usage || []).slice().reverse().forEach(u => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${u.timestamp}</td><td>${u.model}</td><td>${u.prompt_tokens}</td><td>${u.completion_tokens}</td><td>${u.total_tokens}</td><td>${u.cost.toFixed(4)}</td>`;
            tbody.appendChild(tr);
        });
    });
}

// ユーザー辞書をモーダル用に描画（簡易版）
function renderDictionarySection(parent) {
    parent.innerHTML = `<h3>ユーザー辞書</h3><p>ユーザー辞書の管理は今後ここに統合予定です。</p>`;
    // 必要に応じて既存の辞書UIをここに移植
}

// マイク設定タブの実装
function renderMicSettings(parent) {
    parent.innerHTML = `
        <div class="settings-section">
            <label for="micSelect">マイク選択：</label>
            <select id="micSelect" style="max-width:220px;margin-right:10px;"></select>
            <button id="micTestBtn">テスト</button>
            <div id="micTestResult" style="margin-top:12px;"></div>
        </div>
    `;
    const micSelect = parent.querySelector('#micSelect');
    const micTestBtn = parent.querySelector('#micTestBtn');
    const micTestResult = parent.querySelector('#micTestResult');
    // マイク一覧取得
    navigator.mediaDevices.enumerateDevices().then(devices => {
        micSelect.innerHTML = '';
        devices.filter(d => d.kind === 'audioinput').forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.deviceId;
            opt.textContent = d.label || `マイク${micSelect.length+1}`;
            micSelect.appendChild(opt);
        });
        // 保存済み選択肢
        const savedId = localStorage.getItem('selectedMicId');
        if (savedId) micSelect.value = savedId;
    });
    micSelect.addEventListener('change', () => {
        localStorage.setItem('selectedMicId', micSelect.value);
    });
    // テスト機能
    let testStream = null;
    let testAudioContext = null;
    let testAnalyser = null;
    let testAnimationId = null;
    micTestBtn.addEventListener('click', async () => {
        if (testStream) {
            // テスト終了
            testStream.getTracks().forEach(track => track.stop());
            if (testAudioContext) testAudioContext.close();
            cancelAnimationFrame(testAnimationId);
            testStream = null;
            micTestBtn.textContent = 'テスト';
            micTestResult.innerHTML = '';
            return;
        }
        // テスト開始
        try {
            testStream = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: micSelect.value ? { exact: micSelect.value } : undefined } });
            testAudioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = testAudioContext.createMediaStreamSource(testStream);
            testAnalyser = testAudioContext.createAnalyser();
            source.connect(testAnalyser);
            const dataArray = new Uint8Array(testAnalyser.fftSize);
            micTestResult.innerHTML = '<canvas id="micTestCanvas" width="220" height="40" style="background:#333;border-radius:6px;"></canvas>';
            const canvas = micTestResult.querySelector('#micTestCanvas');
            const ctx = canvas.getContext('2d');
            function draw() {
                testAnalyser.getByteTimeDomainData(dataArray);
                ctx.clearRect(0,0,canvas.width,canvas.height);
                // 波形描画
                ctx.beginPath();
                for (let i=0; i<canvas.width; i++) {
                    const v = dataArray[Math.floor(i/dataArray.length*dataArray.length)]/128.0;
                    const y = v*20;
                    if (i===0) ctx.moveTo(i,20+y);
                    else ctx.lineTo(i,20+y);
                }
                ctx.strokeStyle = '#61afef';
                ctx.lineWidth = 2;
                ctx.stroke();
                testAnimationId = requestAnimationFrame(draw);
            }
            draw();
            micTestBtn.textContent = 'テスト終了';
        } catch(e) {
            micTestResult.textContent = 'マイクテストに失敗しました';
            testStream = null;
        }
    });
} 