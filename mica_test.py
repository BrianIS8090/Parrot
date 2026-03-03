import sys
import ctypes
from ctypes.wintypes import MARGINS
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mica Test")
        self.resize(800, 600)
        
        # 1. To see Mica, the window background must be transparent.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Central widget
        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        lbl = QLabel("Mica Glass Effect in PyQt6!")
        lbl.setStyleSheet("font-size: 24px; color: black;")
        layout.addWidget(lbl)
        
        btn = QPushButton("Click Me")
        btn.setStyleSheet("background-color: rgba(255, 255, 255, 0.5); border-radius: 8px; padding: 10px;")
        layout.addWidget(btn)

        self.apply_mica()

    def apply_mica(self):
        if sys.platform != "win32":
            return
        
        hwnd = int(self.winId())
        
        try:
            DWMWA_SYSTEMBACKDROP_TYPE = 38
            DWMSBT_MAINWINDOW = 2 # Mica
            DWMSBT_TABBEDWINDOW = 4 # Acrylic / Mica Alt
            
            # Use Mica (or 3 for Acrylic depending on build)
            val = ctypes.c_int(DWMSBT_MAINWINDOW)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(val), ctypes.sizeof(val)
            )
            
            # Extend frame
            margins = MARGINS(-1, -1, -1, -1)
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
            
        except Exception as e:
            print("Mica error:", e)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    # sys.exit(app.exec()) # don't hang for test
    print("Test ready")
