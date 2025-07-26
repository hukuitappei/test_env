import json
import os
from typing import Dict, Any

# 設定ファイルのパス
SETTINGS_FILE = "settings/app_settings.json"

# デフォルト設定
DEFAULT_SETTINGS = {
    "audio": {
        "chunk_size": 1024,
        "format": "paInt16",
        "channels": 1,
        "sample_rate": 44100,
        "gain": 2.0,
        "duration": 5
    },
    "whisper": {
        "model_size": "base",
        "language": "ja",
        "temperature": 0.0,
        "compression_ratio_threshold": 2.4,
        "logprob_threshold": -1.0,
        "no_speech_threshold": 0.6,
        "condition_on_previous_text": True,
        "initial_prompt": "これは日本語の音声です。"
    },
    "device": {
        "selected_device_index": None,
        "selected_device_name": None,
        "auto_select_default": True,
        "test_device_on_select": True
    },
    "ui": {
        "show_advanced_options": False,
        "auto_save_recordings": True,
        "show_quality_analysis": True,
        "show_level_monitoring": True,
        "auto_start_recording": False,
        "auto_recording_threshold": 300,
        "auto_recording_delay": 1.0
    },
    "troubleshooting": {
        "retry_count": 3,
        "timeout_seconds": 10,
        "enable_error_recovery": True,
        "log_errors": True
    },
    "llm": {
        "api_key": "",
        "provider": "openai",
        "model": "gpt-3.5-turbo",
        "temperature": 0.3,
        "max_tokens": 1000,
        "enabled": False
    }
}

def load_settings() -> Dict[str, Any]:
    """設定ファイルを読み込む"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # 新しい設定項目があれば追加
                for key, value in DEFAULT_SETTINGS.items():
                    if key not in settings:
                        settings[key] = value
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if sub_key not in settings[key]:
                                settings[key][sub_key] = sub_value
                return settings
        else:
            # 設定ファイルが存在しない場合はデフォルト設定で作成
            save_settings(DEFAULT_SETTINGS)
            return DEFAULT_SETTINGS
    except Exception as e:
        print(f"設定ファイル読み込みエラー: {e}")
        return DEFAULT_SETTINGS

def save_settings(settings: Dict[str, Any]) -> bool:
    """設定ファイルを保存する"""
    try:
        # ディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"設定ファイル保存エラー: {e}")
        return False

def get_setting(category: str, key: str, default=None):
    """特定の設定値を取得する"""
    settings = load_settings()
    return settings.get(category, {}).get(key, default)

def set_setting(category: str, key: str, value) -> bool:
    """特定の設定値を設定する"""
    settings = load_settings()
    if category not in settings:
        settings[category] = {}
    settings[category][key] = value
    return save_settings(settings)

def reset_settings() -> bool:
    """設定をデフォルトにリセットする"""
    return save_settings(DEFAULT_SETTINGS) 