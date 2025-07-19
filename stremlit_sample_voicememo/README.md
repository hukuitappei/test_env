# PyAudio音声録音アプリ（WebSocket版）

Streamlit + PyAudio + WebSocketを使用した音声録音・保存アプリケーションです。

## 特徴

- **PyAudio使用**: ブラウザのWebRTCではなく、サーバー側のPyAudioで録音
- **WebSocket通信**: リアルタイムでサーバーと通信
- **ファイル保存**: 録音データをWAVファイルとして保存
- **Streamlit UI**: 使いやすいWebインターフェース
- **ワンクリック起動**: 1つのコマンドで両方のサーバーを同時起動

## 必要なライブラリ

```bash
pip install -r requirements.txt
```

### 主要ライブラリ
- `streamlit`: Webアプリフレームワーク
- `pyaudio`: 音声録音・再生
- `websockets`: WebSocket通信
- `numpy`: 数値計算
- `wave`: WAVファイル操作

## 使用方法

### 🚀 簡単起動（推奨）

#### Windows
```bash
# バッチファイルをダブルクリック、または
start_app.bat
```

#### Linux/Mac
```bash
# 実行権限を付与
chmod +x start_app.sh

# スクリプトを実行
./start_app.sh
```

#### Python直接実行
```bash
python run_app.py
```

### 🔧 手動起動（従来方式）

#### 1. WebSocketサーバー起動

```bash
# 方法1: 直接起動
python audio_server.py

# 方法2: 起動スクリプト使用
python start_server.py
```

サーバーが起動すると、以下のメッセージが表示されます：
```
WebSocketサーバーがポート8765で起動しました
```

#### 2. Streamlitアプリ起動

別のターミナルで以下を実行：

```bash
streamlit run minimal_audio_recorder.py
```

### 3. アプリ使用手順

1. **サーバー接続**: 「サーバー接続」ボタンを押す
2. **録音開始**: 「録音開始」ボタンを押す
3. **録音停止**: 「録音停止」ボタンを押す
4. **ファイル確認**: 保存された音声ファイルが表示される

## ファイル構成

```
stremlit_sample_voicememo/
├── run_app.py              # 統合起動スクリプト（新規）
├── start_app.bat           # Windows起動スクリプト（新規）
├── start_app.sh            # Linux/Mac起動スクリプト（新規）
├── minimal_audio_recorder.py  # Streamlitアプリ（メイン）
├── audio_server.py         # WebSocketサーバー（PyAudio使用）
├── start_server.py         # サーバー起動スクリプト
├── requirements.txt        # 必要なライブラリ
├── README.md              # このファイル
└── audio_chunks/          # 録音ファイル保存先（自動作成）
```

## 技術詳細

### WebSocket通信

- **ポート**: 8765
- **プロトコル**: WebSocket
- **メッセージ形式**: JSON

#### コマンド一覧

| コマンド | 説明 | レスポンス |
|---------|------|-----------|
| `start_recording` | 録音開始 | 成功/エラーメッセージ |
| `stop_recording` | 録音停止 | ファイルパス、フレーム数 |
| `get_status` | 現在の状態取得 | 録音状態、フレーム数 |

### 音声設定

- **フォーマット**: 16bit PCM
- **チャンネル**: モノラル（1チャンネル）
- **サンプリングレート**: 44.1kHz
- **チャンクサイズ**: 1024サンプル

## トラブルシューティング

### よくある問題

1. **PyAudioインストールエラー**
   ```bash
   # Windows
   pip install pipwin
   pipwin install pyaudio
   
   # macOS
   brew install portaudio
   pip install pyaudio
   
   # Linux
   sudo apt-get install portaudio19-dev
   pip install pyaudio
   ```

2. **WebSocket接続エラー**
   - サーバーが起動しているか確認
   - ポート8765が使用可能か確認
   - ファイアウォール設定を確認

3. **録音ができない**
   - マイクが接続されているか確認
   - マイクの権限設定を確認
   - 他のアプリがマイクを使用していないか確認

4. **同時起動でエラーが発生**
   - ポート8501（Streamlit）や8765（WebSocket）が既に使用されている可能性
   - 既存のプロセスを終了してから再実行

### デバッグ

- Streamlitアプリの「デバッグ情報」セクションで状態を確認
- 「状態確認」ボタンでサーバーの詳細情報を取得
- サーバー側のコンソールログも確認

## 拡張機能

### 文字起こし機能の追加

```python
# minimal_audio_recorder.pyに追加
if st.button("文字起こし実行"):
    if st.session_state["audio_path"]:
        # Whisperを使用した文字起こし
        model = whisper.load_model("base")
        result = model.transcribe(st.session_state["audio_path"])
        st.write("文字起こし結果:", result["text"])
```

### リアルタイム録音

現在は録音停止時にファイル保存ですが、リアルタイムでストリーミングすることも可能です。

## ライセンス

MIT License 