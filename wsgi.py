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

# ── Diagnostic: capture full traceback for eventlet blocking errors ──────────
# "Error: do not call blocking functions from the mainloop" is printed by
# hub.squelch_generic_exception(), which swallows the traceback by default.
# Patch that method so we always get the full stack for this specific error.
# The error can also be raised before hub.switch() is reached (inside
# eventlet.sleep / Event.wait / Semaphore.acquire), so we patch those too.
# ALL patches write directly to stderr with flush=True so output is never lost.
# Remove this block once the root cause is confirmed and fixed.
import sys as _sys
import traceback as _tb

def _dump(label, exc_tb=None):
    print(f"\n[WSGI DIAG] BLOCKING FROM MAINLOOP ({label}):", file=_sys.stderr, flush=True)
    if exc_tb:
        _tb.print_tb(exc_tb, file=_sys.stderr)
    else:
        _tb.print_stack(file=_sys.stderr)
    _sys.stderr.flush()

def _is_mainloop():
    try:
        import eventlet.hubs as _h
        from greenlet import getcurrent as _gc
        return _gc() is _h.get_hub().greenlet
    except Exception:
        return False

try:
    import eventlet.hubs as _hubs
    import eventlet.event as _ev_mod
    import eventlet.semaphore as _sem_mod
    from greenlet import getcurrent as _getcurrent

    # 1) squelch_generic_exception — where "Error: ..." is actually printed ────
    _hub = _hubs.get_hub()
    _hub_cls = type(_hub)
    _orig_squelch = _hub_cls.squelch_generic_exception

    def _verbose_squelch(self, exc_info):
        exc_type, exc_value, exc_tb = exc_info
        if 'blocking' in str(exc_value).lower() or 'mainloop' in str(exc_value).lower():
            print("\n[WSGI DIAG] BLOCKING CALL — full traceback:", file=_sys.stderr, flush=True)
            _tb.print_exception(exc_type, exc_value, exc_tb, file=_sys.stderr)
            _sys.stderr.flush()
        return _orig_squelch(self, exc_info)

    _hub_cls.squelch_generic_exception = _verbose_squelch

    # 2) eventlet.sleep ─────────────────────────────────────────────────────────
    _orig_sleep = eventlet.sleep
    def _traced_sleep(seconds=0):
        if _is_mainloop():
            _dump("eventlet.sleep")
        return _orig_sleep(seconds)
    eventlet.sleep = _traced_sleep

    # 3) Event.wait ─────────────────────────────────────────────────────────────
    _orig_event_wait = _ev_mod.Event.wait
    def _traced_event_wait(self):
        if _is_mainloop():
            _dump("Event.wait")
        return _orig_event_wait(self)
    _ev_mod.Event.wait = _traced_event_wait

    # 4) Semaphore.acquire ──────────────────────────────────────────────────────
    _orig_acquire = _sem_mod.Semaphore.acquire
    def _traced_acquire(self, blocking=True, timeout=None):
        if blocking and _is_mainloop():
            _dump("Semaphore.acquire")
        return _orig_acquire(self, blocking, timeout)
    _sem_mod.Semaphore.acquire = _traced_acquire

    # 5) hub.switch ─────────────────────────────────────────────────────────────
    _orig_hub_switch = _hub_cls.switch
    def _traced_hub_switch(self):
        if _getcurrent() is self.greenlet:
            _dump("hub.switch")
        return _orig_hub_switch(self)
    _hub_cls.switch = _traced_hub_switch

    print("[WSGI DIAG] tracers installed: squelch + sleep + Event.wait + Semaphore + hub.switch",
          file=_sys.stderr, flush=True)

except Exception as _e:
    print(f"[WSGI DIAG] tracer install failed: {_e}", file=_sys.stderr, flush=True)

from app import create_app
from config import ProductionConfig

app = create_app(ProductionConfig)
