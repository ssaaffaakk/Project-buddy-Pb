"""
Direct messages — private 1:1 chat between two users.

Live delivery is over SocketIO (event 'dm_message', room 'dm_<conversation_id>');
a poll endpoint is kept as a reconnect / socket-down fallback, exactly like the
study-group chat. Every thread is a single Conversation row per user pair
(canonical low/high id ordering), so opening a chat from either direction lands
in the same thread.
"""

from datetime import datetime, timezone

from flask import Blueprint, render_template, request, jsonify, url_for, abort
from flask_login import login_required, current_user
from flask_socketio import join_room

from extensions import db, limiter, socketio
from models import User, Conversation, DirectMessage
from services import analytics

messages_bp = Blueprint("messages", __name__, url_prefix="/messages")

MAX_BODY = 4000


def _get_or_create_conversation(other_id: int) -> Conversation:
    """Return the (single) conversation between the current user and `other_id`,
    creating it on first contact. Ids are stored canonically low→high."""
    a_id, b_id = Conversation.pair(current_user.id, other_id)
    conv = Conversation.query.filter_by(user_a_id=a_id, user_b_id=b_id).first()
    if conv is None:
        conv = Conversation(user_a_id=a_id, user_b_id=b_id)
        db.session.add(conv)
        db.session.commit()
    return conv


def _msg_json(m: DirectMessage) -> dict:
    return {
        "id": m.id,
        "body": m.body,
        "sender_id": m.sender_id,
        "is_mine": m.sender_id == current_user.id,
        "time": m.created_at.strftime("%H:%M"),
    }


# ── INBOX ─────────────────────────────────────────────────────────────────────
@messages_bp.route("/")
@login_required
def inbox():
    """All conversations the user is part of, newest activity first, each with
    the other person, a last-message preview, and an unread count."""
    convs = (Conversation.query
             .filter((Conversation.user_a_id == current_user.id) |
                     (Conversation.user_b_id == current_user.id))
             .order_by(Conversation.last_message_at.desc())
             .all())
    threads = []
    for c in convs:
        other = c.other(current_user.id)
        if other is None:
            continue
        last = (DirectMessage.query.filter_by(conversation_id=c.id)
                .order_by(DirectMessage.created_at.desc()).first())
        if last is None:
            continue  # empty conversation (created but never used) — hide it
        unread = (DirectMessage.query
                  .filter(DirectMessage.conversation_id == c.id,
                          DirectMessage.sender_id != current_user.id,
                          DirectMessage.is_read == False)  # noqa: E712
                  .count())
        threads.append({
            "user_id": other.id,
            "name": other.get_full_name(),
            "avatar_url": other.avatar_url,
            "initials": (other.first_name[:1] + other.last_name[:1]).upper(),
            "preview": (last.body[:60] + "…") if len(last.body) > 60 else last.body,
            "preview_mine": last.sender_id == current_user.id,
            "time": last.created_at.strftime("%b %d, %H:%M"),
            "unread": unread,
        })
    return render_template("messages/inbox.html", threads=threads, user=current_user)


# ── OPEN / VIEW A THREAD ──────────────────────────────────────────────────────
@messages_bp.route("/with/<int:user_id>")
@login_required
def thread(user_id):
    if user_id == current_user.id:
        abort(404)
    other = User.query.get_or_404(user_id)
    conv = _get_or_create_conversation(other.id)

    msgs = (DirectMessage.query.filter_by(conversation_id=conv.id)
            .order_by(DirectMessage.created_at.asc())
            .limit(200).all())

    # Mark the other person's messages as read now that we're viewing them.
    unread = [m for m in msgs if m.sender_id != current_user.id and not m.is_read]
    if unread:
        for m in unread:
            m.is_read = True
        db.session.commit()

    return render_template(
        "messages/thread.html",
        other=other,
        conversation=conv,
        messages=msgs,
        user=current_user,
    )


# ── SEND A MESSAGE ────────────────────────────────────────────────────────────
@messages_bp.route("/with/<int:user_id>/send", methods=["POST"])
@login_required
@limiter.limit("60 per minute")
def send(user_id):
    if user_id == current_user.id:
        return jsonify({"error": "You cannot message yourself."}), 400
    other = User.query.get(user_id)
    if other is None or other.is_banned or not other.is_active:
        return jsonify({"error": "This user is not available."}), 404

    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Message cannot be empty."}), 400
    if len(body) > MAX_BODY:
        return jsonify({"error": f"Too long (max {MAX_BODY} chars)."}), 400

    conv = _get_or_create_conversation(other.id)
    msg = DirectMessage(conversation_id=conv.id, sender_id=current_user.id, body=body)
    db.session.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)

    # Notify the recipient (in-app + web-push), and log the event.
    from routes.main import create_notification
    create_notification(
        user_id=other.id,
        type="dm",
        message=f"💬 New message from {current_user.get_full_name()}",
        link=url_for("messages.thread", user_id=current_user.id),
    )
    analytics.track("dm_sent", current_user.id, "user", other.id)
    db.session.commit()

    payload = _msg_json(msg)
    # Broadcast to both participants' shared room. The sender's own echo is
    # deduped client-side by message id (same trick as sg_message).
    socketio.emit("dm_message", {**payload, "conversation_id": conv.id},
                  to=f"dm_{conv.id}")
    return jsonify(payload), 201


# ── POLL (reconnect / socket-down fallback) ───────────────────────────────────
@messages_bp.route("/<int:conversation_id>/poll")
@limiter.exempt
@login_required
def poll(conversation_id):
    conv = Conversation.query.get_or_404(conversation_id)
    if not conv.has_member(current_user.id):
        abort(403)
    after_id = request.args.get("after", 0, type=int)
    msgs = (DirectMessage.query
            .filter(DirectMessage.conversation_id == conversation_id,
                    DirectMessage.id > after_id)
            .order_by(DirectMessage.created_at.asc())
            .limit(100).all())
    # Anything from the other side that we're now seeing counts as read.
    changed = False
    for m in msgs:
        if m.sender_id != current_user.id and not m.is_read:
            m.is_read = True
            changed = True
    if changed:
        db.session.commit()
    return jsonify([_msg_json(m) for m in msgs])


# ── UNREAD COUNT (nav badge poll) ─────────────────────────────────────────────
@messages_bp.route("/unread-count")
@limiter.exempt
@login_required
def unread_count():
    n = (DirectMessage.query
         .join(Conversation, Conversation.id == DirectMessage.conversation_id)
         .filter((Conversation.user_a_id == current_user.id) |
                 (Conversation.user_b_id == current_user.id))
         .filter(DirectMessage.sender_id != current_user.id,
                 DirectMessage.is_read == False)  # noqa: E712
         .count())
    return jsonify({"count": n})


# ── SocketIO: join a conversation's room ──────────────────────────────────────
@socketio.on("join_dm")
def on_join_dm(data):
    """Join the private room for a conversation after verifying membership."""
    if not current_user.is_authenticated:
        return
    try:
        conversation_id = int(data.get("conversation_id", 0))
    except (TypeError, ValueError):
        return
    if not conversation_id:
        return
    conv = Conversation.query.get(conversation_id)
    if conv is None or not conv.has_member(current_user.id):
        return
    join_room(f"dm_{conversation_id}")
