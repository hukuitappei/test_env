import os
import streamlit as st
from typing import Optional
from .settings_manager import load_settings

# LLM関連のライブラリ（オプション）
try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

def send_to_llm(transcription_text: str, task: str = "summarize") -> str:
    """文字起こし結果をLLMに送信"""
    settings = load_settings()
    
    if not settings['llm']['enabled']:
        return "LLM機能が無効になっています。設定画面で有効にしてください。"
    
    api_key = settings['llm']['api_key']
    provider = settings['llm']['provider']
    model = settings['llm']['model']
    temperature = settings['llm']['temperature']
    max_tokens = settings['llm']['max_tokens']
    
    # 環境変数からAPIキーを取得
    if not api_key:
        env_api_key = os.getenv(f"{provider.upper()}_API_KEY", "")
        if env_api_key:
            api_key = env_api_key
        else:
            return "APIキーが設定されていません。設定画面でAPIキーを設定してください。"
    
    try:
        if provider == "openai" and openai:
            return _process_with_openai(api_key, model, transcription_text, task, max_tokens, temperature)
            
        elif provider == "anthropic" and anthropic:
            return _process_with_anthropic(api_key, model, transcription_text, task, max_tokens)
            
        elif provider == "google" and genai:
            return _process_with_google(api_key, model, transcription_text, task)
            
        else:
            return f"{provider}のライブラリがインストールされていません。pip install {provider} でインストールしてください。"
            
    except Exception as e:
        return f"LLM処理エラー: {e}"

def _process_with_openai(api_key: str, model: str, transcription_text: str, task: str, max_tokens: int, temperature: float) -> str:
    """OpenAIで処理"""
    client = openai.OpenAI(api_key=api_key)
    
    if task == "summarize":
        prompt = f"以下の文字起こし結果を要約してください：\n\n{transcription_text}"
    elif task == "analyze":
        prompt = f"以下の文字起こし結果を分析し、キーポイントを抽出してください：\n\n{transcription_text}"
    else:
        prompt = f"以下の文字起こし結果について、{task}してください：\n\n{transcription_text}"
    
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature
    )
    return response.choices[0].message.content

def _process_with_anthropic(api_key: str, model: str, transcription_text: str, task: str, max_tokens: int) -> str:
    """Anthropicで処理"""
    client = anthropic.Anthropic(api_key=api_key)
    
    if task == "summarize":
        prompt = f"以下の文字起こし結果を要約してください：\n\n{transcription_text}"
    elif task == "analyze":
        prompt = f"以下の文字起こし結果を分析し、キーポイントを抽出してください：\n\n{transcription_text}"
    else:
        prompt = f"以下の文字起こし結果について、{task}してください：\n\n{transcription_text}"
    
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Anthropicのレスポンス構造を正しく処理
    if response.content and len(response.content) > 0:
        content_block = response.content[0]
        if hasattr(content_block, 'text'):
            return content_block.text
        else:
            return "テキスト形式でないレスポンスです"
    else:
        return "レスポンスが空です"

def _process_with_google(api_key: str, model: str, transcription_text: str, task: str) -> str:
    """Google Generative AIで処理"""
    genai.configure(api_key=api_key)
    model_genai = genai.GenerativeModel(model)
    
    if task == "summarize":
        prompt = f"以下の文字起こし結果を要約してください：\n\n{transcription_text}"
    elif task == "analyze":
        prompt = f"以下の文字起こし結果を分析し、キーポイントを抽出してください：\n\n{transcription_text}"
    else:
        prompt = f"以下の文字起こし結果について、{task}してください：\n\n{transcription_text}"
    
    response = model_genai.generate_content(prompt)
    return response.text

def test_api_key(provider: str, api_key: str, model: str) -> bool:
    """APIキーをテスト"""
    try:
        if provider == "openai" and openai:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            return True
            
        elif provider == "anthropic" and anthropic:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hello"}]
            )
            return True
            
        elif provider == "google" and genai:
            genai.configure(api_key=api_key)
            model_genai = genai.GenerativeModel(model)
            response = model_genai.generate_content("Hello")
            return True
            
        else:
            return False
            
    except Exception as e:
        st.error(f"APIキーテストエラー: {e}")
        return False

def get_available_models(provider: str) -> list:
    """利用可能なモデル一覧を取得"""
    if provider == "openai":
        return ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
    elif provider == "anthropic":
        return ["claude-3-sonnet-20240229", "claude-3-opus-20240229", "claude-3-haiku-20240307"]
    elif provider == "google":
        return ["gemini-pro", "gemini-pro-vision"]
    else:
        return []

def get_llm_status() -> dict:
    """LLMライブラリの状態を取得"""
    return {
        "openai": openai is not None,
        "anthropic": anthropic is not None,
        "google": genai is not None
    } 