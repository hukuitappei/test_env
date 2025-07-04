import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO, emit
import threading
import uuid # For generating session IDs
from werkzeug.utils import secure_filename
from utils.transcribe_utils import transcribe_audio_file
# For encryption (placeholder for now)
# from cryptography.fernet import Fernet
import subprocess
import json
import time
try:
    from dotenv import load_dotenv
    import openai
    from langchain_community.chat_models import ChatOpenAI
    from langchain.prompts import PromptTemplate
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    print("ImportError:", e)
    import traceback
    traceback.print_exc()
    LANGCHAIN_AVAILABLE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)

# ディレクトリの設定
UPLOAD_FOLDER = 'audio_chunks' # チャンクを保存するディレクトリ
TRANSCRIPTION_FOLDER = 'transcriptions'
RECORDINGS_ROOT = 'recordings' # 最終的な録音ファイルをまとめる場所
SETTINGS_FOLDER = 'settings' # 設定ファイルを保存する場所

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TRANSCRIPTION_FOLDER, exist_ok=True)
os.makedirs(RECORDINGS_ROOT, exist_ok=True)
os.makedirs(SETTINGS_FOLDER, exist_ok=True)

# 一時的な音声チャンクの情報を保持する辞書
# {session_id: {chunk_index: filepath, ...}, ...}
# あるいは、文字起こしが完了したチャンクの情報を保持し、後で結合するための情報
# {session_id: [{chunk_index: int, text: str, timestamp: datetime}, ...]}
# チャンクごとに文字起こしを実行するので、ここではセッションごとのチャンク管理は不要かもしれません。
# transcribe_audio_file_async に session_id と chunk_index を渡すことで、
# utils/transcribe_utils.py で適切なファイル名で保存するようにします。

if LANGCHAIN_AVAILABLE:
    load_dotenv()
    openai.api_key = os.getenv('OPENAI_API_KEY')

COMMAND_DICT_PATH = os.path.join(SETTINGS_FOLDER, 'command_dictionary.json')
WORD_DICT_PATH = os.path.join(SETTINGS_FOLDER, 'word_dictionary.json')
TOKEN_USAGE_PATH = os.path.join(SETTINGS_FOLDER, 'token_usage.json')
MODEL_PRICING = {
    'gpt-4o': 0.005 / 1000,  # $0.005/1K tokens
    'gpt-4': 0.03 / 1000,    # $0.03/1K tokens
    'gpt-3.5-turbo': 0.001 / 1000, # $0.001/1K tokens
}

def load_dict(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_dict(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_token_usage():
    if not os.path.exists(TOKEN_USAGE_PATH):
        return []
    with open(TOKEN_USAGE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_token_usage(data):
    with open(TOKEN_USAGE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def record_token_usage(model, prompt_tokens, completion_tokens, total_tokens):
    usage = load_token_usage()
    unit_price = MODEL_PRICING.get(model, 0.005 / 1000)  # デフォルトgpt-4o
    cost = total_tokens * unit_price
    usage.append({
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'model': model,
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'total_tokens': total_tokens,
        'cost': cost
    })
    save_token_usage(usage)

@app.route('/')
def index():
    """
    Webアプリケーションのメインページを提供します。
    """
    return render_template('index.html')

@app.route('/upload_audio_chunk', methods=['POST'])
def upload_audio_chunk():
    """
    録音された音声チャンクを受け取り、文字起こし処理を開始します。
    """
    if 'audio_chunk' not in request.files:
        return jsonify({'error': 'No audio chunk part'}), 400

    audio_chunk = request.files['audio_chunk']
    session_id = request.form.get('session_id')
    chunk_index = request.form.get('chunk_index')

    if not session_id or not chunk_index:
        return jsonify({'error': 'Missing session_id or chunk_index'}), 400

    if audio_chunk.filename == '':
        return jsonify({'error': 'No selected audio chunk'}), 400

    if audio_chunk:
        session_upload_dir = os.path.join(UPLOAD_FOLDER, secure_filename(session_id))
        os.makedirs(session_upload_dir, exist_ok=True)

        # 一時的にwebmで保存
        filename_webm = secure_filename(f"{session_id}_chunk{chunk_index}.webm")
        filepath_webm = os.path.join(session_upload_dir, filename_webm)
        audio_chunk.save(filepath_webm)

        # ffmpegでwav(pcm)に変換
        filename_wav = secure_filename(f"{session_id}_chunk{chunk_index}.wav")
        filepath_wav = os.path.join(session_upload_dir, filename_wav)
        try:
            # ffmpegがインストールされているか確認
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except Exception as e:
            return jsonify({'error': 'ffmpegがインストールされていません。公式サイトからインストールしてください。'}), 500
        try:
            # -y: 上書き, -i: 入力, -ar 16000: サンプリングレート, -ac 1: モノラル, -f wav: WAV形式, -acodec pcm_s16le: PCM16bit
            result = subprocess.run([
                "ffmpeg", "-y", "-i", filepath_webm, "-ar", "16000", "-ac", "1", "-f", "wav", "-acodec", "pcm_s16le", filepath_wav
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                return jsonify({'error': 'ffmpegによる変換に失敗しました: ' + result.stderr.decode('utf-8')}), 500
        except Exception as e:
            return jsonify({'error': f'ffmpeg変換エラー: {str(e)}'}), 500

        # 非同期で文字起こしを実行（wavファイルを渡す）
        threading.Thread(target=transcribe_audio_chunk_async, args=(filepath_wav, session_id, chunk_index, TRANSCRIPTION_FOLDER, None)).start()

        return jsonify({'message': 'Audio chunk uploaded and transcription started', 'filename': filename_wav}), 200
    # audio_chunkがなかった場合
    return jsonify({'error': 'audio_chunkが不正です'}), 400

@app.route('/finalize_recording', methods=['POST'])
def finalize_recording():
    """
    録音セッションの終了を通知し、全てのチャンクの文字起こしが完了した後に最終的なテキストファイルを生成します。
    """
    data = request.get_json() or {}
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'Missing session_id'}), 400

    threading.Thread(target=combine_transcriptions_async, args=(session_id, TRANSCRIPTION_FOLDER, RECORDINGS_ROOT, None)).start()

    return jsonify({'message': f'Recording session {session_id} finalized. Combining transcriptions.'}), 200

@app.route('/transcriptions/<path:filename>') # path converter enables paths with slashes
def get_transcription(filename):
    """
    文字起こしされたテキストファイルを提供します。
    """
    return send_from_directory(TRANSCRIPTION_FOLDER, filename)

@app.route('/list_transcriptions', methods=['GET'])
def list_transcriptions():
    """
    保存されている文字起こしファイルのリストを返します。
    """
    transcription_files = []
    for root, _, files in os.walk(TRANSCRIPTION_FOLDER):
        for file in files:
            if file.endswith('.txt'):
                # root から TRANSCRIPTION_FOLDER の部分を削除して相対パスにする
                relative_path = os.path.relpath(os.path.join(root, file), TRANSCRIPTION_FOLDER)
                transcription_files.append(relative_path)
    return jsonify({'transcriptions': sorted(transcription_files)}), 200

# Placeholder for settings (Step 1.4)
@app.route('/settings', methods=['GET', 'POST'])
def handle_settings():
    # TODO: Implement reading/writing settings from SETTINGS_FOLDER/settings.json
    # For now, just a placeholder.
    if request.method == 'GET':
        return jsonify({'message': 'Settings retrieval not implemented yet.'}), 501
    elif request.method == 'POST':
        return jsonify({'message': 'Settings saving not implemented yet.'}), 501
    return jsonify({'error': 'Invalid method'}), 405

# Placeholder for user trouble logging (Step 1.6 - part 2)
@app.route('/log_trouble', methods=['POST'])
def log_trouble():
    # TODO: Implement logging user-reported troubles
    # request.json will contain details like 'operation', 'what_happened', etc.
    # For now, just a placeholder.
    print(f"User reported trouble: {request.json}")
    return jsonify({'message': 'Trouble reported successfully.'}), 200

@app.route('/summarize', methods=['POST'])
def summarize():
    """
    文字起こしテキストを受け取り、日本語で要約を返すAPI。
    OpenAI APIのusage情報があればトークン利用量を記録する。
    """
    import sys
    print("=== /summarize called ===", flush=True)
    sys.stdout.flush()
    if not LANGCHAIN_AVAILABLE:
        print("LangChainまたはOpenAI関連パッケージがインストールされていません")
        return jsonify({'error': 'LangChainまたはOpenAI関連パッケージがインストールされていません'}), 500
    data = request.get_json() or {}
    print("/summarize called. data:", data)
    text = data.get('text', '')
    print("text:", text)
    if not text:
        print("テキストがありません")
        return jsonify({'error': 'テキストがありません'}), 400
    try:
        prompt = PromptTemplate(
            input_variables=["text"],
            template="""以下の日本語テキストを3行以内で要約してください：\n{text}\n要約："""
        )
        print("PromptTemplate作成完了")
        llm = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo")
        print("ChatOpenAIインスタンス作成完了")
        result = llm.invoke(prompt.format(text=text), max_tokens=256)
        summary = None
        # usage情報取得
        usage = getattr(result, 'usage', None)
        model = getattr(llm, 'model_name', 'gpt-4o')
        if hasattr(llm, 'model'):  # langchainのChatOpenAI
            model = getattr(llm, 'model', model)
        if usage:
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            total_tokens = usage.get('total_tokens', prompt_tokens + completion_tokens)
            record_token_usage(model, prompt_tokens, completion_tokens, total_tokens)
        # summary抽出
        if hasattr(result, "content"):
            summary = str(result.content).strip()
        elif isinstance(result, list) and len(result) > 0:
            first = result[0]
            if hasattr(first, "content"):
                summary = str(first.content).strip()
            elif isinstance(first, dict) and "content" in first:
                summary = str(first.get("content", "")).strip()
            elif isinstance(first, str):
                summary = first.strip()
            else:
                summary = str(first).strip()
        elif isinstance(result, dict) and "content" in result:
            summary = str(result.get("content", "")).strip()
        elif isinstance(result, str):
            summary = result.strip()
        else:
            summary = str(result).strip()
        print("summary生成結果:", summary)
        return jsonify({'summary': summary}), 200
    except Exception as e:
        print("Error in /summarize:", e)
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'要約生成に失敗しました: {str(e)}'}), 500

@app.route('/api/command_dictionary', methods=['GET', 'POST', 'PUT', 'DELETE'])
def command_dictionary():
    if request.method == 'GET':
        return jsonify(load_dict(COMMAND_DICT_PATH)), 200
    elif request.method == 'POST':
        data = request.get_json() or {}
        word = data.get('word', '').strip()
        if not word:
            return jsonify({'error': '単語が空です'}), 400
        dict_data = load_dict(COMMAND_DICT_PATH)
        if word in dict_data:
            return jsonify({'error': '既に登録されています'}), 400
        dict_data.append(word)
        save_dict(COMMAND_DICT_PATH, dict_data)
        return jsonify({'message': '登録しました', 'word': word}), 201
    elif request.method == 'PUT':
        data = request.get_json() or {}
        old_word = data.get('old_word', '').strip()
        new_word = data.get('new_word', '').strip()
        dict_data = load_dict(COMMAND_DICT_PATH)
        if old_word not in dict_data:
            return jsonify({'error': '元の単語が見つかりません'}), 404
        if new_word in dict_data:
            return jsonify({'error': '新しい単語が既に存在します'}), 400
        dict_data[dict_data.index(old_word)] = new_word
        save_dict(COMMAND_DICT_PATH, dict_data)
        return jsonify({'message': '編集しました', 'old_word': old_word, 'new_word': new_word}), 200
    elif request.method == 'DELETE':
        data = request.get_json() or {}
        word = data.get('word', '').strip()
        dict_data = load_dict(COMMAND_DICT_PATH)
        if word not in dict_data:
            return jsonify({'error': '単語が見つかりません'}), 404
        dict_data.remove(word)
        save_dict(COMMAND_DICT_PATH, dict_data)
        return jsonify({'message': '削除しました', 'word': word}), 200
    return jsonify({'error': '不正なメソッドです'}), 405

@app.route('/api/word_dictionary', methods=['GET', 'POST', 'PUT', 'DELETE'])
def word_dictionary():
    if request.method == 'GET':
        return jsonify(load_dict(WORD_DICT_PATH)), 200
    elif request.method == 'POST':
        data = request.get_json() or {}
        word = data.get('word', '').strip()
        if not word:
            return jsonify({'error': '単語が空です'}), 400
        dict_data = load_dict(WORD_DICT_PATH)
        if word in dict_data:
            return jsonify({'error': '既に登録されています'}), 400
        dict_data.append(word)
        save_dict(WORD_DICT_PATH, dict_data)
        return jsonify({'message': '登録しました', 'word': word}), 201
    elif request.method == 'PUT':
        data = request.get_json() or {}
        old_word = data.get('old_word', '').strip()
        new_word = data.get('new_word', '').strip()
        dict_data = load_dict(WORD_DICT_PATH)
        if old_word not in dict_data:
            return jsonify({'error': '元の単語が見つかりません'}), 404
        if new_word in dict_data:
            return jsonify({'error': '新しい単語が既に存在します'}), 400
        dict_data[dict_data.index(old_word)] = new_word
        save_dict(WORD_DICT_PATH, dict_data)
        return jsonify({'message': '編集しました', 'old_word': old_word, 'new_word': new_word}), 200
    elif request.method == 'DELETE':
        data = request.get_json() or {}
        word = data.get('word', '').strip()
        dict_data = load_dict(WORD_DICT_PATH)
        if word not in dict_data:
            return jsonify({'error': '単語が見つかりません'}), 404
        dict_data.remove(word)
        save_dict(WORD_DICT_PATH, dict_data)
        return jsonify({'message': '削除しました', 'word': word}), 200
    return jsonify({'error': '不正なメソッドです'}), 405

@app.route('/api/token_usage', methods=['GET'])
def api_token_usage():
    usage = load_token_usage()
    total_tokens = sum(u['total_tokens'] for u in usage)
    total_cost = sum(u['cost'] for u in usage)
    return jsonify({
        'usage': usage,
        'total_tokens': total_tokens,
        'total_cost': total_cost
    })

def transcribe_audio_chunk_async(filepath, session_id, chunk_index, transcription_folder, client_sid):
    """
    非同期で音声チャンクを文字起こしします。
    """
    # TODO: Decrypt audio file here (Step 1.3)
    # with open(filepath, 'rb') as f:
    #     encrypted_data = f.read()
    # decrypted_data = Fernet(ENCRYPTION_KEY).decrypt(encrypted_data)
    # temp_decrypted_filepath = filepath + ".decrypted"
    # with open(temp_decrypted_filepath, 'wb') as f:
    #     f.write(decrypted_data)

    if client_sid:
        socketio.emit('transcription_status', {'status': 'processing_chunk', 'session_id': session_id, 'chunk_index': chunk_index})

    text = transcribe_audio_file(filepath, session_id, chunk_index, transcription_folder)

    # TODO: Remove temp_decrypted_filepath

    if text:
        if client_sid:
            socketio.emit('transcription_status', {'status': 'chunk_completed', 'session_id': session_id, 'chunk_index': chunk_index, 'text': text})
    else:
        if client_sid:
            socketio.emit('transcription_status', {'status': 'chunk_failed', 'session_id': session_id, 'chunk_index': chunk_index})

def generate_tag(text):
    """
    LLMで内容から短いタグ（キーワード）を生成する。
    """
    if not LANGCHAIN_AVAILABLE:
        return "untagged"
    try:
        prompt = PromptTemplate(
            input_variables=["text"],
            template="""以下の日本語テキストの内容を一言で表す短いタグ（2〜5文字程度）を1つだけ出力してください。\n{text}\nタグ："""
        )
        llm = ChatOpenAI(temperature=0.2, model="gpt-3.5-turbo")
        result = llm.invoke(prompt.format(text=text), max_tokens=16)
        if hasattr(result, "content"):
            tag = str(result.content).strip().replace("\n", "")
        elif isinstance(result, str):
            tag = result.strip().replace("\n", "")
        else:
            tag = str(result).strip().replace("\n", "")
        # 記号や空白を除去
        import re
        tag = re.sub(r"[^\w\u3040-\u30ff\u4e00-\u9fff]", "", tag)
        if not tag:
            tag = "untagged"
        return tag
    except Exception as e:
        print("タグ生成失敗:", e)
        return "untagged"

@app.route('/generate_tag', methods=['POST'])
def api_generate_tag():
    data = request.get_json() or {}
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'テキストがありません'}), 400
    tag = generate_tag(text)
    return jsonify({'tag': tag}), 200

def combine_transcriptions_async(session_id, transcription_folder, recordings_root, client_sid):
    """
    指定されたセッションIDに紐づく全ての文字起こしチャンクを結合し、最終的なテキストファイルを生成します。
    ファイル名はタイムスタンプ＋内容タグとする。
    """
    if client_sid:
        socketio.emit('transcription_status', {'status': 'combining_results', 'session_id': session_id})

    # セッションIDに紐づく文字起こしチャンクファイルを検索し、ソートして結合
    session_transcriptions = []
    session_transcription_dir = os.path.join(transcription_folder, secure_filename(session_id))
    if os.path.exists(session_transcription_dir):
        files = []
        for f in os.listdir(session_transcription_dir):
            if f.startswith(f"{session_id}_chunk") and f.endswith(".txt"):
                try:
                    chunk_num_str = f.replace(f"{session_id}_chunk", "").replace(".txt", "")
                    chunk_num = int(chunk_num_str)
                    files.append((chunk_num, os.path.join(session_transcription_dir, f)))
                except ValueError:
                    continue
        files.sort()
        for _, filepath in files:
            with open(filepath, 'r', encoding='utf-8') as f:
                session_transcriptions.append(f.read())
        final_text = "\n".join(session_transcriptions)
        # タグ生成
        tag = generate_tag(final_text)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        combined_text_filename = f"{timestamp}_{tag}.txt"
        combined_filepath = os.path.join(recordings_root, combined_text_filename)
        with open(combined_filepath, 'w', encoding='utf-8') as f:
            f.write(final_text)
        print(f"Combined transcription saved: {combined_filepath}")
        if client_sid:
            socketio.emit('transcription_status', {'status': 'final_completed', 'session_id': session_id, 'final_filename': combined_text_filename})
    else:
        print(f"No transcription chunks found for session {session_id}")
        if client_sid:
            socketio.emit('transcription_status', {'status': 'final_failed', 'session_id': session_id, 'error': 'No chunks found'})

def test_connect():
    print('Client connected')

def test_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, debug=True) 