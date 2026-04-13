import atexit
import math
import os
import subprocess
import sys
import threading
import time
from contextlib import suppress

from PyQt6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QPainter, QPen, QRadialGradient, QRegion
from PyQt6.QtWidgets import QApplication, QWidget


class OverlayControlSignals(QObject):
    show_requested = pyqtSignal()
    hide_requested = pyqtSignal()
    level_changed = pyqtSignal(float)
    quit_requested = pyqtSignal()


class VoiceReactiveWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAutoFillBackground(False)
        self._target_level = 0.0
        self._level = 0.0
        self._phase = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_voice_level(self, level: float):
        self._target_level = max(0.0, min(1.0, float(level)))

    def reset(self):
        self._target_level = 0.0
        self._level = 0.0
        self.update()

    def _tick(self):
        self._phase += 0.22
        self._level += (self._target_level - self._level) * 0.25
        if self._target_level == 0.0 and self._level < 0.001:
            self._level = 0.0
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setPen(Qt.PenStyle.NoPen)

        width = self.width()
        height = self.height()
        side = min(width, height)
        cx = width / 2.0
        cy = height / 2.0

        # Внешние кольца с прозрачностью по уровню голоса.
        ring_base = side * 0.36
        ring_scale = 1.0 + self._level * 0.55
        ring_radius_1 = ring_base * ring_scale
        ring_radius_2 = (ring_base - 6.0) * (1.0 + self._level * 0.42)

        pen_outer = QPen(QColor(56, 189, 248, int(72 + self._level * 110)), 2.0)
        painter.setPen(pen_outer)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), ring_radius_1, ring_radius_1)

        pen_inner = QPen(QColor(14, 165, 233, int(92 + self._level * 130)), 1.5)
        painter.setPen(pen_inner)
        painter.drawEllipse(QPointF(cx, cy), ring_radius_2, ring_radius_2)

        # Центральное «ядро».
        core_radius = side * 0.27 * (0.95 + self._level * 0.28)
        gradient = QRadialGradient(
            cx - core_radius * 0.25,
            cy - core_radius * 0.25,
            core_radius * 1.4,
        )
        gradient.setColorAt(0.0, QColor(125, 211, 252, 235))
        gradient.setColorAt(0.45, QColor(56, 189, 248, 225))
        gradient.setColorAt(1.0, QColor(14, 165, 233, 205))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)

        # Полоски эквалайзера, реагирующие на голос.
        bars = 5
        bar_width = side * 0.062
        bar_gap = side * 0.026
        total_width = bars * bar_width + (bars - 1) * bar_gap
        start_x = cx - total_width / 2.0
        bar_base_y = cy + side * 0.12

        for index in range(bars):
            wave_a = math.sin(self._phase + index * 0.9)
            wave_b = math.sin(self._phase * 0.63 + index * 1.3)
            wobble = (wave_a + wave_b) * side * 0.015
            bar_height = side * (0.09 + self._level * 0.33) + index * 0.9 + wobble
            bar_height = max(side * 0.08, min(side * 0.45, bar_height))

            alpha = int(90 + self._level * 150)
            painter.setBrush(QColor(245, 252, 255, alpha))
            x = start_x + index * (bar_width + bar_gap)
            y = bar_base_y - bar_height
            rect = QRectF(x, y, bar_width, bar_height)
            rounding = bar_width * 0.48
            painter.drawRoundedRect(rect, rounding, rounding)


class WaveOverlay(VoiceReactiveWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("background: transparent; border: none;")
        self.resize(104, 104)
        self._apply_circle_mask()
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() // 2 - 52, screen.height() - 180)

    @pyqtSlot()
    def show_overlay(self):
        self.show()

    @pyqtSlot()
    def hide_overlay(self):
        self.set_level(0.0)
        self.hide()

    @pyqtSlot(float)
    def set_level(self, level: float):
        value = max(0.0, min(1.0, float(level)))
        self.set_voice_level(value)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_circle_mask()

    def _apply_circle_mask(self):
        size = min(self.width(), self.height())
        offset_x = (self.width() - size) // 2
        offset_y = (self.height() - size) // 2
        mask = QRegion(offset_x, offset_y, size, size, QRegion.RegionType.Ellipse)
        self.setMask(mask)

def listen_commands(signals: OverlayControlSignals):
    """Слушаем команды из stdin для показа/скрытия окна."""
    try:
        for line in sys.stdin:
            raw = line.strip()
            if not raw:
                continue
            cmd = raw.lower()
            if cmd == "show":
                signals.show_requested.emit()
            elif cmd == "hide":
                signals.hide_requested.emit()
            elif cmd.startswith("level "):
                try:
                    _, value = raw.split(" ", 1)
                    signals.level_changed.emit(float(value))
                except Exception:
                    continue
            elif cmd == "exit":
                signals.quit_requested.emit()
                break
    except Exception:
        pass
    finally:
        signals.quit_requested.emit()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    overlay = WaveOverlay()
    signals = OverlayControlSignals()
    signals.show_requested.connect(overlay.show_overlay)
    signals.hide_requested.connect(overlay.hide_overlay)
    signals.level_changed.connect(overlay.set_level)
    signals.quit_requested.connect(app.quit)
    t = threading.Thread(target=listen_commands, args=(signals,), daemon=True)
    t.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


class WaveOverlayController:
    """Управляет процессом оверлея из основного приложения."""

    def __init__(self):
        self.process = None
        self._level_emit_interval = 0.04
        self._last_level_sent = 0.0
        self._last_level_sent_at = 0.0

    def start(self):
        if self.process is not None:
            return
        # В собранном exe (PyInstaller) sys.executable = Parrator.exe,
        # поэтому передаём флаг --wave-overlay вместо пути к скрипту
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--wave-overlay"]
        else:
            cmd = [sys.executable, os.path.abspath(__file__)]
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self._last_level_sent = 0.0
        self._last_level_sent_at = 0.0
        atexit.register(self.stop)

    def show(self):
        self._send_command("show")

    def hide(self):
        self.set_level(0.0)
        self._send_command("hide")

    def set_level(self, level: float):
        if not self.process or not self.process.stdin:
            return
        try:
            value = max(0.0, min(1.0, float(level)))
        except Exception:
            return

        now = time.monotonic()
        level_changed = abs(value - self._last_level_sent) >= 0.08
        should_throttle = (
            value > 0
            and not level_changed
            and (now - self._last_level_sent_at) < self._level_emit_interval
        )
        if should_throttle:
            return

        self._last_level_sent = value
        self._last_level_sent_at = now
        self._send_command(f"level {value:.4f}")

    def stop(self):
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.write("exit\n")
                    self.process.stdin.flush()
            except Exception:
                pass
            with suppress(Exception):
                self.process.terminate()
            self.process = None

    def _send_command(self, command: str):
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(f"{command}\n")
                self.process.stdin.flush()
            except Exception:
                pass
