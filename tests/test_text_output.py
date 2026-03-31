import parrator.text_output as text_output


def test_auto_paste_uses_window_message_first_on_windows(monkeypatch):
  events = []

  monkeypatch.setattr(text_output.time, "sleep", lambda _: None)
  monkeypatch.setattr(text_output, "_prepare_input", lambda: events.append("prepare"))
  monkeypatch.setattr(
    text_output,
    "focus_window_handle",
    lambda window_handle, logger=None: (
      events.append(("focus_window", window_handle)) or False
    ),
  )
  monkeypatch.setattr(text_output.sys, "platform", "win32")
  monkeypatch.setattr(
    text_output,
    "_paste_via_keyboard",
    lambda: events.append("keyboard") or True,
  )
  monkeypatch.setattr(
    text_output,
    "_paste_via_pyautogui",
    lambda: events.append("pyautogui"),
  )

  result = text_output.auto_paste_from_clipboard(
    focus_target=lambda: events.append("focus"),
    paste_via_window_message=lambda: events.append("wm_paste") or False,
    window_handle=123,
  )

  assert result is True
  assert events == [("focus_window", 123), "focus", "prepare", "keyboard"]


def test_auto_paste_falls_back_after_window_message(monkeypatch):
  events = []

  monkeypatch.setattr(text_output.time, "sleep", lambda _: None)
  monkeypatch.setattr(text_output, "_prepare_input", lambda: events.append("prepare"))
  monkeypatch.setattr(
    text_output,
    "focus_window_handle",
    lambda window_handle, logger=None: (
      events.append(("focus_window", window_handle)) or False
    ),
  )
  monkeypatch.setattr(text_output.sys, "platform", "win32")
  monkeypatch.setattr(
    text_output,
    "_paste_via_keyboard",
    lambda: (_ for _ in ()).throw(RuntimeError("blocked")),
  )
  monkeypatch.setattr(
    text_output,
    "_paste_via_pyautogui",
    lambda: events.append("pyautogui") or False,
  )

  result = text_output.auto_paste_from_clipboard(
    focus_target=lambda: events.append("focus"),
    paste_via_window_message=lambda: events.append("wm_paste") or True,
    window_handle=456,
  )

  assert result is True
  assert events == [
    ("focus_window", 456),
    "focus",
    "prepare",
    "pyautogui",
    "wm_paste",
  ]


def test_auto_paste_logs_keyboard_failure_before_fallback(monkeypatch):
  messages = []

  monkeypatch.setattr(text_output.time, "sleep", lambda _: None)
  monkeypatch.setattr(text_output, "_prepare_input", lambda: None)
  monkeypatch.setattr(
    text_output,
    "focus_window_handle",
    lambda window_handle, logger=None: False,
  )
  monkeypatch.setattr(text_output.sys, "platform", "win32")
  monkeypatch.setattr(
    text_output,
    "_paste_via_keyboard",
    lambda: (_ for _ in ()).throw(RuntimeError("boom")),
  )
  monkeypatch.setattr(text_output, "_paste_via_pyautogui", lambda: False)

  result = text_output.auto_paste_from_clipboard(
    focus_target=lambda: None,
    paste_via_window_message=lambda: False,
    window_handle=None,
    logger=messages.append,
  )

  assert result is False
  assert messages == ["Вставка через keyboard.send не сработала: boom"]


def test_auto_paste_skips_callback_when_focus_restored_directly(monkeypatch):
  events = []

  monkeypatch.setattr(text_output.time, "sleep", lambda _: None)
  monkeypatch.setattr(text_output, "_prepare_input", lambda: events.append("prepare"))
  monkeypatch.setattr(
    text_output,
    "focus_window_handle",
    lambda window_handle, logger=None: (
      events.append(("focus_window", window_handle)) or True
    ),
  )
  monkeypatch.setattr(text_output.sys, "platform", "win32")
  monkeypatch.setattr(
    text_output,
    "_paste_via_keyboard",
    lambda: events.append("keyboard") or True,
  )

  result = text_output.auto_paste_from_clipboard(
    focus_target=lambda: events.append("focus"),
    paste_via_window_message=lambda: events.append("wm_paste") or False,
    window_handle=789,
  )

  assert result is True
  assert events == [
    ("focus_window", 789),
    "prepare",
    "keyboard",
  ]


def test_paste_with_type_fallback_uses_direct_type_after_failed_paste():
  events = []
  messages = []

  result = text_output.paste_with_type_fallback(
    "пример",
    paste_text=lambda: events.append("paste") or False,
    type_text=lambda text: events.append(("type", text)) or True,
    logger=messages.append,
  )

  assert result is True
  assert events == ["paste", ("type", "пример")]
  assert messages == [
    "Автовставка не сработала, пробую прямой ввод",
    "Текст напечатан напрямую после сбоя вставки",
  ]


def test_paste_with_type_fallback_returns_false_when_all_methods_failed():
  messages = []

  result = text_output.paste_with_type_fallback(
    "пример",
    paste_text=lambda: False,
    type_text=lambda text: False,
    logger=messages.append,
  )

  assert result is False
  assert messages == ["Автовставка не сработала, пробую прямой ввод"]
