import speech_recognition as sr
import os
import shutil # For cleaning up session-specific transcription folders

def transcribe_audio_file(filepath, session_id, chunk_index, transcription_folder):
    """
    音声チャンクを文字起こしし、結果をセッションIDとチャンクインデックスに基づいたファイル名で保存します。
    """
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(filepath) as source:
            audio_data = recognizer.record(source)
        
        # Google Web Speech API を使用して文字起こし
        text = recognizer.recognize_google(audio_data, language='ja-JP')
        
        # セッションごとの文字起こしディレクトリを作成
        session_transcription_dir = os.path.join(transcription_folder, session_id)
        os.makedirs(session_transcription_dir, exist_ok=True)

        # チャンクごとにテキストファイルを保存
        transcription_filename = f"{session_id}_chunk{chunk_index}.txt"
        transcription_filepath = os.path.join(session_transcription_dir, transcription_filename)
        with open(transcription_filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Transcription chunk saved: {transcription_filepath}")
        return text # 文字起こし結果を返す

    except sr.UnknownValueError:
        print("Google Speech Recognition could not understand audio")
        return None
    except sr.RequestError as e:
        print(f"Could not request results from Google Speech Recognition service; {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during transcription: {e}")
        return None

def clean_up_session_chunks(session_id, upload_folder, transcription_folder):
    """
    指定されたセッションIDに紐づく一時的な音声チャンクと文字起こしチャンクのディレクトリを削除します。
    """
    session_upload_dir = os.path.join(upload_folder, session_id)
    if os.path.exists(session_upload_dir):
        shutil.rmtree(session_upload_dir)
        print(f"Cleaned up upload directory for session {session_id}: {session_upload_dir}")

    session_transcription_dir = os.path.join(transcription_folder, session_id)
    if os.path.exists(session_transcription_dir):
        shutil.rmtree(session_transcription_dir)
        print(f"Cleaned up transcription directory for session {session_id}: {session_transcription_dir}") 