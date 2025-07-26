import whisper
import streamlit as st
import os
from typing import Dict, Any, Optional
from .settings_manager import load_settings

@st.cache_resource
def get_whisper_model(model_size: Optional[str] = None) -> Optional[whisper.Whisper]:
    """Whisperモデルを取得（キャッシュ付き）"""
    if model_size is None:
        settings = load_settings()
        model_size = settings['whisper']['model_size']
    
    try:
        model = whisper.load_model(model_size)
        return model
    except Exception as e:
        st.error(f"Whisperモデル読み込みエラー: {e}")
        return None

def transcribe_audio(audio_file_path: str) -> Optional[str]:
    """通常精度で音声を文字起こし"""
    settings = load_settings()
    model = get_whisper_model(settings['whisper']['model_size'])
    
    if model is None:
        return None
    
    try:
        if not os.path.exists(audio_file_path):
            st.error(f"音声ファイルが見つかりません: {audio_file_path}")
            return None
        
        with st.spinner("文字起こし中..."):
            result = model.transcribe(
                audio_file_path,
                language=settings['whisper']['language'],
                temperature=settings['whisper']['temperature'],
                compression_ratio_threshold=settings['whisper']['compression_ratio_threshold'],
                logprob_threshold=settings['whisper']['logprob_threshold'],
                no_speech_threshold=settings['whisper']['no_speech_threshold'],
                condition_on_previous_text=settings['whisper']['condition_on_previous_text'],
                initial_prompt=settings['whisper']['initial_prompt']
            )
        
        return result["text"]
        
    except Exception as e:
        st.error(f"文字起こしエラー: {e}")
        return None

def transcribe_audio_high_quality(audio_file_path: str) -> Optional[str]:
    """高精度で音声を文字起こし"""
    settings = load_settings()
    
    # 高精度用の設定
    high_quality_settings = settings['whisper'].copy()
    high_quality_settings['temperature'] = 0.0
    high_quality_settings['compression_ratio_threshold'] = 1.6
    high_quality_settings['logprob_threshold'] = -1.0
    high_quality_settings['no_speech_threshold'] = 0.4
    
    model = get_whisper_model(settings['whisper']['model_size'])
    
    if model is None:
        return None
    
    try:
        if not os.path.exists(audio_file_path):
            st.error(f"音声ファイルが見つかりません: {audio_file_path}")
            return None
        
        with st.spinner("高精度文字起こし中..."):
            result = model.transcribe(
                audio_file_path,
                language=high_quality_settings['language'],
                temperature=high_quality_settings['temperature'],
                compression_ratio_threshold=high_quality_settings['compression_ratio_threshold'],
                logprob_threshold=high_quality_settings['logprob_threshold'],
                no_speech_threshold=high_quality_settings['no_speech_threshold'],
                condition_on_previous_text=high_quality_settings['condition_on_previous_text'],
                initial_prompt=high_quality_settings['initial_prompt']
            )
        
        return result["text"]
        
    except Exception as e:
        st.error(f"高精度文字起こしエラー: {e}")
        return None

def compare_transcriptions(audio_file_path: str) -> Dict[str, str]:
    """複数のモデルで文字起こしを比較"""
    results = {}
    
    # 異なるモデルサイズで比較
    model_sizes = ["tiny", "base", "small"]
    
    for model_size in model_sizes:
        try:
            model = get_whisper_model(model_size)
            if model is None:
                continue
            
            with st.spinner(f"{model_size}モデルで文字起こし中..."):
                result = model.transcribe(
                    audio_file_path,
                    language="ja",
                    temperature=0.0
                )
            
            results[f"Whisper {model_size}"] = result["text"]
            
        except Exception as e:
            st.error(f"{model_size}モデルでの文字起こしエラー: {e}")
            results[f"Whisper {model_size}"] = f"エラー: {e}"
    
    return results

def save_transcription(text: str, filename: str) -> bool:
    """文字起こし結果をファイルに保存"""
    try:
        # ディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)
        
        return True
        
    except Exception as e:
        st.error(f"文字起こし結果保存エラー: {e}")
        return False

def load_transcription(filename: str) -> Optional[str]:
    """保存された文字起こし結果を読み込み"""
    try:
        if not os.path.exists(filename):
            return None
        
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
            
    except Exception as e:
        st.error(f"文字起こし結果読み込みエラー: {e}")
        return None

def get_transcription_metadata(audio_file_path: str) -> Dict[str, Any]:
    """文字起こしのメタデータを取得"""
    try:
        import wave
        
        with wave.open(audio_file_path, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / rate
            
            return {
                'duration': duration,
                'sample_rate': rate,
                'channels': wf.getnchannels(),
                'sample_width': wf.getsampwidth(),
                'frames': frames
            }
            
    except Exception as e:
        st.error(f"メタデータ取得エラー: {e}")
        return {}

def batch_transcribe(audio_files: list, model_size: str = "base") -> Dict[str, str]:
    """複数の音声ファイルを一括文字起こし"""
    results = {}
    model = get_whisper_model(model_size)
    
    if model is None:
        return results
    
    for audio_file in audio_files:
        try:
            filename = os.path.basename(audio_file)
            with st.spinner(f"{filename} を文字起こし中..."):
                result = model.transcribe(audio_file, language="ja")
                results[filename] = result["text"]
                
        except Exception as e:
            st.error(f"{filename} の文字起こしエラー: {e}")
            results[filename] = f"エラー: {e}"
    
    return results

def validate_transcription(text: str) -> Dict[str, Any]:
    """文字起こし結果の品質を検証"""
    validation = {
        'length': len(text),
        'has_content': len(text.strip()) > 0,
        'word_count': len(text.split()),
        'char_count': len(text.replace(' ', '')),
        'quality_score': 0.0
    }
    
    # 品質スコアの計算（簡単な例）
    if validation['has_content']:
        # 文字数が少なすぎる場合は低スコア
        if validation['char_count'] < 10:
            validation['quality_score'] = 0.3
        elif validation['char_count'] < 50:
            validation['quality_score'] = 0.6
        else:
            validation['quality_score'] = 0.9
    
    return validation 