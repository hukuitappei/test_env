import json
import os
from typing import Dict, List, Optional
from datetime import datetime
import streamlit as st

class UserDictionary:
    def __init__(self, dictionary_file="settings/user_dictionary.json"):
        self.dictionary_file = dictionary_file
        self.dictionary = self.load_dictionary()
    
    def load_dictionary(self) -> Dict:
        """辞書を読み込み"""
        try:
            if os.path.exists(self.dictionary_file):
                with open(self.dictionary_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # デフォルト辞書を作成
                default_dict = {
                    "categories": {
                        "技術用語": {
                            "description": "技術関連の用語",
                            "entries": {}
                        },
                        "略語": {
                            "description": "略語とその意味",
                            "entries": {}
                        },
                        "カスタム": {
                            "description": "ユーザー定義の用語",
                            "entries": {}
                        }
                    },
                    "metadata": {
                        "created_at": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                        "total_entries": 0
                    }
                }
                self.save_dictionary(default_dict)
                return default_dict
        except Exception as e:
            st.error(f"辞書読み込みエラー: {e}")
            return {"categories": {}, "metadata": {}}
    
    def save_dictionary(self, dictionary: Optional[Dict] = None) -> bool:
        """辞書を保存"""
        try:
            if dictionary is None:
                dictionary = self.dictionary
            
            # メタデータを更新
            dictionary["metadata"]["last_updated"] = datetime.now().isoformat()
            dictionary["metadata"]["total_entries"] = self.count_total_entries(dictionary)
            
            os.makedirs(os.path.dirname(self.dictionary_file), exist_ok=True)
            with open(self.dictionary_file, 'w', encoding='utf-8') as f:
                json.dump(dictionary, f, ensure_ascii=False, indent=2)
            
            self.dictionary = dictionary
            return True
        except Exception as e:
            st.error(f"辞書保存エラー: {e}")
            return False
    
    def count_total_entries(self, dictionary: Optional[Dict] = None) -> int:
        """総エントリ数をカウント"""
        if dictionary is None:
            dictionary = self.dictionary
        
        total = 0
        for category in dictionary.get("categories", {}).values():
            total += len(category.get("entries", {}))
        return total
    
    def add_category(self, category_name: str, description: str = "") -> bool:
        """カテゴリを追加"""
        if category_name in self.dictionary.get("categories", {}):
            st.warning(f"カテゴリ '{category_name}' は既に存在します")
            return False
        
        self.dictionary["categories"][category_name] = {
            "description": description,
            "entries": {}
        }
        return self.save_dictionary()
    
    def delete_category(self, category_name: str) -> bool:
        """カテゴリを削除"""
        if category_name not in self.dictionary.get("categories", {}):
            st.error(f"カテゴリ '{category_name}' が見つかりません")
            return False
        
        del self.dictionary["categories"][category_name]
        return self.save_dictionary()
    
    def add_entry(self, category: str, word: str, definition: str, examples: List[str] = None) -> bool:
        """エントリを追加"""
        if category not in self.dictionary.get("categories", {}):
            st.error(f"カテゴリ '{category}' が見つかりません")
            return False
        
        if examples is None:
            examples = []
        
        self.dictionary["categories"][category]["entries"][word] = {
            "definition": definition,
            "examples": examples,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        return self.save_dictionary()
    
    def update_entry(self, category: str, word: str, definition: str = None, examples: List[str] = None) -> bool:
        """エントリを更新"""
        if category not in self.dictionary.get("categories", {}):
            st.error(f"カテゴリ '{category}' が見つかりません")
            return False
        
        if word not in self.dictionary["categories"][category]["entries"]:
            st.error(f"単語 '{word}' が見つかりません")
            return False
        
        entry = self.dictionary["categories"][category]["entries"][word]
        
        if definition is not None:
            entry["definition"] = definition
        if examples is not None:
            entry["examples"] = examples
        
        entry["last_updated"] = datetime.now().isoformat()
        return self.save_dictionary()
    
    def delete_entry(self, category: str, word: str) -> bool:
        """エントリを削除"""
        if category not in self.dictionary.get("categories", {}):
            st.error(f"カテゴリ '{category}' が見つかりません")
            return False
        
        if word not in self.dictionary["categories"][category]["entries"]:
            st.error(f"単語 '{word}' が見つかりません")
            return False
        
        del self.dictionary["categories"][category]["entries"][word]
        return self.save_dictionary()
    
    def get_entry(self, category: str, word: str) -> Optional[Dict]:
        """エントリを取得"""
        try:
            return self.dictionary["categories"][category]["entries"][word]
        except KeyError:
            return None
    
    def search_entries(self, query: str) -> List[Dict]:
        """エントリを検索"""
        results = []
        query_lower = query.lower()
        
        for category_name, category_data in self.dictionary.get("categories", {}).items():
            for word, entry in category_data.get("entries", {}).items():
                if (query_lower in word.lower() or 
                    query_lower in entry["definition"].lower() or
                    any(query_lower in example.lower() for example in entry.get("examples", []))):
                    results.append({
                        "category": category_name,
                        "word": word,
                        "entry": entry
                    })
        
        return results
    
    def get_categories(self) -> List[str]:
        """カテゴリ一覧を取得"""
        return list(self.dictionary.get("categories", {}).keys())
    
    def get_entries_by_category(self, category: str) -> Dict:
        """カテゴリ別エントリを取得"""
        return self.dictionary.get("categories", {}).get(category, {}).get("entries", {})
    
    def get_statistics(self) -> Dict:
        """統計情報を取得"""
        total_entries = self.count_total_entries()
        categories = self.get_categories()
        
        category_stats = {}
        for category in categories:
            category_stats[category] = len(self.get_entries_by_category(category))
        
        return {
            "total_entries": total_entries,
            "total_categories": len(categories),
            "category_stats": category_stats,
            "last_updated": self.dictionary.get("metadata", {}).get("last_updated", "")
        }
    
    def export_dictionary(self, format_type: str = "json") -> str:
        """辞書をエクスポート"""
        if format_type == "json":
            return json.dumps(self.dictionary, ensure_ascii=False, indent=2)
        elif format_type == "txt":
            lines = []
            lines.append("=== ユーザー辞書 ===\n")
            
            for category_name, category_data in self.dictionary.get("categories", {}).items():
                lines.append(f"\n## {category_name}")
                lines.append(f"説明: {category_data.get('description', '')}")
                
                for word, entry in category_data.get("entries", {}).items():
                    lines.append(f"\n### {word}")
                    lines.append(f"定義: {entry['definition']}")
                    if entry.get("examples"):
                        lines.append("例文:")
                        for example in entry["examples"]:
                            lines.append(f"  - {example}")
                    lines.append(f"作成日: {entry.get('created_at', '')}")
                    lines.append(f"更新日: {entry.get('last_updated', '')}")
            
            return "\n".join(lines)
        else:
            return "サポートされていない形式です"
    
    def import_dictionary(self, data: str, format_type: str = "json") -> bool:
        """辞書をインポート"""
        try:
            if format_type == "json":
                imported_dict = json.loads(data)
                # 基本的な構造チェック
                if "categories" in imported_dict:
                    self.dictionary = imported_dict
                    return self.save_dictionary()
                else:
                    st.error("無効な辞書形式です")
                    return False
            else:
                st.error("サポートされていない形式です")
                return False
        except Exception as e:
            st.error(f"インポートエラー: {e}")
            return False

def create_user_dictionary():
    """UserDictionaryのインスタンスを作成"""
    return UserDictionary() 