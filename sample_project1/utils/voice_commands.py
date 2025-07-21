import speech_recognition as sr
import tempfile
import os
import whisper
import streamlit as st
from typing import Optional, Tuple, List

class VoiceCommandProcessor:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.whisper_model = None
        self.commands = {
            "修正": ["修正", "直して", "変更", "編集"],
            "削除": ["削除", "消して", "削って", "消去"],
            "追加": ["追加", "足して", "加えて", "入れて"],
            "保存": ["保存", "セーブ", "記録"],
            "検索": ["検索", "探して", "見つけて"],
            "要約": ["要約", "まとめて", "簡潔に"],
            "箇条書き": ["箇条書き", "リスト", "項目"],
            "ファイル": ["ファイル", "テキスト", "ダウンロード"]
        }
    
    def load_whisper_model(self, model_size="base"):
        """Whisperモデルを読み込み"""
        try:
            if self.whisper_model is None:
                with st.spinner(f"Whisperモデル({model_size})を読み込み中..."):
                    self.whisper_model = whisper.load_model(model_size)
            return True
        except Exception as e:
            st.error(f"Whisperモデル読み込みエラー: {e}")
            return False
    
    def listen_for_command(self, duration=5) -> Optional[str]:
        """音声コマンドを聞き取る"""
        try:
            with sr.Microphone() as source:
                st.info(f"🎤 {duration}秒間音声を聞き取ります...")
                
                # 環境ノイズを調整
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                
                # 音声を聞き取り
                audio = self.recognizer.listen(source, timeout=duration, phrase_time_limit=duration)
                
                # 音声認識
                text = self.recognizer.recognize_google(audio, language="ja-JP")
                return text
                
        except sr.WaitTimeoutError:
            st.warning("⏰ 音声が検出されませんでした")
            return None
        except sr.UnknownValueError:
            st.warning("🔇 音声を認識できませんでした")
            return None
        except sr.RequestError as e:
            st.error(f"🌐 音声認識サービスエラー: {e}")
            return None
        except Exception as e:
            st.error(f"🎤 音声認識エラー: {e}")
            return None
    
    def transcribe_audio_file(self, audio_file_path: str) -> Optional[str]:
        """音声ファイルを文字起こし"""
        if not self.load_whisper_model():
            return None
        
        try:
            with st.spinner("音声ファイルを文字起こし中..."):
                result = self.whisper_model.transcribe(audio_file_path, language="ja")
                return result["text"]
        except Exception as e:
            st.error(f"文字起こしエラー: {e}")
            return None
    
    def parse_command(self, text: str) -> Tuple[str, str]:
        """音声テキストからコマンドと内容を解析"""
        text = text.lower()
        
        # コマンドを検出
        detected_command = None
        for command, keywords in self.commands.items():
            for keyword in keywords:
                if keyword in text:
                    detected_command = command
                    break
            if detected_command:
                break
        
        # 内容を抽出（コマンド部分を除く）
        content = text
        if detected_command:
            for keyword in self.commands[detected_command]:
                content = content.replace(keyword, "").strip()
        
        return detected_command or "不明", content
    
    def execute_command(self, command: str, content: str, current_text: str = "") -> Tuple[str, str]:
        """コマンドを実行"""
        if command == "修正":
            return self._apply_correction(content, current_text)
        elif command == "削除":
            return self._delete_content(content, current_text)
        elif command == "追加":
            return self._add_content(content, current_text)
        elif command == "要約":
            return self._summarize_content(current_text)
        elif command == "箇条書き":
            return self._convert_to_bullet_points(current_text)
        else:
            return current_text, f"コマンド '{command}' は実装されていません"
    
    def _apply_correction(self, correction: str, current_text: str) -> Tuple[str, str]:
        """修正を適用"""
        # 簡単な置換処理（実際の実装ではより高度な処理が必要）
        if "を" in correction and "に" in correction:
            parts = correction.split("を")
            if len(parts) == 2:
                old_text = parts[0].strip()
                new_text = parts[1].split("に")[0].strip()
                if old_text in current_text:
                    new_content = current_text.replace(old_text, new_text)
                    return new_content, f"'{old_text}' を '{new_text}' に修正しました"
        
        return current_text, f"修正内容を適用できませんでした: {correction}"
    
    def _delete_content(self, content: str, current_text: str) -> Tuple[str, str]:
        """内容を削除"""
        if content in current_text:
            new_content = current_text.replace(content, "")
            return new_content, f"'{content}' を削除しました"
        return current_text, f"削除対象 '{content}' が見つかりませんでした"
    
    def _add_content(self, content: str, current_text: str) -> Tuple[str, str]:
        """内容を追加"""
        if current_text:
            new_content = current_text + "\n" + content
        else:
            new_content = content
        return new_content, f"'{content}' を追加しました"
    
    def _summarize_content(self, content: str) -> Tuple[str, str]:
        """内容を要約"""
        # 簡単な要約処理（実際の実装ではLLMを使用）
        if len(content) > 100:
            summary = content[:100] + "..."
            return summary, "内容を要約しました"
        return content, "内容が短いため要約は不要です"
    
    def _convert_to_bullet_points(self, content: str) -> Tuple[str, str]:
        """箇条書きに変換"""
        lines = content.split('\n')
        bullet_points = []
        for line in lines:
            line = line.strip()
            if line:
                bullet_points.append(f"• {line}")
        
        new_content = '\n'.join(bullet_points)
        return new_content, "箇条書きに変換しました"

def create_voice_command_processor():
    """VoiceCommandProcessorのインスタンスを作成"""
    return VoiceCommandProcessor() 