"""Общие WinAPI-утилиты для работы с окнами и вставкой текста."""

from __future__ import annotations

import ctypes
import sys
import time
from contextlib import suppress
from typing import Optional


def get_foreground_window_handle() -> Optional[int]:
    """Получить дескриптор активного окна (только Windows)."""
    if sys.platform != "win32":
        return None
    try:
        return ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        return None


def focus_target_window(window_handle: Optional[int]) -> bool:
    """Вернуть фокус в целевое окно (только Windows)."""
    if sys.platform != "win32" or not window_handle:
        return False
    try:
        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        if user32.IsIconic(window_handle):
            user32.ShowWindow(window_handle, SW_RESTORE)
        user32.SetForegroundWindow(window_handle)
        time.sleep(0.08)
        return True
    except Exception:
        return False


def paste_via_window_message(window_handle: Optional[int], logger=None) -> bool:
    """Вставить текст через WM_PASTE без симуляции клавиш (только Windows)."""
    if sys.platform != "win32" or not window_handle:
        return False

    try:
        user32 = ctypes.windll.user32
        hwnd = int(window_handle)
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
            focus_hwnd, WM_PASTE, 0, 0, SMTO_ABORTIFHUNG, 150, ctypes.byref(result)
        )
        return bool(ok)
    except Exception as e:
        if logger:
            with suppress(Exception):
                logger(f"WM_PASTE не сработал: {e}")
        return False
