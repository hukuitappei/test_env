import os
import openai
from dotenv import load_dotenv

# .envファイルの絶対パスを指定して読み込む
dotenv_path = r"C:\Users\btsi1\OneDrive\デスクトップ\cursor\myenv\tech_mentor\.env"
load_dotenv(dotenv_path)
print(dotenv_path)
api_key = os.getenv("OPEN_API_KEY")
print(api_key)
if not api_key:
    print("環境変数 OPENAI_API_KEY が設定されていません")
    exit(1)

openai.api_key = api_key

try:
    # シンプルなモデル呼び出し（gpt-3.5-turbo）
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "こんにちは。"}],
        max_tokens=10,
    )
    print("APIキーは有効です。サンプル応答：")
    print(response.choices[0].message.content)
except openai.AuthenticationError as e:
    print("APIキーが無効です。AuthenticationError:", e)
except Exception as e:
    print("API呼び出しでエラーが発生しました:", e)







