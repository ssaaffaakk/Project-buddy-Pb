"""
Study Groups — mini Discord-style group chat rooms.
"""

import os
import json
import uuid
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db, limiter
from models import StudyGroup, StudyGroupMember, StudyGroupMessage, StudyGroupNote, SharedFile
from services.file_storage import storage


def _servers_include_turn(servers: list) -> bool:
    """Return True if any entry is a TURN/TURNS relay (not STUN-only)."""
    for entry in servers:
        urls = entry.get("urls", "")
        for url in (urls if isinstance(urls, list) else [urls]):
            if isinstance(url, str) and url.startswith(("turn:", "turns:")):
                return True
    return False


def _ice_servers():
    """Build ICE server list for WebRTC.

    Production voice chat requires TURN — STUN alone fails behind NAT/firewalls.
    Priority:
      1. Xirsys API (fresh time-limited credentials on each room load)
      2. Static TURN_URLS + TURN_USERNAME + TURN_CREDENTIAL (Metered, Twilio, Coturn…)
      3. Google STUN only (dev / same-LAN; not sufficient for real users)
    """
    import logging
    logger = logging.getLogger(__name__)

    servers = [
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": "stun:stun1.l.google.com:19302"},
    ]

    # ── Xirsys: fetch fresh credentials via API ───────────────────────────────
    ident   = os.environ.get("XIRSYS_IDENT", "")
    secret  = os.environ.get("XIRSYS_SECRET", "")
    channel = os.environ.get("XIRSYS_CHANNEL", "")
    if ident and secret and channel:
        try:
            import requests as _req
            import base64
            import eventlet.tpool
            token = base64.b64encode(f"{ident}:{secret}".encode()).decode()
            resp = eventlet.tpool.execute(
                _req.put,
                f"https://global.xirsys.net/_turn/{channel}",
                headers={"Authorization": f"Basic {token}"},
                timeout=5,
            )
            data = resp.json()
            if data.get("s") == "ok":
                ice = data["v"].get("iceServers", [])
                if isinstance(ice, list) and ice:
                    if _servers_include_turn(ice):
                        return ice
                    logger.warning("Xirsys returned ICE servers but no TURN URLs: %s", ice)
            else:
                logger.warning("Xirsys API error: %s", data)
        except Exception as e:
            logger.warning("Xirsys API call failed: %s", e)

    # ── Static fallback (Metered, Twilio, self-hosted Coturn, etc.) ─────────
    urls_raw   = os.environ.get("TURN_URLS", "")
    username   = os.environ.get("TURN_USERNAME", "")
    credential = os.environ.get("TURN_CREDENTIAL", "")
    if urls_raw and username and credential:
        for url in [u.strip() for u in urls_raw.split(",") if u.strip()]:
            servers.append({"urls": url, "username": username, "credential": credential})

    if not _servers_include_turn(servers):
        logger.warning(
            "WebRTC TURN not configured — voice chat will fail for most production users "
            "(NAT/firewall). Set XIRSYS_* or TURN_URLS/TURN_USERNAME/TURN_CREDENTIAL."
        )

    return servers

# ── File upload config ────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
ALLOWED_EXT = {
    'pdf', 'txt', 'md',
    'png', 'jpg', 'jpeg', 'gif', 'webp',
    'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'csv',
    'py', 'json', 'yaml', 'yml',
    'zip', 'tar', 'gz',
    'mp4', 'mp3', 'wav',
}
MAX_FILE_BYTES = 25 * 1024 * 1024   # 25 MB

study_groups_bp = Blueprint("study_groups", __name__, url_prefix="/study-groups")


# ── LIST / DISCOVER ──────────────────────────────────────────────────────────
@study_groups_bp.route("/")
@login_required
def index():
    """All public groups + groups the user is in."""
    all_groups = StudyGroup.query.filter_by(is_private=False).order_by(StudyGroup.created_at.desc()).all()
    my_ids = {m.group_id for m in StudyGroupMember.query.filter_by(user_id=current_user.id).all()}

    # Live voice presence per group (for "LIVE · n in voice" badges)
    from routes.voice import _get_participants
    voice_counts = {}
    for g in all_groups:
        try:
            n = len(_get_participants(g.id))
        except Exception:
            n = 0
        if n:
            voice_counts[g.id] = n

    return render_template("study_groups/list.html", groups=all_groups, my_ids=my_ids,
                           user=current_user, voice_counts=voice_counts)


# ── CREATE GROUP ─────────────────────────────────────────────────────────────
@study_groups_bp.route("/create", methods=["POST"])
@login_required
def create_group():
    name  = request.form.get("name", "").strip()
    topic = request.form.get("topic", "").strip()
    desc  = request.form.get("description", "").strip()

    if not name:
        flash("Group name is required.", "error")
        return redirect(url_for("study_groups.index"))

    group = StudyGroup(
        name=name, topic=topic or None,
        description=desc or None,
        creator_id=current_user.id,
    )
    db.session.add(group)
    db.session.flush()   # get group.id before commit

    # Creator auto-joins as admin
    db.session.add(StudyGroupMember(group_id=group.id, user_id=current_user.id, role="admin"))
    db.session.commit()
    flash(f"Group «{name}» created!", "success")
    return redirect(url_for("study_groups.room", group_id=group.id))


# ── JOIN / LEAVE ─────────────────────────────────────────────────────────────
@study_groups_bp.route("/<int:group_id>/join", methods=["POST"])
@login_required
def join_group(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    existing = StudyGroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if existing:
        return jsonify({"error": "Already a member."}), 400
    db.session.add(StudyGroupMember(group_id=group_id, user_id=current_user.id))
    from services.analytics import track
    track("group_join", current_user.id, "group", group_id)
    db.session.commit()
    return jsonify({"ok": True, "count": group.member_count()})


@study_groups_bp.route("/<int:group_id>/leave", methods=["POST"])
@login_required
def leave_group(group_id):
    member = StudyGroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if member:
        db.session.delete(member)
        db.session.commit()
    return jsonify({"ok": True})


# ── CHAT ROOM ────────────────────────────────────────────────────────────────
@study_groups_bp.route("/<int:group_id>")
@login_required
def room(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    is_member = group.is_member(current_user.id)
    # Load last 60 messages
    messages = (StudyGroupMessage.query
                .filter_by(group_id=group_id)
                .order_by(StudyGroupMessage.created_at.desc())
                .limit(60).all())
    messages = list(reversed(messages))
    ice = _ice_servers()
    note = StudyGroupNote.query.filter_by(group_id=group_id).first()
    from services.reactions import summarize, ALLOWED
    reactions_map = summarize("group", [m.id for m in messages])
    return render_template(
        "study_groups/room.html",
        group=group, messages=messages,
        is_member=is_member, user=current_user,
        ice_servers=json.dumps(ice),
        voice_has_turn=_servers_include_turn(ice),
        note_content=note.content if note else "",
        reactions_map=reactions_map,
        react_emojis=ALLOWED,
    )


IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


def _attachment_json(sf, group_id):
    """Serialize a SharedFile for inline rendering in the chat stream."""
    if not sf:
        return None
    ext = sf.filename.rsplit(".", 1)[-1].lower() if "." in sf.filename else ""
    is_image = (sf.mime_type or "").startswith("image/") or ext in IMAGE_EXT
    return {
        "id":        sf.id,
        "filename":  sf.filename,
        "file_size": sf.file_size,
        "is_image":  is_image,
        "url":       url_for("study_groups.download_file", group_id=group_id, file_id=sf.id),
    }


def _store_attachment(group_id, f):
    """Persist an uploaded file as a SharedFile. Returns (SharedFile, None) or
    (None, (error_message, status_code))."""
    if not f or not f.filename:
        return None, ("No file selected.", 400)
    if not _allowed(f.filename):
        return None, ("File type not allowed.", 400)
    data = f.read()
    if len(data) > MAX_FILE_BYTES:
        return None, ("File too large (max 25 MB).", 400)
    ext = f.filename.rsplit(".", 1)[1].lower()
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    storage.save(data, stored_name, category="study_groups")
    sf = SharedFile(
        group_id=group_id,
        uploader_id=current_user.id,
        filename=secure_filename(f.filename),
        stored_name=stored_name,
        file_size=len(data),
        mime_type=f.mimetype or "application/octet-stream",
    )
    db.session.add(sf)
    db.session.flush()  # assign sf.id before we reference it on the message
    return sf, None


# ── SEND MESSAGE (optionally with a file dropped into chat) ──────────────────
def _group_reply_json(reply_msg):
    """Compact quote payload for the group message being replied to (or None)."""
    if reply_msg is None:
        return None
    author = reply_msg.author.get_full_name() if reply_msg.author else "Unknown"
    if reply_msg.body:
        text = reply_msg.body
    elif reply_msg.attachment is not None:
        text = "📎 " + reply_msg.attachment.filename
    else:
        text = "Message"
    return {"id": reply_msg.id, "author": author, "snippet": text[:90]}


@study_groups_bp.route("/<int:group_id>/send", methods=["POST"])
@login_required
def send_message(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    if not group.is_member(current_user.id):
        return jsonify({"error": "Join the group first."}), 403

    f = request.files.get("file")
    if f is not None and f.filename:
        body = (request.form.get("body") or "").strip()
        reply_to_id = request.form.get("reply_to_id", type=int)
    else:
        f = None
        data = request.get_json(silent=True) or {}
        body = (data.get("body") or "").strip()
        try:
            reply_to_id = int(data.get("reply_to_id")) if data.get("reply_to_id") else None
        except (TypeError, ValueError):
            reply_to_id = None

    if len(body) > 2000:
        return jsonify({"error": "Too long (max 2000 chars)."}), 400

    # Only allow quoting a message from this same group.
    if reply_to_id is not None:
        quoted = StudyGroupMessage.query.filter_by(id=reply_to_id, group_id=group_id).first()
        if quoted is None:
            reply_to_id = None

    attachment = None
    if f is not None:
        attachment, err = _store_attachment(group_id, f)
        if err:
            return jsonify({"error": err[0]}), err[1]

    if not body and attachment is None:
        return jsonify({"error": "Message cannot be empty."}), 400

    msg = StudyGroupMessage(
        group_id=group_id, author_id=current_user.id, body=body,
        attachment_id=attachment.id if attachment else None,
        reply_to_id=reply_to_id,
    )
    db.session.add(msg)
    db.session.commit()

    u = current_user
    payload = {
        "id":              msg.id,
        "body":            body,
        "author_name":     f"{u.first_name} {u.last_name}",
        "author_initials": u.first_name[0] + u.last_name[0],
        "author_avatar":   u.avatar_url or "",
        "author_id":       u.id,
        "time":            msg.created_at.strftime("%H:%M"),
        "attachment":      _attachment_json(attachment, group_id),
        "reply":           _group_reply_json(msg.reply_to),
    }

    # Push to everyone in the group's collab room in real time (the same room
    # members already join for shared notes). The sender's own browser also
    # receives this echo, but appendMessage() on the client is idempotent by
    # message id, so its optimistic local render is never duplicated.
    from extensions import socketio
    socketio.emit("sg_message", payload, to=f"collab_{group_id}")

    return jsonify(payload)


# ── REACT TO A GROUP MESSAGE (emoji) ──────────────────────────────────────────
@study_groups_bp.route("/<int:group_id>/react", methods=["POST"])
@login_required
def react_message(group_id):
    from services.reactions import is_allowed, toggle
    group = StudyGroup.query.get_or_404(group_id)
    if not group.is_member(current_user.id):
        return jsonify({"error": "Join the group first."}), 403
    data = request.get_json(silent=True) or {}
    try:
        mid = int(data.get("message_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Bad message id."}), 400
    emoji = (data.get("emoji") or "").strip()
    if not is_allowed(emoji):
        return jsonify({"error": "Unsupported emoji."}), 400
    msg = StudyGroupMessage.query.filter_by(id=mid, group_id=group_id).first()
    if msg is None:
        return jsonify({"error": "Message not found."}), 404
    pills = toggle("group", mid, current_user.id, emoji)
    from extensions import socketio
    socketio.emit("sg_reaction", {"message_id": mid, "reactions": pills}, to=f"collab_{group_id}")
    return jsonify({"message_id": mid, "reactions": pills})


# ── POLL NEW MESSAGES ────────────────────────────────────────────────────────
@study_groups_bp.route("/<int:group_id>/messages")
@limiter.exempt  # realtime fallback + reconnect catch-up — must not eat the rate budget
@login_required
def poll_messages(group_id):
    """Return messages with id > after_id.

    Live delivery is over SocketIO ('sg_message'); this endpoint is now only a
    fallback the client calls on (re)connect and while the socket is down."""
    group = StudyGroup.query.get_or_404(group_id)
    if not group.is_member(current_user.id):
        return jsonify({"error": "Join the group first."}), 403
    after_id = request.args.get("after", 0, type=int)
    msgs = (StudyGroupMessage.query
            .filter(StudyGroupMessage.group_id == group_id,
                    StudyGroupMessage.id > after_id)
            .order_by(StudyGroupMessage.created_at)
            .limit(50).all())
    return jsonify([{
        "id":              m.id,
        "body":            m.body,
        "author_name":     f"{m.author.first_name} {m.author.last_name}",
        "author_initials": m.author.first_name[0] + m.author.last_name[0],
        "author_avatar":   m.author.avatar_url or "",
        "author_id":       m.author.id,
        "time":            m.created_at.strftime("%H:%M"),
        "is_mine":         m.author_id == current_user.id,
        "attachment":      _attachment_json(m.attachment, group_id) if m.attachment_id else None,
        "reply":           _group_reply_json(m.reply_to),
    } for m in msgs])


# ── DELETE A MESSAGE ─────────────────────────────────────────────────────────
@study_groups_bp.route("/<int:group_id>/messages/<int:message_id>/delete", methods=["POST"])
@login_required
def delete_message(group_id, message_id):
    """Delete a chat message. Allowed for its author, the group creator, or an
    admin. Broadcasts 'sg_delete' so it disappears for everyone in real time."""
    group = StudyGroup.query.get_or_404(group_id)
    msg = StudyGroupMessage.query.filter_by(id=message_id, group_id=group_id).first_or_404()

    is_author = msg.author_id == current_user.id
    is_manager = group.creator_id == current_user.id or current_user.role == "admin"
    if not (is_author or is_manager):
        return jsonify({"error": "You can only delete your own messages."}), 403

    db.session.delete(msg)
    db.session.commit()

    from extensions import socketio
    socketio.emit("sg_delete", {"id": message_id}, to=f"collab_{group_id}")
    return jsonify({"ok": True})


# ── AI MEETING NOTES (transcribe a recording → summary → shared notes) ────────
@study_groups_bp.route("/<int:group_id>/transcribe", methods=["POST"])
@login_required
@limiter.limit("4 per minute; 30 per day")
def transcribe_meeting(group_id):
    """Transcribe an uploaded recording, summarize it, and append the summary to
    the group's shared notes. Members only; audio processed in-memory (never
    stored)."""
    group = StudyGroup.query.get_or_404(group_id)
    if not group.is_member(current_user.id):
        return jsonify({"error": "Only group members can add meeting notes."}), 403

    f = request.files.get("audio")
    if not f or not f.filename:
        return jsonify({"error": "No audio uploaded."}), 400
    ctype = (f.mimetype or "").lower()
    if not (ctype.startswith("audio/") or ctype.startswith("video/webm")):
        return jsonify({"error": "Unsupported audio format."}), 400
    audio_bytes = f.read()

    from services.meeting_notes import transcribe_and_summarize, MeetingNotesError, MAX_AUDIO_BYTES
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return jsonify({"error": "Recording too large (max 25 MB)."}), 400

    from datetime import datetime, timezone
    try:
        summary, _transcript = transcribe_and_summarize(audio_bytes, f.filename)
    except MeetingNotesError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        from flask import current_app
        current_app.logger.exception("meeting-notes transcription failed")
        return jsonify({"error": "Something went wrong. Please try again."}), 500

    stamp = datetime.now(timezone.utc).strftime("%b %d, %H:%M")
    block = (f"\n\n──────────\nAI meeting notes · {stamp} "
             f"(by {current_user.get_full_name()})\n{summary}\n")

    note = StudyGroupNote.query.filter_by(group_id=group_id).first()
    if not note:
        note = StudyGroupNote(group_id=group_id, content=block.strip(),
                              updated_by=current_user.id)
        db.session.add(note)
    else:
        note.content = (note.content or "") + block
        note.updated_by = current_user.id
    db.session.commit()

    # Broadcast the updated note so every member's live notepad refreshes.
    try:
        from extensions import socketio
        socketio.emit("note_update",
                      {"content": note.content, "by": current_user.get_full_name()},
                      to=f"collab_{group_id}")
    except Exception:
        pass

    from services import analytics
    analytics.track("meeting_notes_created", current_user.id, "group", group_id, commit=True)
    return jsonify({"summary": summary, "note": note.content})


# ── DELETE GROUP (creator/admin only) ────────────────────────────────────────
@study_groups_bp.route("/<int:group_id>/delete", methods=["POST"])
@login_required
def delete_group(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    if group.creator_id != current_user.id and current_user.role != "admin":
        return jsonify({"error": "Not authorized."}), 403
    db.session.delete(group)
    db.session.commit()
    return jsonify({"ok": True})


# ── FILE SHARING ──────────────────────────────────────────────────────────────

def _allowed(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


@study_groups_bp.route("/<int:group_id>/upload", methods=["POST"])
@login_required
def upload_file(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    if not group.is_member(current_user.id):
        return jsonify({"error": "Join the group first."}), 403

    if 'file' not in request.files:
        return jsonify({"error": "No file provided."}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({"error": "No file selected."}), 400
    if not _allowed(f.filename):
        return jsonify({"error": "File type not allowed."}), 400

    data = f.read()
    if len(data) > MAX_FILE_BYTES:
        return jsonify({"error": "File too large (max 25 MB)."}), 400

    ext = f.filename.rsplit('.', 1)[1].lower()
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    storage.save(data, stored_name, category="study_groups")

    sf = SharedFile(
        group_id=group_id,
        uploader_id=current_user.id,
        filename=secure_filename(f.filename),
        stored_name=stored_name,
        file_size=len(data),
        mime_type=f.mimetype or 'application/octet-stream',
    )
    db.session.add(sf)
    db.session.commit()

    return jsonify({
        "id":           sf.id,
        "filename":     sf.filename,
        "file_size":    sf.file_size,
        "uploader":     current_user.get_full_name(),
        "created_at":   sf.created_at.strftime("%b %d, %H:%M"),
        "download_url": url_for('study_groups.download_file', group_id=group_id, file_id=sf.id),
    })


@study_groups_bp.route("/<int:group_id>/files")
@login_required
def list_files(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    if not group.is_member(current_user.id):
        return jsonify({"error": "Join the group first."}), 403
    files = (SharedFile.query
             .filter_by(group_id=group_id)
             .order_by(SharedFile.created_at.desc())
             .all())
    return jsonify([{
        "id":           sf.id,
        "filename":     sf.filename,
        "file_size":    sf.file_size,
        "uploader":     sf.uploader.get_full_name(),
        "created_at":   sf.created_at.strftime("%b %d, %H:%M"),
        "download_url": url_for('study_groups.download_file', group_id=group_id, file_id=sf.id),
    } for sf in files])


@study_groups_bp.route("/<int:group_id>/files/<int:file_id>/download")
@login_required
def download_file(group_id, file_id):
    # Only group members may download files
    group = StudyGroup.query.get_or_404(group_id)
    if not group.is_member(current_user.id):
        return jsonify({"error": "Join the group first."}), 403
    sf = SharedFile.query.filter_by(id=file_id, group_id=group_id).first_or_404()

    # S3: redirect to a pre-signed URL
    presigned = storage.download_url(f"study_groups/{sf.stored_name}")
    if presigned:
        from flask import redirect as _redirect
        return _redirect(presigned)

    # Local: serve directly from disk
    local_dir = storage.local_path("study_groups", sf.stored_name)
    return send_from_directory(
        local_dir,
        sf.stored_name,
        as_attachment=True,
        download_name=sf.filename,
    )
