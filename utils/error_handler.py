import pyaudio
import time
import logging
from typing import Tuple, Optional, Dict, Any
import numpy as np

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PyAudioErrorHandler:
    """PyAudioエラーハンドリングクラス"""
    
    @staticmethod
    def get_error_description(error_msg: str) -> str:
        """エラーメッセージから詳細な説明を取得"""
        error_msg = str(error_msg)
        
        if "Errno -9999" in error_msg:
            return "ホストエラー: デバイスが他のアプリで使用中または権限不足"
        elif "Errno -9998" in error_msg:
            return "ストリームエラー: デバイスが利用できない"
        elif "Errno -9997" in error_msg:
            return "デバイスエラー: デバイスが存在しない"
        elif "Errno -9996" in error_msg:
            return "バッファエラー: バッファサイズが不適切"
        elif "Errno -9995" in error_msg:
            return "バッファオーバーフロー: データ処理が追いつかない"
        elif "Errno -9994" in error_msg:
            return "バッファアンダーフロー: データが不足"
        elif "Errno -9993" in error_msg:
            return "デバイスバスy: デバイスが使用中"
        elif "Errno -9992" in error_msg:
            return "デバイスが利用できない"
        elif "Errno -9991" in error_msg:
            return "デバイスが存在しない"
        else:
            return f"不明なエラー: {error_msg}"
    
    @staticmethod
    def get_solution_suggestions(error_msg: str) -> list:
        """エラーに対する解決策を提案"""
        error_msg = str(error_msg)
        suggestions = []
        
        if "Errno -9999" in error_msg:
            suggestions = [
                "他のアプリケーションがマイクを使用していないか確認してください",
                "Windows設定 → プライバシーとセキュリティ → マイクでアクセス許可を確認",
                "デバイスドライバーを更新してください",
                "仮想オーディオデバイスを一時的に無効化してください",
                "アプリを管理者として実行してください",
                "チャンクサイズを大きくする（2048, 4096）",
                "サンプルレートを下げる（22050, 16000）"
            ]
        elif "Errno -9998" in error_msg:
            suggestions = [
                "デバイスを再接続してください",
                "デバイスを再起動してください",
                "他のアプリを終了してください",
                "デバイスドライバーを再インストールしてください"
            ]
        elif "Errno -9997" in error_msg:
            suggestions = [
                "デバイスドライバーを再インストールしてください",
                "デバイスが正しく接続されているか確認してください",
                "デバイスマネージャーでデバイスの状態を確認してください"
            ]
        elif "Errno -9996" in error_msg:
            suggestions = [
                "チャンクサイズを調整してください",
                "サンプルレートを変更してください",
                "チャンネル数を変更してください"
            ]
        elif "Errno -9995" in error_msg:
            suggestions = [
                "チャンクサイズを大きくしてください",
                "サンプルレートを下げてください",
                "他のアプリを終了してください"
            ]
        elif "Errno -9994" in error_msg:
            suggestions = [
                "チャンクサイズを小さくしてください",
                "サンプルレートを上げてください",
                "音声レベルを上げてください"
            ]
        else:
            suggestions = [
                "デバイスを再接続してください",
                "アプリを再起動してください",
                "デバイスドライバーを更新してください"
            ]
        
        return suggestions

class DeviceTester:
    """デバイステストクラス"""
    
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.p = None
    
    def __enter__(self):
        self.p = pyaudio.PyAudio()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.p:
            self.p.terminate()
    
    def test_device_access(self, device_index: int, retry_count: int = 3) -> Tuple[bool, str, list]:
        """デバイスアクセステスト（リトライ機能付き）"""
        if not self.p:
            return False, "PyAudioが初期化されていません", []
        
        for attempt in range(retry_count):
            try:
                # デバイス情報取得
                device_info = self.p.get_device_info_by_index(device_index)
                
                # ストリーム作成テスト
                if int(device_info['maxInputChannels']) > 0:
                    try:
                        # 設定からパラメータを取得
                        chunk_size = self.settings['audio']['chunk_size']
                        sample_rate = self.settings['audio']['sample_rate']
                        channels = self.settings['audio']['channels']
                        
                        stream = self.p.open(
                            format=pyaudio.paInt16,
                            channels=channels,
                            rate=sample_rate,
                            input=True,
                            input_device_index=device_index,
                            frames_per_buffer=chunk_size
                        )
                        stream.close()
                        return True, "アクセス可能", []
                    except Exception as e:
                        error_msg = str(e)
                        error_desc = PyAudioErrorHandler.get_error_description(error_msg)
                        suggestions = PyAudioErrorHandler.get_solution_suggestions(error_msg)
                        
                        if attempt < retry_count - 1:
                            logger.warning(f"デバイス {device_index} テスト試行 {attempt + 1} 失敗: {error_desc}")
                            time.sleep(1)  # 1秒待機
                            continue
                        else:
                            return False, error_desc, suggestions
                else:
                    return False, "入力チャンネルなし", []
                    
            except Exception as e:
                error_msg = str(e)
                if attempt < retry_count - 1:
                    logger.warning(f"デバイス {device_index} 情報取得試行 {attempt + 1} 失敗: {error_msg}")
                    time.sleep(1)
                    continue
                else:
                    return False, f"デバイス情報取得エラー: {error_msg}", []
        
        return False, "テスト失敗", []

class AudioRecorder:
    """音声録音クラス（エラーハンドリング強化）"""
    
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.p = None
    
    def __enter__(self):
        self.p = pyaudio.PyAudio()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.p:
            self.p.terminate()
    
    def record_with_error_handling(self, device_index: int, duration: int, gain: float) -> Tuple[Optional[list], Optional[int], Optional[str]]:
        """エラーハンドリング付き録音"""
        if not self.p:
            return None, None, "PyAudioが初期化されていません"
        
        try:
            # 設定からパラメータを取得
            chunk_size = self.settings['audio']['chunk_size']
            sample_rate = self.settings['audio']['sample_rate']
            channels = self.settings['audio']['channels']
            
            # ストリーム作成
            stream = self.p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=chunk_size
            )
            
            frames = []
            target_frames = int(sample_rate / chunk_size * duration)
            
            for i in range(target_frames):
                try:
                    data = stream.read(chunk_size, exception_on_overflow=False)
                    
                    # 音声レベルを上げる
                    audio_array = np.frombuffer(data, dtype=np.int16)
                    amplified_array = np.clip(audio_array * gain, -32768, 32767).astype(np.int16)
                    amplified_data = amplified_array.tobytes()
                    
                    frames.append(amplified_data)
                    
                except Exception as e:
                    error_msg = str(e)
                    error_desc = PyAudioErrorHandler.get_error_description(error_msg)
                    stream.close()
                    return None, None, error_desc
            
            stream.close()
            return frames, sample_rate, None
            
        except Exception as e:
            error_msg = str(e)
            error_desc = PyAudioErrorHandler.get_error_description(error_msg)
            return None, None, error_desc

def check_windows_microphone_permissions() -> Dict[str, Any]:
    """Windowsマイク権限の確認"""
    import subprocess
    import re
    
    result = {
        'microphone_enabled': False,
        'app_access_allowed': False,
        'desktop_app_access_allowed': False,
        'details': []
    }
    
    try:
        # PowerShellコマンドでレジストリを確認
        cmd = [
            'powershell', 
            '-Command', 
            'Get-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\microphone" -ErrorAction SilentlyContinue'
        ]
        
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        
        # 結果を解析
        if "Value" in output:
            result['microphone_enabled'] = True
            result['details'].append("マイク機能が有効です")
        else:
            result['details'].append("マイク機能が無効の可能性があります")
        
        # アプリアクセス権限を確認
        cmd_app = [
            'powershell',
            '-Command',
            'Get-ItemProperty -Path "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\microphone\\NonPackaged" -ErrorAction SilentlyContinue'
        ]
        
        try:
            output_app = subprocess.check_output(cmd_app, text=True, stderr=subprocess.STDOUT)
            if "Value" in output_app:
                result['app_access_allowed'] = True
                result['details'].append("アプリアクセスが許可されています")
            else:
                result['details'].append("アプリアクセスが制限されている可能性があります")
        except:
            result['details'].append("アプリアクセス権限の確認に失敗しました")
        
    except Exception as e:
        result['details'].append(f"権限確認エラー: {e}")
    
    return result

def get_audio_device_diagnostics() -> Dict[str, Any]:
    """オーディオデバイスの診断情報を取得"""
    p = pyaudio.PyAudio()
    diagnostics = {
        'total_devices': 0,
        'input_devices': 0,
        'output_devices': 0,
        'default_input': None,
        'default_output': None,
        'device_details': [],
        'errors': []
    }
    
    try:
        device_count = p.get_device_count()
        diagnostics['total_devices'] = device_count
        
        for i in range(device_count):
            try:
                device_info = p.get_device_info_by_index(i)
                device_detail = {
                    'index': i,
                    'name': device_info['name'],
                    'max_input_channels': int(device_info['maxInputChannels']),
                    'max_output_channels': int(device_info['maxOutputChannels']),
                    'default_sample_rate': int(device_info['defaultSampleRate']),
                    'host_api': device_info['hostApi']
                }
                
                if device_detail['max_input_channels'] > 0:
                    diagnostics['input_devices'] += 1
                if device_detail['max_output_channels'] > 0:
                    diagnostics['output_devices'] += 1
                
                diagnostics['device_details'].append(device_detail)
                
            except Exception as e:
                diagnostics['errors'].append(f"デバイス {i} の情報取得エラー: {e}")
        
        # デフォルトデバイス情報
        try:
            default_input = p.get_default_input_device_info()
            diagnostics['default_input'] = {
                'index': default_input['index'],
                'name': default_input['name']
            }
        except Exception as e:
            diagnostics['errors'].append(f"デフォルト入力デバイス取得エラー: {e}")
        
        try:
            default_output = p.get_default_output_device_info()
            diagnostics['default_output'] = {
                'index': default_output['index'],
                'name': default_output['name']
            }
        except Exception as e:
            diagnostics['errors'].append(f"デフォルト出力デバイス取得エラー: {e}")
        
    except Exception as e:
        diagnostics['errors'].append(f"診断エラー: {e}")
    finally:
        p.terminate()
    
    return diagnostics 