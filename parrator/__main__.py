#!/usr/bin/env python3
"""
Parrator Tray - Simple Speech-to-Text System Tray Application
"""

import sys
import signal


class _NullStream:
  """Тихий поток для запуска через pythonw без консоли."""

  def write(self, _data):
    return 0

  def flush(self):
    return None

  def isatty(self):
    return False


def _ensure_std_streams():
  """Гарантирует наличие stdout/stderr для библиотек с прогресс-выводом."""
  if sys.stdout is None:
    sys.stdout = _NullStream()
  if sys.stderr is None:
    sys.stderr = _NullStream()


def _set_windows_app_id():
  """Устанавливает AppUserModelID для корректной иконки в Windows."""
  if sys.platform != "win32":
    return
  try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Parrator.App")
  except Exception:
    pass


def signal_handler(signum, frame):
    """Handle system signals for clean shutdown."""
    print("Received shutdown signal, cleaning up...")
    sys.exit(0)


def main():
  """Main entry point."""
  _ensure_std_streams()
  _set_windows_app_id()

  from parrator.tray_app import ParratorTrayApp
  from parrator.gui_app import ParratorGuiApp

  # Обработка сигналов для корректного завершения
  signal.signal(signal.SIGINT, signal_handler)
  signal.signal(signal.SIGTERM, signal_handler)

  use_gui = "--gui" in sys.argv
  app = ParratorGuiApp() if use_gui else ParratorTrayApp()

  try:
    if use_gui:
      app.run()
    else:
      app.start()
  except KeyboardInterrupt:
    print("Application interrupted by user")
  except Exception as e:
    print(f"Application error: {e}")
    import traceback
    traceback.print_exc()
  finally:
    if hasattr(app, "cleanup"):
      app.cleanup()


if __name__ == "__main__":
    main()
