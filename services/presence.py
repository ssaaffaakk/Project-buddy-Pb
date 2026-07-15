"""In-memory online-presence registry (green-dot indicator).

The app runs on a single eventlet worker (Procfile: gunicorn -w 1), so a
process-local dict is a correct, dependency-free presence store — no Redis or
DB column needed. A user counts as "online" if they've been seen within
ONLINE_WINDOW seconds. Every authenticated request refreshes the timestamp,
and the client sends a lightweight heartbeat while a tab is open so idle
readers stay green. State resets on restart, which is fine for a dot: everyone
re-touches on their next request.
"""

import time

ONLINE_WINDOW = 75  # seconds since last activity to still count as online

_last_seen = {}  # user_id -> unix timestamp


def touch(user_id):
    """Mark a user active now."""
    if user_id:
        _last_seen[int(user_id)] = time.time()


def is_online(user_id):
    if not user_id:
        return False
    ts = _last_seen.get(int(user_id))
    return ts is not None and (time.time() - ts) <= ONLINE_WINDOW


def online_ids():
    """List of user_ids seen within the online window (stale entries dropped)."""
    cutoff = time.time() - ONLINE_WINDOW
    stale = [uid for uid, ts in list(_last_seen.items()) if ts < cutoff]
    for uid in stale:
        _last_seen.pop(uid, None)
    return list(_last_seen.keys())
