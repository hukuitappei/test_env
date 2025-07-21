import os
import json
from datetime import datetime
from typing import List, Dict, Optional

class TranscriptionManager:
    """文字起こし結果の管理クラス"""
    
    def __init__(self, transcriptions_dir: str = "transcriptions", history_file: str = "settings/transcription_history.json"):
        self.transcriptions_dir = transcriptions_dir
        self.history_file = history_file
        os.makedirs(transcriptions_dir, exist_ok=True)
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
    
    def add_transcription(self, session_id: str, chunk_id: int, text: str, audio_path: Optional[str] = None) -> Dict:
        """文字起こし結果を追加"""
        # ファイルに保存
        file_path = self._save_transcription_file(session_id, chunk_id, text)
        
        # 履歴に追加
        history_entry = {
            "id": f"{session_id}_{chunk_id}",
            "session_id": session_id,
            "chunk_id": chunk_id,
            "file_path": file_path,
            "audio_path": audio_path,
            "text": text,
            "created_at": datetime.now().isoformat(),
            "text_length": len(text),
            "word_count": len(text.split())
        }
        
        self._add_to_history(history_entry)
        return history_entry
    
    def _save_transcription_file(self, session_id: str, chunk_id: int, text: str) -> str:
        """文字起こしファイルを保存"""
        session_dir = os.path.join(self.transcriptions_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        filename = f"{session_id}_chunk{chunk_id}.txt"
        file_path = os.path.join(session_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        return file_path
    
    def _add_to_history(self, entry: Dict):
        """履歴ファイルにエントリを追加"""
        history = self.load_history()
        history.append(entry)
        
        # 最新の100件のみ保持
        if len(history) > 100:
            history = history[-100:]
        
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    def load_history(self) -> List[Dict]:
        """履歴を読み込み"""
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def get_transcription_files(self) -> List[str]:
        """文字起こしファイル一覧を取得"""
        files = []
        if os.path.exists(self.transcriptions_dir):
            for root, dirs, filenames in os.walk(self.transcriptions_dir):
                for f in filenames:
                    if f.endswith('.txt'):
                        file_path = os.path.join(root, f)
                        files.append(file_path)
        return sorted(files, reverse=True)
    
    def read_transcription_file(self, file_path: str) -> str:
        """文字起こしファイルを読み込み"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"ファイル読み込みエラー: {str(e)}"
    
    def search_transcriptions(self, query: str) -> List[Dict]:
        """文字起こしを検索"""
        history = self.load_history()
        results = []
        
        query_lower = query.lower()
        for entry in history:
            if query_lower in entry.get('text', '').lower():
                results.append(entry)
        
        return results
    
    def filter_by_date(self, date_str: str) -> List[Dict]:
        """日付でフィルタリング"""
        history = self.load_history()
        results = []
        
        for entry in history:
            created_at = entry.get('created_at', '')
            if date_str in created_at:
                results.append(entry)
        
        return results
    
    def get_statistics(self) -> Dict:
        """統計情報を取得"""
        history = self.load_history()
        
        if not history:
            return {
                "total_transcriptions": 0,
                "total_words": 0,
                "total_characters": 0,
                "average_length": 0
            }
        
        total_transcriptions = len(history)
        total_words = sum(entry.get('word_count', 0) for entry in history)
        total_characters = sum(entry.get('text_length', 0) for entry in history)
        average_length = total_characters / total_transcriptions if total_transcriptions > 0 else 0
        
        return {
            "total_transcriptions": total_transcriptions,
            "total_words": total_words,
            "total_characters": total_characters,
            "average_length": round(average_length, 1)
        }
    
    def delete_transcription(self, file_path: str) -> bool:
        """文字起こしファイルを削除"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                
                # 履歴からも削除
                history = self.load_history()
                history = [entry for entry in history if entry.get('file_path') != file_path]
                
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
                
                return True
        except Exception:
            return False
    
    def update_transcription(self, file_path: str, new_text: str) -> bool:
        """文字起こし内容を更新"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_text)
            
            # 履歴も更新
            history = self.load_history()
            for entry in history:
                if entry.get('file_path') == file_path:
                    entry['text'] = new_text
                    entry['text_length'] = len(new_text)
                    entry['word_count'] = len(new_text.split())
                    entry['updated_at'] = datetime.now().isoformat()
                    break
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception:
            return False 