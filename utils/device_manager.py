import pyaudio
import streamlit as st
from typing import List, Dict, Any, Optional
from .settings_manager import load_settings, save_settings

def get_all_audio_devices() -> List[Dict[str, Any]]:
    """すべてのオーディオデバイスを取得"""
    try:
        p = pyaudio.PyAudio()
        devices = []
        
        for i in range(p.get_device_count()):
            try:
                device_info = p.get_device_info_by_index(i)
                devices.append({
                    'index': i,
                    'name': device_info['name'],
                    'channels': device_info['maxInputChannels'],
                    'sample_rate': int(device_info['defaultSampleRate']),
                    'host_api': device_info['hostApi']
                })
            except Exception as e:
                print(f"デバイス {i} の情報取得エラー: {e}")
                continue
        
        p.terminate()
        return devices
    except Exception as e:
        print(f"オーディオデバイス取得エラー: {e}")
        return []

def get_default_devices() -> Dict[str, Any]:
    """デフォルトの入力・出力デバイスを取得"""
    try:
        p = pyaudio.PyAudio()
        default_input = p.get_default_input_device_info()
        default_output = p.get_default_output_device_info()
        p.terminate()
        
        return {
            'input': {
                'index': default_input['index'],
                'name': default_input['name']
            },
            'output': {
                'index': default_output['index'],
                'name': default_output['name']
            }
        }
    except Exception as e:
        print(f"デフォルトデバイス取得エラー: {e}")
        return {'input': None, 'output': None}

def test_device_access(device_index: int) -> bool:
    """デバイスへのアクセスをテスト"""
    try:
        p = pyaudio.PyAudio()
        device_info = p.get_device_info_by_index(device_index)
        
        if device_info['maxInputChannels'] == 0:
            p.terminate()
            return False
        
        # テスト用のストリームを作成
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=1024
        )
        
        stream.close()
        p.terminate()
        return True
    except Exception as e:
        print(f"デバイステストエラー: {e}")
        return False

def get_microphone_devices() -> List[Dict[str, Any]]:
    """マイクデバイスのみを取得"""
    all_devices = get_all_audio_devices()
    microphone_devices = []
    
    for device in all_devices:
        if device['channels'] > 0:  # 入力チャンネルがあるデバイス
            microphone_devices.append(device)
    
    return microphone_devices

def auto_select_default_microphone() -> Optional[Dict[str, Any]]:
    """デフォルトマイクを自動選択"""
    try:
        p = pyaudio.PyAudio()
        default_input = p.get_default_input_device_info()
        p.terminate()
        
        if default_input['maxInputChannels'] > 0:
            return {
                'index': default_input['index'],
                'name': default_input['name'],
                'channels': default_input['maxInputChannels'],
                'sample_rate': int(default_input['defaultSampleRate'])
            }
    except Exception as e:
        print(f"デフォルトマイク自動選択エラー: {e}")
    
    # デフォルトマイクが見つからない場合は最初のマイクを選択
    microphone_devices = get_microphone_devices()
    if microphone_devices:
        return microphone_devices[0]
    
    return None

def save_device_selection(device: Dict[str, Any]) -> bool:
    """選択されたデバイスを設定に保存"""
    settings = load_settings()
    settings['device']['selected_device_index'] = device['index']
    settings['device']['selected_device_name'] = device['name']
    return save_settings(settings)

def load_saved_device() -> Optional[Dict[str, Any]]:
    """保存されたデバイス設定を読み込み"""
    settings = load_settings()
    saved_index = settings['device']['selected_device_index']
    
    if saved_index is not None:
        devices = get_microphone_devices()
        for device in devices:
            if device['index'] == saved_index:
                return device
    
    return None

def get_device_info(device_index: int) -> Optional[Dict[str, Any]]:
    """特定のデバイス情報を取得"""
    try:
        p = pyaudio.PyAudio()
        device_info = p.get_device_info_by_index(device_index)
        p.terminate()
        
        return {
            'index': device_index,
            'name': device_info['name'],
            'channels': device_info['maxInputChannels'],
            'sample_rate': int(device_info['defaultSampleRate']),
            'host_api': device_info['hostApi']
        }
    except Exception as e:
        print(f"デバイス情報取得エラー: {e}")
        return None 