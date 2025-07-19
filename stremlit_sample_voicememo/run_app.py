#!/usr/bin/env python3
"""
WebSocketサーバーとStreamlitアプリを同時に起動するスクリプト
"""

import subprocess
import sys
import time
import os
import threading
import signal
import atexit

class AppLauncher:
    def __init__(self):
        self.websocket_process = None
        self.streamlit_process = None
        self.running = True
        
        # シグナルハンドラー設定
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # 終了時の処理を登録
        atexit.register(self.cleanup)
    
    def signal_handler(self, signum, frame):
        """シグナルハンドラー"""
        print(f"\nシグナル {signum} を受信しました。アプリケーションを終了します...")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """プロセスをクリーンアップ"""
        print("プロセスを終了しています...")
        
        if self.streamlit_process:
            print("Streamlitプロセスを終了中...")
            self.streamlit_process.terminate()
            try:
                self.streamlit_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.streamlit_process.kill()
        
        if self.websocket_process:
            print("WebSocketプロセスを終了中...")
            self.websocket_process.terminate()
            try:
                self.websocket_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.websocket_process.kill()
        
        print("すべてのプロセスが終了しました")
    
    def start_websocket_server(self):
        """WebSocketサーバーを起動"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            server_path = os.path.join(current_dir, "audio_server.py")
            
            print("WebSocketサーバーを起動しています...")
            self.websocket_process = subprocess.Popen(
                [sys.executable, server_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print(f"WebSocketサーバーが起動しました (PID: {self.websocket_process.pid})")
            
            # サーバーが起動するまで少し待機
            time.sleep(2)
            
            # プロセスの状態を確認
            if self.websocket_process.poll() is None:
                print("WebSocketサーバーが正常に起動しました")
                return True
            else:
                stdout, stderr = self.websocket_process.communicate()
                print(f"WebSocketサーバー起動エラー: {stderr}")
                return False
                
        except Exception as e:
            print(f"WebSocketサーバー起動エラー: {e}")
            return False
    
    def start_streamlit_app(self):
        """Streamlitアプリを起動"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            app_path = os.path.join(current_dir, "minimal_audio_recorder.py")
            
            print("Streamlitアプリを起動しています...")
            self.streamlit_process = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", app_path, "--server.port", "8501"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print(f"Streamlitアプリが起動しました (PID: {self.streamlit_process.pid})")
            print("ブラウザで http://localhost:8501 にアクセスしてください")
            
            return True
            
        except Exception as e:
            print(f"Streamlitアプリ起動エラー: {e}")
            return False
    
    def monitor_processes(self):
        """プロセスの監視"""
        while self.running:
            time.sleep(1)
            
            # WebSocketプロセスの状態確認
            if self.websocket_process and self.websocket_process.poll() is not None:
                print("WebSocketサーバーが予期せず終了しました")
                self.running = False
                break
            
            # Streamlitプロセスの状態確認
            if self.streamlit_process and self.streamlit_process.poll() is not None:
                print("Streamlitアプリが予期せず終了しました")
                self.running = False
                break
    
    def run(self):
        """アプリケーションを実行"""
        print("=" * 50)
        print("PyAudio音声録音アプリ - 統合起動スクリプト")
        print("=" * 50)
        
        # WebSocketサーバー起動
        if not self.start_websocket_server():
            print("WebSocketサーバーの起動に失敗しました")
            return False
        
        # Streamlitアプリ起動
        if not self.start_streamlit_app():
            print("Streamlitアプリの起動に失敗しました")
            self.cleanup()
            return False
        
        print("\n" + "=" * 50)
        print("アプリケーションが正常に起動しました！")
        print("ブラウザで http://localhost:8501 にアクセスしてください")
        print("Ctrl+Cで終了できます")
        print("=" * 50)
        
        # プロセス監視
        self.monitor_processes()
        
        return True

def main():
    """メイン関数"""
    launcher = AppLauncher()
    try:
        launcher.run()
    except KeyboardInterrupt:
        print("\nキーボード割り込みを検出しました")
    except Exception as e:
        print(f"予期しないエラー: {e}")
    finally:
        launcher.cleanup()

if __name__ == "__main__":
    main() 