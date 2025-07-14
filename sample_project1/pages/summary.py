import streamlit as st
import os

st.header('文字起こし一覧・要約')

TRANSCRIPTIONS_DIR = '../transcriptions/'

def list_transcriptions():
    files = []
    for root, dirs, filenames in os.walk(TRANSCRIPTIONS_DIR):
        for f in filenames:
            if f.endswith('.txt'):
                files.append(os.path.join(root, f))
    return files

files = list_transcriptions()
if not files:
    st.info('文字起こしファイルがありません')
else:
    selected = st.selectbox('文字起こしファイルを選択', files)
    with open(selected, 'r', encoding='utf-8') as f:
        text = f.read()
    st.text_area('内容', text, height=200)
    # 要約機能
    st.subheader('要約')
    api_key = st.text_input('OpenAI APIキー', type='password', key='openai_api_key')
    if st.button('要約実行'):
        if not api_key:
            st.error('APIキーを入力してください')
        else:
            st.write('（ここでAPIを呼び出して要約を表示）')
            # 実際の要約処理はutils等に分離してimportして使う想定 