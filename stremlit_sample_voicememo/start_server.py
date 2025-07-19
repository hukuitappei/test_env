#!/usr/bin/env python3
"""
WebSocketサーバー起動スクリプト
"""

import subprocess
import sys
import time
import os

def start_websocket_server():
    """WebSocketサーバーを起動"""
    print("WebSocketサーバーを起動しています...")
    
    # audio_server.pyのパスを取得
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(current_dir, "audio_server.py")
    
    try:
        # WebSocketサーバーを起動
        process = subprocess.Popen([sys.executable, server_path])
        print(f"WebSocketサーバーが起動しました (PID: {process.pid})")
        print("サーバーはポート8765で動作しています")
        print("Ctrl+Cで停止できます")
        
        # プロセスが終了するまで待機
        process.wait()
        
    except KeyboardInterrupt:
        print("\nサーバーを停止しています...")
        if process:
            process.terminate()
            process.wait()
        print("サーバーが停止しました")
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    start_websocket_server() 