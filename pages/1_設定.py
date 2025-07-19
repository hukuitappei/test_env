import streamlit as st
import pyaudio
import os
import json
from datetime import datetime
import sys

# エラーハンドリングモジュールをインポート
try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
    from error_handler import PyAudioErrorHandler, DeviceTester, check_windows_microphone_permissions, get_audio_device_diagnostics
    ERROR_HANDLER_AVAILABLE = True
except ImportError:
    # エラーハンドリングモジュールがない場合のフォールバック
    ERROR_HANDLER_AVAILABLE = False
    
    class PyAudioErrorHandler:
        @staticmethod
        def get_error_description(error_msg):
            return f"エラー: {error_msg}"
        
        @staticmethod
        def get_solution_suggestions(error_msg):
            return ["デバイスを再接続してください", "アプリを再起動してください"]
    
    class DeviceTester:
        def __init__(self, settings):
            self.settings = settings
            self.p = None
        
        def __enter__(self):
            self.p = pyaudio.PyAudio()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.p:
                self.p.terminate()
        
        def test_device_access(self, device_index, retry_count=3):
            return False, "エラーハンドリングモジュールが利用できません", []
    
    def check_windows_microphone_permissions():
        return {'microphone_enabled': False, 'details': ['権限確認が利用できません']}
    
    def get_audio_device_diagnostics():
        return {'total_devices': 0, 'errors': ['診断機能が利用できません']}

st.set_page_config(page_title="設定", page_icon="⚙️", layout="wide")
st.title("⚙️ 設定")

# エラーハンドリングモジュールの状態表示
if not ERROR_HANDLER_AVAILABLE:
    st.warning("⚠️ エラーハンドリングモジュールが利用できません。基本的な機能のみ利用可能です。")

# 設定ファイルのパス
SETTINGS_FILE = "settings/app_settings.json"

# 設定ディレクトリの作成
os.makedirs("settings", exist_ok=True)

# デフォルト設定
DEFAULT_SETTINGS = {
    "audio": {
        "chunk_size": 1024,
        "format": "paInt16",
        "channels": 1,
        "sample_rate": 44100,
        "gain": 2.0,
        "duration": 5
    },
    "whisper": {
        "model_size": "base",
        "language": "ja",
        "temperature": 0.0,
        "compression_ratio_threshold": 2.4,
        "logprob_threshold": -1.0,
        "no_speech_threshold": 0.6,
        "condition_on_previous_text": True,
        "initial_prompt": "これは日本語の音声です。"
    },
    "device": {
        "selected_device_index": None,
        "selected_device_name": None,
        "auto_select_default": True,
        "test_device_on_select": True
    },
    "ui": {
        "show_advanced_options": False,
        "auto_save_recordings": True,
        "show_quality_analysis": True,
        "show_level_monitoring": True
    },
    "troubleshooting": {
        "retry_count": 3,
        "timeout_seconds": 10,
        "enable_error_recovery": True,
        "log_errors": True
    }
}

def load_settings():
    """設定を読み込み"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # 新しい設定項目を追加
                for category, default_values in DEFAULT_SETTINGS.items():
                    if category not in settings:
                        settings[category] = default_values
                    else:
                        for key, default_value in default_values.items():
                            if key not in settings[category]:
                                settings[category][key] = default_value
                return settings
        else:
            return DEFAULT_SETTINGS.copy()
    except Exception as e:
        st.error(f"設定読み込みエラー: {e}")
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """設定を保存"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        st.success("設定を保存しました")
        return True
    except Exception as e:
        st.error(f"設定保存エラー: {e}")
        return False

def get_microphone_devices():
    """利用可能なマイクデバイスを取得"""
    p = pyaudio.PyAudio()
    devices = []
    
    try:
        for i in range(p.get_device_count()):
            try:
                device_info = p.get_device_info_by_index(i)
                if int(device_info['maxInputChannels']) > 0:
                    devices.append({
                        'index': i,
                        'name': device_info['name'],
                        'channels': int(device_info['maxInputChannels']),
                        'sample_rate': int(device_info['defaultSampleRate']),
                        'host_api': device_info['hostApi'],
                        'is_default': device_info['name'] == p.get_default_input_device_info()['name']
                    })
            except Exception as e:
                st.warning(f"デバイス {i} の情報取得エラー: {e}")
    except Exception as e:
        st.error(f"デバイス情報取得エラー: {e}")
    finally:
        p.terminate()
    
    return devices

def test_device_access(device_index, settings):
    """デバイスへのアクセステスト（エラーハンドリング強化）"""
    if ERROR_HANDLER_AVAILABLE:
        with DeviceTester(settings) as tester:
            return tester.test_device_access(device_index, settings['troubleshooting']['retry_count'])
    else:
        # フォールバック: 基本的なテスト
        p = pyaudio.PyAudio()
        try:
            device_info = p.get_device_info_by_index(device_index)
            if int(device_info['maxInputChannels']) > 0:
                try:
                    chunk_size = settings['audio']['chunk_size']
                    sample_rate = settings['audio']['sample_rate']
                    channels = settings['audio']['channels']
                    
                    stream = p.open(
                        format=pyaudio.paInt16,
                        channels=channels,
                        rate=sample_rate,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=chunk_size
                    )
                    stream.close()
                    return True, "アクセス可能", []
                except Exception as e:
                    error_msg = str(e)
                    if "Errno -9999" in error_msg:
                        return False, "ホストエラー: デバイスが他のアプリで使用中または権限不足", [
                            "他のアプリケーションがマイクを使用していないか確認してください",
                            "Windows設定 → プライバシーとセキュリティ → マイクでアクセス許可を確認",
                            "デバイスドライバーを更新してください"
                        ]
                    else:
                        return False, f"アクセスエラー: {error_msg}", ["デバイスを再接続してください"]
            else:
                return False, "入力チャンネルなし", []
        except Exception as e:
            return False, f"デバイス情報取得エラー: {e}", []
        finally:
            p.terminate()

# 設定を読み込み
settings = load_settings()

# タブ作成
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎤 録音設定", 
    "🤖 Whisper設定", 
    "🔧 デバイス設定", 
    "🎨 UI設定", 
    "🔧 トラブルシューティング",
    "🔍 システム診断"
])

with tab1:
    st.subheader("🎤 録音設定")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**基本設定**")
        settings['audio']['chunk_size'] = st.selectbox(
            "チャンクサイズ",
            [512, 1024, 2048, 4096],
            index=[512, 1024, 2048, 4096].index(settings['audio']['chunk_size']),
            help="音声処理の単位サイズ。小さいほど低遅延、大きいほど安定"
        )
        
        settings['audio']['sample_rate'] = st.selectbox(
            "サンプルレート",
            [8000, 16000, 22050, 44100, 48000],
            index=[8000, 16000, 22050, 44100, 48000].index(settings['audio']['sample_rate']),
            help="音声の品質。高いほど高品質だがファイルサイズも大きくなる"
        )
        
        settings['audio']['channels'] = st.selectbox(
            "チャンネル数",
            [1, 2],
            index=[1, 2].index(settings['audio']['channels']),
            help="モノラル(1)またはステレオ(2)"
        )
    
    with col2:
        st.write("**録音設定**")
        settings['audio']['duration'] = st.slider(
            "録音時間（秒）",
            min_value=1,
            max_value=60,
            value=settings['audio']['duration'],
            help="録音の長さ"
        )
        
        settings['audio']['gain'] = st.slider(
            "音声ゲイン",
            min_value=1.0,
            max_value=5.0,
            value=settings['audio']['gain'],
            step=0.1,
            help="音声レベルを上げる倍率"
        )

with tab2:
    st.subheader("🤖 Whisper設定")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**基本設定**")
        settings['whisper']['model_size'] = st.selectbox(
            "モデルサイズ",
            ["tiny", "base", "small", "medium", "large"],
            index=["tiny", "base", "small", "medium", "large"].index(settings['whisper']['model_size']),
            help="tiny: 最も軽量、large: 最も高精度（重い）"
        )
        
        settings['whisper']['language'] = st.selectbox(
            "言語",
            ["ja", "en", "auto"],
            index=["ja", "en", "auto"].index(settings['whisper']['language']),
            help="音声認識の言語"
        )
        
        settings['whisper']['temperature'] = st.slider(
            "温度",
            min_value=0.0,
            max_value=1.0,
            value=settings['whisper']['temperature'],
            step=0.1,
            help="決定論的サンプリング（0.0）またはランダムサンプリング"
        )
    
    with col2:
        st.write("**高精度設定**")
        settings['whisper']['compression_ratio_threshold'] = st.slider(
            "圧縮比閾値",
            min_value=1.0,
            max_value=5.0,
            value=settings['whisper']['compression_ratio_threshold'],
            step=0.1,
            help="音声圧縮の閾値"
        )
        
        settings['whisper']['logprob_threshold'] = st.slider(
            "対数確率閾値",
            min_value=-2.0,
            max_value=0.0,
            value=settings['whisper']['logprob_threshold'],
            step=0.1,
            help="音声認識の確信度閾値"
        )
        
        settings['whisper']['no_speech_threshold'] = st.slider(
            "無音閾値",
            min_value=0.0,
            max_value=1.0,
            value=settings['whisper']['no_speech_threshold'],
            step=0.1,
            help="無音判定の閾値"
        )
    
    settings['whisper']['condition_on_previous_text'] = st.checkbox(
        "前のテキストを条件とする",
        value=settings['whisper']['condition_on_previous_text'],
        help="前の音声の内容を考慮して認識精度を向上"
    )
    
    settings['whisper']['initial_prompt'] = st.text_area(
        "初期プロンプト",
        value=settings['whisper']['initial_prompt'],
        help="音声認識の初期ヒント"
    )

with tab3:
    st.subheader("🔧 デバイス設定")
    
    # マイクデバイス一覧
    devices = get_microphone_devices()
    
    if devices:
        st.write(f"**見つかったマイクデバイス数**: {len(devices)}")
        
        # デバイス選択
        device_options = [f"{d['name']} (ID: {d['index']})" for d in devices]
        device_names = [d['name'] for d in devices]
        
        if settings['device']['selected_device_name'] in device_names:
            default_index = device_names.index(settings['device']['selected_device_name'])
        else:
            default_index = 0
        
        selected_device_str = st.selectbox(
            "録音デバイスを選択",
            device_options,
            index=default_index,
            help="録音に使用するマイクデバイス"
        )
        
        # 選択されたデバイスの情報を取得
        selected_device_index = int(selected_device_str.split("(ID: ")[1].split(")")[0])
        selected_device = next((d for d in devices if d['index'] == selected_device_index), None)
        
        if selected_device:
            settings['device']['selected_device_index'] = selected_device_index
            settings['device']['selected_device_name'] = selected_device['name']
            
            # デバイス情報表示
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**デバイス情報**")
                st.write(f"名前: {selected_device['name']}")
                st.write(f"ID: {selected_device['index']}")
                st.write(f"ホストAPI: {selected_device['host_api']}")
            
            with col2:
                st.write("**仕様**")
                st.write(f"チャンネル数: {selected_device['channels']}")
                st.write(f"サンプルレート: {selected_device['sample_rate']} Hz")
                st.write(f"デフォルト: {'はい' if selected_device['is_default'] else 'いいえ'}")
            
            with col3:
                st.write("**ステータス**")
                # アクセステスト
                if st.button("アクセステスト", key="device_test"):
                    with st.spinner("テスト中..."):
                        success, message, suggestions = test_device_access(selected_device_index, settings)
                        if success:
                            st.success("✅ " + message)
                        else:
                            st.error("❌ " + message)
                            
                            # 解決策を表示
                            if suggestions:
                                st.info("**解決策:**")
                                for i, suggestion in enumerate(suggestions, 1):
                                    st.write(f"{i}. {suggestion}")
        
        # 自動設定
        st.markdown("---")
        st.write("**自動設定**")
        
        settings['device']['auto_select_default'] = st.checkbox(
            "デフォルトデバイスを自動選択",
            value=settings['device']['auto_select_default'],
            help="起動時にデフォルトマイクを自動選択"
        )
        
        settings['device']['test_device_on_select'] = st.checkbox(
            "デバイス選択時に自動テスト",
            value=settings['device']['test_device_on_select'],
            help="デバイス選択時に自動でアクセステストを実行"
        )
    else:
        st.error("マイクデバイスが見つかりません")

with tab4:
    st.subheader("🎨 UI設定")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**表示設定**")
        settings['ui']['show_advanced_options'] = st.checkbox(
            "詳細オプションを表示",
            value=settings['ui']['show_advanced_options'],
            help="上級者向けの設定を表示"
        )
        
        settings['ui']['show_quality_analysis'] = st.checkbox(
            "音声品質分析を表示",
            value=settings['ui']['show_quality_analysis'],
            help="録音後の音声品質分析を表示"
        )
        
        settings['ui']['show_level_monitoring'] = st.checkbox(
            "レベル監視を表示",
            value=settings['ui']['show_level_monitoring'],
            help="リアルタイム音声レベル監視を表示"
        )
    
    with col2:
        st.write("**ファイル設定**")
        settings['ui']['auto_save_recordings'] = st.checkbox(
            "録音を自動保存",
            value=settings['ui']['auto_save_recordings'],
            help="録音完了時に自動でファイルを保存"
        )

with tab5:
    st.subheader("🔧 トラブルシューティング設定")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**エラー処理**")
        settings['troubleshooting']['retry_count'] = st.slider(
            "リトライ回数",
            min_value=1,
            max_value=10,
            value=settings['troubleshooting']['retry_count'],
            help="エラー時のリトライ回数"
        )
        
        settings['troubleshooting']['timeout_seconds'] = st.slider(
            "タイムアウト（秒）",
            min_value=5,
            max_value=30,
            value=settings['troubleshooting']['timeout_seconds'],
            help="操作のタイムアウト時間"
        )
    
    with col2:
        st.write("**ログ設定**")
        settings['troubleshooting']['enable_error_recovery'] = st.checkbox(
            "エラー回復を有効",
            value=settings['troubleshooting']['enable_error_recovery'],
            help="エラー時の自動回復を試行"
        )
        
        settings['troubleshooting']['log_errors'] = st.checkbox(
            "エラーログを記録",
            value=settings['troubleshooting']['log_errors'],
            help="エラーをログファイルに記録"
        )

with tab6:
    st.subheader("🔍 システム診断")
    
    # 診断実行ボタン
    if st.button("🔍 システム診断を実行", type="primary"):
        with st.spinner("診断中..."):
            
            # 1. システム情報
            st.markdown("### 💻 システム情報")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Pythonバージョン**: {sys.version}")
                st.write("**PyAudio**: インストール済み")
                st.write(f"**現在のディレクトリ**: {os.getcwd()}")
            
            with col2:
                st.write(f"**OS**: {os.name}")
                st.write(f"**プラットフォーム**: {sys.platform}")
            
            # 2. Windowsマイク権限確認
            st.markdown("### 🎤 Windowsマイク権限")
            permissions = check_windows_microphone_permissions()
            
            col1, col2 = st.columns(2)
            
            with col1:
                if permissions['microphone_enabled']:
                    st.success("✅ マイク機能が有効")
                else:
                    st.warning("⚠️ マイク機能が無効の可能性")
                
                if permissions.get('app_access_allowed', False):
                    st.success("✅ アプリアクセスが許可")
                else:
                    st.warning("⚠️ アプリアクセスが制限の可能性")
            
            with col2:
                st.write("**詳細情報:**")
                for detail in permissions.get('details', []):
                    st.write(f"• {detail}")
            
            # 3. オーディオデバイス診断
            st.markdown("### 🔊 オーディオデバイス診断")
            diagnostics = get_audio_device_diagnostics()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("総デバイス数", diagnostics['total_devices'])
            
            with col2:
                st.metric("入力デバイス数", diagnostics['input_devices'])
            
            with col3:
                st.metric("出力デバイス数", diagnostics['output_devices'])
            
            # デフォルトデバイス情報
            if diagnostics['default_input']:
                st.success(f"**デフォルト入力**: {diagnostics['default_input']['name']}")
            else:
                st.error("デフォルト入力デバイスが見つかりません")
            
            if diagnostics['default_output']:
                st.success(f"**デフォルト出力**: {diagnostics['default_output']['name']}")
            else:
                st.error("デフォルト出力デバイスが見つかりません")
            
            # エラー情報
            if diagnostics['errors']:
                st.markdown("### ❌ エラー情報")
                for error in diagnostics['errors']:
                    st.error(error)
            
            # 4. 推奨設定
            st.markdown("### 💡 推奨設定")
            
            recommendations = []
            
            # チャンクサイズの推奨
            if settings['audio']['chunk_size'] < 1024:
                recommendations.append("チャンクサイズを1024以上に設定することを推奨（安定性向上）")
            
            # サンプルレートの推奨
            if settings['audio']['sample_rate'] > 44100:
                recommendations.append("サンプルレートを44100Hz以下に設定することを推奨（互換性向上）")
            
            # リトライ回数の推奨
            if settings['troubleshooting']['retry_count'] < 3:
                recommendations.append("リトライ回数を3回以上に設定することを推奨（エラー耐性向上）")
            
            if recommendations:
                for rec in recommendations:
                    st.info(rec)
            else:
                st.success("現在の設定は適切です")

# 設定の保存・リセット
st.markdown("---")
st.subheader("💾 設定の保存・管理")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("💾 設定を保存", type="primary"):
        if save_settings(settings):
            st.success("設定を保存しました")

with col2:
    if st.button("🔄 デフォルトに戻す"):
        settings = DEFAULT_SETTINGS.copy()
        st.success("設定をデフォルトに戻しました")

with col3:
    if st.button("📋 設定をエクスポート"):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_file = f"settings/exported_settings_{timestamp}.json"
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            st.success(f"設定をエクスポートしました: {export_file}")
        except Exception as e:
            st.error(f"エクスポートエラー: {e}")

# 設定ファイルのインポート
st.markdown("---")
st.subheader("📥 設定のインポート")

uploaded_settings = st.file_uploader(
    "設定ファイルをアップロード",
    type=['json'],
    help="以前にエクスポートした設定ファイルをアップロード"
)

if uploaded_settings is not None:
    try:
        imported_settings = json.load(uploaded_settings)
        if st.button("📥 インポートして適用"):
            settings.update(imported_settings)
            if save_settings(settings):
                st.success("設定をインポートしました")
                st.rerun()
    except Exception as e:
        st.error(f"インポートエラー: {e}")

# 現在の設定表示
st.markdown("---")
st.subheader("📋 現在の設定")

if st.checkbox("現在の設定を表示"):
    st.json(settings)

# トラブルシューティング情報
st.markdown("---")
st.subheader("🔧 よくある問題と解決方法")

with st.expander("Errno -9999 ホストエラーについて", expanded=False):
    st.markdown("""
    ### Errno -9999 ホストエラーの原因と解決方法
    
    **原因:**
    - 他のアプリケーションがマイクを使用中
    - マイクへのアクセス権限が不足
    - デバイスドライバーの問題
    - 仮想オーディオデバイスの競合
    
    **解決方法:**
    
    1. **他のアプリを確認**
       - ブラウザ、Zoom、Teams、Discordなど
       - マイクを使用しているアプリを終了
    
    2. **Windows設定を確認**
       - Windows設定 → プライバシーとセキュリティ → マイク
       - 「アプリがマイクにアクセスすることを許可」をON
       - 「デスクトップアプリがマイクにアクセスすることを許可」をON
    
    3. **デバイスドライバーを更新**
       - デバイスマネージャー → オーディオ入力と出力
       - マイクデバイスを右クリック → ドライバーの更新
    
    4. **仮想オーディオデバイスを無効化**
       - デバイスマネージャーで仮想オーディオデバイスを一時的に無効化
       - テスト後に必要に応じて再有効化
    
    5. **アプリを管理者として実行**
       - コマンドプロンプトを管理者として実行
       - `streamlit run app.py` を実行
    
    6. **設定の調整**
       - チャンクサイズを大きくする（2048, 4096）
       - サンプルレートを下げる（22050, 16000）
       - リトライ回数を増やす
    """)

with st.expander("その他のエラーについて", expanded=False):
    st.markdown("""
    ### その他のよくあるエラー
    
    **Errno -9998 ストリームエラー**
    - デバイスが利用できない状態
    - 解決方法: デバイスを再接続または再起動
    
    **Errno -9997 デバイスエラー**
    - デバイスが存在しない
    - 解決方法: デバイスドライバーを再インストール
    
    **Errno -9996 バッファエラー**
    - バッファサイズが不適切
    - 解決方法: チャンクサイズを調整
    
    **Errno -9995 バッファオーバーフロー**
    - データ処理が追いつかない
    - 解決方法: チャンクサイズを大きくする
    
    **Errno -9994 バッファアンダーフロー**
    - データが不足
    - 解決方法: チャンクサイズを小さくする
    
    **メモリ不足エラー**
    - 大きなWhisperモデルを使用時
    - 解決方法: モデルサイズを小さくする（tiny, base）
    
    **音声レベルが低い**
    - マイクの音量設定を確認
    - ゲイン設定を上げる
    - マイクに近づく
    """) 