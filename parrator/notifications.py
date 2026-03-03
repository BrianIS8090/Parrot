"""
Cross-platform system notifications.
"""

import platform
from typing import Optional


class NotificationManager:
    """Manages system notifications across platforms."""

    def __init__(self):
        self.system = platform.system().lower()

    def show(self, title: str, message: str, error: bool = False):
        """Show a system notification."""
        try:
            if self.system == "windows":
                self._show_windows_notification(title, message)
            elif self.system == "darwin":
                self._show_macos_notification(title, message)
            else:
                self._show_linux_notification(title, message)
        except Exception as e:
            print(f"Notification failed: {e}")
            # Fallback to console output
            print(f"{'ERROR' if error else 'INFO'}: {title} - {message}")

    def _show_windows_notification(self, title: str, message: str):
        """Show Windows notification."""
        try:
            import win10toast
            toaster = win10toast.ToastNotifier()
            toaster.show_toast(title, message, duration=3)
        except ImportError:
            # Fallback using plyer
            self._show_plyer_notification(title, message)

    def _show_macos_notification(self, title: str, message: str):
        """Show macOS notification."""
        try:
            import subprocess
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(['osascript', '-e', script], check=True)
        except:
            self._show_plyer_notification(title, message)

    def _show_linux_notification(self, title: str, message: str):
        """Show Linux notification."""
        try:
            import subprocess
            subprocess.run(['notify-send', title, message], check=True)
        except:
            self._show_plyer_notification(title, message)

    def _show_plyer_notification(self, title: str, message: str):
        """Fallback notification using plyer."""
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                timeout=3
            )
        except ImportError:
            print(f"NOTIFICATION: {title} - {message}")
