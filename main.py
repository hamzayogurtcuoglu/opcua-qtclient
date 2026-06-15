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


def _install_asyncua_request_timeout_patch(default_timeout: float = 600.0) -> None:
    """Stop asyncua cancelling method calls after its hardcoded 1-second default.

    asyncua's high-level service calls (read/write/call) pass a structural
    default timeout of ``1`` second down to ``UASocketProtocol.send_request``,
    which overrides the ``Client(timeout=...)`` the script configured. Any method
    that takes longer than ~1 s is then cancelled and surfaces as
    "Unhandled exception while sending request to OPC UA server". We rewrite that
    structural ``1`` to a generous timeout so scripts run from the frozen exe
    behave the same as from a terminal.
    """
    try:
        from asyncua.client import ua_client as _uac
        from asyncua import ua as _ua
    except Exception:
        return
    proto = getattr(_uac, "UASocketProtocol", None)
    if proto is None or getattr(proto, "_request_timeout_patched", False):
        return
    import os as _os
    try:
        configured = float(_os.environ.get("ASYNCUA_REQUEST_TIMEOUT", "") or default_timeout)
    except (TypeError, ValueError):
        configured = default_timeout
    original = proto.send_request

    async def send_request(self, request, timeout=None, message_type=_ua.MessageType.SecureMessage):
        if timeout == 1:
            timeout = configured
        return await original(self, request, timeout, message_type)

    try:
        proto.send_request = send_request
        proto._request_timeout_patched = True
    except Exception:
        pass


def _run_script_and_exit() -> None:
    """Frozen-exe entry point used by the Script Runner.

    When the bundled executable is launched as
    ``OPCUA_Client.exe --run-script <script.py> [args...]`` it must NOT open the
    GUI. Instead it runs the given Python script in-process (the exe already
    bundles Python + asyncua + all dependencies), exactly as if a normal Python
    interpreter had executed ``python <script.py> [args...]``. This is required
    because in a PyInstaller build ``sys.executable`` is the app itself, not a
    Python interpreter, so spawning ``sys.executable script.py`` would just
    re-launch the app.
    """
    import runpy

    script_path = sys.argv[2]
    script_args = sys.argv[3:]

    _install_asyncua_request_timeout_patch()

    # Make output appear live in the Script Runner's captured pipe.
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    # Present argv to the script as if it were invoked directly.
    sys.argv = [script_path, *script_args]
    try:
        runpy.run_path(script_path, run_name="__main__")
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.exit(1)
    sys.exit(0)


def setup_logging():
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    """Application entry point."""
    # Script Runner mode (used by the frozen executable to run user scripts).
    if len(sys.argv) >= 3 and sys.argv[1] == "--run-script":
        _run_script_and_exit()
        return

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
