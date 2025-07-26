import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import streamlit as st

class CommandProcessor:
    def __init__(self, commands_file="settings/commands.json"):
        self.commands_file = commands_file
        self.commands = self.load_commands()
        
        # デフォルトコマンド
        self.default_commands = {
            "箇条書き": {
                "description": "文字起こし結果を箇条書きに変換",
                "llm_prompt": "以下の文字起こし結果を箇条書きに変換してください：\n\n{text}",
                "output_format": "bullet_points",
                "enabled": True
            },
            "要約": {
                "description": "文字起こし結果を要約",
                "llm_prompt": "以下の文字起こし結果を簡潔に要約してください：\n\n{text}",
                "output_format": "summary",
                "enabled": True
            },
            "テキストファイル出力": {
                "description": "文字起こし結果をテキストファイルとして保存",
                "llm_prompt": "以下の文字起こし結果を整理してテキストファイル用にフォーマットしてください：\n\n{text}",
                "output_format": "text_file",
                "enabled": True
            },
            "LLM要約ファイル出力": {
                "description": "LLM要約結果をテキストファイルとして保存",
                "llm_prompt": "以下の文字起こし結果を詳細に分析し、構造化された要約を作成してください：\n\n{text}",
                "output_format": "llm_summary_file",
                "enabled": True
            },
            "キーポイント抽出": {
                "description": "重要なポイントを抽出",
                "llm_prompt": "以下の文字起こし結果から重要なポイントを抽出してください：\n\n{text}",
                "output_format": "key_points",
                "enabled": True
            },
            "アクションアイテム抽出": {
                "description": "アクションアイテムを抽出",
                "llm_prompt": "以下の文字起こし結果からアクションアイテム（タスク）を抽出してください：\n\n{text}",
                "output_format": "action_items",
                "enabled": True
            }
        }
    
    def load_commands(self) -> Dict:
        """コマンドを読み込み"""
        try:
            if os.path.exists(self.commands_file):
                with open(self.commands_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # デフォルトコマンドで初期化
                commands = {
                    "commands": self.default_commands,
                    "metadata": {
                        "created_at": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                        "total_commands": len(self.default_commands)
                    }
                }
                self.save_commands(commands)
                return commands
        except Exception as e:
            st.error(f"コマンド読み込みエラー: {e}")
            return {"commands": {}, "metadata": {}}
    
    def save_commands(self, commands: Optional[Dict] = None) -> bool:
        """コマンドを保存"""
        try:
            if commands is None:
                commands = self.commands
            
            # メタデータを更新
            commands["metadata"]["last_updated"] = datetime.now().isoformat()
            commands["metadata"]["total_commands"] = len(commands.get("commands", {}))
            
            os.makedirs(os.path.dirname(self.commands_file), exist_ok=True)
            with open(self.commands_file, 'w', encoding='utf-8') as f:
                json.dump(commands, f, ensure_ascii=False, indent=2)
            
            self.commands = commands
            return True
        except Exception as e:
            st.error(f"コマンド保存エラー: {e}")
            return False
    
    def add_command(self, name: str, description: str, llm_prompt: str, output_format: str) -> bool:
        """コマンドを追加"""
        if name in self.commands.get("commands", {}):
            st.warning(f"コマンド '{name}' は既に存在します")
            return False
        
        self.commands["commands"][name] = {
            "description": description,
            "llm_prompt": llm_prompt,
            "output_format": output_format,
            "enabled": True,
            "created_at": datetime.now().isoformat()
        }
        return self.save_commands()
    
    def update_command(self, name: str, description: str = None, llm_prompt: str = None, 
                      output_format: str = None, enabled: bool = None) -> bool:
        """コマンドを更新"""
        if name not in self.commands.get("commands", {}):
            st.error(f"コマンド '{name}' が見つかりません")
            return False
        
        command = self.commands["commands"][name]
        
        if description is not None:
            command["description"] = description
        if llm_prompt is not None:
            command["llm_prompt"] = llm_prompt
        if output_format is not None:
            command["output_format"] = output_format
        if enabled is not None:
            command["enabled"] = enabled
        
        command["last_updated"] = datetime.now().isoformat()
        return self.save_commands()
    
    def delete_command(self, name: str) -> bool:
        """コマンドを削除"""
        if name not in self.commands.get("commands", {}):
            st.error(f"コマンド '{name}' が見つかりません")
            return False
        
        del self.commands["commands"][name]
        return self.save_commands()
    
    def get_command(self, name: str) -> Optional[Dict]:
        """コマンドを取得"""
        return self.commands.get("commands", {}).get(name)
    
    def get_all_commands(self) -> Dict:
        """全コマンドを取得"""
        return self.commands.get("commands", {})
    
    def get_enabled_commands(self) -> Dict:
        """有効なコマンドを取得"""
        return {name: cmd for name, cmd in self.commands.get("commands", {}).items() 
                if cmd.get("enabled", True)}
    
    def execute_command(self, command_name: str, text: str, llm_processor=None) -> Tuple[str, str]:
        """コマンドを実行"""
        command = self.get_command(command_name)
        if not command:
            return text, f"コマンド '{command_name}' が見つかりません"
        
        if not command.get("enabled", True):
            return text, f"コマンド '{command_name}' は無効です"
        
        llm_prompt = command["llm_prompt"].format(text=text)
        output_format = command["output_format"]
        
        # LLM処理
        if llm_processor:
            try:
                with st.spinner(f"コマンド '{command_name}' を実行中..."):
                    result = llm_processor.process_text(llm_prompt)
                    return result, f"コマンド '{command_name}' を実行しました"
            except Exception as e:
                return text, f"LLM処理エラー: {e}"
        else:
            # LLMがない場合は基本的な処理
            return self._basic_command_processing(command_name, text, output_format)
    
    def _basic_command_processing(self, command_name: str, text: str, output_format: str) -> Tuple[str, str]:
        """基本的なコマンド処理（LLMなし）"""
        if output_format == "bullet_points":
            lines = text.split('\n')
            bullet_points = []
            for line in lines:
                line = line.strip()
                if line:
                    bullet_points.append(f"• {line}")
            return '\n'.join(bullet_points), f"箇条書きに変換しました"
        
        elif output_format == "summary":
            if len(text) > 200:
                summary = text[:200] + "..."
                return summary, "内容を要約しました"
            return text, "内容が短いため要約は不要です"
        
        elif output_format == "text_file":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            header = f"=== 文字起こし結果 ===\n"
            header += f"作成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"文字数: {len(text)}\n"
            header += "=" * 50 + "\n\n"
            return header + text, "テキストファイル形式に変換しました"
        
        elif output_format == "llm_summary_file":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            header = f"=== LLM要約結果 ===\n"
            header += f"作成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"元テキスト文字数: {len(text)}\n"
            header += "=" * 50 + "\n\n"
            return header + text, "LLM要約ファイル形式に変換しました"
        
        elif output_format == "key_points":
            lines = text.split('\n')
            key_points = []
            for i, line in enumerate(lines[:5], 1):  # 最初の5行をキーポイントとして扱う
                line = line.strip()
                if line:
                    key_points.append(f"{i}. {line}")
            return '\n'.join(key_points), "キーポイントを抽出しました"
        
        elif output_format == "action_items":
            lines = text.split('\n')
            action_items = []
            for i, line in enumerate(lines[:3], 1):  # 最初の3行をアクションアイテムとして扱う
                line = line.strip()
                if line:
                    action_items.append(f"□ {line}")
            return '\n'.join(action_items), "アクションアイテムを抽出しました"
        
        else:
            return text, f"出力形式 '{output_format}' はサポートされていません"
    
    def save_to_file(self, content: str, filename: str, output_dir: str = "outputs") -> bool:
        """結果をファイルに保存"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
        except Exception as e:
            st.error(f"ファイル保存エラー: {e}")
            return False
    
    def get_statistics(self) -> Dict:
        """統計情報を取得"""
        commands = self.commands.get("commands", {})
        enabled_commands = [cmd for cmd in commands.values() if cmd.get("enabled", True)]
        
        return {
            "total_commands": len(commands),
            "enabled_commands": len(enabled_commands),
            "disabled_commands": len(commands) - len(enabled_commands),
            "last_updated": self.commands.get("metadata", {}).get("last_updated", "")
        }
    
    def export_commands(self, format_type: str = "json") -> str:
        """コマンドをエクスポート"""
        if format_type == "json":
            return json.dumps(self.commands, ensure_ascii=False, indent=2)
        elif format_type == "txt":
            lines = []
            lines.append("=== コマンド一覧 ===\n")
            
            for name, command in self.commands.get("commands", {}).items():
                lines.append(f"\n## {name}")
                lines.append(f"説明: {command.get('description', '')}")
                lines.append(f"出力形式: {command.get('output_format', '')}")
                lines.append(f"有効: {'はい' if command.get('enabled', True) else 'いいえ'}")
                lines.append(f"LLMプロンプト: {command.get('llm_prompt', '')}")
                lines.append(f"作成日: {command.get('created_at', '')}")
                if 'last_updated' in command:
                    lines.append(f"更新日: {command['last_updated']}")
            
            return "\n".join(lines)
        else:
            return "サポートされていない形式です"
    
    def import_commands(self, data: str, format_type: str = "json") -> bool:
        """コマンドをインポート"""
        try:
            if format_type == "json":
                imported_commands = json.loads(data)
                # 基本的な構造チェック
                if "commands" in imported_commands:
                    self.commands = imported_commands
                    return self.save_commands()
                else:
                    st.error("無効なコマンド形式です")
                    return False
            else:
                st.error("サポートされていない形式です")
                return False
        except Exception as e:
            st.error(f"インポートエラー: {e}")
            return False

def create_command_processor():
    """CommandProcessorのインスタンスを作成"""
    return CommandProcessor() 