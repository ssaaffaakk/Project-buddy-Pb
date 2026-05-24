"""
Study Groups — mini Discord-style group chat rooms.
"""

import os
import json
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models import StudyGroup, StudyGroupMember, StudyGroupMessage, Notification, SharedFile
from services.file_storage import storage


def _ice_servers():
    """Build ICE server list from environment variables.

    TURN_URLS  — comma-separated turn:/turns: URLs from Xirsys (or any provider)
    TURN_USERNAME / TURN_CREDENTIAL — shared credential for all TURN URLs
    Falls back to Google STUN only when TURN vars are not set (dev mode).
    """
    servers = [
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": "stun:stun1.l.google.com:19302"},
    ]
    urls_raw  = os.environ.get("TURN_URLS", "")
    username  = os.environ.get("TURN_USERNAME", "")
    credential = os.environ.get("TURN_CREDENTIAL", "")
    if urls_raw and username and credential:
        for url in [u.strip() for u in urls_raw.split(",") if u.strip()]:
            servers.append({"urls": url, "username": username, "credential": credential})
    return servers

# ── File upload config ────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
ALLOWED_EXT = {
    'pdf', 'txt', 'md',
    'png', 'jpg', 'jpeg', 'gif', 'webp',
    'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'csv',
    'py', 'js', 'ts', 'html', 'css', 'json', 'yaml', 'yml',
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
    return render_template("study_groups/list.html", groups=all_groups, my_ids=my_ids, user=current_user)


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
    return render_template(
        "study_groups/room.html",
        group=group, messages=messages,
        is_member=is_member, user=current_user,
        ice_servers=json.dumps(_ice_servers()),
    )


# ── SEND MESSAGE ─────────────────────────────────────────────────────────────
@study_groups_bp.route("/<int:group_id>/send", methods=["POST"])
@login_required
def send_message(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    if not group.is_member(current_user.id):
        return jsonify({"error": "Join the group first."}), 403

    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Message cannot be empty."}), 400
    if len(body) > 2000:
        return jsonify({"error": "Too long (max 2000 chars)."}), 400

    msg = StudyGroupMessage(group_id=group_id, author_id=current_user.id, body=body)
    db.session.add(msg)
    db.session.commit()

    u = current_user
    return jsonify({
        "id":              msg.id,
        "body":            body,
        "author_name":     f"{u.first_name} {u.last_name}",
        "author_initials": u.first_name[0] + u.last_name[0],
        "author_avatar":   u.avatar_url or "",
        "author_id":       u.id,
        "time":            msg.created_at.strftime("%H:%M"),
    })


# ── POLL NEW MESSAGES ────────────────────────────────────────────────────────
@study_groups_bp.route("/<int:group_id>/messages")
@login_required
def poll_messages(group_id):
    """Return messages with id > after_id (frontend polls every 3 s)."""
    StudyGroup.query.get_or_404(group_id)
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
    } for m in msgs])


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
    StudyGroup.query.get_or_404(group_id)
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
