import streamlit as st
import os
import json

st.header('辞書管理')

DICT_PATH = '../settings/dictionary.json'

def load_dict():
    if os.path.exists(DICT_PATH):
        with open(DICT_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_dict(d):
    with open(DICT_PATH, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

d = load_dict()
st.subheader('コマンド辞書')
if 'commands' not in d:
    d['commands'] = {}
cmd = st.text_input('コマンド名')
val = st.text_input('内容')
if st.button('追加/更新'):
    d['commands'][cmd] = val
    save_dict(d)
    st.success('保存しました')
if st.button('全削除'):
    d['commands'] = {}
    save_dict(d)
    st.warning('全削除しました')
st.write(d['commands'])

st.subheader('単語辞書')
if 'words' not in d:
    d['words'] = {}
word = st.text_input('単語')
meaning = st.text_input('意味')
if st.button('単語追加/更新'):
    d['words'][word] = meaning
    save_dict(d)
    st.success('保存しました')
if st.button('単語全削除'):
    d['words'] = {}
    save_dict(d)
    st.warning('単語全削除しました')
st.write(d['words']) 