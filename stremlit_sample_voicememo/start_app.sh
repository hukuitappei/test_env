#!/bin/bash

echo "================================================"
echo "PyAudio音声録音アプリ - Linux/Mac起動スクリプト"
echo "================================================"
echo

# Pythonがインストールされているか確認
if ! command -v python3 &> /dev/null; then
    echo "エラー: Python3がインストールされていません"
    echo "Python3をインストールしてから再実行してください"
    exit 1
fi

# 必要なライブラリがインストールされているか確認
echo "必要なライブラリを確認しています..."
python3 -c "import streamlit, pyaudio, websockets" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "必要なライブラリをインストールしています..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "エラー: ライブラリのインストールに失敗しました"
        exit 1
    fi
fi

echo
echo "アプリケーションを起動しています..."
echo

# 統合起動スクリプトを実行
python3 run_app.py

echo
echo "アプリケーションが終了しました" 