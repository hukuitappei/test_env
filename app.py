import streamlit as st
import os
from datetime import datetime

# 新機能のインポート
from utils.voice_commands import create_voice_command_processor
from utils.user_dictionary import create_user_dictionary
from utils.command_processor import create_command_processor

# ショートカットキー機能のインポート
try:
    from utils.shortcut_handler import ShortcutHandler, create_shortcut_javascript, handle_shortcut_event
    SHORTCUT_AVAILABLE = True
except ImportError:
    SHORTCUT_AVAILABLE = False

# 新しいモジュールのインポート
from utils.settings_manager import load_settings, save_settings
from utils.device_manager import auto_select_default_microphone, load_saved_device
from utils.audio_processor import (
    record_audio_with_device, 
    auto_record_with_level_monitoring, 
    analyze_audio_quality, 
    save_audio_file,
    monitor_audio_level
)
from utils.transcription_manager import (
    get_whisper_model,
    transcribe_audio,
    transcribe_audio_high_quality,
    compare_transcriptions,
    save_transcription
)
from utils.llm_manager import send_to_llm
from utils.ui_components import (
    render_audio_settings_tab,
    render_whisper_settings_tab,
    render_device_settings_tab,
    render_ui_settings_tab,
    render_llm_settings_tab,
    render_file_management_tab,
    render_settings_save_button,
    render_troubleshooting_tab,
    render_system_diagnostic_tab,
    render_usage_guide_tab,
    render_microphone_info_tab
)
from utils.recording_animation import show_recording_animation

st.set_page_config(page_title="音声録音＆文字起こし", page_icon="🎤", layout="wide")
st.title("🎤 音声録音＆文字起こし（統合版）")

# 設定を読み込み
settings = load_settings()

# recordingsディレクトリの作成
os.makedirs('recordings', exist_ok=True)

# セッション状態の初期化
if 'current_transcription' not in st.session_state:
    st.session_state['current_transcription'] = ""

# ショートカットキー機能の初期化
if SHORTCUT_AVAILABLE:
    if 'shortcut_handler' not in st.session_state:
        st.session_state.shortcut_handler = ShortcutHandler("settings/app_settings.json")

# Whisperモデルの読み込み
whisper_model = get_whisper_model(settings['whisper']['model_size'])

# アプリ起動時にマイクを選択
if 'selected_device' not in st.session_state:
    # 保存された設定からマイクを復元
    saved_device = load_saved_device()
    if saved_device:
        st.session_state['selected_device'] = saved_device
    else:
        # 設定がない場合はデフォルトマイクを自動選択
        default_device = auto_select_default_microphone()
        if default_device:
            st.session_state['selected_device'] = default_device

# メインUI
st.markdown("---")

# ヘッダー部分に設定ボタンを追加
col1, col2 = st.columns([4, 1])
with col1:
    st.markdown("### 🎤 録音・文字起こし")
with col2:
    if st.button("⚙️ 設定", help="詳細設定を開く", type="secondary"):
        st.session_state['show_settings'] = True

# 設定画面の表示
if st.session_state.get('show_settings', False):
    st.markdown("---")
    st.subheader("⚙️ 詳細設定")
    
    # 設定タブ
    settings_tab1, settings_tab2, settings_tab3, settings_tab4, settings_tab5, settings_tab6, settings_tab7, settings_tab8, settings_tab9, settings_tab10 = st.tabs([
        "🎤 録音設定", "🤖 Whisper設定", "🔧 デバイス設定", "🎨 UI設定", "🔧 トラブルシューティング", "💻 システム診断", "📖 使用方法", "🔍 マイク情報", "📁 ファイル管理", "🤖 LLM設定"
    ])
    
    with settings_tab1:
        settings = render_audio_settings_tab(settings)
    
    with settings_tab2:
        settings = render_whisper_settings_tab(settings)
    
    with settings_tab3:
        settings = render_device_settings_tab(settings)
    
    with settings_tab4:
        settings = render_ui_settings_tab(settings)
        
        # マイクレベル監視機能
        st.markdown("---")
        st.markdown("#### 🔍 マイクレベル監視")
        if 'selected_device' in st.session_state:
            selected_device = st.session_state['selected_device']
            st.info(f"**現在選択中のマイク**: {selected_device['name']} (ID: {selected_device['index']})")
            if st.button("🎤 マイクレベルをテスト", type="secondary"):
                try:
                    avg_level, levels = monitor_audio_level(selected_device['index'])
                    st.write(f"**平均音声レベル**: {avg_level:.1f}")
                    st.progress(min(avg_level / 1000, 1.0))
                    
                    if avg_level < 100:
                        st.warning("⚠️ 音声レベルが低いです。マイクの音量を上げてください。")
                    elif avg_level < 500:
                        st.info("ℹ️ 音声レベルは正常です。")
                    else:
                        st.success("✅ 音声レベルが良好です。")
                        
                except Exception as e:
                    st.error(f"レベル監視エラー: {e}")
        else:
            st.warning("⚠️ マイクデバイスが選択されていません。先にマイクを選択してください。")
    
    with settings_tab5:
        settings = render_troubleshooting_tab(settings)
    
    with settings_tab6:
        render_system_diagnostic_tab()
    
    with settings_tab7:
        render_usage_guide_tab()
    
    with settings_tab8:
        render_microphone_info_tab()
    
    with settings_tab9:
        render_file_management_tab()
    
    with settings_tab10:
        settings = render_llm_settings_tab(settings)
    
    # 設定保存ボタン
    render_settings_save_button(settings)

# --- 録音ボタン（最上部） ---
st.markdown("---")
st.subheader("🎤 録音")

recording_mode = st.radio(
    "録音モード",
    ["通常録音", "自動録音（音声レベル監視）"],
    help="通常録音: ボタンを押してから指定時間録音\n自動録音: 音声レベルが一定以上になったら自動で録音開始"
)

if 'selected_device' in st.session_state:
    selected = st.session_state['selected_device']
else:
    selected = None

# 録音中フラグ
if 'is_recording' not in st.session_state:
    st.session_state['is_recording'] = False

if recording_mode == "通常録音":
    if st.button("🎤 選択されたマイクで録音開始", type="primary", key="record_btn_normal"):
        st.session_state['is_recording'] = True
        show_recording_animation()
        st.rerun()
    if st.session_state['is_recording']:
        show_recording_animation()
        # 録音処理
        if whisper_model is None:
            st.error("Whisperモデルが読み込まれていません。ページを再読み込みしてください。")
        elif selected is not None:
            try:
                frames, rate = record_audio_with_device(settings['audio']['duration'], settings['audio']['gain'], selected['index'])
                if frames and rate:
                    st.session_state['recorded_frames'] = frames
                    st.session_state['recorded_rate'] = rate
                    st.session_state['recorded_device'] = selected['name']
                    if settings['ui']['auto_save_recordings']:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        device_name = selected['name'].replace(" ", "_").replace("(", "").replace(")", "")
                        filename = f"recordings/recording_{device_name}_{timestamp}.wav"
                        if save_audio_file(frames, rate, filename):
                            st.session_state['saved_audio_file'] = filename
                            st.session_state['audio_saved'] = True
                        else:
                            st.session_state['audio_saved'] = False
                    else:
                        st.session_state['audio_saved'] = False
                else:
                    st.error("録音データの取得に失敗しました")
            except Exception as e:
                st.error(f"録音エラー: {e}")
        st.session_state['is_recording'] = False
        st.rerun()
else:
    if st.button("🎤 音声レベル監視付き録音開始", type="primary", key="record_btn_auto"):
        st.session_state['is_recording'] = True
        show_recording_animation()
        st.rerun()
    if st.session_state['is_recording']:
        show_recording_animation()
        if whisper_model is None:
            st.error("Whisperモデルが読み込まれていません。ページを再読み込みしてください。")
        elif selected is not None:
            try:
                frames, rate = auto_record_with_level_monitoring(selected['index'], settings['audio']['duration'], settings['audio']['gain'])
                if frames and rate:
                    st.session_state['recorded_frames'] = frames
                    st.session_state['recorded_rate'] = rate
                    st.session_state['recorded_device'] = selected['name']
                    if settings['ui']['auto_save_recordings']:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        device_name = selected['name'].replace(" ", "_").replace("(", "").replace(")", "")
                        filename = f"recordings/recording_{device_name}_{timestamp}.wav"
                        if save_audio_file(frames, rate, filename):
                            st.session_state['saved_audio_file'] = filename
                            st.session_state['audio_saved'] = True
                        else:
                            st.session_state['audio_saved'] = False
                    else:
                        st.session_state['audio_saved'] = False
                else:
                    st.error("録音データの取得に失敗しました")
            except Exception as e:
                st.error(f"録音エラー: {e}")
        st.session_state['is_recording'] = False
        st.rerun()

# --- 文字起こしボタン（録音ボタンの直下） ---
st.markdown("---")
st.subheader("📝 文字起こし")
col1, col2 = st.columns(2)
with col1:
    transcribe_enabled = 'recorded_frames' in st.session_state and st.session_state['recorded_frames']
    if st.button("🔍 通常精度で文字起こし", key="transcribe_normal", disabled=not transcribe_enabled):
        if 'saved_audio_file' in st.session_state and st.session_state['saved_audio_file']:
            filename = st.session_state['saved_audio_file']
            transcription = transcribe_audio(filename)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_filename = f"temp_recording_{timestamp}.wav"
            if save_audio_file(st.session_state['recorded_frames'], st.session_state['recorded_rate'], temp_filename):
                transcription = transcribe_audio(temp_filename)
                try:
                    os.remove(temp_filename)
                except:
                    pass
            else:
                st.error("一時ファイルの保存に失敗しました")
                st.stop()
        st.session_state['current_transcription'] = transcription
        st.success("文字起こし完了！")
        st.rerun()
with col2:
    if st.button("🎯 高精度で文字起こし", key="transcribe_high", disabled=not transcribe_enabled):
        if 'saved_audio_file' in st.session_state and st.session_state['saved_audio_file']:
            filename = st.session_state['saved_audio_file']
            transcription = transcribe_audio_high_quality(filename)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_filename = f"temp_recording_{timestamp}.wav"
            if save_audio_file(st.session_state['recorded_frames'], st.session_state['recorded_rate'], temp_filename):
                transcription = transcribe_audio_high_quality(temp_filename)
                try:
                    os.remove(temp_filename)
                except:
                    pass
            else:
                st.error("一時ファイルの保存に失敗しました")
                st.stop()
        st.session_state['current_transcription'] = transcription
        st.success("文字起こし完了！")
        st.rerun()

# --- 文字起こし結果（最下部） ---
st.markdown("---")
st.markdown("### 📝 文字起こし結果")
current_transcription = st.session_state.get('current_transcription', '')
st.text_area("文字起こし結果", current_transcription, height=200, key="current_transcription_display", placeholder="ここに文字起こし結果が表示されます...")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("📋 結果をコピー", key="copy_current"):
        if current_transcription:
            st.write("結果をクリップボードにコピーしました")
        else:
            st.warning("コピーする結果がありません")
with col2:
    if st.button("🗑️ 結果をクリア", key="clear_current"):
        st.session_state['current_transcription'] = ""
        st.rerun()
with col3:
    if st.button("💾 結果を保存", key="save_current"):
        if current_transcription:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"transcription_{timestamp}.txt"
            if save_transcription(current_transcription, filename):
                st.success(f"結果を {filename} に保存しました")
            else:
                st.error("保存に失敗しました")
        else:
            st.warning("保存する結果がありません")

# ショートカットキー情報表示
if SHORTCUT_AVAILABLE and st.session_state.shortcut_handler.is_enabled():
    st.info("⌨️ **ショートカットキー**: F9=録音開始, F10=録音停止, F11=文字起こし, F12=テキストクリア")

# ショートカットイベントの処理
if SHORTCUT_AVAILABLE and 'shortcut_event' in st.session_state:
    handle_shortcut_event(st.session_state['shortcut_event'], st.session_state.shortcut_handler)
    del st.session_state['shortcut_event']

# 新機能の初期化（条件付き）
if settings.get('ui', {}).get('show_advanced_options', False):
    # 音声コマンド処理機能
    @st.cache_resource
    def get_voice_processor():
        return create_voice_command_processor()
    
    # ユーザー辞書機能
    @st.cache_resource
    def get_user_dict():
        return create_user_dictionary()
    
    # コマンド処理機能
    @st.cache_resource
    def get_command_processor():
        return create_command_processor()
    
    # 新機能のUI表示
    st.markdown("---")
    st.markdown("### 🆕 新機能")
    
    # 音声コマンド処理
    voice_processor = get_voice_processor()
    if voice_processor:
        st.markdown("#### 🎤 音声コマンド処理")
        voice_processor.render_ui()
    
    # ユーザー辞書
    user_dict = get_user_dict()
    if user_dict:
        st.markdown("#### 📖 ユーザー辞書")
        user_dict.render_ui()
    
    # コマンド処理
    command_processor = get_command_processor()
    if command_processor:
        st.markdown("#### ⚡ コマンド処理")
        command_processor.render_ui()

