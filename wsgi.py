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

# ── Diagnostic: capture full stack for "do not call blocking functions" errors ──
# Writes directly to stderr so output appears regardless of logging config.
# The error is raised by an `assert` in eventlet.sleep() / Event.wait() BEFORE
# hub.switch() is called, so we patch all three entry points.
# Remove once the root cause is confirmed fixed.
import sys as _sys, traceback as _tb

def _dump_blocking_stack(label):
    print(
        f"\n[WSGI DIAGNOSTIC] BLOCKING CALL FROM MAINLOOP ({label}):\n",
        file=_sys.stderr,
    )
    _tb.print_stack(file=_sys.stderr)
    _sys.stderr.flush()

def _is_mainloop():
    import eventlet.hubs as _h
    from greenlet import getcurrent as _gc
    try:
        return _gc() is _h.get_hub().greenlet
    except Exception:
        return False

try:
    # 1) eventlet.sleep ──────────────────────────────────────────────────────────
    _orig_sleep = eventlet.sleep
    def _traced_sleep(seconds=0):
        if _is_mainloop():
            _dump_blocking_stack("eventlet.sleep")
        return _orig_sleep(seconds)
    eventlet.sleep = _traced_sleep

    # 2) eventlet.event.Event.wait ───────────────────────────────────────────────
    import eventlet.event as _ev_mod
    _orig_event_wait = _ev_mod.Event.wait
    def _traced_event_wait(self):
        if _is_mainloop():
            _dump_blocking_stack("Event.wait")
        return _orig_event_wait(self)
    _ev_mod.Event.wait = _traced_event_wait

    # 3) hub.switch ──────────────────────────────────────────────────────────────
    import eventlet.hubs as _hubs
    from greenlet import getcurrent as _getcurrent
    _hub = _hubs.get_hub()
    _hub_cls = type(_hub)
    _orig_hub_switch = _hub_cls.switch
    def _traced_hub_switch(self):
        if _getcurrent() is self.greenlet:
            _dump_blocking_stack("hub.switch")
        return _orig_hub_switch(self)
    _hub_cls.switch = _traced_hub_switch

    print("[WSGI DIAGNOSTIC] blocking-call tracers installed (sleep / Event.wait / hub.switch)",
          file=_sys.stderr, flush=True)
except Exception as _e:
    print(f"[WSGI DIAGNOSTIC] tracer install failed: {_e}", file=_sys.stderr, flush=True)

from app import create_app
from config import ProductionConfig

app = create_app(ProductionConfig)
