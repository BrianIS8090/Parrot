#!/usr/bin/env python3
"""
Parrator Tray - Simple Speech-to-Text System Tray Application
"""

import sys
import signal
from parrator.tray_app import ParratorTrayApp
from parrator.gui_app import ParratorGuiApp


def signal_handler(signum, frame):
    """Handle system signals for clean shutdown."""
    print("Received shutdown signal, cleaning up...")
    sys.exit(0)


def main():
    """Main entry point."""
    # Handle clean shutdown
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
