"""
WebRTC Voice Chat — SocketIO signaling for Study Group voice rooms.

Flow:
  1. User clicks "Join Voice" → frontend calls socket.emit('join_voice', {group_id})
  2. Server joins them to room 'voice_{group_id}' and broadcasts they joined
  3. Existing participants receive 'voice_user_joined' and initiate WebRTC offers
  4. New joiner receives 'voice_existing_participants' to initiate offers to everyone else
  5. SDP offers/answers and ICE candidates are relayed peer-to-peer via server
"""

import logging
from flask import request
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from extensions import socketio

logger = logging.getLogger(__name__)

# In-memory voice state: {group_id (int): {sid (str): participant_dict}}
_voice_rooms: dict = {}


def _initials(name: str) -> str:
    parts = name.split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()


def _remove_sid(sid: str) -> None:
    """Remove a socket ID from whatever voice room it's in and notify peers."""
    for group_id, participants in list(_voice_rooms.items()):
        if sid in participants:
            del participants[sid]
            if not participants:
                del _voice_rooms[group_id]
            emit('voice_user_left', {'sid': sid}, to=f'voice_{group_id}')
            leave_room(f'voice_{group_id}', sid=sid)
            break


# ── Events ───────────────────────────────────────────────────────────────────

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

    if group_id not in _voice_rooms:
        _voice_rooms[group_id] = {}

    # Send new joiner the list of everyone already here
    existing = list(_voice_rooms[group_id].values())
    emit('voice_existing_participants', {'participants': existing, 'my_sid': request.sid})

    # Register them now (after sending existing so they don't see themselves)
    _voice_rooms[group_id][request.sid] = me

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
    if group_id in _voice_rooms and sid in _voice_rooms[group_id]:
        del _voice_rooms[group_id][sid]
        if not _voice_rooms[group_id]:
            del _voice_rooms[group_id]
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
