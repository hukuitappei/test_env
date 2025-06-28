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

recordButton.addEventListener('click', () => {
    startRecording();
});

stopButton.addEventListener('click', () => {
    stopRecording();
});

// 利用可能なマイク一覧を取得してセレクトボックスに追加
async function populateMicList() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        return;
    }
    const devices = await navigator.mediaDevices.enumerateDevices();
    const audioInputs = devices.filter(device => device.kind === 'audioinput');
    micSelect.innerHTML = '';
    audioInputs.forEach(device => {
        const option = document.createElement('option');
        option.value = device.deviceId;
        option.text = device.label || `マイク${micSelect.length + 1}`;
        micSelect.appendChild(option);
    });
    if (audioInputs.length > 0) {
        selectedDeviceId = audioInputs[0].deviceId;
    }
}

micSelect.addEventListener('change', (e) => {
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

        // 録音セッションの終了をサーバーに通知
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
    }
}

// 音声チャンクをサーバーに送信
async function sendAudioChunk(audioBlob, sessionId, chunkIndex) {
    const formData = new FormData();
    formData.append('audio_chunk', audioBlob, `chunk_${chunkIndex}.webm`);
    formData.append('session_id', sessionId);
    formData.append('chunk_index', chunkIndex);

    try {
        const response = await fetch('/upload_audio_chunk', {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();
        if (!response.ok) {
            displayErrorMessage(`音声チャンクのアップロードに失敗しました: ${data.error}`);
        }
    } catch (error) {
        console.error('Error uploading audio chunk:', error);
        displayErrorMessage('音声チャンクのアップロード中にエラーが発生しました。');
    }
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
        recordButton.disabled = true;
        stopButton.disabled = false;
        recordButton.style.backgroundColor = 'red';
        stopButton.style.backgroundColor = ''; // デフォルトに戻す
    } else {
        recordButton.disabled = false;
        stopButton.disabled = true;
        recordButton.style.backgroundColor = 'green';
        stopButton.style.backgroundColor = '';
    }
}

// エラーメッセージの表示
function displayErrorMessage(message, isError = true) {
    errorMessageDiv.textContent = message;
    errorMessageDiv.style.display = message ? 'block' : 'none';
    errorMessageDiv.style.backgroundColor = isError ? '#dc3545' : '#28a745'; // 赤 (エラー) または緑 (成功)
}

// 設定の読み込みと保存
async function loadSettings() {
    try {
        const response = await fetch('/settings');
        if (response.ok) {
            const data = await response.json();
            settings = data.settings; // Assuming settings are nested under 'settings' key
            autoRecordToggle.checked = settings.autoRecord || false;
            if (autoRecordToggle.checked) {
                startRecording();
            }
        } else if (response.status === 501) {
            // Not Implemented: 初回起動などで設定がない場合、デフォルト値を設定
            settings = { autoRecord: false };
            autoRecordToggle.checked = false;
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
            autoRecord: autoRecordToggle.checked
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

autoRecordToggle.addEventListener('change', saveSettings);

// 過去の文字起こしリストの読み込み
async function loadTranscriptions() {
    try {
        const response = await fetch('/list_transcriptions');
        if (response.ok) {
            const data = await response.json();
            transcriptionListUl.innerHTML = ''; // Clear current list
            if (data.transcriptions && data.transcriptions.length > 0) {
                data.transcriptions.forEach(filename => {
                    const li = document.createElement('li');
                    const link = document.createElement('a');
                    link.href = `javascript:void(0)`; // Prevents page reload
                    link.textContent = filename;
                    link.addEventListener('click', () => displayTranscriptionContent(filename));
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
        displayErrorMessage('文字起こしリストの読み込み中にエラーが発生しました。');
    }
}

// 文字起こしファイルの内容を表示
async function displayTranscriptionContent(filename) {
    try {
        const response = await fetch(`/transcriptions/${filename}`);
        if (response.ok) {
            const textContent = await response.text();
            transcriptionResultDiv.innerHTML = `<h2>${filename}</h2><pre>${textContent}</pre>`;
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