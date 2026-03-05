"""
Simplified tray application.
"""

import ctypes
import os
import subprocess
import sys
import threading
import time
from contextlib import suppress
from typing import Optional

import pystray
from PIL import Image

from .audio_recorder import AudioRecorder
from .config import Config
from .hotkey_manager import HotkeyManager
from .notifications import NotificationManager
from .startup import StartupManager
from .transcriber import Transcriber
from .wave_overlay import WaveOverlayController


class ParratorTrayApp:
    """Main tray application."""

    def __init__(self):
        self.config = Config()
        self.transcriber = Transcriber(self.config)
        self.audio_recorder = AudioRecorder(self.config)
        self.notification_manager = NotificationManager()
        self.startup_manager = StartupManager()
        self.hotkey_manager: Optional[HotkeyManager] = None
        self.tray_icon: Optional[pystray.Icon] = None
        self.is_recording = False
        self.model_loaded = False
        self.target_window_handle: Optional[int] = None
        self.wave_overlay = WaveOverlayController()

    def start(self):
        """Start the application."""
        print("Starting Parrator...")
        self.wave_overlay.start()

        # Load transcription model in background
        self._load_model_async()

        # Setup tray icon
        self._setup_tray()

        # Setup hotkeys
        self._setup_hotkeys()

        hotkey = self.config.get('hotkey')
        if self.hotkey_manager and self.hotkey_manager.is_hold_mode:
            print(f"Ready! Hold {hotkey} to record")
        else:
            print(f"Ready! Press {hotkey} to record")

        # Run tray (this blocks)
        try:
            self.tray_icon.run()
        except KeyboardInterrupt:
            print("Application interrupted")
        finally:
            self.cleanup()

    def _load_model_async(self):
        """Load the transcription model in a background thread."""
        def load_model():
            if self.transcriber.load_model():
                self.model_loaded = True
                self._update_tray_icon()
                print("Model loaded successfully")
                self._show_runtime_status(
                    "Parrator",
                    "Модель загружена. Нажмите горячую клавишу для записи."
                )
            else:
                print("Failed to load model")
                self._show_runtime_status(
                    "Parrator",
                    "Не удалось загрузить модель распознавания.",
                    error=True
                )

        thread = threading.Thread(target=load_model, daemon=True)
        thread.start()

    def _setup_tray(self):
        """Setup the system tray icon."""
        # Load icon from resources
        icon_path = self._get_icon_path()
        try:
            image = Image.open(icon_path)
        except Exception as e:
            print(f"Could not load icon: {e}")
            # Create simple fallback icon
            image = Image.new('RGB', (64, 64), color='blue')

        # Create menu
        menu = pystray.Menu(
            pystray.MenuItem("Toggle Recording", self._toggle_recording),
            pystray.MenuItem("Settings", self._show_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Start with System",
                self._toggle_startup,
                checked=lambda item: self.startup_manager.is_enabled()
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit_application)
        )

        self.tray_icon = pystray.Icon(
            "parrator",
            image,
            "Parrator - Loading...",
            menu
        )

    def _setup_hotkeys(self):
        """Setup global hotkeys."""
        hotkey_combo = self.config.get('hotkey', 'ctrl+shift+;')
        self.hotkey_manager = HotkeyManager(
            hotkey_combo,
            self._on_hotkey_press,
            self._on_hotkey_release
        )

        if not self.hotkey_manager.start():
            print(f"Could not register hotkey: {hotkey_combo}")

    def _on_hotkey_press(self):
        """Handle hotkey press event."""
        if not self.model_loaded:
            print("Model still loading, please wait...")
            return

        if self.hotkey_manager and self.hotkey_manager.is_hold_mode:
            if not self.is_recording:
                self._start_recording()
            return

        self._toggle_recording()

    def _on_hotkey_release(self):
        """Handle hotkey release event."""
        if (
            self.hotkey_manager
            and self.hotkey_manager.is_hold_mode
            and self.is_recording
        ):
            self._stop_recording()

    def _toggle_recording(self):
        """Toggle recording state."""
        if not self.model_loaded:
            print("Model still loading, please wait...")
            return

        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        """Start audio recording."""
        print("Recording started...")
        self.is_recording = True
        self.target_window_handle = self._get_foreground_window_handle()
        self._update_tray_icon()
        self._show_runtime_status("Parrator", "Идет запись...")
        self.wave_overlay.show()

        if not self.audio_recorder.start_recording():
            print("Failed to start recording")
            self.is_recording = False
            self.wave_overlay.hide()
            self._update_tray_icon()
            self._show_runtime_status(
                "Parrator",
                "Не удалось начать запись с микрофона.",
                error=True
            )

    def _stop_recording(self):
        """Stop recording and process audio."""
        if not self.is_recording:
            return

        print("Recording stopped, processing...")
        self.is_recording = False
        self.wave_overlay.hide()
        self._update_tray_icon()
        self._show_runtime_status("Parrator", "Распознавание...")

        # Stop recording and get audio data
        audio_data = self.audio_recorder.stop_recording()

        if audio_data is not None:
            self._process_audio_async(audio_data)
        else:
            print("No audio data captured")

    def _process_audio_async(self, audio_data):
        """Process audio in background thread."""
        def process():
            try:
                # Save temporary audio file
                temp_path = self.audio_recorder.save_temp_audio(audio_data)
                if not temp_path:
                    print("Failed to save audio")
                    return

                # Transcribe
                success, text = self.transcriber.transcribe_file(temp_path)

                # Cleanup temp file
                with suppress(Exception):
                    os.remove(temp_path)

                if success and text:
                    self._handle_transcription_result(text)
                else:
                    print("Transcription failed")
                    self._show_runtime_status(
                        "Parrator",
                        "Распознавание не дало результата.",
                        error=True
                    )

            except Exception as e:
                print(f"Processing error: {e}")
                self._show_runtime_status(
                    "Parrator",
                    f"Ошибка обработки: {e}",
                    error=True
                )

        thread = threading.Thread(target=process, daemon=True)
        thread.start()

    def _handle_transcription_result(self, text: str):
        """Handle successful transcription."""
        print(f"Transcribed: {text}")
        preview = text if len(text) <= 80 else f"{text[:77]}..."
        self._show_runtime_status("Parrator", f"Готово: {preview}")

        output_mode = str(self.config.get("output_mode", "paste")).strip().lower()
        if output_mode == "type":
            if self._type_direct(text):
                print("Typed directly")
                return
            print("Direct typing failed, fallback to clipboard mode")

        try:
            import pyperclip
            pyperclip.copy(text)
            print("Copied to clipboard")

            # Auto-paste if enabled
            if self.config.get('auto_paste', True):
                self._auto_paste()

        except Exception as e:
            print(f"Clipboard error: {e}")

    def _type_direct(self, text: str) -> bool:
        """Type text directly into target app without Ctrl+V."""
        self._focus_target_window()

        try:
            from pynput.keyboard import Controller
            keyboard_controller = Controller()
            time.sleep(0.12)
            keyboard_controller.type(text)
            return True
        except Exception as e:
            print(f"Direct typing failed: {e}")
            return False

    def _auto_paste(self):
        """Automatically paste from clipboard."""
        self._focus_target_window()
        time.sleep(0.12)

        try:
            import pyautogui
            pyautogui.hotkey('ctrl', 'v')
            print("Auto-pasted")
            return
        except Exception as e:
            print(f"Auto-paste via pyautogui failed: {e}")

        try:
            import keyboard
            time.sleep(0.12)
            keyboard.send("ctrl+v")
            print("Auto-pasted")
            return
        except Exception as e:
            print(f"Auto-paste via keyboard failed: {e}")

        if self._paste_via_window_message():
            print("Auto-pasted")
            return

        print("Auto-paste did not work")

    def _paste_via_window_message(self) -> bool:
        """Paste into target window via WM_PASTE without key simulation."""
        if sys.platform != "win32" or not self.target_window_handle:
            return False

        try:
            user32 = ctypes.windll.user32
            hwnd = int(self.target_window_handle)
            target_thread = user32.GetWindowThreadProcessId(hwnd, None)
            if not target_thread:
                return False

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            class GUITHREADINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_uint),
                    ("flags", ctypes.c_uint),
                    ("hwndActive", ctypes.c_void_p),
                    ("hwndFocus", ctypes.c_void_p),
                    ("hwndCapture", ctypes.c_void_p),
                    ("hwndMenuOwner", ctypes.c_void_p),
                    ("hwndMoveSize", ctypes.c_void_p),
                    ("hwndCaret", ctypes.c_void_p),
                    ("rcCaret", RECT),
                ]

            info = GUITHREADINFO()
            info.cbSize = ctypes.sizeof(info)
            if not user32.GetGUIThreadInfo(target_thread, ctypes.byref(info)):
                return False

            focus_hwnd = int(info.hwndFocus) if info.hwndFocus else hwnd
            WM_PASTE = 0x0302
            SMTO_ABORTIFHUNG = 0x0002
            result = ctypes.c_ulong(0)
            ok = user32.SendMessageTimeoutW(
                focus_hwnd,
                WM_PASTE,
                0,
                0,
                SMTO_ABORTIFHUNG,
                150,
                ctypes.byref(result),
            )
            return bool(ok)
        except Exception as e:
            print(f"WM_PASTE failed: {e}")
            return False

    def _get_foreground_window_handle(self) -> Optional[int]:
        """Get current active window handle on Windows."""
        if sys.platform != "win32":
            return None
        try:
            return ctypes.windll.user32.GetForegroundWindow()
        except Exception:
            return None

    def _focus_target_window(self):
        """Try to return focus to the window where recording started."""
        if sys.platform != "win32":
            return
        if not self.target_window_handle:
            return

        try:
            user32 = ctypes.windll.user32
            SW_RESTORE = 9
            if user32.IsIconic(self.target_window_handle):
                user32.ShowWindow(self.target_window_handle, SW_RESTORE)
            user32.SetForegroundWindow(self.target_window_handle)
            time.sleep(0.08)
        except Exception as e:
            print(f"Could not focus target window: {e}")

    def _show_runtime_status(self, title: str, message: str, error: bool = False):
        """Show runtime status without delayed OS notifications."""
        level = "ERROR" if error else "INFO"
        print(f"{level}: {message}")

        if self.tray_icon:
            with suppress(Exception):
                self.tray_icon.title = f"Parrator - {message}"

    def _update_tray_icon(self):
        """Update tray icon title based on current state."""
        if self.tray_icon:
            if self.is_recording:
                title = "Parrator - Recording..."
            elif self.model_loaded:
                title = "Parrator - Ready"
            else:
                title = "Parrator - Loading..."

            self.tray_icon.title = title

    def _show_settings(self):
        """Open settings file in default editor."""
        try:
            config_path = self.config.config_path

            if sys.platform == "win32":
                os.startfile(config_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", config_path])
            else:
                subprocess.run(["xdg-open", config_path])

            print(f"Opened settings: {config_path}")

        except Exception as e:
            print(f"Could not open settings: {e}")

    def _toggle_startup(self):
        """Toggle startup with system."""
        if self.startup_manager.is_enabled():
            if self.startup_manager.disable():
                print("Disabled startup with system")
            else:
                print("Failed to disable startup")
        else:
            if self.startup_manager.enable():
                print("Enabled startup with system")
            else:
                print("Failed to enable startup")

    def _quit_application(self):
        """Quit the application."""
        print("Quitting...")
        self.cleanup()
        self.tray_icon.stop()

    def _get_icon_path(self):
        """Get path to tray icon."""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        return os.path.join(base_path, 'resources', 'icon.png')

    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, 'wave_overlay') and self.wave_overlay:
            self.wave_overlay.stop()
        if self.hotkey_manager:
            self.hotkey_manager.stop()
        if self.audio_recorder:
            self.audio_recorder.cleanup()
