import streamlit as st
from utils.user_dictionary import create_user_dictionary
from datetime import datetime

st.set_page_config(page_title="ユーザー辞書", page_icon="📚", layout="wide")

st.title("📚 ユーザー辞書管理")

# ユーザー辞書の初期化
user_dict = create_user_dictionary()

# タブ作成
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
        st.metric("最終更新", stats["last_updated"][:19] if stats["last_updated"] else "なし")
    with col4:
        if st.button("🔄 更新"):
            st.rerun()
    
    # カテゴリ選択
    categories = user_dict.get_categories()
    if categories:
        selected_category = st.selectbox("カテゴリを選択", categories)
        
        # カテゴリ情報表示
        category_data = user_dict.dictionary["categories"][selected_category]
        st.write(f"**説明**: {category_data.get('description', '説明なし')}")
        
        # エントリ一覧
        entries = user_dict.get_entries_by_category(selected_category)
        if entries:
            st.write(f"**エントリ数**: {len(entries)}")
            
            for word, entry in entries.items():
                with st.expander(f"📝 {word}", expanded=False):
                    st.write(f"**定義**: {entry['definition']}")
                    
                    if entry.get("examples"):
                        st.write("**例文**:")
                        for i, example in enumerate(entry["examples"], 1):
                            st.write(f"{i}. {example}")
                    
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.caption(f"作成日: {entry.get('created_at', '')[:19]}")
                    with col_info2:
                        st.caption(f"更新日: {entry.get('last_updated', '')[:19]}")
                    with col_info3:
                        if st.button("🗑️ 削除", key=f"delete_{word}"):
                            if user_dict.delete_entry(selected_category, word):
                                st.success("削除しました")
                                st.rerun()
                            else:
                                st.error("削除に失敗しました")
        else:
            st.info("このカテゴリにはエントリがありません")
    else:
        st.info("辞書にカテゴリがありません")

with tab2:
    st.subheader("➕ エントリ追加")
    
    # カテゴリ追加
    st.markdown("### 📂 カテゴリ追加")
    col_cat1, col_cat2 = st.columns([2, 1])
    
    with col_cat1:
        new_category = st.text_input("新しいカテゴリ名")
    with col_cat2:
        category_description = st.text_input("説明（オプション）")
    
    if st.button("➕ カテゴリを追加"):
        if new_category:
            if user_dict.add_category(new_category, category_description):
                st.success(f"カテゴリ '{new_category}' を追加しました")
                st.rerun()
            else:
                st.error("カテゴリの追加に失敗しました")
        else:
            st.warning("カテゴリ名を入力してください")
    
    st.markdown("---")
    
    # エントリ追加
    st.markdown("### 📝 エントリ追加")
    
    categories = user_dict.get_categories()
    if categories:
        selected_category = st.selectbox("カテゴリを選択", categories, key="add_entry_category")
        
        new_word = st.text_input("単語・用語")
        new_definition = st.text_area("定義・説明", height=100)
        
        # 例文追加
        st.write("**例文（オプション）**")
        examples = []
        for i in range(3):
            example = st.text_input(f"例文 {i+1}", key=f"example_{i}")
            if example:
                examples.append(example)
        
        if st.button("➕ エントリを追加"):
            if new_word and new_definition:
                if user_dict.add_entry(selected_category, new_word, new_definition, examples):
                    st.success(f"エントリ '{new_word}' を追加しました")
                    st.rerun()
                else:
                    st.error("エントリの追加に失敗しました")
            else:
                st.warning("単語と定義を入力してください")
    else:
        st.info("まずカテゴリを追加してください")

with tab3:
    st.subheader("🔍 検索")
    
    # 検索機能
    search_query = st.text_input("検索キーワード", placeholder="単語、定義、例文で検索...")
    
    if search_query:
        results = user_dict.search_entries(search_query)
        
        if results:
            st.write(f"**検索結果**: {len(results)}件")
            
            for result in results:
                with st.expander(f"📝 {result['word']} ({result['category']})", expanded=False):
                    st.write(f"**定義**: {result['entry']['definition']}")
                    
                    if result['entry'].get("examples"):
                        st.write("**例文**:")
                        for i, example in enumerate(result['entry']["examples"], 1):
                            st.write(f"{i}. {example}")
                    
                    col_search1, col_search2 = st.columns(2)
                    with col_search1:
                        st.caption(f"カテゴリ: {result['category']}")
                    with col_search2:
                        st.caption(f"更新日: {result['entry'].get('last_updated', '')[:19]}")
        else:
            st.info("検索条件に一致するエントリがありません")
    else:
        st.info("検索キーワードを入力してください")

with tab4:
    st.subheader("⚙️ 管理")
    
    # 統計情報
    st.markdown("### 📊 統計情報")
    stats = user_dict.get_statistics()
    
    col_stats1, col_stats2 = st.columns(2)
    
    with col_stats1:
        st.write(f"**総エントリ数**: {stats['total_entries']}")
        st.write(f"**総カテゴリ数**: {stats['total_categories']}")
        st.write(f"**最終更新**: {stats['last_updated'][:19] if stats['last_updated'] else 'なし'}")
    
    with col_stats2:
        st.write("**カテゴリ別エントリ数**:")
        for category, count in stats['category_stats'].items():
            st.write(f"- {category}: {count}件")
    
    st.markdown("---")
    
    # エクスポート・インポート
    st.markdown("### 📤 エクスポート・インポート")
    
    col_export1, col_export2 = st.columns(2)
    
    with col_export1:
        st.markdown("#### 📤 エクスポート")
        export_format = st.selectbox("形式", ["json", "txt"], key="export_format")
        
        if st.button("📤 辞書をエクスポート"):
            export_data = user_dict.export_dictionary(export_format)
            
            if export_format == "json":
                st.download_button(
                    label="📥 JSONファイルをダウンロード",
                    data=export_data,
                    file_name=f"user_dictionary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            else:
                st.download_button(
                    label="📥 テキストファイルをダウンロード",
                    data=export_data,
                    file_name=f"user_dictionary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
    
    with col_export2:
        st.markdown("#### 📥 インポート")
        import_format = st.selectbox("形式", ["json"], key="import_format")
        uploaded_file = st.file_uploader("辞書ファイルをアップロード", type=["json"])
        
        if uploaded_file is not None:
            if st.button("📥 辞書をインポート"):
                try:
                    import_data = uploaded_file.read().decode('utf-8')
                    if user_dict.import_dictionary(import_data, import_format):
                        st.success("辞書をインポートしました")
                        st.rerun()
                    else:
                        st.error("インポートに失敗しました")
                except Exception as e:
                    st.error(f"インポートエラー: {e}")
    
    st.markdown("---")
    
    # 辞書リセット
    st.markdown("### 🗑️ 辞書リセット")
    
    if st.button("🗑️ 辞書をリセット", type="secondary"):
        if st.checkbox("本当に辞書をリセットしますか？"):
            try:
                # 辞書ファイルを削除
                import os
                if os.path.exists(user_dict.dictionary_file):
                    os.remove(user_dict.dictionary_file)
                st.success("辞書をリセットしました")
                st.rerun()
            except Exception as e:
                st.error(f"リセットエラー: {e}")

# サイドバー
with st.sidebar:
    st.header("📚 クイックアクセス")
    
    # 統計情報
    stats = user_dict.get_statistics()
    st.metric("総エントリ数", stats["total_entries"])
    st.metric("カテゴリ数", stats["total_categories"])
    
    st.markdown("---")
    
    # 最近追加されたエントリ
    st.subheader("📝 最近のエントリ")
    
    # 全エントリを取得して日付順にソート
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
    
    for entry in all_entries[:5]:  # 最新5件
        created_at = entry["entry"].get("created_at", "")[:19]
        st.caption(f"{created_at}")
        st.write(f"**{entry['word']}** ({entry['category']})")
        st.write(entry["entry"]["definition"][:50] + "...")
        st.markdown("---") 