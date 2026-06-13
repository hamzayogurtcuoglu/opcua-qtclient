"""OPC UA Client — Entry Point.

A modern OPC UA client application built with PyQt6 and asyncua.
"""

import sys
import asyncio
import logging

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from qasync import QEventLoop

from app.main_window import MainWindow
from app.theme import get_stylesheet


def setup_logging():
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    """Application entry point."""
    setup_logging()

    # Create application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("OPC UA Client")
    app.setOrganizationName("OPC UA Tools")

    # Apply dark theme
    app.setStyleSheet(get_stylesheet())

    # Set up async event loop (bridges Qt and asyncio)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
