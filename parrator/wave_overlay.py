import atexit
import math
import os
import subprocess
import sys
import threading
import time
from contextlib import suppress

from PyQt6.QtCore import QObject, QRectF, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QLinearGradient,
    QPainter,
    QPen,
    QRegion,
)
from PyQt6.QtWidgets import QApplication, QWidget


class OverlayControlSignals(QObject):
    show_requested = pyqtSignal()
    hide_requested = pyqtSignal()
    level_changed = pyqtSignal(float)
    quit_requested = pyqtSignal()


def get_overlay_screen(widget: QWidget | None = None):
    cursor_screen = QApplication.screenAt(QCursor.pos())
    if cursor_screen is not None:
        return cursor_screen

    if widget is not None:
        widget_screen = widget.screen()
        if widget_screen is not None:
            return widget_screen

    return QApplication.primaryScreen()


def build_overlay_mask(width: int, height: int) -> QRegion:
    safe_width = max(1, int(width))
    safe_height = max(1, int(height))
    return QRegion(0, 0, safe_width, safe_height)


class VoiceReactiveWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAutoFillBackground(False)
        self._target_level = 0.0
        self._level = 0.0
        self._peak_level = 0.0
        self._phase = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_voice_level(self, level: float):
        value = max(0.0, min(1.0, float(level)))
        if value > 0.0:
            # Поднимаем чувствительность для спокойной речи,
            # чтобы эквалайзер не выглядел «мёртвым».
            value = min(1.0, math.pow(value, 0.62) * 1.08)
        self._target_level = value
        self._peak_level = max(self._peak_level, value)

    def reset(self):
        self._target_level = 0.0
        self._level = 0.0
        self._peak_level = 0.0
        self.update()

    def _tick(self):
        self._phase += 0.2
        smoothing = 0.34 if self._target_level > self._level else 0.16
        self._level += (self._target_level - self._level) * smoothing
        self._peak_level = max(self._level, self._peak_level * 0.92)
        if self._target_level == 0.0 and self._level < 0.001:
            self._level = 0.0
            self._peak_level = 0.0
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setPen(Qt.PenStyle.NoPen)

        frame_rect = self.rect().adjusted(1, 1, -1, -1)
        background_gradient = QLinearGradient(
            frame_rect.left(),
            frame_rect.top(),
            frame_rect.left(),
            frame_rect.bottom(),
        )
        background_gradient.setColorAt(0.0, QColor(31, 36, 45, 238))
        background_gradient.setColorAt(1.0, QColor(10, 13, 18, 230))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background_gradient)
        painter.drawRect(frame_rect)

        border_gradient = QLinearGradient(
            frame_rect.left(),
            frame_rect.top(),
            frame_rect.right(),
            frame_rect.bottom(),
        )
        border_gradient.setColorAt(0.0, QColor(125, 211, 252, 90))
        border_gradient.setColorAt(1.0, QColor(20, 184, 166, 45))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_gradient, 1.0))
        painter.drawRect(frame_rect)

        content_rect = frame_rect.adjusted(16, 12, -16, -12)
        bars = 12
        slot_width = content_rect.width() / bars
        bar_width = max(6.0, slot_width * 0.54)
        bottom = content_rect.bottom()
        center = (bars - 1) / 2.0

        for index in range(bars):
            distance = abs(index - center) / max(1.0, center)
            emphasis = 1.0 - distance * 0.38
            wave_a = math.sin(self._phase * 1.35 + index * 0.62)
            wave_b = math.sin(self._phase * 0.72 + index * 1.17)
            wobble = (wave_a * 0.11 + wave_b * 0.07) * (0.4 + self._level * 0.6)
            bar_ratio = 0.14 + self._level * (0.38 + emphasis * 0.34)
            bar_ratio += self._peak_level * 0.18 + wobble
            bar_ratio = max(0.12, min(0.98, bar_ratio))

            bar_height = content_rect.height() * bar_ratio
            x = (
                content_rect.left()
                + index * slot_width
                + (slot_width - bar_width) / 2.0
            )
            y = bottom - bar_height
            rect = QRectF(x, y, bar_width, bar_height)
            rounding = min(bar_width / 2.0, 7.0)

            bar_gradient = QLinearGradient(
                rect.left(),
                rect.top(),
                rect.left(),
                rect.bottom(),
            )
            alpha = int(165 + min(1.0, self._peak_level + 0.15) * 70)
            bar_gradient.setColorAt(0.0, QColor(103, 232, 249, alpha))
            bar_gradient.setColorAt(0.55, QColor(45, 212, 191, alpha - 10))
            bar_gradient.setColorAt(1.0, QColor(15, 118, 110, alpha - 25))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bar_gradient)
            painter.drawRoundedRect(rect, rounding, rounding)

        glow_rect = QRectF(
            content_rect.left(),
            frame_rect.top() + 8,
            content_rect.width(),
            10,
        )
        glow_gradient = QLinearGradient(
            glow_rect.left(),
            glow_rect.top(),
            glow_rect.right(),
            glow_rect.top(),
        )
        glow_gradient.setColorAt(0.0, QColor(255, 255, 255, 0))
        glow_gradient.setColorAt(0.5, QColor(255, 255, 255, 28))
        glow_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(glow_gradient)
        painter.drawRect(glow_rect)


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
        self.resize(216, 80)
        self._apply_rect_mask()
        self._position_on_screen()

    @pyqtSlot()
    def show_overlay(self):
        self._apply_rect_mask()
        self._position_on_screen()
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
        self._apply_rect_mask()

    def _position_on_screen(self):
        screen = get_overlay_screen(self)
        if screen is None:
            return
        geometry = screen.availableGeometry()
        x = geometry.center().x() - self.width() // 2
        y = geometry.bottom() - self.height() - 56
        self.move(x, y)

    def _apply_rect_mask(self):
        self.setMask(build_overlay_mask(self.width(), self.height()))


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
        self._level_emit_interval = 0.02
        self._level_delta_threshold = 0.015
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
        level_changed = (
            abs(value - self._last_level_sent) >= self._level_delta_threshold
        )
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
