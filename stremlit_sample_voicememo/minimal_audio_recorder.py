import streamlit as st
import websocket
import json
import threading
import time
import os
import uuid
import wave
import numpy as np

# Whisperのインポート
try:
    import whisper
except ImportError:
    whisper = None

st.title("PyAudio音声録音＆保存（WebSocket）")

# WebSocket接続管理
if "websocket" not in st.session_state:
    st.session_state["websocket"] = None
if "recording" not in st.session_state:
    st.session_state["recording"] = False
if "audio_saved" not in st.session_state:
    st.session_state["audio_saved"] = False
if "audio_path" not in st.session_state:
    st.session_state["audio_path"] = None
if "server_status" not in st.session_state:
    st.session_state["server_status"] = "未接続"

def connect_websocket():
    """WebSocket接続"""
    try:
        ws = websocket.create_connection("ws://localhost:8765")
        st.session_state["websocket"] = ws
        st.session_state["server_status"] = "接続済み"
        st.write("[WebSocket] サーバーに接続しました")
        return True
    except Exception as e:
        st.error(f"[WebSocket] 接続エラー: {e}")
        st.session_state["server_status"] = "接続エラー"
        return False

def disconnect_websocket():
    """WebSocket切断"""
    if st.session_state["websocket"]:
        try:
            st.session_state["websocket"].close()
            st.session_state["websocket"] = None
            st.session_state["server_status"] = "未接続"
            st.write("[WebSocket] 接続を切断しました")
        except Exception as e:
            st.error(f"[WebSocket] 切断エラー: {e}")

def send_command(command):
    """WebSocketサーバーにコマンド送信"""
    if not st.session_state["websocket"]:
        if not connect_websocket():
            return None
    
    try:
        message = json.dumps({"command": command})
        st.session_state["websocket"].send(message)
        response = st.session_state["websocket"].recv()
        return json.loads(response)
    except Exception as e:
        st.error(f"[WebSocket] コマンド送信エラー: {e}")
        disconnect_websocket()
        return None

# 接続管理
st.subheader("サーバー接続")
col1, col2 = st.columns(2)
with col1:
    if st.button("サーバー接続"):
        connect_websocket()
with col2:
    if st.button("サーバー切断"):
        disconnect_websocket()

st.write(f"サーバー状態: {st.session_state['server_status']}")

# 録音制御
st.subheader("録音制御")
col1, col2 = st.columns(2)

with col1:
    if st.button("録音開始", disabled=st.session_state["recording"]):
        result = send_command("start_recording")
        if result and result.get("status") == "success":
            st.session_state["recording"] = True
            st.session_state["audio_saved"] = False
            st.session_state["audio_path"] = None
            st.write(f"[録音開始] {result.get('message')}")
        else:
            st.error(f"[録音開始] エラー: {result.get('message') if result else 'サーバー接続エラー'}")

with col2:
    if st.button("録音停止", disabled=not st.session_state["recording"]):
        result = send_command("stop_recording")
        if result and result.get("status") == "success":
            st.session_state["recording"] = False
            st.session_state["audio_saved"] = True
            st.session_state["audio_path"] = result.get("file_path")
            st.success(f"[録音停止] {result.get('message')}")
            st.info(f"保存ファイル: {result.get('file_path')}")
            st.info(f"フレーム数: {result.get('frame_count')}")
        else:
            st.error(f"[録音停止] エラー: {result.get('message') if result else 'サーバー接続エラー'}")

# 状態確認
if st.button("状態確認"):
    result = send_command("get_status")
    if result:
        st.write("サーバー状態:", result)
    else:
        st.error("状態取得エラー")

# デバッグ表示
st.markdown("---")
st.subheader("[デバッグ情報]")
st.write("st.session_state:", dict(st.session_state))

# 保存されたファイルの表示
if st.session_state["audio_path"] and os.path.exists(st.session_state["audio_path"]):
    st.subheader("保存された音声ファイル")
    st.write(f"ファイルパス: {st.session_state['audio_path']}")
    
    # ファイル情報表示
    try:
        with wave.open(st.session_state["audio_path"], "rb") as wf:
            st.write(f"チャンネル数: {wf.getnchannels()}")
            st.write(f"サンプル幅: {wf.getsampwidth()}")
            st.write(f"サンプリングレート: {wf.getframerate()}")
            st.write(f"フレーム数: {wf.getnframes()}")
            st.write(f"再生時間: {wf.getnframes() / wf.getframerate():.2f}秒")
    except Exception as e:
        st.error(f"ファイル情報取得エラー: {e}")
    
    # 音声再生（HTML5 audio）
    st.audio(st.session_state["audio_path"])

# 注意事項
st.markdown("---")
st.warning("""
**使用方法:**
1. まず「サーバー接続」ボタンを押してWebSocketサーバーに接続
2. 「録音開始」ボタンで録音開始
3. 「録音停止」ボタンで録音停止・ファイル保存

**注意:** WebSocketサーバー（audio_server.py）を別途起動する必要があります。
""") 