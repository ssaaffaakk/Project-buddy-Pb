"""
Direct messages — private 1:1 chat between two users.

Live delivery is over SocketIO (event 'dm_message', room 'dm_<conversation_id>');
a poll endpoint is kept as a reconnect / socket-down fallback, exactly like the
study-group chat. Every thread is a single Conversation row per user pair
(canonical low/high id ordering), so opening a chat from either direction lands
in the same thread.
"""

import uuid
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, jsonify, url_for, abort, send_from_directory
from flask_login import login_required, current_user
from flask_socketio import join_room, emit
from werkzeug.utils import secure_filename

from extensions import db, limiter, socketio
from models import (User, Conversation, DirectMessage, DmAttachment,
                    ProjectMember, StudyGroupMember)
from services import analytics
from services.file_storage import storage

messages_bp = Blueprint("messages", __name__, url_prefix="/messages")

MAX_BODY = 4000

# Same file rules as study-group chat (routes/study_groups.py)
ALLOWED_EXT = {
    'pdf', 'txt', 'md',
    'png', 'jpg', 'jpeg', 'gif', 'webp',
    'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'csv',
    'py', 'js', 'ts', 'html', 'css', 'json', 'yaml', 'yml',
    'zip', 'tar', 'gz',
    'mp4', 'mp3', 'wav',
}
IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_FILE_BYTES = 25 * 1024 * 1024   # 25 MB


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


def _attachment_json(att: DmAttachment):
    """Serialize a DmAttachment for inline rendering in the chat stream."""
    if not att:
        return None
    ext = att.filename.rsplit(".", 1)[-1].lower() if "." in att.filename else ""
    is_image = (att.mime_type or "").startswith("image/") or ext in IMAGE_EXT
    return {
        "id": att.id,
        "filename": att.filename,
        "file_size": att.file_size,
        "is_image": is_image,
        "url": url_for("messages.download_attachment", file_id=att.id),
    }


def _shared_post_json(post):
    """Serialize a shared CommunityPost as a compact preview card, or a
    tombstone if the post was deleted after sharing."""
    if post is None:
        return {"deleted": True}
    body = post.body or ""
    return {
        "deleted": False,
        "id": post.id,
        "title": post.title,
        "excerpt": (body[:140] + "…") if len(body) > 140 else body,
        "author": post.author.get_full_name() if post.author else "Unknown",
        "media_url": post.media_url if post.media_type == "image" else None,
        "media_type": post.media_type,
        "url": url_for("community.feed") + f"#post-{post.id}",
    }


def _msg_json(m: DirectMessage) -> dict:
    return {
        "id": m.id,
        "body": m.body,
        "sender_id": m.sender_id,
        "is_mine": m.sender_id == current_user.id,
        "time": m.created_at.strftime("%H:%M"),
        "attachment": _attachment_json(m.attachment) if m.attachment_id else None,
        "shared_post": _shared_post_json(m.shared_post) if m.shared_post_id else None,
    }


def _store_attachment(conversation_id, f):
    """Persist an uploaded file as a DmAttachment. Returns (DmAttachment, None)
    or (None, (error_message, status_code)). Mirrors study-group uploads."""
    if not f or not f.filename:
        return None, ("No file selected.", 400)
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        return None, ("File type not allowed.", 400)
    data = f.read()
    if len(data) > MAX_FILE_BYTES:
        return None, ("File too large (max 25 MB).", 400)
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    storage.save(data, stored_name, category="dm")
    att = DmAttachment(
        conversation_id=conversation_id,
        uploader_id=current_user.id,
        filename=secure_filename(f.filename) or f"file.{ext}",
        stored_name=stored_name,
        file_size=len(data),
        mime_type=f.mimetype or "application/octet-stream",
    )
    db.session.add(att)
    db.session.flush()  # assign att.id before we reference it on the message
    return att, None


def _people_suggestions(limit=8):
    """People the current user is likely to message: project teammates first,
    then study-group co-members, then newest active users — excluding anyone
    they already have a conversation with."""
    me = current_user.id

    existing = set()
    for c in (Conversation.query
              .filter((Conversation.user_a_id == me) | (Conversation.user_b_id == me))
              .all()):
        existing.add(c.user_a_id)
        existing.add(c.user_b_id)
    existing.add(me)

    suggestions, seen = [], set()

    def _add(user, reason):
        if (user is None or user.id in existing or user.id in seen
                or user.is_banned or not user.is_active or user.role == "admin"):
            return
        seen.add(user.id)
        suggestions.append({
            "id": user.id,
            "name": user.get_full_name(),
            "avatar_url": user.avatar_url,
            "initials": (user.first_name[:1] + user.last_name[:1]).upper(),
            "reason": reason,
            "department": user.department,
        })

    # 1) Teammates on my active projects
    my_project_ids = [m.project_id for m in ProjectMember.query.filter_by(
        user_id=me, removed=False).all()]
    if my_project_ids:
        mates = (ProjectMember.query
                 .filter(ProjectMember.project_id.in_(my_project_ids),
                         ProjectMember.removed == False,  # noqa: E712
                         ProjectMember.user_id != me)
                 .limit(40).all())
        for m in mates:
            _add(m.user, "Project teammate")
            if len(suggestions) >= limit:
                return suggestions

    # 2) People in my study groups
    my_group_ids = [g.group_id for g in StudyGroupMember.query.filter_by(user_id=me).all()]
    if my_group_ids:
        peers = (StudyGroupMember.query
                 .filter(StudyGroupMember.group_id.in_(my_group_ids),
                         StudyGroupMember.user_id != me)
                 .limit(40).all())
        for p in peers:
            _add(p.user, "Study group")
            if len(suggestions) >= limit:
                return suggestions

    # 3) Fill with newest members
    newest = (User.query
              .filter(User.id != me, User.is_banned == False,  # noqa: E712
                      User.is_active == True)  # noqa: E712
              .order_by(User.created_at.desc())
              .limit(20).all())
    for u in newest:
        _add(u, "New on ProjectBuddy")
        if len(suggestions) >= limit:
            break
    return suggestions


# ── INBOX ─────────────────────────────────────────────────────────────────────
@messages_bp.route("/")
@login_required
def inbox():
    """All conversations the user is part of — pinned first, then by recency,
    with the ones the user archived tucked into a collapsed section."""
    convs = (Conversation.query
             .filter((Conversation.user_a_id == current_user.id) |
                     (Conversation.user_b_id == current_user.id))
             .order_by(Conversation.last_message_at.desc())
             .all())
    threads, archived = [], []
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
        preview = last.body or ("📎 Attachment" if last.attachment_id else "")
        entry = {
            "conversation_id": c.id,
            "user_id": other.id,
            "name": other.get_full_name(),
            "avatar_url": other.avatar_url,
            "initials": (other.first_name[:1] + other.last_name[:1]).upper(),
            "preview": (preview[:60] + "…") if len(preview) > 60 else preview,
            "preview_mine": last.sender_id == current_user.id,
            "time": last.created_at.strftime("%b %d, %H:%M"),
            "unread": unread,
            "pinned": c.pinned_for(current_user.id),
        }
        (archived if c.archived_for(current_user.id) else threads).append(entry)
    # Pinned conversations float to the top; both groups stay recency-sorted.
    threads.sort(key=lambda t: not t["pinned"])
    return render_template("messages/inbox.html", threads=threads, archived=archived,
                           suggestions=_people_suggestions(), user=current_user)


# ── ARCHIVE / PIN (per-member inbox organisation) ────────────────────────────
def _my_conversation_or_404(conversation_id):
    conv = Conversation.query.get_or_404(conversation_id)
    if not conv.has_member(current_user.id):
        abort(403)
    return conv


@messages_bp.route("/<int:conversation_id>/archive", methods=["POST"])
@login_required
def toggle_archive(conversation_id):
    """Toggle my archive flag on a conversation. Only affects my inbox."""
    conv = _my_conversation_or_404(conversation_id)
    new_state = not conv.archived_for(current_user.id)
    conv.set_archived(current_user.id, new_state)
    if new_state:
        # Archiving implies un-pinning — a chat can't be both tucked away and on top.
        conv.set_pinned(current_user.id, False)
    db.session.commit()
    return jsonify({"archived": new_state})


@messages_bp.route("/<int:conversation_id>/pin", methods=["POST"])
@login_required
def toggle_pin(conversation_id):
    """Toggle my pin flag on a conversation. Pinned chats sort first."""
    conv = _my_conversation_or_404(conversation_id)
    new_state = not conv.pinned_for(current_user.id)
    conv.set_pinned(current_user.id, new_state)
    if new_state:
        conv.set_archived(current_user.id, False)
    db.session.commit()
    return jsonify({"pinned": new_state})


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

    # ICE servers for the 1:1 voice/video call (same helper the group rooms use)
    import json
    from routes.study_groups import _ice_servers, _servers_include_turn
    ice = _ice_servers()

    return render_template(
        "messages/thread.html",
        other=other,
        conversation=conv,
        messages=msgs,
        user=current_user,
        ice_servers=json.dumps(ice),
        call_has_turn=_servers_include_turn(ice),
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

    # Multipart (file drop) or plain JSON — same dual shape as study-group chat.
    f = request.files.get("file")
    if f is not None and f.filename:
        body = (request.form.get("body") or "").strip()
    else:
        f = None
        data = request.get_json(silent=True) or {}
        body = (data.get("body") or "").strip()

    if len(body) > MAX_BODY:
        return jsonify({"error": f"Too long (max {MAX_BODY} chars)."}), 400

    conv = _get_or_create_conversation(other.id)

    attachment = None
    if f is not None:
        attachment, err = _store_attachment(conv.id, f)
        if err:
            return jsonify({"error": err[0]}), err[1]

    if not body and attachment is None:
        return jsonify({"error": "Message cannot be empty."}), 400

    payload = _deliver_dm(conv, other, body,
                          attachment_id=attachment.id if attachment else None)
    return jsonify(payload), 201


def _deliver_dm(conv, other, body, attachment_id=None, shared_post_id=None,
                notif_message=None):
    """Persist a DM, bump/unarchive the conversation, notify the recipient, log
    the event and broadcast it over SocketIO. Returns the JSON payload.
    Shared by the normal send route and the "share a post" route. Assumes the
    caller has validated `other` and the body/attachment/post."""
    msg = DirectMessage(conversation_id=conv.id, sender_id=current_user.id, body=body,
                        attachment_id=attachment_id, shared_post_id=shared_post_id)
    db.session.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    # Fresh activity pulls an archived chat back into both inboxes.
    conv.a_archived = False
    conv.b_archived = False

    # Notify the recipient (in-app + web-push), and log the event.
    from routes.main import create_notification
    create_notification(
        user_id=other.id,
        type="dm",
        message=notif_message or f"💬 New message from {current_user.get_full_name()}",
        link=url_for("messages.thread", user_id=current_user.id),
    )
    analytics.track("dm_sent", current_user.id, "user", other.id)
    db.session.commit()

    payload = _msg_json(msg)
    # Broadcast to both participants' shared room. The sender's own echo is
    # deduped client-side by message id (same trick as sg_message).
    socketio.emit("dm_message", {**payload, "conversation_id": conv.id},
                  to=f"dm_{conv.id}")
    return payload


# ── SHARE A COMMUNITY POST INTO DMs ───────────────────────────────────────────
@messages_bp.route("/share-post", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def share_post():
    """Send a community post as a preview card to one or more users' DMs.
    Body: {post_id: int, user_ids: [int, ...], note: "optional message"}."""
    from models import CommunityPost
    data = request.get_json(silent=True) or {}
    try:
        post_id = int(data.get("post_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid post."}), 400
    post = CommunityPost.query.get(post_id)
    if post is None:
        return jsonify({"error": "Post not found."}), 404

    raw_ids = data.get("user_ids") or []
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"error": "Pick at least one person."}), 400
    if len(raw_ids) > 20:
        return jsonify({"error": "You can share with up to 20 people at once."}), 400

    note = (data.get("note") or "").strip()
    if len(note) > MAX_BODY:
        return jsonify({"error": f"Note too long (max {MAX_BODY} chars)."}), 400

    sent = 0
    for raw in raw_ids:
        try:
            uid = int(raw)
        except (TypeError, ValueError):
            continue
        if uid == current_user.id:
            continue
        other = User.query.get(uid)
        if other is None or other.is_banned or not other.is_active or other.role == "admin":
            continue
        conv = _get_or_create_conversation(other.id)
        _deliver_dm(conv, other, note, shared_post_id=post.id,
                    notif_message=f"🔗 {current_user.get_full_name()} shared a post with you")
        sent += 1

    if sent == 0:
        return jsonify({"error": "None of those people could be reached."}), 400
    analytics.track("post_shared", current_user.id, "post", post.id, value=sent, commit=True)
    return jsonify({"sent": sent}), 201


@messages_bp.route("/share-targets")
@limiter.exempt
@login_required
def share_targets():
    """People the user can share a post with — existing chats first, then
    teammates, then study-group peers. Used by the community Share picker."""
    me = current_user.id
    out, seen = [], {me}

    def _add(user, reason):
        if (user is None or user.id in seen or user.is_banned
                or not user.is_active or user.role == "admin"):
            return
        seen.add(user.id)
        out.append({
            "id": user.id,
            "name": user.get_full_name(),
            "avatar_url": user.avatar_url,
            "initials": (user.first_name[:1] + user.last_name[:1]).upper(),
            "reason": reason,
        })

    # 1) People I already talk to (most likely share targets)
    convs = (Conversation.query
             .filter((Conversation.user_a_id == me) | (Conversation.user_b_id == me))
             .order_by(Conversation.last_message_at.desc())
             .all())
    for c in convs:
        _add(c.other(me), "Recent chat")

    # 2) Project teammates
    my_project_ids = [m.project_id for m in ProjectMember.query.filter_by(
        user_id=me, removed=False).all()]
    if my_project_ids:
        for m in (ProjectMember.query
                  .filter(ProjectMember.project_id.in_(my_project_ids),
                          ProjectMember.removed == False,  # noqa: E712
                          ProjectMember.user_id != me).all()):
            _add(m.user, "Teammate")

    # 3) Study-group peers
    my_group_ids = [g.group_id for g in StudyGroupMember.query.filter_by(user_id=me).all()]
    if my_group_ids:
        for p in (StudyGroupMember.query
                  .filter(StudyGroupMember.group_id.in_(my_group_ids),
                          StudyGroupMember.user_id != me).all()):
            _add(p.user, "Study group")

    return jsonify({"people": out})


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


# ── ATTACHMENT DOWNLOAD ───────────────────────────────────────────────────────
@messages_bp.route("/file/<int:file_id>")
@login_required
def download_attachment(file_id):
    """Serve a DM attachment — only to the two conversation members."""
    att = DmAttachment.query.get_or_404(file_id)
    conv = Conversation.query.get_or_404(att.conversation_id)
    if not conv.has_member(current_user.id):
        abort(403)

    # S3: redirect to a pre-signed URL
    presigned = storage.download_url(f"dm/{att.stored_name}")
    if presigned:
        from flask import redirect as _redirect
        return _redirect(presigned)

    # Local: serve directly from disk
    local_dir = storage.local_path("dm", att.stored_name)
    is_image = (att.mime_type or "").startswith("image/")
    return send_from_directory(
        local_dir,
        att.stored_name,
        as_attachment=not is_image,  # images render inline in the stream
        download_name=att.filename,
    )


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


# ── SocketIO: 1:1 voice / video calls (WebRTC signaling) ─────────────────────
# Both members join room 'dm_<conversation_id>' while viewing the thread, so
# call events are simply relayed to that room (excluding the sender). The
# actual media flows peer-to-peer over WebRTC; the server only forwards
# offers/answers/ICE candidates — the same model as the group voice rooms.

def _dm_call_conv(data):
    """Validated Conversation for a call event, or None."""
    if not current_user.is_authenticated:
        return None
    try:
        conversation_id = int(data.get("conversation_id", 0))
    except (TypeError, ValueError):
        return None
    conv = Conversation.query.get(conversation_id)
    if conv is None or not conv.has_member(current_user.id):
        return None
    return conv


@socketio.on("dm_call_invite")
def on_dm_call_invite(data):
    """Caller rings the other side. `video` selects camera-call vs voice-call."""
    conv = _dm_call_conv(data)
    if conv is None:
        return
    emit("dm_call_invite", {
        "conversation_id": conv.id,
        "from_id": current_user.id,
        "from_name": current_user.get_full_name(),
        "video": bool(data.get("video")),
    }, to=f"dm_{conv.id}", include_self=False)
    analytics.track("dm_call_invite", current_user.id, "conversation", conv.id)


@socketio.on("dm_call_accept")
def on_dm_call_accept(data):
    conv = _dm_call_conv(data)
    if conv is None:
        return
    emit("dm_call_accept", {"conversation_id": conv.id, "from_id": current_user.id},
         to=f"dm_{conv.id}", include_self=False)


@socketio.on("dm_call_decline")
def on_dm_call_decline(data):
    conv = _dm_call_conv(data)
    if conv is None:
        return
    emit("dm_call_decline", {"conversation_id": conv.id, "from_id": current_user.id},
         to=f"dm_{conv.id}", include_self=False)


@socketio.on("dm_call_signal")
def on_dm_call_signal(data):
    """Relay WebRTC SDP offers/answers and ICE candidates between the pair."""
    conv = _dm_call_conv(data)
    if conv is None:
        return
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return
    emit("dm_call_signal", {"conversation_id": conv.id, "payload": payload},
         to=f"dm_{conv.id}", include_self=False)


@socketio.on("dm_call_hangup")
def on_dm_call_hangup(data):
    conv = _dm_call_conv(data)
    if conv is None:
        return
    emit("dm_call_hangup", {"conversation_id": conv.id, "from_id": current_user.id},
         to=f"dm_{conv.id}", include_self=False)
