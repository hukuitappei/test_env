import streamlit as st
import sys
import os
from datetime import datetime

# 親ディレクトリをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.user_dictionary import create_user_dictionary

st.set_page_config(page_title="ユーザー辞書管理", page_icon="📚", layout="wide")

st.title("📚 ユーザー辞書管理")

# ユーザー辞書の初期化
@st.cache_resource
def get_user_dictionary():
    return create_user_dictionary()

user_dict = get_user_dictionary()

# タブを作成
tab1, tab2, tab3, tab4 = st.tabs(["📖 辞書表示", "➕ エントリ追加", "🔍 検索", "⚙️ 管理"])

with tab1:
    st.subheader("📖 辞書表示")
    
    # 統計情報
    stats = user_dict.get_statistics()
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("総エントリ数", stats["total_entries"])
    with col2:
        st.metric("カテゴリ数", stats["total_categories"])
    with col3:
        st.metric("最終更新", stats["last_updated"][:10] if stats["last_updated"] else "なし")
    with col4:
        st.metric("辞書サイズ", f"{len(str(user_dict.dictionary)):,} 文字")
    
    # カテゴリ別表示
    categories = user_dict.get_categories()
    
    if categories:
        selected_category = st.selectbox("カテゴリを選択", categories)
        
        if selected_category:
            entries = user_dict.get_entries_by_category(selected_category)
            
            if entries:
                st.markdown(f"### {selected_category} ({len(entries)}件)")
                
                for word, entry in entries.items():
                    with st.expander(f"📝 {word}"):
                        st.write(f"**定義:** {entry['definition']}")
                        
                        if entry.get("examples"):
                            st.write("**例文:**")
                            for example in entry["examples"]:
                                st.write(f"• {example}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**作成日:** {entry.get('created_at', '')[:10]}")
                        with col2:
                            st.write(f"**更新日:** {entry.get('last_updated', '')[:10]}")
                        
                        # 編集・削除ボタン
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✏️ 編集", key=f"edit_{word}"):
                                st.session_state[f"editing_{word}"] = True
                        
                        with col2:
                            if st.button("🗑️ 削除", key=f"delete_{word}"):
                                if user_dict.delete_entry(selected_category, word):
                                    st.success(f"'{word}' を削除しました")
                                    st.rerun()
                        
                        # 編集フォーム
                        if st.session_state.get(f"editing_{word}", False):
                            with st.form(key=f"edit_form_{word}"):
                                new_definition = st.text_area("定義", entry["definition"], key=f"def_{word}")
                                new_examples = st.text_area("例文（改行区切り）", 
                                                           "\n".join(entry.get("examples", [])), 
                                                           key=f"ex_{word}")
                                
                                if st.form_submit_button("更新"):
                                    examples_list = [ex.strip() for ex in new_examples.split('\n') if ex.strip()]
                                    if user_dict.update_entry(selected_category, word, new_definition, examples_list):
                                        st.success(f"'{word}' を更新しました")
                                        st.session_state[f"editing_{word}"] = False
                                        st.rerun()
            else:
                st.info(f"カテゴリ '{selected_category}' にエントリがありません")
    else:
        st.info("辞書にカテゴリがありません")

with tab2:
    st.subheader("➕ エントリ追加")
    
    with st.form("add_entry_form"):
        # カテゴリ選択または新規作成
        categories = user_dict.get_categories()
        category_option = st.selectbox("カテゴリ", ["新規作成"] + categories)
        
        if category_option == "新規作成":
            new_category = st.text_input("新しいカテゴリ名")
            category_description = st.text_input("カテゴリの説明")
        else:
            new_category = None
            category_description = None
        
        # エントリ情報
        word = st.text_input("単語・用語")
        definition = st.text_area("定義・説明")
        examples = st.text_area("例文（改行区切りで複数入力可能）")
        
        submitted = st.form_submit_button("追加")
        
        if submitted:
            if not word or not definition:
                st.error("単語と定義は必須です")
            else:
                # 新規カテゴリの作成
                if category_option == "新規作成" and new_category:
                    if user_dict.add_category(new_category, category_description or ""):
                        st.success(f"カテゴリ '{new_category}' を作成しました")
                        category_to_use = new_category
                    else:
                        st.error("カテゴリの作成に失敗しました")
                        category_to_use = None
                else:
                    category_to_use = category_option
                
                if category_to_use:
                    # 例文をリストに変換
                    examples_list = [ex.strip() for ex in examples.split('\n') if ex.strip()]
                    
                    if user_dict.add_entry(category_to_use, word, definition, examples_list):
                        st.success(f"エントリ '{word}' を追加しました")
                        st.rerun()
                    else:
                        st.error("エントリの追加に失敗しました")

with tab3:
    st.subheader("🔍 検索")
    
    search_query = st.text_input("検索キーワード")
    
    if search_query:
        results = user_dict.search_entries(search_query)
        
        if results:
            st.write(f"**検索結果: {len(results)}件**")
            
            for result in results:
                with st.expander(f"📝 {result['word']} ({result['category']})"):
                    st.write(f"**定義:** {result['entry']['definition']}")
                    
                    if result['entry'].get("examples"):
                        st.write("**例文:**")
                        for example in result["entry"]["examples"]:
                            st.write(f"• {example}")
                    
                    st.write(f"**カテゴリ:** {result['category']}")
        else:
            st.info("検索結果がありません")
    else:
        st.info("検索キーワードを入力してください")

with tab4:
    st.subheader("⚙️ 管理")
    
    # 統計情報
    stats = user_dict.get_statistics()
    st.markdown("### 📊 統計情報")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**総エントリ数:** {stats['total_entries']}")
        st.write(f"**カテゴリ数:** {stats['total_categories']}")
    
    with col2:
        st.write(f"**最終更新:** {stats['last_updated'][:19] if stats['last_updated'] else 'なし'}")
        
        # カテゴリ別統計
        if stats['category_stats']:
            st.write("**カテゴリ別エントリ数:**")
            for category, count in stats['category_stats'].items():
                st.write(f"• {category}: {count}件")
    
    # インポート・エクスポート
    st.markdown("### 📁 インポート・エクスポート")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📤 エクスポート")
        export_format = st.selectbox("形式", ["json", "txt"], key="export_format")
        
        if st.button("エクスポート"):
            export_data = user_dict.export_dictionary(export_format)
            st.download_button(
                label="📥 ダウンロード",
                data=export_data,
                file_name=f"user_dictionary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}",
                mime="text/plain"
            )
    
    with col2:
        st.markdown("#### 📥 インポート")
        import_format = st.selectbox("形式", ["json"], key="import_format")
        uploaded_file = st.file_uploader("辞書ファイルをアップロード", type=[import_format])
        
        if uploaded_file is not None:
            file_content = uploaded_file.read().decode('utf-8')
            if st.button("インポート"):
                if user_dict.import_dictionary(file_content, import_format):
                    st.success("辞書をインポートしました")
                    st.rerun()
                else:
                    st.error("インポートに失敗しました")
    
    # 辞書リセット
    st.markdown("### ⚠️ 危険な操作")
    
    if st.button("🗑️ 辞書をリセット", type="secondary"):
        if st.checkbox("本当に辞書をリセットしますか？"):
            try:
                os.remove(user_dict.dictionary_file)
                st.success("辞書をリセットしました。ページを再読み込みしてください。")
                st.rerun()
            except Exception as e:
                st.error(f"リセットエラー: {e}")

# サイドバーにクイックアクセス
st.sidebar.markdown("## 📚 クイックアクセス")
if st.sidebar.button("🏠 メインページに戻る"):
    st.switch_page("app.py") 