"""
WebRTC Voice Chat — SocketIO signaling for Study Group voice rooms.

Flow:
  1. User clicks "Join Voice" → frontend calls socket.emit('join_voice', {group_id})
  2. Server joins them to room 'voice_{group_id}' and broadcasts they joined
  3. Existing participants receive 'voice_user_joined' and initiate WebRTC offers
  4. New joiner receives 'voice_existing_participants' to initiate offers to everyone else
  5. SDP offers/answers and ICE candidates are relayed peer-to-peer via server

Voice room state storage:
  - If REDIS_URL is set: stored in Redis (shared across workers, survives restarts)
  - Otherwise: stored in an in-process dict (dev / single-worker only)
"""

import os
import json
import logging
from flask import request
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from extensions import socketio

logger = logging.getLogger(__name__)


# ── Room state backend ────────────────────────────────────────────────────────

def _get_redis():
    """Return a Redis client if REDIS_URL is configured, else None."""
    redis_url = os.environ.get('REDIS_URL')
    if not redis_url:
        return None
    try:
        import redis
        return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.warning("Redis unavailable, falling back to in-memory voice state: %s", e)
        return None


# Fallback: in-process dict used when Redis is not available.
# {group_id (int): {sid (str): participant_dict}}
_local_voice_rooms: dict = {}


def _room_key(group_id: int) -> str:
    return f"voice_room:{group_id}"


def _get_participants(group_id: int) -> dict:
    """Return {sid: participant_dict} for a room."""
    r = _get_redis()
    if r:
        raw = r.get(_room_key(group_id))
        return json.loads(raw) if raw else {}
    return _local_voice_rooms.get(group_id, {})


def _set_participants(group_id: int, participants: dict) -> None:
    r = _get_redis()
    if r:
        if participants:
            r.set(_room_key(group_id), json.dumps(participants), ex=86400)  # 24h TTL
        else:
            r.delete(_room_key(group_id))
    else:
        if participants:
            _local_voice_rooms[group_id] = participants
        else:
            _local_voice_rooms.pop(group_id, None)


def _add_participant(group_id: int, sid: str, info: dict) -> None:
    participants = _get_participants(group_id)
    participants[sid] = info
    _set_participants(group_id, participants)


def _remove_participant(group_id: int, sid: str) -> None:
    participants = _get_participants(group_id)
    participants.pop(sid, None)
    _set_participants(group_id, participants)


def _find_group_for_sid(sid: str):
    """Find which group_id a sid belongs to. Returns (group_id, participants) or (None, {})."""
    r = _get_redis()
    if r:
        for key in r.scan_iter("voice_room:*"):
            raw = r.get(key)
            if not raw:
                continue
            participants = json.loads(raw)
            if sid in participants:
                group_id = int(key.split(":")[-1])
                return group_id, participants
        return None, {}
    else:
        for group_id, participants in list(_local_voice_rooms.items()):
            if sid in participants:
                return group_id, participants
        return None, {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _initials(name: str) -> str:
    parts = name.split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()


def _remove_sid(sid: str) -> None:
    """Remove a socket ID from whatever voice room it's in and notify peers."""
    group_id, participants = _find_group_for_sid(sid)
    if group_id is None:
        return
    participants.pop(sid, None)
    _set_participants(group_id, participants)
    emit('voice_user_left', {'sid': sid}, to=f'voice_{group_id}')
    leave_room(f'voice_{group_id}', sid=sid)


# ── Events ────────────────────────────────────────────────────────────────────

@socketio.on('join_voice')
def on_join_voice(data):
    if not current_user.is_authenticated:
        return
    try:
        group_id = int(data.get('group_id', 0))
    except (TypeError, ValueError):
        return
    if not group_id:
        return

    room = f'voice_{group_id}'
    join_room(room)

    name = current_user.get_full_name()
    me = {
        'sid':      request.sid,
        'user_id':  current_user.id,
        'name':     name,
        'initials': _initials(name),
    }

    # Send new joiner the list of everyone already here
    existing = list(_get_participants(group_id).values())
    emit('voice_existing_participants', {'participants': existing, 'my_sid': request.sid})

    # Register them now (after sending existing so they don't see themselves)
    _add_participant(group_id, request.sid, me)

    # Tell everyone else a new person joined
    emit('voice_user_joined', me, to=room, include_self=False)


@socketio.on('leave_voice')
def on_leave_voice(data):
    try:
        group_id = int(data.get('group_id', 0))
    except (TypeError, ValueError):
        return
    sid = request.sid
    room = f'voice_{group_id}'
    leave_room(room)
    _remove_participant(group_id, sid)
    emit('voice_user_left', {'sid': sid}, to=room)


@socketio.on('disconnect')
def on_disconnect():
    _remove_sid(request.sid)


# ── WebRTC relay ─────────────────────────────────────────────────────────────

@socketio.on('webrtc_offer')
def on_offer(data):
    """Relay SDP offer from one peer to another."""
    emit('webrtc_offer',
         {'offer': data['offer'], 'from_sid': request.sid},
         to=data['to_sid'])


@socketio.on('webrtc_answer')
def on_answer(data):
    """Relay SDP answer."""
    emit('webrtc_answer',
         {'answer': data['answer'], 'from_sid': request.sid},
         to=data['to_sid'])


@socketio.on('webrtc_ice')
def on_ice(data):
    """Relay ICE candidate."""
    emit('webrtc_ice',
         {'candidate': data['candidate'], 'from_sid': request.sid},
         to=data['to_sid'])
