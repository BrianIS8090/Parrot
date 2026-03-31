from __future__ import annotations

import ctypes
import sys
import time
from contextlib import suppress
from ctypes import c_size_t, wintypes
from typing import Callable, Optional

LogFn = Callable[[str], None]
FocusFn = Callable[[], None]
PasteFn = Callable[[], bool]


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
SW_SHOW = 5
SW_RESTORE = 9
ASFW_ANY = 0xFFFFFFFF
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_V = 0x56


ULONG_PTR = getattr(wintypes, "ULONG_PTR", c_size_t)


class KEYBDINPUT(ctypes.Structure):
  _fields_ = [
    ("wVk", wintypes.WORD),
    ("wScan", wintypes.WORD),
    ("dwFlags", wintypes.DWORD),
    ("time", wintypes.DWORD),
    ("dwExtraInfo", ULONG_PTR),
  ]


class INPUT_UNION(ctypes.Union):
  _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
  _anonymous_ = ("union",)
  _fields_ = [
    ("type", wintypes.DWORD),
    ("union", INPUT_UNION),
  ]


def auto_paste_from_clipboard(
  *,
  focus_target: FocusFn,
  paste_via_window_message: PasteFn,
  window_handle: Optional[int] = None,
  logger: Optional[LogFn] = None,
) -> bool:
  if not focus_window_handle(window_handle, logger=logger):
    focus_target()
  _prepare_input()
  time.sleep(0.12)

  strategies: list[tuple[str, Callable[[], bool]]] = [
    ("keyboard.send", _paste_via_keyboard),
    ("pyautogui.hotkey", _paste_via_pyautogui),
  ]

  for strategy_name, strategy in strategies:
    try:
      if strategy():
        return True
    except Exception as exc:
      _log(logger, f"Вставка через {strategy_name} не сработала: {exc}")

  if sys.platform == "win32":
    try:
      if paste_via_window_message():
        return True
    except Exception as exc:
      _log(logger, f"Вставка через WM_PASTE не сработала: {exc}")

  return False


def paste_with_type_fallback(
  text: str,
  *,
  paste_text: Callable[[], bool],
  type_text: Callable[[str], bool],
  logger: Optional[LogFn] = None,
) -> bool:
  if paste_text():
    return True

  _log(logger, "Автовставка не сработала, пробую прямой ввод")
  if type_text(text):
    _log(logger, "Текст напечатан напрямую после сбоя вставки")
    return True

  return False


def focus_window_handle(
  window_handle: Optional[int],
  *,
  logger: Optional[LogFn] = None,
) -> bool:
  if sys.platform != "win32" or not window_handle:
    return False

  user32 = ctypes.windll.user32
  kernel32 = ctypes.windll.kernel32
  hwnd = int(window_handle)
  attached_threads: list[tuple[int, int]] = []

  try:
    foreground_hwnd = user32.GetForegroundWindow()
    current_thread = (
      user32.GetWindowThreadProcessId(foreground_hwnd, None)
      if foreground_hwnd
      else 0
    )
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    app_thread = kernel32.GetCurrentThreadId()

    for source_thread, target in (
      (app_thread, current_thread),
      (app_thread, target_thread),
      (current_thread, target_thread),
    ):
      if not source_thread or not target or source_thread == target:
        continue
      if user32.AttachThreadInput(source_thread, target, True):
        attached_threads.append((source_thread, target))

    user32.AllowSetForegroundWindow(ASFW_ANY)
    if user32.IsIconic(hwnd):
      user32.ShowWindow(hwnd, SW_RESTORE)
    else:
      user32.ShowWindow(hwnd, SW_SHOW)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.SetActiveWindow(hwnd)
    user32.SetFocus(hwnd)
    time.sleep(0.08)

    if user32.GetForegroundWindow() != hwnd:
      user32.keybd_event(VK_MENU, 0, 0, 0)
      user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
      user32.SetForegroundWindow(hwnd)
      time.sleep(0.04)

    is_focused = user32.GetForegroundWindow() == hwnd
    if not is_focused:
      _log(logger, "Не удалось вернуть фокус в целевое окно для вставки")
    return is_focused
  except Exception as exc:
    _log(logger, f"Не удалось вернуть фокус в целевое окно: {exc}")
    return False
  finally:
    for source_thread, target in reversed(attached_threads):
      with suppress(Exception):
        user32.AttachThreadInput(source_thread, target, False)


def _prepare_input() -> None:
  _release_modifiers_via_sendinput()

  with suppress(Exception):
    import keyboard

    for key in ("ctrl", "shift", "alt", "windows"):
      keyboard.release(key)

  with suppress(Exception):
    from pynput.keyboard import Controller, Key

    controller = Controller()
    for key in (
      Key.ctrl,
      Key.ctrl_l,
      Key.ctrl_r,
      Key.shift,
      Key.shift_l,
      Key.shift_r,
      Key.alt,
      Key.alt_l,
      Key.alt_r,
      Key.cmd,
      Key.cmd_l,
      Key.cmd_r,
    ):
      with suppress(Exception):
        controller.release(key)

  time.sleep(0.04)


def _log(logger: Optional[LogFn], message: str) -> None:
  if logger:
    logger(message)


def _paste_via_sendinput() -> bool:
  if sys.platform != "win32":
    return False

  return _send_inputs(
    [
      _keyboard_input(w_vk=VK_CONTROL),
      _keyboard_input(w_vk=VK_V),
      _keyboard_input(w_vk=VK_V, flags=KEYEVENTF_KEYUP),
      _keyboard_input(w_vk=VK_CONTROL, flags=KEYEVENTF_KEYUP),
    ]
  )


def _paste_via_keyboard() -> bool:
  import keyboard

  keyboard.send("ctrl+v")
  return True


def _paste_via_pyautogui() -> bool:
  import pyautogui

  pyautogui.hotkey("ctrl", "v")
  return True


def _release_modifiers_via_sendinput() -> None:
  if sys.platform != "win32":
    return

  _send_inputs(
    [
      _keyboard_input(w_vk=VK_V, flags=KEYEVENTF_KEYUP),
      _keyboard_input(w_vk=VK_CONTROL, flags=KEYEVENTF_KEYUP),
      _keyboard_input(w_vk=VK_SHIFT, flags=KEYEVENTF_KEYUP),
      _keyboard_input(w_vk=VK_MENU, flags=KEYEVENTF_KEYUP),
      _keyboard_input(w_vk=VK_LWIN, flags=KEYEVENTF_KEYUP),
      _keyboard_input(w_vk=VK_RWIN, flags=KEYEVENTF_KEYUP),
    ]
  )


def _keyboard_input(
  *,
  w_vk: int = 0,
  w_scan: int = 0,
  flags: int = 0,
) -> INPUT:
  return INPUT(
    type=INPUT_KEYBOARD,
    ki=KEYBDINPUT(
      wVk=w_vk,
      wScan=w_scan,
      dwFlags=flags,
      time=0,
      dwExtraInfo=0,
    ),
  )


def _send_inputs(inputs: list[INPUT]) -> bool:
  if sys.platform != "win32" or not inputs:
    return False

  array_type = INPUT * len(inputs)
  sent = ctypes.windll.user32.SendInput(
    len(inputs),
    array_type(*inputs),
    ctypes.sizeof(INPUT),
  )
  return sent == len(inputs)
