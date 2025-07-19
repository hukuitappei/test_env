@echo off
echo ================================================
echo PyAudio音声録音アプリ - Windows起動スクリプト
echo ================================================
echo.

REM Pythonがインストールされているか確認
python --version >nul 2>&1
if errorlevel 1 (
    echo エラー: Pythonがインストールされていません
    echo Pythonをインストールしてから再実行してください
    pause
    exit /b 1
)

REM 必要なライブラリがインストールされているか確認
echo 必要なライブラリを確認しています...
python -c "import streamlit, pyaudio, websockets" >nul 2>&1
if errorlevel 1 (
    echo 必要なライブラリをインストールしています...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo エラー: ライブラリのインストールに失敗しました
        pause
        exit /b 1
    )
)

echo.
echo アプリケーションを起動しています...
echo.

REM 統合起動スクリプトを実行
python run_app.py

echo.
echo アプリケーションが終了しました
pause 