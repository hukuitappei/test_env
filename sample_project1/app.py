import streamlit as st
from utils.transcribe_utils import transcribe_audio_file
from utils.transcription_manager import TranscriptionManager
from utils.voice_commands import create_voice_command_processor
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import av
import numpy as np
import wave
import uuid
import os
import tempfile
from datetime import datetime

st.title("Tech Mentor 音声文字起こしアプリ")

# ヘルプセクション
with st.expander("ℹ️ 使用方法", expanded=False):
    st.markdown("""
    ### 🎯 主な機能
    
    **🎤 録音タブ**: リアルタイム録音と文字起こし
    - 録音開始→停止で自動文字起こし
    - 音声レベル監視
    - 結果の編集・保存
    
    **📁 ファイルアップロードタブ**: 既存音声ファイルの文字起こし
    - WAV、MP3、M4A、FLAC形式対応
    - ファイル情報表示
    - 文字起こし結果のダウンロード
    
    **📊 結果管理タブ**: 文字起こし履歴の管理
    - 検索・フィルタリング
    - 編集・削除機能
    - 統計情報表示
    
    ### 🔧 使い方
    
    1. **録音**: 録音タブで「録音開始」→「録音停止」
    2. **ファイル**: ファイルアップロードタブで音声ファイルをアップロード
    3. **管理**: 結果管理タブで履歴を確認・編集
    4. **詳細**: サイドバーから各機能ページにアクセス
    
    ### 💡 ヒント
    
    - 音声レベルが低い場合は警告が表示されます
    - 文字起こし結果は自動で履歴に保存されます
    - 検索機能で過去の文字起こしを素早く見つけられます
    """)

st.write("下の録音開始/停止ボタンで音声を録音し、録音停止時に自動で保存・再生・文字起こしを行います。\n\n録音・文字起こしはこのメインページから直接利用できます。\n\n設定や要約・辞書管理はサイドバーからどうぞ。\n")

# タブ作成
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎤 録音", "📁 ファイルアップロード", "📊 結果管理", "🎙️ 音声修正", "📚 ユーザー辞書"])

# 文字起こし管理クラスの初期化
transcription_manager = TranscriptionManager()
voice_processor = create_voice_command_processor()

# サイドバー
with st.sidebar:
    st.header("📊 クイックアクセス")
    
    # 統計情報
    stats = transcription_manager.get_statistics()
    st.metric("総文字起こし数", stats["total_transcriptions"])
    st.metric("総単語数", stats["total_words"])
    
    st.markdown("---")
    
    # クイックアクション
    if st.button("📋 結果管理ページへ"):
        st.switch_page("pages/transcription_results.py")
    
    if st.button("📚 ユーザー辞書"):
        st.switch_page("pages/user_dictionary.py")
    
    if st.button("⚡ コマンド管理"):
        st.switch_page("pages/commands.py")
    
    if st.button("📝 辞書管理"):
        st.switch_page("pages/dictionary.py")
    
    if st.button("📊 要約機能"):
        st.switch_page("pages/summary.py")
    
    if st.button("⚙️ 設定"):
        st.switch_page("pages/settings.py")
    
    st.markdown("---")
    
    # 最近の履歴（サイドバー版）
    st.subheader("📝 最近の履歴")
    history = transcription_manager.load_history()
    if history:
        recent_history = history[-3:]  # 最新3件
        for entry in reversed(recent_history):
            created_at = entry.get('created_at', '')[:19]
            text_preview = entry.get('text', '')[:30] + "..." if len(entry.get('text', '')) > 30 else entry.get('text', '')
            st.caption(f"{created_at}")
            st.write(text_preview)
            if st.button(f"詳細", key=f"sidebar_detail_{entry.get('id', '')}"):
                st.session_state["selected_history_item"] = entry
                st.rerun()
    else:
        st.info("履歴がありません")

# 録音状態管理
if "recording" not in st.session_state:
    st.session_state["recording"] = False
if "audio_saved" not in st.session_state:
    st.session_state["audio_saved"] = False
if "audio_path" not in st.session_state:
    st.session_state["audio_path"] = None
if "transcribed_text" not in st.session_state:
    st.session_state["transcribed_text"] = None
if "transcribe_error" not in st.session_state:
    st.session_state["transcribe_error"] = None
if "audio_level" not in st.session_state:
    st.session_state["audio_level"] = 0.0
if "search_query" not in st.session_state:
    st.session_state["search_query"] = ""
if "selected_history_item" not in st.session_state:
    st.session_state["selected_history_item"] = None

class AudioRecorder(AudioProcessorBase):
    def __init__(self):
        self.frames = []
        self.level = 0.0
    def recv_audio(self, frame: av.AudioFrame) -> av.AudioFrame:
        pcm = frame.to_ndarray()
        if st.session_state["recording"]:
            self.frames.append(pcm)
        rms = np.sqrt(np.mean(np.square(pcm.astype(np.float32))))
        self.level = rms
        st.session_state["audio_level"] = float(rms)
        return frame

recorder_ctx = webrtc_streamer(
    key="audio",
    mode=WebRtcMode.SENDRECV,
    audio_receiver_size=1024,
    audio_processor_factory=AudioRecorder,
    media_stream_constraints={"audio": True, "video": False},
)

with tab1:
    st.subheader("🎤 録音・文字起こし")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("録音開始", disabled=st.session_state["recording"]):
            st.session_state["recording"] = True
            st.session_state["audio_saved"] = False
            st.session_state["audio_path"] = None
            st.session_state["transcribed_text"] = None
            st.session_state["transcribe_error"] = None
            if recorder_ctx and recorder_ctx.audio_processor:
                recorder_ctx.audio_processor.frames = []
    with col2:
        if st.button("録音停止", disabled=not st.session_state["recording"]):
            st.session_state["recording"] = False

    # 録音中インジケータと音量メーターの表示
    if recorder_ctx and recorder_ctx.state.playing:
        if st.session_state["recording"]:
            st.markdown('<span style="color:red;font-weight:bold;">● 録音中</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span style="color:gray;font-weight:bold;">録音停止中</span>', unsafe_allow_html=True)
        audio_level = st.session_state.get("audio_level", 0.0)
        st.progress(min(int(audio_level * 100), 100), text=f"音声入力レベル: {audio_level:.2f}")

    # 録音停止時に保存・再生・文字起こし
    if recorder_ctx and recorder_ctx.audio_processor and not st.session_state["recording"] and not st.session_state["audio_saved"]:
        frames = recorder_ctx.audio_processor.frames
        if frames:
            try:
                session_id = str(uuid.uuid4())
                temp_dir = "audio_chunks"
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, f"{session_id}.wav")
                audio = np.concatenate(frames)
                
                # 音声レベルチェック
                audio_array = np.frombuffer(audio.tobytes(), dtype=np.int16)
                rms = np.sqrt(np.mean(audio_array**2))
                
                if rms < 100:
                    st.warning("⚠️ 音声レベルが低いです。マイクの音量を確認してください。")
                
                with wave.open(temp_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(48000)
                    wf.writeframes(audio.tobytes())
                
                st.session_state["audio_saved"] = True
                st.session_state["audio_path"] = temp_path
                
                # 再生
                with open(temp_path, "rb") as f:
                    st.audio(f.read(), format="audio/wav")
                
                # 文字起こし
                with st.spinner("文字起こし中..."):
                    text, error_message = transcribe_audio_file(temp_path, session_id, 0, "transcriptions", return_error=True)
                
                if text:
                    st.session_state["transcribed_text"] = text
                    st.session_state["transcribe_error"] = None
                    
                    # 文字起こし管理クラスに追加
                    transcription_manager.add_transcription(session_id, 0, text, temp_path)
                    
                    # 成功メッセージ
                    st.success("✅ 文字起こしが完了しました！")
                else:
                    st.session_state["transcribed_text"] = None
                    st.session_state["transcribe_error"] = error_message
                    st.error("❌ 文字起こしに失敗しました")
                
                # framesをリセット
                recorder_ctx.audio_processor.frames = []
                
            except Exception as e:
                st.error(f"録音処理エラー: {str(e)}")
                st.session_state["audio_saved"] = True
        else:
            st.warning("録音データがありません。録音開始→録音停止の順で操作してください。")
            st.session_state["audio_saved"] = True  # 空でも一度だけ警告

    # 結果表示
    if st.session_state["audio_path"]:
        st.success("録音データを保存しました")
        with open(st.session_state["audio_path"], "rb") as f:
            st.audio(f.read(), format="audio/wav")

    if st.session_state["transcribed_text"]:
        st.success("文字起こし結果:")
        
        # 結果表示エリア
        col_result1, col_result2 = st.columns([3, 1])
        
        with col_result1:
            # 編集可能なテキストエリア
            edited_text = st.text_area(
                "テキスト（編集可能）", 
                st.session_state["transcribed_text"], 
                height=200,
                key="editable_transcription"
            )
            
            # 編集内容が変更された場合の保存
            if edited_text != st.session_state["transcribed_text"]:
                if st.button("💾 編集内容を保存"):
                    # 履歴を更新
                    history = transcription_manager.load_history()
                    if history:
                        latest_entry = history[-1]
                        if transcription_manager.update_transcription(latest_entry.get('file_path', ''), edited_text):
                            st.session_state["transcribed_text"] = edited_text
                            st.success("編集内容を保存しました！")
                            st.rerun()
                        else:
                            st.error("保存に失敗しました")
        
        with col_result2:
            # アクションボタン
            st.subheader("アクション")
            
            # ダウンロードボタン
            st.download_button(
                label="📥 ダウンロード",
                data=edited_text if 'edited_text' in locals() else st.session_state["transcribed_text"],
                file_name=f"transcription_{session_id}.txt",
                mime="text/plain"
            )
            
            # 結果管理ページへのリンク
            if st.button("📋 結果管理ページへ"):
                st.switch_page("pages/transcription_results.py")
            
            # 統計情報
            stats = transcription_manager.get_statistics()
            st.subheader("統計")
            st.metric("総文字起こし数", stats["total_transcriptions"])
            st.metric("総文字数", stats["total_characters"])
            st.metric("総単語数", stats["total_words"])

    if st.session_state["transcribe_error"]:
        st.error("文字起こしに失敗しました")
        st.error(f"詳細: {st.session_state['transcribe_error']}")

with tab2:
    st.subheader("📁 ファイルアップロード")
    
    # ファイルアップロード
    uploaded_file = st.file_uploader(
        "音声ファイルをアップロード", 
        type=['wav', 'mp3', 'm4a', 'flac'],
        help="WAV、MP3、M4A、FLAC形式の音声ファイルをアップロードできます"
    )
    
    if uploaded_file is not None:
        # ファイル情報表示
        file_details = {
            "ファイル名": uploaded_file.name,
            "ファイルサイズ": f"{uploaded_file.size / 1024:.1f} KB",
            "ファイルタイプ": uploaded_file.type
        }
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**ファイル情報:**")
            for key, value in file_details.items():
                st.write(f"- {key}: {value}")
        
        with col2:
            # 文字起こし実行ボタン
            if st.button("🔍 文字起こし実行", type="primary"):
                try:
                    # 一時ファイルとして保存
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_file_path = tmp_file.name
                    
                    # 文字起こし実行
                    with st.spinner("文字起こし中..."):
                        session_id = str(uuid.uuid4())
                        text, error_message = transcribe_audio_file(tmp_file_path, session_id, 0, "transcriptions", return_error=True)
                    
                    if text:
                        # 文字起こし管理クラスに追加
                        transcription_manager.add_transcription(session_id, 0, text, tmp_file_path)
                        
                        # 結果表示
                        st.success("文字起こし完了！")
                        st.text_area("文字起こし結果", text, height=200)
                        
                        # アクションボタン
                        col_action1, col_action2 = st.columns(2)
                        with col_action1:
                            st.download_button(
                                label="📥 ダウンロード",
                                data=text,
                                file_name=f"transcription_{uploaded_file.name}.txt",
                                mime="text/plain"
                            )
                        with col_action2:
                            if st.button("📋 結果管理ページへ"):
                                st.switch_page("pages/transcription_results.py")
                    else:
                        st.error(f"文字起こしに失敗しました: {error_message}")
                    
                    # 一時ファイルを削除
                    try:
                        os.unlink(tmp_file_path)
                    except:
                        pass
                        
                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}")

with tab3:
    st.subheader("📊 結果管理")
    
    # 検索機能
    col_search1, col_search2 = st.columns([3, 1])
    with col_search1:
        search_query = st.text_input(
            "🔍 キーワード検索", 
            value=st.session_state["search_query"],
            placeholder="文字起こし内容で検索..."
        )
        if search_query != st.session_state["search_query"]:
            st.session_state["search_query"] = search_query
    
    with col_search2:
        if st.button("🔄 検索クリア"):
            st.session_state["search_query"] = ""
            st.rerun()
    
    # 統計情報
    stats = transcription_manager.get_statistics()
    col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
    
    with col_stats1:
        st.metric("総文字起こし数", stats["total_transcriptions"])
    with col_stats2:
        st.metric("総単語数", stats["total_words"])
    with col_stats3:
        st.metric("総文字数", stats["total_characters"])
    with col_stats4:
        st.metric("平均文字数", stats["average_length"])
    
    # 履歴表示
    st.subheader("📝 文字起こし履歴")
    history = transcription_manager.load_history()
    
    if history:
        # 検索フィルタリング
        if st.session_state["search_query"]:
            filtered_history = transcription_manager.search_transcriptions(st.session_state["search_query"])
            history = filtered_history
            st.info(f"検索結果: {len(history)}件")
        
        if history:
            # 履歴をテーブル形式で表示
            for i, entry in enumerate(reversed(history[-10:])):  # 最新10件
                created_at = entry.get('created_at', '')
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_at = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        created_at = created_at[:19]
                
                with st.expander(f"📝 {created_at} - {entry.get('text', '')[:50]}...", expanded=False):
                    # テキスト表示
                    st.text_area(
                        "文字起こし内容", 
                        entry.get('text', ''), 
                        height=150,
                        key=f"history_text_{i}",
                        disabled=True
                    )
                    
                    # 情報とアクション
                    col_info1, col_info2, col_info3, col_info4 = st.columns(4)
                    
                    with col_info1:
                        st.caption(f"📊 文字数: {entry.get('text_length', 0)}")
                    with col_info2:
                        st.caption(f"📝 単語数: {entry.get('word_count', 0)}")
                    with col_info3:
                        st.caption(f"📅 作成日: {created_at}")
                    with col_info4:
                        if entry.get('file_path'):
                            if st.button(f"📁 ファイルを開く", key=f"open_file_{i}"):
                                st.session_state["selected_history_item"] = entry
                                st.rerun()
                    
                    # アクションボタン
                    col_action1, col_action2, col_action3 = st.columns(3)
                    
                    with col_action1:
                        st.download_button(
                            label="📥 ダウンロード",
                            data=entry.get('text', ''),
                            file_name=f"transcription_{entry.get('id', 'unknown')}.txt",
                            mime="text/plain",
                            key=f"download_{i}"
                        )
                    
                    with col_action2:
                        if st.button("✏️ 編集", key=f"edit_{i}"):
                            st.session_state["selected_history_item"] = entry
                            st.rerun()
                    
                    with col_action3:
                        if st.button("🗑️ 削除", key=f"delete_{i}"):
                            if entry.get('file_path'):
                                if transcription_manager.delete_transcription(entry.get('file_path')):
                                    st.success("削除しました")
                                    st.rerun()
                                else:
                                    st.error("削除に失敗しました")
                            else:
                                st.error("ファイルパスが見つかりません")
        else:
            st.info("検索条件に一致する履歴がありません")
    else:
        st.info("まだ文字起こし履歴がありません")
    
    # 選択された履歴アイテムの詳細表示
    if st.session_state["selected_history_item"]:
        st.markdown("---")
        st.subheader("📋 詳細表示・編集")
        
        selected_item = st.session_state["selected_history_item"]
        
        # 編集モード
        edited_content = st.text_area(
            "文字起こし内容（編集可能）",
            selected_item.get('text', ''),
            height=200,
            key="edit_selected_item"
        )
        
        col_edit1, col_edit2, col_edit3 = st.columns(3)
        
        with col_edit1:
            if st.button("💾 保存"):
                if selected_item.get('file_path'):
                    if transcription_manager.update_transcription(selected_item.get('file_path'), edited_content):
                        st.success("保存しました！")
                        st.session_state["selected_history_item"] = None
                        st.rerun()
                    else:
                        st.error("保存に失敗しました")
                else:
                    st.error("ファイルパスが見つかりません")
        
        with col_edit2:
            if st.button("❌ キャンセル"):
                st.session_state["selected_history_item"] = None
                st.rerun()
        
        with col_edit3:
            if st.button("📋 結果管理ページへ"):
                st.switch_page("pages/transcription_results.py")

with tab4:
    st.subheader("🎙️ 音声修正")
    
    # 音声修正機能の説明
    st.info("""
    **音声修正機能の使い方:**
    
    1. **音声コマンドを聞き取る**: 「修正」ボタンを押して音声で指示
    2. **コマンドを解析**: 音声からコマンドと内容を自動解析
    3. **修正を適用**: 文字起こし結果に修正を適用
    
    **対応コマンド:**
    - 修正: 「〇〇を△△に修正」
    - 削除: 「〇〇を削除」
    - 追加: 「〇〇を追加」
    - 要約: 「要約して」
    - 箇条書き: 「箇条書きにして」
    """)
    
    # 修正対象の文字起こし結果を選択
    st.markdown("### 📝 修正対象を選択")
    
    # 現在の文字起こし結果
    if st.session_state.get("transcribed_text"):
        current_text = st.session_state["transcribed_text"]
        st.text_area("現在の文字起こし結果", current_text, height=200, key="voice_correction_text")
        
        # 音声コマンド機能
        st.markdown("### 🎤 音声コマンド")
        
        col_voice1, col_voice2 = st.columns(2)
        
        with col_voice1:
            if st.button("🎤 音声コマンドを聞き取る", type="primary"):
                try:
                    # 音声を聞き取る
                    voice_text = voice_processor.listen_for_command(duration=5)
                    
                    if voice_text:
                        st.session_state["voice_command"] = voice_text
                        st.success(f"音声を認識しました: {voice_text}")
                        
                        # コマンドを解析
                        command, content = voice_processor.parse_command(voice_text)
                        st.session_state["parsed_command"] = command
                        st.session_state["parsed_content"] = content
                        
                        st.info(f"**検出されたコマンド**: {command}")
                        st.info(f"**内容**: {content}")
                    else:
                        st.warning("音声を認識できませんでした")
                        
                except Exception as e:
                    st.error(f"音声認識エラー: {e}")
        
        with col_voice2:
            if st.button("🔄 コマンドを実行", disabled=not st.session_state.get("parsed_command")):
                if st.session_state.get("parsed_command") and st.session_state.get("parsed_content"):
                    command = st.session_state["parsed_command"]
                    content = st.session_state["parsed_content"]
                    current_text = st.session_state.get("transcribed_text", "")
                    
                    # コマンドを実行
                    new_text, message = voice_processor.execute_command(command, content, current_text)
                    
                    if new_text != current_text:
                        st.session_state["transcribed_text"] = new_text
                        st.success(message)
                        st.rerun()
                    else:
                        st.warning(message)
        
        # 手動コマンド入力
        st.markdown("### ✏️ 手動コマンド入力")
        
        col_manual1, col_manual2 = st.columns(2)
        
        with col_manual1:
            manual_command = st.selectbox(
                "コマンド",
                ["修正", "削除", "追加", "要約", "箇条書き"],
                key="manual_command"
            )
        
        with col_manual2:
            manual_content = st.text_input("内容", key="manual_content")
        
        if st.button("🔄 手動コマンドを実行"):
            if manual_content:
                new_text, message = voice_processor.execute_command(manual_command, manual_content, current_text)
                
                if new_text != current_text:
                    st.session_state["transcribed_text"] = new_text
                    st.success(message)
                    st.rerun()
                else:
                    st.warning(message)
            else:
                st.warning("内容を入力してください")
        
        # 修正履歴
        if st.session_state.get("voice_command"):
            st.markdown("### 📋 修正履歴")
            st.write(f"**最後の音声コマンド**: {st.session_state['voice_command']}")
            if st.session_state.get("parsed_command"):
                st.write(f"**解析結果**: {st.session_state['parsed_command']} - {st.session_state['parsed_content']}")
    
    else:
        st.info("文字起こし結果がありません。まず録音タブで文字起こしを実行してください。")

with tab5:
    st.subheader("📚 ユーザー辞書")
    
    # ユーザー辞書機能の説明
    st.info("""
    **ユーザー辞書機能:**
    
    - カスタム用語や略語を管理
    - 文字起こし結果の理解向上
    - 専門用語の定義と例文
    """)
    
    # 辞書ページへのリンク
    if st.button("📚 辞書管理ページへ"):
        st.switch_page("pages/user_dictionary.py")
    
    # 簡単な辞書表示
    from utils.user_dictionary import create_user_dictionary
    user_dict = create_user_dictionary()
    
    stats = user_dict.get_statistics()
    col_dict1, col_dict2 = st.columns(2)
    
    with col_dict1:
        st.metric("総エントリ数", stats["total_entries"])
    with col_dict2:
        st.metric("カテゴリ数", stats["total_categories"])
    
    # 最近のエントリ
    st.markdown("### 📝 最近の辞書エントリ")
    
    all_entries = []
    for category_name, category_data in user_dict.dictionary.get("categories", {}).items():
        for word, entry in category_data.get("entries", {}).items():
            all_entries.append({
                "category": category_name,
                "word": word,
                "entry": entry
            })
    
    # 作成日でソート（最新順）
    all_entries.sort(key=lambda x: x["entry"].get("created_at", ""), reverse=True)
    
    for entry in all_entries[:3]:  # 最新3件
        with st.expander(f"📝 {entry['word']} ({entry['category']})", expanded=False):
            st.write(f"**定義**: {entry['entry']['definition']}")
            if entry['entry'].get("examples"):
                st.write("**例文**:")
                for i, example in enumerate(entry["entry"]["examples"], 1):
                    st.write(f"{i}. {example}")



