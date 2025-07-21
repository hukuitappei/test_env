import streamlit as st
from utils.command_processor import create_command_processor
from utils.transcription_manager import TranscriptionManager
from datetime import datetime
import os

st.set_page_config(page_title="コマンド", page_icon="⚡", layout="wide")

st.title("⚡ コマンド管理")

# コマンドプロセッサーの初期化
command_processor = create_command_processor()
transcription_manager = TranscriptionManager()

# タブ作成
tab1, tab2, tab3, tab4 = st.tabs(["🚀 コマンド実行", "📋 コマンド一覧", "➕ コマンド追加", "⚙️ 管理"])

with tab1:
    st.subheader("🚀 コマンド実行")
    
    # 文字起こし履歴から選択
    st.markdown("### 📝 文字起こし結果を選択")
    
    history = transcription_manager.load_history()
    if history:
        # 履歴から選択
        history_options = []
        for entry in history:
            created_at = entry.get('created_at', '')[:19]
            text_preview = entry.get('text', '')[:50] + "..." if len(entry.get('text', '')) > 50 else entry.get('text', '')
            history_options.append(f"{created_at} - {text_preview}")
        
        selected_history_index = st.selectbox(
            "文字起こし履歴から選択",
            range(len(history_options)),
            format_func=lambda x: history_options[x] if x < len(history_options) else "選択してください"
        )
        
        if selected_history_index < len(history):
            selected_text = history[selected_history_index].get('text', '')
            st.text_area("選択された文字起こし結果", selected_text, height=150, disabled=True)
            
            # コマンド選択
            st.markdown("### ⚡ 実行するコマンドを選択")
            enabled_commands = command_processor.get_enabled_commands()
            
            if enabled_commands:
                command_names = list(enabled_commands.keys())
                selected_command = st.selectbox("コマンド", command_names)
                
                if selected_command:
                    command_info = enabled_commands[selected_command]
                    st.write(f"**説明**: {command_info.get('description', '')}")
                    st.write(f"**出力形式**: {command_info.get('output_format', '')}")
                    
                    # コマンド実行
                    if st.button("🚀 コマンドを実行", type="primary"):
                        if selected_text:
                            result, message = command_processor.execute_command(selected_command, selected_text)
                            
                            st.success(message)
                            st.markdown("### 📄 実行結果")
                            st.text_area("結果", result, height=300)
                            
                            # ファイル保存オプション
                            if st.button("💾 結果をファイルに保存"):
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"{selected_command}_{timestamp}.txt"
                                
                                if command_processor.save_to_file(result, filename):
                                    st.success(f"ファイルを保存しました: {filename}")
                                    
                                    # ダウンロードボタン
                                    st.download_button(
                                        label="📥 ファイルをダウンロード",
                                        data=result,
                                        file_name=filename,
                                        mime="text/plain"
                                    )
                                else:
                                    st.error("ファイル保存に失敗しました")
                        else:
                            st.warning("文字起こし結果を選択してください")
            else:
                st.info("有効なコマンドがありません")
        else:
            st.info("文字起こし履歴を選択してください")
    else:
        st.info("文字起こし履歴がありません")
    
    # 直接テキスト入力
    st.markdown("---")
    st.markdown("### 📝 直接テキスト入力")
    
    direct_text = st.text_area("テキストを直接入力", height=150)
    
    if direct_text:
        enabled_commands = command_processor.get_enabled_commands()
        
        if enabled_commands:
            command_names = list(enabled_commands.keys())
            selected_direct_command = st.selectbox("コマンド", command_names, key="direct_command")
            
            if selected_direct_command:
                command_info = enabled_commands[selected_direct_command]
                st.write(f"**説明**: {command_info.get('description', '')}")
                
                if st.button("🚀 コマンドを実行", key="execute_direct"):
                    result, message = command_processor.execute_command(selected_direct_command, direct_text)
                    
                    st.success(message)
                    st.markdown("### 📄 実行結果")
                    st.text_area("結果", result, height=300, key="direct_result")
                    
                    # ファイル保存オプション
                    if st.button("💾 結果をファイルに保存", key="save_direct"):
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{selected_direct_command}_{timestamp}.txt"
                        
                        if command_processor.save_to_file(result, filename):
                            st.success(f"ファイルを保存しました: {filename}")
                            
                            # ダウンロードボタン
                            st.download_button(
                                label="📥 ファイルをダウンロード",
                                data=result,
                                file_name=filename,
                                mime="text/plain",
                                key="download_direct"
                            )
                        else:
                            st.error("ファイル保存に失敗しました")

with tab2:
    st.subheader("📋 コマンド一覧")
    
    # 統計情報
    stats = command_processor.get_statistics()
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("総コマンド数", stats["total_commands"])
    with col2:
        st.metric("有効コマンド数", stats["enabled_commands"])
    with col3:
        st.metric("無効コマンド数", stats["disabled_commands"])
    with col4:
        st.metric("最終更新", stats["last_updated"][:19] if stats["last_updated"] else "なし")
    
    # コマンド一覧
    all_commands = command_processor.get_all_commands()
    
    if all_commands:
        for name, command in all_commands.items():
            with st.expander(f"⚡ {name}", expanded=False):
                st.write(f"**説明**: {command.get('description', '')}")
                st.write(f"**出力形式**: {command.get('output_format', '')}")
                st.write(f"**有効**: {'はい' if command.get('enabled', True) else 'いいえ'}")
                
                with st.expander("LLMプロンプト", expanded=False):
                    st.code(command.get('llm_prompt', ''), language='text')
                
                col_cmd1, col_cmd2, col_cmd3 = st.columns(3)
                
                with col_cmd1:
                    st.caption(f"作成日: {command.get('created_at', '')[:19]}")
                with col_cmd2:
                    if 'last_updated' in command:
                        st.caption(f"更新日: {command['last_updated'][:19]}")
                with col_cmd3:
                    if st.button("🗑️ 削除", key=f"delete_cmd_{name}"):
                        if command_processor.delete_command(name):
                            st.success("削除しました")
                            st.rerun()
                        else:
                            st.error("削除に失敗しました")
    else:
        st.info("コマンドがありません")

with tab3:
    st.subheader("➕ コマンド追加")
    
    # 新しいコマンドの追加
    new_command_name = st.text_input("コマンド名")
    new_command_description = st.text_area("説明", height=100)
    new_command_prompt = st.text_area("LLMプロンプト", height=150, 
                                     help="LLMに送信するプロンプト。{text}で文字起こし結果を参照できます")
    
    # 出力形式の選択
    output_formats = [
        "bullet_points", "summary", "text_file", "llm_summary_file", 
        "key_points", "action_items", "custom"
    ]
    new_command_output_format = st.selectbox("出力形式", output_formats)
    
    if new_command_output_format == "custom":
        new_command_output_format = st.text_input("カスタム出力形式名")
    
    if st.button("➕ コマンドを追加"):
        if new_command_name and new_command_description and new_command_prompt:
            if command_processor.add_command(
                new_command_name, 
                new_command_description, 
                new_command_prompt, 
                new_command_output_format
            ):
                st.success(f"コマンド '{new_command_name}' を追加しました")
                st.rerun()
            else:
                st.error("コマンドの追加に失敗しました")
        else:
            st.warning("すべての項目を入力してください")

with tab4:
    st.subheader("⚙️ 管理")
    
    # 統計情報
    st.markdown("### 📊 統計情報")
    stats = command_processor.get_statistics()
    
    col_stats1, col_stats2 = st.columns(2)
    
    with col_stats1:
        st.write(f"**総コマンド数**: {stats['total_commands']}")
        st.write(f"**有効コマンド数**: {stats['enabled_commands']}")
        st.write(f"**無効コマンド数**: {stats['disabled_commands']}")
    
    with col_stats2:
        st.write(f"**最終更新**: {stats['last_updated'][:19] if stats['last_updated'] else 'なし'}")
    
    st.markdown("---")
    
    # エクスポート・インポート
    st.markdown("### 📤 エクスポート・インポート")
    
    col_export1, col_export2 = st.columns(2)
    
    with col_export1:
        st.markdown("#### 📤 エクスポート")
        export_format = st.selectbox("形式", ["json", "txt"], key="export_format")
        
        if st.button("📤 コマンドをエクスポート"):
            export_data = command_processor.export_commands(export_format)
            
            if export_format == "json":
                st.download_button(
                    label="📥 JSONファイルをダウンロード",
                    data=export_data,
                    file_name=f"commands_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            else:
                st.download_button(
                    label="📥 テキストファイルをダウンロード",
                    data=export_data,
                    file_name=f"commands_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
    
    with col_export2:
        st.markdown("#### 📥 インポート")
        import_format = st.selectbox("形式", ["json"], key="import_format")
        uploaded_file = st.file_uploader("コマンドファイルをアップロード", type=["json"])
        
        if uploaded_file is not None:
            if st.button("📥 コマンドをインポート"):
                try:
                    import_data = uploaded_file.read().decode('utf-8')
                    if command_processor.import_commands(import_data, import_format):
                        st.success("コマンドをインポートしました")
                        st.rerun()
                    else:
                        st.error("インポートに失敗しました")
                except Exception as e:
                    st.error(f"インポートエラー: {e}")
    
    st.markdown("---")
    
    # 出力ファイル管理
    st.markdown("### 📁 出力ファイル管理")
    
    output_dir = "outputs"
    if os.path.exists(output_dir):
        files = [f for f in os.listdir(output_dir) if f.endswith('.txt')]
        
        if files:
            st.write(f"**出力ファイル数**: {len(files)}")
            
            for file in sorted(files, reverse=True):
                file_path = os.path.join(output_dir, file)
                file_size = os.path.getsize(file_path)
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                with st.expander(f"📄 {file} ({file_size:,} bytes, {file_time.strftime('%Y-%m-%d %H:%M:%S')})"):
                    col_file1, col_file2, col_file3 = st.columns([2, 1, 1])
                    
                    with col_file1:
                        st.write(f"**ファイル名**: {file}")
                        st.write(f"**サイズ**: {file_size:,} bytes")
                        st.write(f"**作成日時**: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    with col_file2:
                        # ファイル内容表示
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            st.text_area("内容", content, height=100, key=f"content_{file}")
                        except Exception as e:
                            st.error(f"ファイル読み込みエラー: {e}")
                    
                    with col_file3:
                        # ダウンロードボタン
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_content = f.read()
                            st.download_button(
                                label="📥 ダウンロード",
                                data=file_content,
                                file_name=file,
                                mime="text/plain",
                                key=f"download_{file}"
                            )
                        except Exception as e:
                            st.error(f"ダウンロードエラー: {e}")
                        
                        # 削除ボタン
                        if st.button("🗑️ 削除", key=f"delete_file_{file}"):
                            try:
                                os.remove(file_path)
                                st.success("ファイルを削除しました")
                                st.rerun()
                            except Exception as e:
                                st.error(f"削除エラー: {e}")
        else:
            st.info("出力ファイルがありません")
    else:
        st.info("出力ディレクトリが存在しません")

# サイドバー
with st.sidebar:
    st.header("⚡ クイックアクセス")
    
    # 統計情報
    stats = command_processor.get_statistics()
    st.metric("総コマンド数", stats["total_commands"])
    st.metric("有効コマンド数", stats["enabled_commands"])
    
    st.markdown("---")
    
    # 最近のコマンド
    st.subheader("⚡ 最近のコマンド")
    
    all_commands = command_processor.get_all_commands()
    # 作成日でソート（最新順）
    sorted_commands = sorted(
        all_commands.items(), 
        key=lambda x: x[1].get("created_at", ""), 
        reverse=True
    )
    
    for name, command in sorted_commands[:5]:  # 最新5件
        created_at = command.get("created_at", "")[:19]
        st.caption(f"{created_at}")
        st.write(f"**{name}**")
        st.write(command.get("description", "")[:50] + "...")
        st.markdown("---") 