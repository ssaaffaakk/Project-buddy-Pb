"""
WSGI entry point for production deployment.

Usage (gunicorn + eventlet):
    gunicorn --worker-class eventlet -w 1 --timeout 120 --bind 0.0.0.0:$PORT wsgi:app

The app must be named `app` so Flask-SocketIO's monkey-patching fires
before any stdlib imports.

This file is the production entry point — it always uses ProductionConfig.
Never import DevelopmentConfig here; use `python app.py` for local dev.
"""

import eventlet
eventlet.monkey_patch()

# ── Full-traceback capture for "do not call blocking functions from the mainloop"
# ─────────────────────────────────────────────────────────────────────────────────
# Eventlet normally prints this error without a stack trace, making it impossible
# to identify the source. This patch wraps hub.switch() so that whenever it is
# called from the hub's own greenlet we log the COMPLETE Python call stack at
# CRITICAL level. Check Render logs for "BLOCKING CALL FROM MAINLOOP" to see
# exactly which file/line is responsible.
# Remove this block once the root cause has been identified and fixed.
try:
    import traceback as _tb
    import logging as _log
    import eventlet.hubs as _hubs
    from greenlet import getcurrent as _getcurrent

    _hub = _hubs.get_hub()
    _hub_cls = type(_hub)
    _orig_hub_switch = _hub_cls.switch  # unbound function in Python 3

    def _traced_hub_switch(self):
        if _getcurrent() is self.greenlet:
            _log.getLogger("eventlet.hub").critical(
                "BLOCKING CALL FROM MAINLOOP — full stack:\n%s",
                "".join(_tb.format_stack()),
            )
        return _orig_hub_switch(self)

    _hub_cls.switch = _traced_hub_switch
    _log.getLogger("eventlet.hub").info("hub.switch() tracing enabled")
except Exception as _patch_err:
    import logging as _log
    _log.getLogger("wsgi").warning("Could not patch hub.switch for tracing: %s", _patch_err)

from app import create_app
from config import ProductionConfig

app = create_app(ProductionConfig)
