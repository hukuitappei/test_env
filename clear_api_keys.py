#!/usr/bin/env python3
"""
設定ファイルからAPIキーを削除するスクリプト
セキュリティのため、設定ファイルに保存されたAPIキーを削除します
"""

import json
import os
from pathlib import Path

def clear_api_keys_from_settings():
    """設定ファイルからAPIキーを削除"""
    settings_file = Path("settings/app_settings.json")
    
    if not settings_file.exists():
        print("設定ファイルが見つかりません")
        return
    
    try:
        # 設定ファイルを読み込み
        with open(settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        # APIキーを削除
        if 'llm' in settings and 'api_key' in settings['llm']:
            old_api_key = settings['llm']['api_key']
            settings['llm']['api_key'] = ""
            
            # 設定ファイルを保存
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            
            if old_api_key:
                print("✅ 設定ファイルからAPIキーを削除しました")
                print("💡 今後は環境変数または.envファイルでAPIキーを管理してください")
            else:
                print("ℹ️ 設定ファイルにAPIキーは保存されていませんでした")
        
    except Exception as e:
        print(f"❌ エラー: {e}")

def create_env_file():
    """環境変数テンプレートファイルを作成"""
    env_file = Path(".env")
    
    if env_file.exists():
        print("ℹ️ .envファイルは既に存在します")
        return
    
    env_template = """# API Keys for LLM Services
# Copy this file to .env and fill in your actual API keys

# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic API Key  
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Google Generative AI API Key
GOOGLE_API_KEY=your_google_api_key_here

# Other configuration
# STREAMLIT_SERVER_PORT=8501
# STREAMLIT_SERVER_ADDRESS=localhost
"""
    
    try:
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(env_template)
        print("✅ .envファイルを作成しました")
        print("💡 .envファイルに実際のAPIキーを設定してください")
    except Exception as e:
        print(f"❌ .envファイル作成エラー: {e}")

if __name__ == "__main__":
    print("🔒 APIキーセキュリティ設定")
    print("=" * 40)
    
    # 設定ファイルからAPIキーを削除
    clear_api_keys_from_settings()
    
    print()
    
    # .envファイルを作成
    create_env_file()
    
    print()
    print("📋 次の手順:")
    print("1. .envファイルに実際のAPIキーを設定")
    print("2. .envファイルがGitにコミットされないことを確認")
    print("3. アプリケーションを再起動") 