import sys
import threading
import os
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl, pyqtSlot

class WaveOverlay(QMainWindow):
    def __init__(self):
        super().__init__()
        # Настройки для прозрачного окна поверх всех окон
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Веб-вью для отображения HTML/SVG
        self.webview = QWebEngineView(self)
        self.webview.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.webview.setStyleSheet("background: transparent;")
        self.webview.page().setBackgroundColor(Qt.GlobalColor.transparent)
        
        # Загружаем HTML-анимацию
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'wave.html'))
        self.webview.setUrl(QUrl.fromLocalFile(html_path))
        
        self.setCentralWidget(self.webview)
        self.resize(70, 70)
        
        # Позиционируем снизу по центру на первом мониторе
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() // 2 - 35, screen.height() - 150)

    @pyqtSlot()
    def show_overlay(self):
        self.show()

    @pyqtSlot()
    def hide_overlay(self):
        self.hide()

def listen_commands(app, overlay):
    """Слушаем команды из stdin для показа/скрытия окна."""
    try:
        for line in sys.stdin:
            cmd = line.strip().lower()
            if cmd == "show":
                overlay.metaObject().invokeMethod(overlay, "show_overlay", Qt.ConnectionType.QueuedConnection)
            elif cmd == "hide":
                overlay.metaObject().invokeMethod(overlay, "hide_overlay", Qt.ConnectionType.QueuedConnection)
            elif cmd == "exit":
                app.metaObject().invokeMethod(app, "quit", Qt.ConnectionType.QueuedConnection)
                break
    except Exception:
        pass
    finally:
        app.metaObject().invokeMethod(app, "quit", Qt.ConnectionType.QueuedConnection)

def main():
    app = QApplication(sys.argv)
    
    # Чтобы приложение не закрывалось, когда нет видимых окон
    app.setQuitOnLastWindowClosed(False)
    
    overlay = WaveOverlay()
    
    t = threading.Thread(target=listen_commands, args=(app, overlay), daemon=True)
    t.start()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

import subprocess
import atexit

class WaveOverlayController:
    """Управляет процессом оверлея из основного приложения."""
    def __init__(self):
        self.process = None

    def start(self):
        if self.process is not None:
            return
        # Запускаем этот же скрипт как отдельный процесс
        script_path = os.path.abspath(__file__)
        self.process = subprocess.Popen(
            [sys.executable, script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )
        atexit.register(self.stop)

    def show(self):
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write("show\n")
                self.process.stdin.flush()
            except Exception:
                pass

    def hide(self):
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write("hide\n")
                self.process.stdin.flush()
            except Exception:
                pass

    def stop(self):
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.write("exit\n")
                    self.process.stdin.flush()
            except Exception:
                pass
            try:
                self.process.terminate()
            except Exception:
                pass
            self.process = None

