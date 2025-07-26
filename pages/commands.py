import streamlit as st
import sys
import os
from datetime import datetime

# 親ディレクトリをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.command_processor import create_command_processor

st.set_page_config(page_title="コマンド管理", page_icon="⚙️", layout="wide")

st.title("⚙️ コマンド管理")

# コマンドプロセッサーの初期化
@st.cache_resource
def get_command_processor():
    return create_command_processor()

command_processor = get_command_processor()

# タブを作成
tab1, tab2, tab3, tab4 = st.tabs(["🚀 コマンド実行", "📋 コマンド一覧", "➕ コマンド追加", "⚙️ 管理"])

with tab1:
    st.subheader("🚀 コマンド実行")
    
    # 実行方法選択
    execution_method = st.radio("実行方法", ["文字起こし結果から実行", "直接テキスト入力"])
    
    if execution_method == "文字起こし結果から実行":
        # 文字起こし結果の選択
        st.markdown("### 📝 文字起こし結果を選択")
        
        # 録音ファイルからの文字起こし結果
        recordings_dir = "../recordings"
        if os.path.exists(recordings_dir):
            files = [f for f in os.listdir(recordings_dir) if f.endswith('.wav')]
            
            if files:
                selected_file = st.selectbox("録音ファイルを選択", files)
                
                if selected_file:
                    file_path = os.path.join(recordings_dir, selected_file)
                    
                    # 文字起こし実行
                    if st.button("🔍 文字起こし実行"):
                        try:
                            # 文字起こし処理（簡易版）
                            with st.spinner("文字起こし中..."):
                                # 実際の実装ではWhisperを使用
                                transcription = f"サンプル文字起こし結果: {selected_file}"
                                st.session_state['current_transcription'] = transcription
                                st.success("文字起こし完了")
                        except Exception as e:
                            st.error(f"文字起こしエラー: {e}")
                    
                    # 保存された文字起こし結果を表示
                    if 'current_transcription' in st.session_state:
                        st.markdown("### 📝 現在の文字起こし結果")
                        st.text_area("文字起こし結果", st.session_state['current_transcription'], height=150)
                        
                        # コマンド実行
                        st.markdown("### ⚙️ コマンド実行")
                        enabled_commands = command_processor.get_enabled_commands()
                        
                        if enabled_commands:
                            selected_command = st.selectbox("実行するコマンド", list(enabled_commands.keys()))
                            
                            if st.button("🚀 コマンド実行"):
                                result, message = command_processor.execute_command(
                                    selected_command, 
                                    st.session_state['current_transcription']
                                )
                                
                                st.success(message)
                                st.markdown("### 📋 実行結果")
                                st.text_area("結果", result, height=200)
                                
                                # ファイル保存
                                if st.button("💾 結果をファイルに保存"):
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    filename = f"command_result_{selected_command}_{timestamp}.txt"
                                    
                                    if command_processor.save_to_file(result, filename):
                                        st.success(f"ファイルを保存しました: {filename}")
                                        
                                        # ダウンロードボタン
                                        with open(os.path.join("outputs", filename), 'r', encoding='utf-8') as f:
                                            file_content = f.read()
                                        
                                        st.download_button(
                                            label="📥 ダウンロード",
                                            data=file_content,
                                            file_name=filename,
                                            mime="text/plain"
                                        )
                                    else:
                                        st.error("ファイル保存に失敗しました")
                        else:
                            st.warning("有効なコマンドがありません")
            else:
                st.info("録音ファイルがありません")
        else:
            st.info("recordingsディレクトリが存在しません")
    
    else:  # 直接テキスト入力
        st.markdown("### 📝 テキスト入力")
        input_text = st.text_area("処理するテキストを入力", height=150)
        
        if input_text:
            # コマンド実行
            st.markdown("### ⚙️ コマンド実行")
            enabled_commands = command_processor.get_enabled_commands()
            
            if enabled_commands:
                selected_command = st.selectbox("実行するコマンド", list(enabled_commands.keys()), key="direct_command")
                
                if st.button("🚀 コマンド実行", key="execute_direct"):
                    result, message = command_processor.execute_command(selected_command, input_text)
                    
                    st.success(message)
                    st.markdown("### 📋 実行結果")
                    st.text_area("結果", result, height=200, key="direct_result")
                    
                    # ファイル保存
                    if st.button("💾 結果をファイルに保存", key="save_direct"):
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"command_result_{selected_command}_{timestamp}.txt"
                        
                        if command_processor.save_to_file(result, filename):
                            st.success(f"ファイルを保存しました: {filename}")
                            
                            # ダウンロードボタン
                            with open(os.path.join("outputs", filename), 'r', encoding='utf-8') as f:
                                file_content = f.read()
                            
                            st.download_button(
                                label="📥 ダウンロード",
                                data=file_content,
                                file_name=filename,
                                mime="text/plain",
                                key="download_direct"
                            )
                        else:
                            st.error("ファイル保存に失敗しました")
            else:
                st.warning("有効なコマンドがありません")

with tab2:
    st.subheader("📋 コマンド一覧")
    
    commands = command_processor.get_all_commands()
    
    if commands:
        for name, command in commands.items():
            with st.expander(f"⚙️ {name}"):
                st.write(f"**説明:** {command.get('description', '')}")
                st.write(f"**出力形式:** {command.get('output_format', '')}")
                st.write(f"**有効:** {'はい' if command.get('enabled', True) else 'いいえ'}")
                
                with st.expander("LLMプロンプト"):
                    st.code(command.get('llm_prompt', ''), language='text')
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**作成日:** {command.get('created_at', '')[:10]}")
                with col2:
                    if 'last_updated' in command:
                        st.write(f"**更新日:** {command['last_updated'][:10]}")
                
                # 編集・削除ボタン
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ 編集", key=f"edit_cmd_{name}"):
                        st.session_state[f"editing_cmd_{name}"] = True
                
                with col2:
                    if st.button("🗑️ 削除", key=f"delete_cmd_{name}"):
                        if command_processor.delete_command(name):
                            st.success(f"コマンド '{name}' を削除しました")
                            st.rerun()
                
                # 編集フォーム
                if st.session_state.get(f"editing_cmd_{name}", False):
                    with st.form(key=f"edit_cmd_form_{name}"):
                        new_description = st.text_input("説明", command.get("description", ""), key=f"desc_{name}")
                        new_prompt = st.text_area("LLMプロンプト", command.get("llm_prompt", ""), key=f"prompt_{name}")
                        new_format = st.selectbox("出力形式", 
                                                ["bullet_points", "summary", "text_file", "llm_summary_file", "key_points", "action_items"],
                                                index=["bullet_points", "summary", "text_file", "llm_summary_file", "key_points", "action_items"].index(command.get("output_format", "bullet_points")),
                                                key=f"format_{name}")
                        new_enabled = st.checkbox("有効", command.get("enabled", True), key=f"enabled_{name}")
                        
                        if st.form_submit_button("更新"):
                            if command_processor.update_command(name, new_description, new_prompt, new_format, new_enabled):
                                st.success(f"コマンド '{name}' を更新しました")
                                st.session_state[f"editing_cmd_{name}"] = False
                                st.rerun()
    else:
        st.info("コマンドがありません")

with tab3:
    st.subheader("➕ コマンド追加")
    
    with st.form("add_command_form"):
        name = st.text_input("コマンド名")
        description = st.text_input("説明")
        llm_prompt = st.text_area("LLMプロンプト（{text}でテキストを指定）")
        output_format = st.selectbox("出力形式", 
                                   ["bullet_points", "summary", "text_file", "llm_summary_file", "key_points", "action_items"])
        
        submitted = st.form_submit_button("追加")
        
        if submitted:
            if not name or not description or not llm_prompt:
                st.error("コマンド名、説明、LLMプロンプトは必須です")
            else:
                if command_processor.add_command(name, description, llm_prompt, output_format):
                    st.success(f"コマンド '{name}' を追加しました")
                    st.rerun()
                else:
                    st.error("コマンドの追加に失敗しました")

with tab4:
    st.subheader("⚙️ 管理")
    
    # 統計情報
    stats = command_processor.get_statistics()
    st.markdown("### 📊 統計情報")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("総コマンド数", stats["total_commands"])
    with col2:
        st.metric("有効コマンド数", stats["enabled_commands"])
    with col3:
        st.metric("無効コマンド数", stats["disabled_commands"])
    
    st.write(f"**最終更新:** {stats['last_updated'][:19] if stats['last_updated'] else 'なし'}")
    
    # インポート・エクスポート
    st.markdown("### 📁 インポート・エクスポート")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📤 エクスポート")
        export_format = st.selectbox("形式", ["json", "txt"], key="cmd_export_format")
        
        if st.button("エクスポート"):
            export_data = command_processor.export_commands(export_format)
            st.download_button(
                label="📥 ダウンロード",
                data=export_data,
                file_name=f"commands_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}",
                mime="text/plain"
            )
    
    with col2:
        st.markdown("#### 📥 インポート")
        import_format = st.selectbox("形式", ["json"], key="cmd_import_format")
        uploaded_file = st.file_uploader("コマンドファイルをアップロード", type=[import_format], key="cmd_upload")
        
        if uploaded_file is not None:
            file_content = uploaded_file.read().decode('utf-8')
            if st.button("インポート"):
                if command_processor.import_commands(file_content, import_format):
                    st.success("コマンドをインポートしました")
                    st.rerun()
                else:
                    st.error("インポートに失敗しました")
    
    # 出力ファイル管理
    st.markdown("### 📁 出力ファイル管理")
    
    outputs_dir = "outputs"
    if os.path.exists(outputs_dir):
        files = [f for f in os.listdir(outputs_dir) if f.endswith('.txt')]
        
        if files:
            st.write(f"**出力ファイル数:** {len(files)}")
            
            for file in sorted(files, reverse=True):
                file_path = os.path.join(outputs_dir, file)
                file_size = os.path.getsize(file_path)
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"📄 {file}")
                    st.write(f"サイズ: {file_size:,} bytes, 作成: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                with col2:
                    # ダウンロードボタン
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    
                    st.download_button(
                        label="📥",
                        data=file_content,
                        file_name=file,
                        mime="text/plain",
                        key=f"download_{file}"
                    )
                
                with col3:
                    if st.button("🗑️", key=f"delete_output_{file}"):
                        try:
                            os.remove(file_path)
                            st.success("ファイルを削除しました")
                            st.rerun()
                        except Exception as e:
                            st.error(f"削除エラー: {e}")
        else:
            st.info("出力ファイルがありません")
    else:
        st.info("outputsディレクトリが存在しません")

# サイドバーにクイックアクセス
st.sidebar.markdown("## ⚙️ クイックアクセス")
if st.sidebar.button("🏠 メインページに戻る"):
    st.switch_page("app.py") 