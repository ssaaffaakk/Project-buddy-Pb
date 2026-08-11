"""
Community learning feed — posts, comments, likes, @mentions.
"""

import secrets
from datetime import datetime, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from extensions import db
from models import CommunityComment, CommunityLike, CommunityPost, Notification
from services.file_storage import storage

community_bp = Blueprint("community", __name__, url_prefix="/community")

ALLOWED_IMAGE  = {"jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_VIDEO  = {"mp4", "webm", "mov"}
MAX_BYTES      = 50 * 1024 * 1024   # 50 MB


def _media_type(filename: str):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ALLOWED_IMAGE:
        return "image"
    if ext in ALLOWED_VIDEO:
        return "video"
    return None


def _save_media(file):
    """Save an uploaded media file; return (url, type) or (None, None)."""
    if not file or not file.filename:
        return None, None

    # 1. Extension check
    mtype = _media_type(file.filename)
    if not mtype:
        return "BAD_EXT", None

    # 2. Content-type header check (client-supplied but adds one extra layer)
    ct = (file.content_type or "").lower().split(";")[0].strip()
    allowed_ct = {
        "image/jpeg", "image/png", "image/webp", "image/gif",
        "video/mp4", "video/webm", "video/quicktime",
    }
    if ct and ct not in allowed_ct:
        return "BAD_EXT", None

    # 3. Magic-byte sniff for images (first 12 bytes)
    header = file.read(12)
    file.seek(0)
    _IMG_MAGIC = (
        b'\xff\xd8\xff',        # JPEG
        b'\x89PNG',             # PNG
        b'RIFF',                # WebP (RIFF....WEBP)
        b'GIF87a', b'GIF89a',  # GIF
    )
    _VID_MAGIC = (
        b'\x00\x00\x00',       # MP4/MOV (ftyp box — first 4 bytes vary)
        b'\x1a\x45\xdf\xa3',   # WebM (EBML)
    )
    if mtype == "image" and not any(header.startswith(m) for m in _IMG_MAGIC):
        return "BAD_EXT", None
    # (Video magic-byte check is intentionally lenient — MP4 headers vary widely)

    # 4. Size check
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_BYTES:
        return "TOO_LARGE", None

    # 5. Save with a sanitised, non-guessable filename
    ext        = file.filename.rsplit(".", 1)[-1].lower()
    rand_token = secrets.token_hex(8)
    filename   = secure_filename(
        f"p_{current_user.id}_{int(datetime.now(timezone.utc).timestamp())}_{rand_token}.{ext}"
    )
    data = file.read()
    url  = storage.save(data, filename, category="community")
    return url, mtype


# ── FEED ─────────────────────────────────────────────────────────────────────
@community_bp.route("/")
@login_required
def feed():
    posts = (
        CommunityPost.query
        .order_by(CommunityPost.created_at.desc())
        .all()
    )
    liked_ids = {
        like.post_id
        for like in CommunityLike.query.filter_by(user_id=current_user.id).all()
    }
    from models import SavedPost
    saved_ids = {
        s.post_id
        for s in SavedPost.query.filter_by(user_id=current_user.id).all()
    }
    return render_template(
        "community.html",
        posts=posts,
        liked_ids=liked_ids,
        saved_ids=saved_ids,
        user=current_user,
    )


# ── NEW POST ─────────────────────────────────────────────────────────────────
@community_bp.route("/new", methods=["POST"])
@login_required
def new_post():
    title = request.form.get("title", "").strip()
    body  = request.form.get("body",  "").strip()

    if not body:
        flash("Post content cannot be empty.", "error")
        return redirect(url_for("community.feed"))

    media_url, media_type = _save_media(request.files.get("media"))

    if media_url == "BAD_EXT":
        flash("Invalid file type. Use JPG, PNG, WebP, GIF, MP4, WebM.", "error")
        return redirect(url_for("community.feed"))
    if media_url == "TOO_LARGE":
        flash("File too large — max 50 MB.", "error")
        return redirect(url_for("community.feed"))

    post = CommunityPost(
        author_id  = current_user.id,
        title      = title or None,
        body       = body,
        media_url  = media_url,
        media_type = media_type,
    )
    db.session.add(post)
    db.session.flush()
    from services.analytics import track
    track("post_created", current_user.id, "post", post.id)
    db.session.commit()
    flash("Post shared to the community!", "success")
    return redirect(url_for("community.feed"))


# ── TOGGLE LIKE ───────────────────────────────────────────────────────────────
@community_bp.route("/<int:post_id>/like", methods=["POST"])
@login_required
def toggle_like(post_id):
    CommunityPost.query.get_or_404(post_id)
    existing = CommunityLike.query.filter_by(
        post_id=post_id, user_id=current_user.id
    ).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(CommunityLike(post_id=post_id, user_id=current_user.id))
        liked = True
    db.session.commit()
    count = CommunityLike.query.filter_by(post_id=post_id).count()
    return jsonify({"liked": liked, "count": count})


# ── TOGGLE SAVE (bookmark — same logic as saved projects) ────────────────────
@community_bp.route("/<int:post_id>/save", methods=["POST"])
@login_required
def toggle_save(post_id):
    from models import SavedPost
    CommunityPost.query.get_or_404(post_id)
    existing = SavedPost.query.filter_by(
        post_id=post_id, user_id=current_user.id
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"saved": False})
    db.session.add(SavedPost(post_id=post_id, user_id=current_user.id))
    db.session.commit()
    return jsonify({"saved": True})


# ── ADD COMMENT ───────────────────────────────────────────────────────────────
@community_bp.route("/<int:post_id>/comment", methods=["POST"])
@login_required
def add_comment(post_id):
    CommunityPost.query.get_or_404(post_id)
    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()

    if not body:
        return jsonify({"error": "Comment cannot be empty."}), 400
    if len(body) > 2000:
        return jsonify({"error": "Comment is too long (max 2000 chars)."}), 400

    post = CommunityPost.query.get(post_id)
    c = CommunityComment(post_id=post_id, author_id=current_user.id, body=body)
    db.session.add(c)

    # Notify post author (not if they're commenting on their own post)
    if post and post.author_id != current_user.id:
        snippet = body[:60] + ("…" if len(body) > 60 else "")
        db.session.add(Notification(
            user_id = post.author_id,
            type    = "comment",
            message = f"💬 {current_user.first_name} {current_user.last_name} commented: \"{snippet}\"",
            link    = "/community",
        ))

    db.session.commit()

    u = current_user
    return jsonify({
        "id":              c.id,
        "body":            body,
        "author_name":     f"{u.first_name} {u.last_name}",
        "author_handle":   u.first_name + u.last_name,
        "author_initials": u.first_name[0] + u.last_name[0],
        "author_id":       u.id,
        "author_role":     u.role,
        "author_avatar":   u.avatar_url or "",
        "can_delete":      True,
    })


# ── DELETE POST ───────────────────────────────────────────────────────────────
@community_bp.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    if post.author_id != current_user.id and current_user.role != "admin":
        return jsonify({"error": "Not authorized."}), 403
    db.session.delete(post)
    db.session.commit()
    return jsonify({"ok": True})


# ── DELETE COMMENT ────────────────────────────────────────────────────────────
@community_bp.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    comment = CommunityComment.query.get_or_404(comment_id)
    if comment.author_id != current_user.id and current_user.role != "admin":
        return jsonify({"error": "Not authorized."}), 403
    db.session.delete(comment)
    db.session.commit()
    return jsonify({"ok": True})
