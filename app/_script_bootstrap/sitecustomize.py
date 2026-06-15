"""Auto-loaded startup hook for scripts launched by the Script Runner.

Python imports a module named ``sitecustomize`` automatically at interpreter
startup (via the ``site`` module) if it is found on ``sys.path``. The Script
Runner puts this directory on ``PYTHONPATH`` so this file runs *before* the
user's script — without modifying the user's script at all.

Why it exists
-------------
asyncua hardcodes a 1-second per-request timeout for high-level service calls:
``UaClient._send_request`` / ``Session._send_request`` default ``timeout`` to
``1`` (not ``None``). That value is passed straight down to
``UASocketProtocol.send_request`` and *overrides* the ``Client(timeout=...)``
the script configured. Any method call (e.g. ``close_drawer.call_method`` in a
SIL setup script) that takes longer than ~1 second to return is therefore
cancelled after 1 second and surfaces as:

    Unhandled exception while sending request to OPC UA server
    -> TimeoutError -> CancelledError

This is timing-sensitive: in a fast TTY the call finishes just under 1 s, but
when stdout is piped through the app the subprocess runs slightly slower and the
same call crosses the 1 s boundary and fails.

The patch below makes the structural default of ``1`` fall back to a generous
timeout (``ASYNCUA_REQUEST_TIMEOUT`` env var, default 600 s). Calls that pass an
explicit timeout, or ``None`` (used by connect / secure-channel which rely on
the protocol's own timeout), are left untouched.
"""

import os


def _install_asyncua_request_timeout_patch() -> None:
    try:
        from asyncua.client import ua_client as _uac
        from asyncua import ua as _ua
    except Exception:
        # asyncua not installed for this script — nothing to do.
        return

    proto = getattr(_uac, "UASocketProtocol", None)
    if proto is None or getattr(proto, "_request_timeout_patched", False):
        return

    original = proto.send_request

    try:
        configured = float(os.environ.get("ASYNCUA_REQUEST_TIMEOUT", "600") or "600")
    except (TypeError, ValueError):
        configured = 600.0

    async def send_request(self, request, timeout=None, message_type=_ua.MessageType.SecureMessage):
        # ``1`` is asyncua's structural default for high-level service calls and
        # ignores the configured Client timeout. Replace it with the configured
        # generous timeout so long-running methods are not cancelled after 1 s.
        if timeout == 1:
            timeout = configured
        return await original(self, request, timeout, message_type)

    try:
        proto.send_request = send_request
        proto._request_timeout_patched = True
    except Exception:
        pass


_install_asyncua_request_timeout_patch()
