import streamlit as st
import time

def show_recording_animation():
    """
    録音中アニメーションを表示する（Streamlit用）。
    点滅する赤丸と「録音中...」のテキストを表示。
    """
    st.markdown(
        """
        <style>
        .blinking {
            animation: blinker 1s linear infinite;
            color: red;
            font-size: 2em;
        }
        @keyframes blinker {
            50% { opacity: 0; }
        }
        </style>
        <div class="blinking">● 録音中...</div>
        """,
        unsafe_allow_html=True
    ) 