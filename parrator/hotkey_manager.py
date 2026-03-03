"""
Global hotkey management using pynput.
"""

from typing import Callable, Optional
from pynput import keyboard


class HotkeyManager:
    """Manages global hotkeys using pynput."""

    def __init__(
        self,
        hotkey_combo: str,
        on_press: Callable,
        on_release: Optional[Callable] = None
    ):
        self.hotkey_combo = hotkey_combo
        self.on_press = on_press
        self.on_release = on_release

        self.hotkey_listener: Optional[keyboard.GlobalHotKeys] = None
        self.key_listener: Optional[keyboard.Listener] = None

        self._hold_mode = self._supports_hold_mode()
        self._is_pressed = False
        self._target_key = self._parse_single_key(
            self.hotkey_combo) if self._hold_mode else None

    @property
    def is_hold_mode(self) -> bool:
        """Returns True when hotkey uses hold-to-talk mode."""
        return self._hold_mode

    def start(self) -> bool:
        """Start listening for hotkeys."""
        try:
            if self._hold_mode and self._target_key is not None and self.on_release:
                self.key_listener = keyboard.Listener(
                    on_press=self._on_key_press,
                    on_release=self._on_key_release
                )
                self.key_listener.start()
                print(
                    f"Hotkey '{self.hotkey_combo}' registered successfully "
                    "as hold-to-talk"
                )
                return True

            pynput_hotkey = self._convert_hotkey_format(self.hotkey_combo)
            hotkey_map = {pynput_hotkey: self.on_press}
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
            self.hotkey_listener.start()

            print(
                f"Hotkey '{self.hotkey_combo}' registered successfully as "
                f"'{pynput_hotkey}'"
            )
            return True

        except Exception as e:
            print(f"Failed to register hotkey '{self.hotkey_combo}': {e}")
            return False

    def _supports_hold_mode(self) -> bool:
        return "+" not in self.hotkey_combo.strip()

    def _parse_single_key(self, hotkey: str):
        key_name = hotkey.strip().lower()
        if len(key_name) == 1:
            return keyboard.KeyCode.from_char(key_name)

        special_map = {
            "space": keyboard.Key.space,
            "enter": keyboard.Key.enter,
            "esc": keyboard.Key.esc,
            "escape": keyboard.Key.esc,
            "tab": keyboard.Key.tab
        }
        if key_name in special_map:
            return special_map[key_name]

        return getattr(keyboard.Key, key_name, None)

    def _keys_equal(self, incoming_key, target_key) -> bool:
        if isinstance(target_key, keyboard.KeyCode):
            return (
                isinstance(incoming_key, keyboard.KeyCode) and
                (incoming_key.char or "").lower() == (target_key.char or "").lower()
            )
        return incoming_key == target_key

    def _on_key_press(self, key):
        if self._target_key is None or not self._keys_equal(key, self._target_key):
            return
        if self._is_pressed:
            return

        self._is_pressed = True
        self.on_press()

    def _on_key_release(self, key):
        if self._target_key is None or not self._keys_equal(key, self._target_key):
            return
        if not self._is_pressed:
            return

        self._is_pressed = False
        if self.on_release:
            self.on_release()

    def _convert_hotkey_format(self, hotkey: str) -> str:
        """Convert config hotkey format to pynput format."""
        parts = hotkey.lower().split('+')
        converted_parts = []

        for part in parts:
            part = part.strip()
            if part in ['ctrl', 'control']:
                converted_parts.append('<ctrl>')
            elif part in ['shift']:
                converted_parts.append('<shift>')
            elif part in ['alt']:
                converted_parts.append('<alt>')
            elif part in ['cmd', 'win', 'super']:
                converted_parts.append('<cmd>')
            elif len(part) == 1:
                converted_parts.append(part)
            else:
                converted_parts.append(f'<{part}>')

        return '+'.join(converted_parts)

    def stop(self):
        """Stop listening for hotkeys."""
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener = None

        if self.key_listener:
            self.key_listener.stop()
            self.key_listener = None

        self._is_pressed = False
        print("Hotkey listener stopped")
