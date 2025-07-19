import asyncio
import websockets
import json
import pyaudio
import wave
import numpy as np
import uuid
import os
from datetime import datetime

class AudioServer:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.recording = False
        self.frames = []
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.chunk = 1024
        
    def start_recording(self):
        """録音開始"""
        try:
            if not self.recording:
                self.recording = True
                self.frames = []
                self.stream = self.p.open(
                    format=self.audio_format,
                    channels=self.channels,
                    rate=self.rate,
                    input=True,
                    frames_per_buffer=self.chunk
                )
                print("録音開始")
                # 録音データ収集を開始
                self._start_recording_thread()
                return {"status": "success", "message": "録音開始"}
            return {"status": "error", "message": "既に録音中です"}
        except Exception as e:
            print(f"録音開始エラー: {e}")
            self.recording = False
            return {"status": "error", "message": f"録音開始エラー: {e}"}
    
    def _start_recording_thread(self):
        """録音データ収集スレッド"""
        import threading
        def record_audio():
            while self.recording and self.stream:
                try:
                    data = self.stream.read(self.chunk, exception_on_overflow=False)
                    self.frames.append(data)
                except Exception as e:
                    print(f"録音データ収集エラー: {e}")
                    break
        
        self.record_thread = threading.Thread(target=record_audio)
        self.record_thread.daemon = True
        self.record_thread.start()
    
    def stop_recording(self):
        """録音停止"""
        try:
            if self.recording:
                self.recording = False
                if self.stream:
                    self.stream.stop_stream()
                    self.stream.close()
                    self.stream = None
                
                # ファイル保存
                if self.frames:
                    session_id = str(uuid.uuid4())
                    temp_dir = "audio_chunks"
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_path = os.path.join(temp_dir, f"{session_id}.wav")
                    
                    with wave.open(temp_path, "wb") as wf:
                        wf.setnchannels(self.channels)
                        wf.setsampwidth(self.p.get_sample_size(self.audio_format))
                        wf.setframerate(self.rate)
                        wf.writeframes(b''.join(self.frames))
                    
                    print(f"録音停止: {temp_path}")
                    return {
                        "status": "success", 
                        "message": "録音停止", 
                        "file_path": temp_path,
                        "frame_count": len(self.frames)
                    }
                else:
                    return {"status": "error", "message": "録音データがありません"}
            return {"status": "error", "message": "録音中ではありません"}
        except Exception as e:
            print(f"録音停止エラー: {e}")
            self.recording = False
            return {"status": "error", "message": f"録音停止エラー: {e}"}
    
    def get_status(self):
        """現在の状態を取得"""
        return {
            "recording": self.recording,
            "frame_count": len(self.frames),
            "audio_info": {
                "format": self.audio_format,
                "channels": self.channels,
                "rate": self.rate,
                "chunk": self.chunk
            }
        }

# グローバルインスタンス
audio_server = AudioServer()

async def websocket_handler(websocket):
    """WebSocketハンドラー"""
    print(f"新しいWebSocket接続: {websocket.remote_address}")
    try:
        async for message in websocket:
            print(f"受信メッセージ: {message}")
            try:
                data = json.loads(message)
                command = data.get("command")
                print(f"コマンド: {command}")
                
                if command == "start_recording":
                    result = audio_server.start_recording()
                    response = json.dumps(result)
                    print(f"録音開始レスポンス: {response}")
                    await websocket.send(response)
                    
                elif command == "stop_recording":
                    result = audio_server.stop_recording()
                    response = json.dumps(result)
                    print(f"録音停止レスポンス: {response}")
                    await websocket.send(response)
                    
                elif command == "get_status":
                    result = audio_server.get_status()
                    response = json.dumps(result)
                    print(f"状態取得レスポンス: {response}")
                    await websocket.send(response)
                    
                else:
                    response = json.dumps({
                        "status": "error", 
                        "message": f"不明なコマンド: {command}"
                    })
                    print(f"エラーレスポンス: {response}")
                    await websocket.send(response)
                    
            except json.JSONDecodeError as e:
                error_response = json.dumps({
                    "status": "error",
                    "message": f"JSONパースエラー: {e}"
                })
                print(f"JSONエラーレスポンス: {error_response}")
                await websocket.send(error_response)
            except Exception as e:
                error_response = json.dumps({
                    "status": "error",
                    "message": f"処理エラー: {e}"
                })
                print(f"処理エラーレスポンス: {error_response}")
                await websocket.send(error_response)
                
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket接続が閉じられました")
    except Exception as e:
        print(f"WebSocketハンドラーエラー: {e}")
        try:
            error_response = json.dumps({
                "status": "error",
                "message": f"WebSocketエラー: {e}"
            })
            await websocket.send(error_response)
        except:
            pass

async def main():
    """WebSocketサーバー起動"""
    server = await websockets.serve(websocket_handler, "localhost", 8765)
    print("WebSocketサーバーがポート8765で起動しました")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main()) 