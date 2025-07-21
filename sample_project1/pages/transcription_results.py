import streamlit as st
import os
import json
from datetime import datetime
import pandas as pd
from utils.transcription_manager import TranscriptionManager

st.header('文字起こし結果管理')

# 文字起こし管理クラスの初期化
transcription_manager = TranscriptionManager()

# セッション状態の初期化
if 'selected_file' not in st.session_state:
    st.session_state.selected_file = None
if 'edited_text' not in st.session_state:
    st.session_state.edited_text = None
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

# サイドバー - 検索・フィルタリング
with st.sidebar:
    st.subheader("検索・フィルタリング")
    
    # 検索機能
    search_query = st.text_input("キーワード検索", value=st.session_state.search_query)
    if search_query != st.session_state.search_query:
        st.session_state.search_query = search_query
    
    # 日付フィルタリング
    st.subheader("日付フィルタリング")
    date_filter = st.date_input(
        "日付を選択",
        value=None,
        help="特定の日付の文字起こしのみを表示"
    )
    
    # 統計情報
    st.subheader("統計情報")
    stats = transcription_manager.get_statistics()
    st.metric("総文字起こし数", stats["total_transcriptions"])
    st.metric("総単語数", stats["total_words"])
    st.metric("総文字数", stats["total_characters"])
    st.metric("平均文字数", stats["average_length"])

# メインコンテンツ
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("文字起こしファイル一覧")
    
    # ファイル一覧を取得
    files = transcription_manager.get_transcription_files()
    
    if not files:
        st.info("文字起こしファイルがありません")
    else:
        # 検索フィルタリング
        if st.session_state.search_query:
            search_results = transcription_manager.search_transcriptions(st.session_state.search_query)
            filtered_files = [entry.get('file_path') for entry in search_results if entry.get('file_path') in files]
            files = filtered_files
        
        # 日付フィルタリング
        if date_filter:
            date_str = date_filter.strftime("%Y-%m-%d")
            date_results = transcription_manager.filter_by_date(date_str)
            filtered_files = [entry.get('file_path') for entry in date_results if entry.get('file_path') in files]
            files = filtered_files
        
        if not files:
            st.info("条件に一致するファイルがありません")
        else:
            # ファイル選択
            file_options = [os.path.basename(f) for f in files]
            selected_index = st.selectbox(
                "ファイルを選択",
                range(len(file_options)),
                format_func=lambda x: f"{file_options[x]} ({os.path.getmtime(files[x]):%Y-%m-%d %H:%M})"
            )
            
            if selected_index is not None:
                st.session_state.selected_file = files[selected_index]

with col2:
    st.subheader("文字起こし結果")
    
    if st.session_state.selected_file:
        # ファイル情報表示
        file_info = os.stat(st.session_state.selected_file)
        st.caption(f"ファイル: {os.path.basename(st.session_state.selected_file)}")
        st.caption(f"更新日時: {datetime.fromtimestamp(file_info.st_mtime):%Y-%m-%d %H:%M:%S}")
        st.caption(f"サイズ: {file_info.st_size} bytes")
        
        # 文字起こし内容表示・編集
        content = transcription_manager.read_transcription_file(st.session_state.selected_file)
        
        # 編集モード切り替え
        edit_mode = st.checkbox("編集モード", key="edit_mode")
        
        if edit_mode:
            # 編集可能なテキストエリア
            edited_content = st.text_area(
                "文字起こし内容（編集可能）",
                value=content,
                height=400,
                key="editable_content"
            )
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("💾 保存"):
                    if transcription_manager.update_transcription(st.session_state.selected_file, edited_content):
                        st.success("保存しました！")
                        st.rerun()
                    else:
                        st.error("保存に失敗しました")
            
            with col_cancel:
                if st.button("❌ キャンセル"):
                    st.rerun()
        else:
            # 読み取り専用表示
            st.text_area(
                "文字起こし内容",
                value=content,
                height=400,
                disabled=True
            )
        
        # アクション
        st.subheader("アクション")
        
        col_copy, col_download, col_delete = st.columns(3)
        
        with col_copy:
            if st.button("📋 クリップボードにコピー"):
                st.write("クリップボードにコピーしました")
                # 実際のクリップボード機能は追加実装が必要
        
        with col_download:
            st.download_button(
                label="📥 ダウンロード",
                data=content,
                file_name=f"{os.path.basename(st.session_state.selected_file)}",
                mime="text/plain"
            )
        
        with col_delete:
            if st.button("🗑️ 削除", type="secondary"):
                if st.checkbox("本当に削除しますか？"):
                    if transcription_manager.delete_transcription(st.session_state.selected_file):
                        st.success("ファイルを削除しました")
                        st.session_state.selected_file = None
                        st.rerun()
                    else:
                        st.error("削除に失敗しました")
    else:
        st.info("左側からファイルを選択してください")

# 最近の文字起こし履歴
st.subheader("最近の文字起こし履歴")
history = transcription_manager.load_history()
if history:
    # 履歴をテーブル形式で表示
    history_data = []
    for entry in history[-10:]:  # 最新10件
        created_at = entry.get('created_at', '')
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                created_at = dt.strftime('%Y-%m-%d %H:%M')
            except:
                created_at = created_at[:19]
        
        history_data.append({
            '日時': created_at,
            '文字数': entry.get('text_length', 0),
            '単語数': entry.get('word_count', 0),
            '内容': entry.get('text', '')[:100] + '...' if len(entry.get('text', '')) > 100 else entry.get('text', '')
        })
    
    if history_data:
        df = pd.DataFrame(history_data)
        st.dataframe(df, use_container_width=True)
        
        # 詳細表示
        st.subheader("詳細表示")
        for entry in history[-5:]:
            with st.expander(f"📝 {entry.get('created_at', '')[:19]} - {entry.get('text', '')[:50]}..."):
                st.text(entry.get('text', ''))
                col_hist1, col_hist2, col_hist3 = st.columns(3)
                with col_hist1:
                    st.caption(f"文字数: {entry.get('text_length', 0)}")
                with col_hist2:
                    st.caption(f"単語数: {entry.get('word_count', 0)}")
                with col_hist3:
                    if entry.get('file_path'):
                        if st.button(f"開く", key=f"open_{entry.get('id', '')}"):
                            st.session_state.selected_file = entry.get('file_path')
                            st.rerun()
else:
    st.info("まだ文字起こし履歴がありません")

# 一括操作
st.subheader("一括操作")
col_bulk1, col_bulk2, col_bulk3 = st.columns(3)

with col_bulk1:
    if st.button("📊 統計レポート生成"):
        stats = transcription_manager.get_statistics()
        st.json(stats)

with col_bulk2:
    if st.button("📁 全ファイル一覧"):
        files = transcription_manager.get_transcription_files()
        if files:
            file_list = [os.path.basename(f) for f in files]
            st.write(file_list)
        else:
            st.info("ファイルがありません")

with col_bulk3:
    if st.button("🔄 ページ更新"):
        st.rerun() 