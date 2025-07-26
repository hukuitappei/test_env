import streamlit as st
import os
import glob
from datetime import datetime
from typing import Dict, Any
from .settings_manager import load_settings, save_settings
from .device_manager import get_microphone_devices, test_device_access, save_device_selection
from .llm_manager import test_api_key, get_available_models, get_llm_status

def render_audio_settings_tab(settings: Dict[str, Any]) -> Dict[str, Any]:
    """録音設定タブを表示"""
    st.markdown("### 🎤 録音設定")
    st.info("💡 **録音設定**: マイクで音を録音するときの設定です。音の質や録音時間を調整できます。")
    
    col1, col2 = st.columns(2)
    
    with col1:
        settings['audio']['chunk_size'] = st.number_input(
            "チャンクサイズ", 
            min_value=512, 
            max_value=4096, 
            value=settings['audio']['chunk_size'], 
            step=512,
            help="音を録音するときのデータの塊の大きさ（大きいほど安定するけど遅くなる）"
        )
        settings['audio']['sample_rate'] = st.selectbox(
            "サンプルレート", 
            [8000, 16000, 22050, 44100, 48000], 
            index=[8000, 16000, 22050, 44100, 48000].index(settings['audio']['sample_rate']),
            help="1秒間に何回音を測るか（大きいほど音質が良くなるけどファイルが大きくなる）"
        )
        settings['audio']['channels'] = st.selectbox(
            "チャンネル数", 
            [1, 2], 
            index=settings['audio']['channels']-1,
            help="録音する音の種類（1=モノラル、2=ステレオ。ステレオは左右の音を録音）"
        )
    
    with col2:
        settings['audio']['gain'] = st.slider(
            "音声ゲイン", 
            min_value=1.0, 
            max_value=5.0, 
            value=settings['audio']['gain'], 
            step=0.1,
            help="録音する音を大きくする倍率（1.0=そのまま、2.0=2倍の音量）"
        )
        settings['audio']['duration'] = st.slider(
            "録音時間（秒）", 
            min_value=1, 
            max_value=60, 
            value=settings['audio']['duration'], 
            step=1,
            help="録音ボタンを押してから何秒間録音するか"
        )
    
    return settings

def render_whisper_settings_tab(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Whisper設定タブを表示"""
    st.markdown("### 🤖 Whisper設定")
    st.info("💡 **Whisper設定**: 音声を文字に変換するAI（Whisper）の設定です。精度や速度を調整できます。")
    
    col1, col2 = st.columns(2)
    
    with col1:
        settings['whisper']['model_size'] = st.selectbox(
            "モデルサイズ", 
            ["tiny", "base", "small", "medium", "large"], 
            index=["tiny", "base", "small", "medium", "large"].index(settings['whisper']['model_size']),
            help="AIの大きさ（小さい=速いけど精度低い、大きい=遅いけど精度高い）"
        )
        settings['whisper']['language'] = st.selectbox(
            "言語", 
            ["ja", "en", "auto"], 
            index=["ja", "en", "auto"].index(settings['whisper']['language']),
            help="録音した音声の言語（ja=日本語、en=英語、auto=自動判定）"
        )
        settings['whisper']['temperature'] = st.slider(
            "温度", 
            min_value=0.0, 
            max_value=1.0, 
            value=settings['whisper']['temperature'], 
            step=0.1,
            help="AIの創造性（0.0=正確、1.0=創造的。音声認識では0.0がおすすめ）"
        )
    
    with col2:
        settings['whisper']['compression_ratio_threshold'] = st.slider(
            "圧縮比閾値", 
            min_value=1.0, 
            max_value=5.0, 
            value=settings['whisper']['compression_ratio_threshold'], 
            step=0.1,
            help="音声の圧縮比の閾値（低いほど厳密）"
        )
        settings['whisper']['logprob_threshold'] = st.slider(
            "対数確率閾値", 
            min_value=-2.0, 
            max_value=0.0, 
            value=settings['whisper']['logprob_threshold'], 
            step=0.1,
            help="文字起こしの確信度の閾値（高いほど厳密）"
        )
        settings['whisper']['no_speech_threshold'] = st.slider(
            "無音閾値", 
            min_value=0.0, 
            max_value=1.0, 
            value=settings['whisper']['no_speech_threshold'], 
            step=0.1,
            help="無音と判定する閾値（低いほど厳密）"
        )
    
    return settings

def render_device_settings_tab(settings: Dict[str, Any]) -> Dict[str, Any]:
    """デバイス設定タブを表示"""
    st.markdown("### 🔧 デバイス設定")
    st.info("💡 **デバイス設定**: マイクやスピーカーの設定です。")
    
    # マイクデバイス一覧
    devices = get_microphone_devices()
    
    if devices:
        device_names = [f"{d['name']} (ID: {d['index']})" for d in devices]
        current_device_index = settings['device']['selected_device_index']
        
        if current_device_index is not None:
            current_device_name = None
            for device in devices:
                if device['index'] == current_device_index:
                    current_device_name = f"{device['name']} (ID: {device['index']})"
                    break
            if current_device_name:
                current_index = device_names.index(current_device_name)
            else:
                current_index = 0
        else:
            current_index = 0
        
        selected_device_name = st.selectbox(
            "マイクデバイス",
            device_names,
            index=current_index,
            help="録音に使用するマイクを選択してください"
        )
        
        # 選択されたデバイスの情報を取得
        selected_device = None
        for device in devices:
            if f"{device['name']} (ID: {device['index']})" == selected_device_name:
                selected_device = device
                break
        
        if selected_device:
            st.info(f"**選択されたデバイス**: {selected_device['name']}")
            st.write(f"チャンネル数: {selected_device['channels']}")
            st.write(f"サンプルレート: {selected_device['sample_rate']} Hz")
            
            # デバイステスト
            if st.button("🔍 デバイスをテスト", key=f"test_device_{selected_device['index']}"):
                if test_device_access(selected_device['index']):
                    st.success("✅ デバイステスト成功！")
                    # 設定を保存
                    settings['device']['selected_device_index'] = selected_device['index']
                    settings['device']['selected_device_name'] = selected_device['name']
                    save_settings(settings)
                else:
                    st.error("❌ デバイステスト失敗")
    else:
        st.error("マイクデバイスが見つかりません")
    
    # 自動選択設定
    settings['device']['auto_select_default'] = st.checkbox(
        "起動時にデフォルトマイクを自動選択",
        value=settings['device']['auto_select_default'],
        help="アプリ起動時にデフォルトのマイクを自動で選択するかどうか"
    )
    
    settings['device']['test_device_on_select'] = st.checkbox(
        "デバイス選択時にテストを実行",
        value=settings['device']['test_device_on_select'],
        help="新しいデバイスを選択したときに自動でテストを実行するかどうか"
    )
    
    return settings

def render_ui_settings_tab(settings: Dict[str, Any]) -> Dict[str, Any]:
    """UI設定タブを表示"""
    st.markdown("### 🎨 UI設定")
    st.info("💡 **UI設定**: 画面の表示や動作に関する設定です。")
    
    col1, col2 = st.columns(2)
    
    with col1:
        settings['ui']['show_advanced_options'] = st.checkbox(
            "詳細オプションを表示",
            value=settings['ui']['show_advanced_options'],
            help="詳細な設定オプションを表示するかどうか"
        )
        settings['ui']['auto_save_recordings'] = st.checkbox(
            "録音を自動保存",
            value=settings['ui']['auto_save_recordings'],
            help="録音完了時に自動でファイルに保存するかどうか"
        )
        settings['ui']['show_quality_analysis'] = st.checkbox(
            "音声品質分析を表示",
            value=settings['ui']['show_quality_analysis'],
            help="録音後に音声品質の分析結果を表示するかどうか"
        )
    
    with col2:
        settings['ui']['show_level_monitoring'] = st.checkbox(
            "音声レベル監視を表示",
            value=settings['ui']['show_level_monitoring'],
            help="音声レベル監視機能を表示するかどうか"
        )
        settings['ui']['auto_start_recording'] = st.checkbox(
            "音声検出で自動録音開始",
            value=settings['ui']['auto_start_recording'],
            help="音声レベルが一定以上になったら自動で録音を開始するかどうか"
        )
        
        if settings['ui']['auto_start_recording']:
            settings['ui']['auto_recording_threshold'] = st.slider(
                "自動録音閾値",
                min_value=100,
                max_value=1000,
                value=settings['ui']['auto_recording_threshold'],
                step=50,
                help="自動録音を開始する音声レベルのしきい値"
            )
            settings['ui']['auto_recording_delay'] = st.slider(
                "自動録音遅延（秒）",
                min_value=0.5,
                max_value=3.0,
                value=settings['ui']['auto_recording_delay'],
                step=0.1,
                help="音声検出から録音開始までの待ち時間"
            )
    
    return settings

def render_llm_settings_tab(settings: Dict[str, Any]) -> Dict[str, Any]:
    """LLM設定タブを表示"""
    st.markdown("### 🤖 LLM設定")
    st.info("💡 **LLM設定**: 大規模言語モデル（LLM）の設定です。文字起こし結果の要約や分析に使用します。")
    
    # LLMライブラリの状態を確認
    llm_status = get_llm_status()
    
    col1, col2 = st.columns(2)
    
    with col1:
        # LLM機能の有効/無効
        settings['llm']['enabled'] = st.checkbox(
            "LLM機能を有効にする",
            value=settings['llm']['enabled'],
            help="LLM機能を使用するかどうか"
        )
        
        if settings['llm']['enabled']:
            # プロバイダー選択
            provider = st.selectbox(
                "プロバイダー",
                ["openai", "anthropic", "google"],
                index=["openai", "anthropic", "google"].index(settings['llm']['provider']),
                help="使用するLLMプロバイダー"
            )
            settings['llm']['provider'] = provider
            
            # プロバイダーの状態を表示
            if provider == "openai":
                if llm_status["openai"]:
                    st.success("✅ OpenAIライブラリが利用可能")
                else:
                    st.error("❌ OpenAIライブラリがインストールされていません")
            elif provider == "anthropic":
                if llm_status["anthropic"]:
                    st.success("✅ Anthropicライブラリが利用可能")
                else:
                    st.error("❌ Anthropicライブラリがインストールされていません")
            elif provider == "google":
                if llm_status["google"]:
                    st.success("✅ Google Generative AIライブラリが利用可能")
                else:
                    st.error("❌ Google Generative AIライブラリがインストールされていません")
            
            # モデル選択
            available_models = get_available_models(provider)
            if available_models:
                model = st.selectbox(
                    "モデル",
                    available_models,
                    index=available_models.index(settings['llm']['model']) if settings['llm']['model'] in available_models else 0
                )
                settings['llm']['model'] = model
    
    with col2:
        if settings['llm']['enabled']:
            # 環境変数の確認
            env_api_key = os.getenv(f"{settings['llm']['provider'].upper()}_API_KEY", "")
            if env_api_key:
                st.success(f"✅ 環境変数 {settings['llm']['provider'].upper()}_API_KEY が設定されています")
                st.info("💡 環境変数が設定されている場合、設定ファイルのAPIキーは無視されます")
            else:
                st.warning(f"⚠️ 環境変数 {settings['llm']['provider'].upper()}_API_KEY が設定されていません")
                st.info("💡 セキュリティのため、.envファイルで環境変数を設定することを推奨します")
            
            # APIキー入力（環境変数がない場合のみ表示）
            if not env_api_key:
                api_key = st.text_input(
                    "APIキー（非推奨）",
                    value=settings['llm']['api_key'],
                    type="password",
                    help="LLMサービス用のAPIキー（環境変数の使用を推奨）"
                )
                settings['llm']['api_key'] = api_key
            else:
                # 環境変数が設定されている場合は表示のみ
                st.text_input(
                    "APIキー",
                    value="***環境変数から取得***",
                    disabled=True,
                    help="環境変数から取得されています"
                )
            
            # 温度設定
            temperature = st.slider(
                "温度 (Temperature)",
                min_value=0.0,
                max_value=2.0,
                value=settings['llm']['temperature'],
                step=0.1,
                help="値が高いほど創造的、低いほど決定論的になります"
            )
            settings['llm']['temperature'] = temperature
            
            # 最大トークン数
            max_tokens = st.number_input(
                "最大トークン数",
                min_value=100,
                max_value=4000,
                value=settings['llm']['max_tokens'],
                step=100,
                help="生成するテキストの最大長"
            )
            settings['llm']['max_tokens'] = max_tokens
    
    # APIキーテスト
    if settings['llm']['enabled']:
        st.markdown("---")
        st.markdown("#### 🧪 APIキーテスト")
        
        # テスト用のAPIキーを取得
        test_api_key_value = env_api_key if env_api_key else settings['llm']['api_key']
        
        if test_api_key_value:
            if st.button("🔍 APIキーをテスト", key=f"test_api_key_{settings['llm']['provider']}_{settings['llm']['model']}"):
                if test_api_key(settings['llm']['provider'], test_api_key_value, settings['llm']['model']):
                    st.success("✅ APIキーテスト成功！")
                else:
                    st.error("❌ APIキーテスト失敗")
        else:
            st.warning("⚠️ APIキーが設定されていません")
    
    return settings

def render_file_management_tab() -> None:
    """ファイル管理タブを表示"""
    st.markdown("### 📁 ファイル管理")
    st.info("💡 **ファイル管理**: 録音ファイルや文字起こし結果の管理を行います。")
    
    # 録音ファイル一覧
    st.markdown("#### 🎤 録音ファイル")
    if os.path.exists("recordings"):
        audio_files = glob.glob("recordings/*.wav")
        if audio_files:
            for audio_file in sorted(audio_files, reverse=True):
                file_size = os.path.getsize(audio_file)
                file_time = datetime.fromtimestamp(os.path.getmtime(audio_file))
                
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"📁 {os.path.basename(audio_file)}")
                    st.caption(f"サイズ: {file_size:,} bytes | 更新: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                with col2:
                    if st.button("🗑️", key=f"delete_{audio_file}"):
                        try:
                            os.remove(audio_file)
                            st.success("ファイルを削除しました")
                            st.rerun()
                        except Exception as e:
                            st.error(f"削除エラー: {e}")
                
                with col3:
                    if st.button("📥", key=f"download_{audio_file}"):
                        with open(audio_file, "rb") as f:
                            st.download_button(
                                label="ダウンロード",
                                data=f.read(),
                                file_name=os.path.basename(audio_file),
                                mime="audio/wav"
                            )
        else:
            st.info("録音ファイルがありません")
    else:
        st.info("recordingsディレクトリが存在しません")
    
    # 文字起こしファイル一覧
    st.markdown("#### 📝 文字起こしファイル")
    transcription_files = glob.glob("*.txt")
    if transcription_files:
        for txt_file in sorted(transcription_files, reverse=True):
            file_size = os.path.getsize(txt_file)
            file_time = datetime.fromtimestamp(os.path.getmtime(txt_file))
            
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"📄 {txt_file}")
                st.caption(f"サイズ: {file_size:,} bytes | 更新: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            with col2:
                if st.button("🗑️", key=f"delete_txt_{txt_file}"):
                    try:
                        os.remove(txt_file)
                        st.success("ファイルを削除しました")
                        st.rerun()
                    except Exception as e:
                        st.error(f"削除エラー: {e}")
            
            with col3:
                if st.button("📥", key=f"download_txt_{txt_file}"):
                    with open(txt_file, "r", encoding="utf-8") as f:
                        st.download_button(
                            label="ダウンロード",
                            data=f.read(),
                            file_name=txt_file,
                            mime="text/plain"
                        )
    else:
        st.info("文字起こしファイルがありません")

def render_settings_save_button(settings: Dict[str, Any]) -> None:
    """設定保存ボタンを表示"""
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 設定を保存", type="primary", key="ui_save_settings"):
            if save_settings(settings):
                st.success("✅ 設定を保存しました")
            else:
                st.error("❌ 設定の保存に失敗しました")
    
    with col2:
        if st.button("🔄 設定をリセット", key="ui_reset_settings"):
            if st.button("本当にリセットしますか？", key="ui_confirm_reset"):
                from .settings_manager import reset_settings
                if reset_settings():
                    st.success("✅ 設定をリセットしました")
                    st.rerun()
                else:
                    st.error("❌ 設定のリセットに失敗しました") 

def render_troubleshooting_tab(settings: Dict[str, Any]) -> Dict[str, Any]:
    """トラブルシューティングタブを表示"""
    st.markdown("### 🔧 トラブルシューティング")
    st.info("💡 **トラブルシューティング**: 問題が発生した場合の対処法です。")
    
    col1, col2 = st.columns(2)
    
    with col1:
        settings['troubleshooting']['retry_count'] = st.number_input(
            "リトライ回数",
            min_value=1,
            max_value=10,
            value=settings['troubleshooting']['retry_count'],
            help="エラーが発生した場合のリトライ回数"
        )
        settings['troubleshooting']['timeout_seconds'] = st.number_input(
            "タイムアウト（秒）",
            min_value=5,
            max_value=60,
            value=settings['troubleshooting']['timeout_seconds'],
            help="処理のタイムアウト時間"
        )
    
    with col2:
        settings['troubleshooting']['enable_error_recovery'] = st.checkbox(
            "エラー回復を有効にする",
            value=settings['troubleshooting']['enable_error_recovery'],
            help="エラーが発生した場合に自動で回復を試みるかどうか"
        )
        settings['troubleshooting']['log_errors'] = st.checkbox(
            "エラーログを記録",
            value=settings['troubleshooting']['log_errors'],
            help="エラーをログファイルに記録するかどうか"
        )
    
    return settings

def render_system_diagnostic_tab() -> None:
    """システム診断タブを表示"""
    st.markdown("### 💻 システム診断")
    st.info("💡 **システム診断**: システムの状態を確認します。")
    
    # システム情報
    st.markdown("#### 🔍 システム情報")
    import platform
    st.write(f"**OS**: {platform.system()} {platform.release()}")
    st.write(f"**Python**: {platform.python_version()}")
    st.write(f"**Streamlit**: {st.__version__}")
    
    # ライブラリの状態確認
    st.markdown("#### 📦 ライブラリ状態")
    
    # PyAudio
    try:
        import pyaudio
        st.success("✅ PyAudio: 利用可能")
    except ImportError:
        st.error("❌ PyAudio: インストールされていません")
    
    # Whisper
    try:
        import whisper
        st.success("✅ Whisper: 利用可能")
    except ImportError:
        st.error("❌ Whisper: インストールされていません")
    
    # NumPy
    try:
        import numpy
        st.success("✅ NumPy: 利用可能")
    except ImportError:
        st.error("❌ NumPy: インストールされていません")
    
    # SciPy
    try:
        import scipy
        st.success("✅ SciPy: 利用可能")
    except ImportError:
        st.error("❌ SciPy: インストールされていません")
    
    # Librosa
    try:
        import librosa
        st.success("✅ Librosa: 利用可能")
    except ImportError:
        st.error("❌ Librosa: インストールされていません")

def render_usage_guide_tab() -> None:
    """使用方法タブを表示"""
    st.markdown("### 📖 使用方法")
    st.info("💡 **使用方法**: アプリケーションの使い方を説明します。")
    
    st.markdown("""
    #### 🎤 録音機能
    1. **マイク選択**: 設定画面で使用するマイクを選択してください
    2. **録音開始**: 録音ボタンをクリックして録音を開始します
    3. **録音停止**: 設定された時間が経過すると自動で停止します
    
    #### 📝 文字起こし機能
    1. **通常精度**: 高速で文字起こしを行います
    2. **高精度**: より正確な文字起こしを行います（時間がかかります）
    3. **複数モデル比較**: 異なるモデルで文字起こしを比較します
    
    #### 🤖 LLM機能
    1. **設定**: LLM設定でAPIキーを設定してください
    2. **要約**: 文字起こし結果を要約します
    3. **分析**: 文字起こし結果を分析します
    
    #### ⌨️ ショートカットキー
    - **F9**: 録音開始
    - **F10**: 録音停止
    - **F11**: 文字起こし
    - **F12**: テキストクリア
    """)

def render_microphone_info_tab() -> None:
    """マイク情報タブを表示"""
    st.markdown("### 🔍 マイク情報")
    st.info("💡 **マイク情報**: 利用可能なマイクデバイスの詳細情報です。")
    
    from .device_manager import get_microphone_devices, test_device_access
    
    devices = get_microphone_devices()
    if devices:
        st.write(f"**利用可能なマイク数**: {len(devices)}")
        
        for i, device in enumerate(devices):
            with st.expander(f"🎤 {device['name']} (ID: {device['index']})"):
                st.write(f"**チャンネル数**: {device['channels']}")
                st.write(f"**サンプルレート**: {device['sample_rate']} Hz")
                
                # デバイステスト
                if st.button(f"🔍 テスト {i}", key=f"test_device_info_{i}"):
                    if test_device_access(device['index']):
                        st.success("✅ デバイステスト成功！")
                    else:
                        st.error("❌ デバイステスト失敗") 