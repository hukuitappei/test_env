import streamlit as st
import json
import os
from typing import Dict, Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)

class ShortcutHandler:
    """ショートカットキー処理クラス"""
    
    def __init__(self, settings_file: str = "settings/app_settings.json"):
        self.settings_file = settings_file
        self.shortcuts = self.load_shortcuts()
        self.callbacks = {}
        self.is_initialized = False
    
    def load_shortcuts(self) -> Dict[str, Any]:
        """ショートカット設定を読み込み"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    return settings.get('shortcuts', self.get_default_shortcuts())
            else:
                return self.get_default_shortcuts()
        except Exception as e:
            logger.error(f"ショートカット設定読み込みエラー: {e}")
            return self.get_default_shortcuts()
    
    def get_default_shortcuts(self) -> Dict[str, Any]:
        """デフォルトショートカット設定"""
        return {
            "enabled": True,
            "global_hotkeys": True,
            "keys": {
                "start_recording": "F9",
                "stop_recording": "F10",
                "transcribe": "F11",
                "clear_text": "F12",
                "save_recording": "Ctrl+S",
                "open_settings": "Ctrl+,",
                "open_dictionary": "Ctrl+D",
                "open_commands": "Ctrl+Shift+C",
                "voice_correction": "Ctrl+V"
            },
            "modifiers": {
                "ctrl": True,
                "shift": False,
                "alt": False
            }
        }
    
    def save_shortcuts(self) -> bool:
        """ショートカット設定を保存"""
        try:
            # 既存の設定を読み込み
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            else:
                settings = {}
            
            # ショートカット設定を更新
            settings['shortcuts'] = self.shortcuts
            
            # 保存
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"ショートカット設定保存エラー: {e}")
            return False
    
    def register_callback(self, action: str, callback: Callable) -> None:
        """コールバック関数を登録"""
        self.callbacks[action] = callback
    
    def get_shortcut_key(self, action: str) -> str:
        """アクションに対応するショートカットキーを取得"""
        return self.shortcuts.get('keys', {}).get(action, '')
    
    def is_enabled(self) -> bool:
        """ショートカットが有効かどうか"""
        return self.shortcuts.get('enabled', True)
    
    def get_all_shortcuts(self) -> Dict[str, str]:
        """すべてのショートカットを取得"""
        return self.shortcuts.get('keys', {})
    
    def update_shortcut(self, action: str, key: str) -> bool:
        """ショートカットを更新"""
        try:
            self.shortcuts['keys'][action] = key
            return self.save_shortcuts()
        except Exception as e:
            logger.error(f"ショートカット更新エラー: {e}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """デフォルト設定にリセット"""
        try:
            self.shortcuts = self.get_default_shortcuts()
            return self.save_shortcuts()
        except Exception as e:
            logger.error(f"ショートカットリセットエラー: {e}")
            return False

def create_shortcut_javascript(shortcuts: Dict[str, str]) -> str:
    """ショートカットキー処理用のJavaScriptコードを生成"""
    shortcuts_json = json.dumps(shortcuts)
    js_code = f"""
    <script>
    // ショートカットキー処理
    document.addEventListener('keydown', function(event) {{
        const key = event.key;
        const ctrl = event.ctrlKey;
        const shift = event.shiftKey;
        const alt = event.altKey;
        
        // キーの組み合わせを判定
        let keyCombo = '';
        if (ctrl) keyCombo += 'Ctrl+';
        if (shift) keyCombo += 'Shift+';
        if (alt) keyCombo += 'Alt+';
        keyCombo += key;
        
        // ショートカットマッピング
        const shortcuts = {shortcuts_json};
        
        // マッチするショートカットを検索
        for (const [action, shortcut] of Object.entries(shortcuts)) {{
            if (keyCombo === shortcut) {{
                event.preventDefault();
                
                // Streamlitのセッション状態を更新
                const data = {{
                    shortcut_action: action,
                    shortcut_key: keyCombo,
                    timestamp: Date.now()
                }};
                
                // Streamlitにデータを送信
                if (window.parent && window.parent.postMessage) {{
                    window.parent.postMessage({{
                        type: 'streamlit:setComponentValue',
                        value: JSON.stringify(data)
                    }}, '*');
                }}
                
                // 視覚的フィードバック
                showShortcutFeedback(action, keyCombo);
                break;
            }}
        }}
    }});
    
    // ショートカット実行時の視覚的フィードバック
    function showShortcutFeedback(action, keyCombo) {{
        // 既存のフィードバック要素を削除
        const existingFeedback = document.getElementById('shortcut-feedback');
        if (existingFeedback) {{
            existingFeedback.remove();
        }}
        
        // 新しいフィードバック要素を作成
        const feedback = document.createElement('div');
        feedback.id = 'shortcut-feedback';
        feedback.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #4CAF50;
            color: white;
            padding: 10px 15px;
            border-radius: 5px;
            font-size: 14px;
            font-weight: bold;
            z-index: 10000;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            animation: fadeInOut 2s ease-in-out;
        `;
        
        // アクション名の日本語マッピング
        const actionNames = {{
            'start_recording': '録音開始',
            'stop_recording': '録音停止',
            'transcribe': '文字起こし',
            'clear_text': 'テキストクリア',
            'save_recording': '録音保存',
            'open_settings': '設定を開く',
            'open_dictionary': '辞書を開く',
            'open_commands': 'コマンドを開く',
            'voice_correction': '音声修正'
        }};
        
        const actionName = actionNames[action] || action;
        feedback.textContent = `${{actionName}} (${{keyCombo}})`;
        
        // CSSアニメーション
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeInOut {{
                0% {{ opacity: 0; transform: translateY(-20px); }}
                20% {{ opacity: 1; transform: translateY(0); }}
                80% {{ opacity: 1; transform: translateY(0); }}
                100% {{ opacity: 0; transform: translateY(-20px); }}
            }}
        `;
        
        document.head.appendChild(style);
        document.body.appendChild(feedback);
        
        // 2秒後に削除
        setTimeout(() => {{
            if (feedback.parentNode) {{
                feedback.parentNode.removeChild(feedback);
            }}
        }}, 2000);
    }}
    
    // ショートカットヘルプ表示
    function showShortcutHelp() {{
        const shortcuts = {shortcuts_json};
        const actionNames = {{
            'start_recording': '録音開始',
            'stop_recording': '録音停止',
            'transcribe': '文字起こし',
            'clear_text': 'テキストクリア',
            'save_recording': '録音保存',
            'open_settings': '設定を開く',
            'open_dictionary': '辞書を開く',
            'open_commands': 'コマンドを開く',
            'voice_correction': '音声修正'
        }};
        
        let helpText = 'ショートカットキー一覧:\\n';
        for (const [action, shortcut] of Object.entries(shortcuts)) {{
            const actionName = actionNames[action] || action;
            helpText += `${{actionName}}: ${{shortcut}}\\n`;
        }}
        
        alert(helpText);
    }}
    
    // F1キーでヘルプ表示
    document.addEventListener('keydown', function(event) {{
        if (event.key === 'F1') {{
            event.preventDefault();
            showShortcutHelp();
        }}
    }});
    </script>
    """
    
    return js_code

def create_shortcut_settings_ui(shortcut_handler: ShortcutHandler) -> None:
    """ショートカット設定用のUIを作成"""
    st.subheader("⌨️ ショートカットキー設定")
    
    # ショートカット有効/無効
    col1, col2 = st.columns(2)
    
    with col1:
        enabled = st.checkbox(
            "ショートカットキーを有効にする",
            value=shortcut_handler.is_enabled(),
            help="キーボードショートカットの使用を有効/無効"
        )
        
        if enabled != shortcut_handler.shortcuts.get('enabled', True):
            shortcut_handler.shortcuts['enabled'] = enabled
            shortcut_handler.save_shortcuts()
    
    with col2:
        global_hotkeys = st.checkbox(
            "グローバルホットキーを有効にする",
            value=shortcut_handler.shortcuts.get('global_hotkeys', True),
            help="アプリがフォーカスされていない時もショートカットを有効"
        )
        
        if global_hotkeys != shortcut_handler.shortcuts.get('global_hotkeys', True):
            shortcut_handler.shortcuts['global_hotkeys'] = global_hotkeys
            shortcut_handler.save_shortcuts()
    
    st.markdown("---")
    
    # ショートカットキー設定
    st.write("**ショートカットキー設定**")
    
    # アクション名の日本語マッピング
    action_names = {
        'start_recording': '録音開始',
        'stop_recording': '録音停止',
        'transcribe': '文字起こし',
        'clear_text': 'テキストクリア',
        'save_recording': '録音保存',
        'open_settings': '設定を開く',
        'open_dictionary': '辞書を開く',
        'open_commands': 'コマンドを開く',
        'voice_correction': '音声修正'
    }
    
    # よく使うキーの候補
    common_keys = [
        'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
        'Ctrl+S', 'Ctrl+O', 'Ctrl+N', 'Ctrl+Z', 'Ctrl+Y', 'Ctrl+X', 'Ctrl+C', 'Ctrl+V',
        'Ctrl+A', 'Ctrl+F', 'Ctrl+R', 'Ctrl+T', 'Ctrl+W', 'Ctrl+Q',
        'Ctrl+Shift+S', 'Ctrl+Shift+O', 'Ctrl+Shift+N', 'Ctrl+Shift+C',
        'Alt+R', 'Alt+T', 'Alt+S', 'Alt+D', 'Alt+C'
    ]
    
    # 各ショートカットの設定
    for action, action_name in action_names.items():
        current_key = shortcut_handler.get_shortcut_key(action)
        
        col1, col2, col3 = st.columns([2, 3, 1])
        
        with col1:
            st.write(f"**{action_name}**")
        
        with col2:
            new_key = st.selectbox(
                f"{action_name}のショートカット",
                options=common_keys,
                index=common_keys.index(current_key) if current_key in common_keys else 0,
                key=f"shortcut_{action}",
                help=f"{action_name}のショートカットキーを設定"
            )
        
        with col3:
            if st.button("リセット", key=f"reset_{action}"):
                # デフォルト値にリセット
                default_shortcuts = shortcut_handler.get_default_shortcuts()
                default_key = default_shortcuts['keys'].get(action, '')
                if default_key in common_keys:
                    new_key = default_key
        
        # キーが変更された場合、保存
        if new_key != current_key:
            shortcut_handler.update_shortcut(action, new_key)
            st.success(f"{action_name}のショートカットを {new_key} に変更しました")
    
    st.markdown("---")
    
    # 一括操作
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 デフォルトに戻す", type="secondary"):
            if shortcut_handler.reset_to_defaults():
                st.success("ショートカットをデフォルトに戻しました")
                st.rerun()
            else:
                st.error("リセットに失敗しました")
    
    with col2:
        if st.button("📋 ショートカット一覧表示"):
            shortcuts = shortcut_handler.get_all_shortcuts()
            st.write("**現在のショートカット一覧:**")
            for action, key in shortcuts.items():
                action_name = action_names.get(action, action)
                st.write(f"• {action_name}: `{key}`")
    
    with col3:
        if st.button("❓ ヘルプ表示"):
            st.info("""
            **ショートカットキーの使い方:**
            
            • **F1**: ショートカットヘルプを表示
            • **F9**: 録音開始
            • **F10**: 録音停止  
            • **F11**: 文字起こし実行
            • **F12**: テキストクリア
            • **Ctrl+S**: 録音保存
            • **Ctrl+,**: 設定を開く
            • **Ctrl+D**: 辞書を開く
            • **Ctrl+Shift+C**: コマンドを開く
            • **Ctrl+V**: 音声修正
            
            **カスタムショートカット:**
            上記の設定で各機能のショートカットを変更できます。
            """)

def handle_shortcut_event(shortcut_handler: ShortcutHandler, event_data: str) -> Optional[str]:
    """ショートカットイベントを処理"""
    try:
        data = json.loads(event_data)
        action = data.get('shortcut_action')
        key = data.get('shortcut_key')
        
        if action and key:
            logger.info(f"ショートカット実行: {action} ({key})")
            return action
        
    except Exception as e:
        logger.error(f"ショートカットイベント処理エラー: {e}")
    
    return None 