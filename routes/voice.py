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

# Module-level Redis client singleton — created once, reuses the connection pool.
# Creating a new client on every event would exhaust Redis connections under load.
_redis_client = None
_redis_checked = False


def _get_redis():
    """Return the module-level Redis client if REDIS_URL is configured, else None.

    Lazily initialised on first call; result is cached for the process lifetime
    so we reuse the connection pool rather than opening a new connection per event.
    """
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    redis_url = os.environ.get('REDIS_URL')
    if not redis_url:
        return None
    try:
        import redis as _redis_lib
        _redis_client = _redis_lib.from_url(redis_url, decode_responses=True)
        # Verify the connection is actually reachable at startup
        _redis_client.ping()
        logger.info("Voice room state: Redis (%s)", redis_url.split("@")[-1])
    except Exception as e:
        logger.warning("Redis unavailable, falling back to in-memory voice state: %s", e)
        _redis_client = None
    return _redis_client


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
        emit('voice_error', {'message': 'Please sign in again to use voice chat.'})
        return
    try:
        group_id = int(data.get('group_id', 0))
    except (TypeError, ValueError):
        return
    if not group_id:
        return

    # Authorization: only members of the group may join its voice call.
    # (Matches the is_member() gate the REST endpoints already enforce.)
    if not _verify_member(group_id):
        emit('voice_error', {'message': 'You must be a member of this group to join its voice call.'})
        return

    room = f'voice_{group_id}'
    join_room(room)

    name = current_user.get_full_name()
    me = {
        'sid':      request.sid,
        'user_id':  current_user.id,
        'name':     name,
        'initials': _initials(name),
        'avatar':   getattr(current_user, 'avatar_url', None) or '',
    }

    # Send new joiner the list of everyone already here
    existing = list(_get_participants(group_id).values())
    emit('voice_existing_participants', {'participants': existing, 'my_sid': request.sid})

    # Register them now (after sending existing so they don't see themselves)
    _add_participant(group_id, request.sid, me)

    # Tell everyone else a new person joined
    emit('voice_user_joined', me, to=room, include_self=False)
    logger.info(
        "voice join: user=%s group=%s sid=%s peers=%d redis=%s",
        current_user.id, group_id, request.sid, len(existing), bool(_get_redis()),
    )


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

def _relay_allowed(to_sid: str) -> bool:
    """True only if the sender and target are participants of the same voice room.

    Stops a peer from injecting/relaying signalling into a call it isn't part of,
    or bridging two separate rooms via a guessed/leaked SID.
    """
    if not to_sid:
        return False
    group_id, participants = _find_group_for_sid(request.sid)
    return group_id is not None and to_sid in participants


@socketio.on('webrtc_offer')
def on_offer(data):
    """Relay SDP offer from one peer to another."""
    if not current_user.is_authenticated:
        return
    to_sid = data.get('to_sid')
    if 'offer' not in data or not _relay_allowed(to_sid):
        return
    emit('webrtc_offer',
         {'offer': data['offer'], 'from_sid': request.sid},
         to=to_sid)


@socketio.on('webrtc_answer')
def on_answer(data):
    """Relay SDP answer."""
    if not current_user.is_authenticated:
        return
    to_sid = data.get('to_sid')
    if 'answer' not in data or not _relay_allowed(to_sid):
        return
    emit('webrtc_answer',
         {'answer': data['answer'], 'from_sid': request.sid},
         to=to_sid)


@socketio.on('webrtc_ice')
def on_ice(data):
    """Relay ICE candidate."""
    if not current_user.is_authenticated:
        return
    to_sid = data.get('to_sid')
    if 'candidate' not in data or not _relay_allowed(to_sid):
        return
    emit('webrtc_ice',
         {'candidate': data['candidate'], 'from_sid': request.sid},
         to=to_sid)


@socketio.on('voice_state')
def on_voice_state(data):
    """Relay a participant's mute / camera / screen-share state to the room so
    peers can render the right tile chrome (mic icon, 'presenting' badge)."""
    if not current_user.is_authenticated:
        return
    try:
        group_id = int(data.get('group_id', 0))
    except (TypeError, ValueError):
        return
    if not group_id:
        return
    payload = {'sid': request.sid}
    if 'muted' in data:
        payload['muted'] = bool(data['muted'])
    if 'video' in data:
        kind = data['video']
        payload['video'] = kind if kind in ('camera', 'screen', 'none') else 'none'
    emit('voice_state', payload, to=f'voice_{group_id}', include_self=False)


# ── Collaborative notes ──────────────────────────────────────────────────────

NOTE_MAX_LEN = 50_000


def _verify_member(group_id: int):
    """Return the StudyGroup if current_user is a member, else None."""
    from models import StudyGroup
    group = StudyGroup.query.get(group_id)
    if group and group.is_member(current_user.id):
        return group
    return None


@socketio.on('join_collab')
def on_join_collab(data):
    """Join the group's collaboration room (shared notes sync)."""
    if not current_user.is_authenticated:
        return
    try:
        group_id = int(data.get('group_id', 0))
    except (TypeError, ValueError):
        return
    if not group_id or not _verify_member(group_id):
        return
    join_room(f'collab_{group_id}')


@socketio.on('note_update')
def on_note_update(data):
    """Persist the shared note and broadcast it to everyone else in the room."""
    if not current_user.is_authenticated:
        return
    try:
        group_id = int(data.get('group_id', 0))
    except (TypeError, ValueError):
        return
    content = data.get('content')
    if not group_id or not isinstance(content, str) or not _verify_member(group_id):
        return
    content = content[:NOTE_MAX_LEN]

    from extensions import db
    from models import StudyGroupNote
    note = StudyGroupNote.query.filter_by(group_id=group_id).first()
    if not note:
        note = StudyGroupNote(group_id=group_id, content=content, updated_by=current_user.id)
        db.session.add(note)
    else:
        note.content = content
        note.updated_by = current_user.id
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        emit('note_saved', {'ok': False})
        return

    emit('note_update',
         {'content': content, 'by': current_user.get_full_name()},
         to=f'collab_{group_id}', include_self=False)
    emit('note_saved', {'ok': True})
