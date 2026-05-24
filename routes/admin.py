from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required
from extensions import db, admin_required
from models import Report, User, Project, Application, Badge, AdminMessage

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── REPORTS ───────────────────────────────────────────────────────────────────

@admin_bp.route("/reports", methods=["GET"])
@admin_required
def list_reports():
    try:
        return jsonify({"reports": [
            {"id": r.id, "reporter_id": r.reporter_id, "target_user_id": r.target_user_id,
             "reason": r.reason, "status": r.status}
            for r in Report.query.all()
        ]}), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while fetching reports."}), 500


@admin_bp.route("/reports/<int:report_id>/warn", methods=["POST"])
@admin_required
def warn_user(report_id):
    """Issue a warning to the reported user."""
    try:
        report = Report.query.get_or_404(report_id)
        if report.status != "pending":
            return jsonify({"error": "Report has already been processed."}), 400
        if not report.target_user_id:
            return jsonify({"error": "This report has no target user to warn."}), 400
        from flask_login import current_user
        report.status = "warned"
        db.session.add(AdminMessage(
            user_id=report.target_user_id,
            sender_id=current_user.id,
            content=f"You have received a warning regarding a report filed against you. Reason: {report.reason}",
            is_warning=True,
        ))
        db.session.commit()
        return jsonify({"message": "User has been warned."}), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while processing the report."}), 500


@admin_bp.route("/reports/<int:report_id>/ban", methods=["POST"])
@admin_required
def ban_user(report_id):
    """Ban the reported user."""
    try:
        ban_report = Report.query.get_or_404(report_id)
        if ban_report.status != "pending":
            return jsonify({"error": "Report has already been processed."}), 400
        user_to_ban = User.query.get(ban_report.target_user_id)
        if not user_to_ban:
            return jsonify({"error": "User not found."}), 404
        if user_to_ban.is_banned:
            return jsonify({"error": "User is already banned."}), 400
        user_to_ban.is_banned = True
        ban_report.status = "resolved"
        db.session.commit()
        return jsonify({"message": "User has been banned."}), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while banning the user."}), 500


@admin_bp.route("/reports/<int:report_id>/dismiss", methods=["POST"])
@admin_required
def dismiss_report(report_id):
    """Dismiss a report as invalid."""
    try:
        report = Report.query.get_or_404(report_id)
        if report.status != "pending":
            return jsonify({"error": "Report has already been processed."}), 400
        report.status = "dismissed"
        db.session.commit()
        return jsonify({"message": "Report has been dismissed."}), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while dismissing the report."}), 500


# ── PROJECTS ──────────────────────────────────────────────────────────────────

@admin_bp.route("/projects/<int:project_id>/remove", methods=["DELETE"])
@admin_required
def remove_project(project_id):
    """Remove a fake or misleading project listing."""
    try:
        project_to_remove = Project.query.get_or_404(project_id)
        db.session.delete(project_to_remove)
        db.session.commit()
        return jsonify({"message": "Project has been removed."}), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while removing the project."}), 500


# ── STATS ─────────────────────────────────────────────────────────────────────

@admin_bp.route("/stats", methods=["GET"])
@admin_required
def platform_stats():
    """Return overall platform activity stats."""
    try:
        return jsonify({
            "total_users":        User.query.count(),
            "total_projects":     Project.query.count(),
            "total_applications": Application.query.count(),
            "total_reports":      Report.query.count(),
            "total_badges":       Badge.query.count(),
        }), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while fetching platform stats."}), 500


# ── AI CHAT LOGS ──────────────────────────────────────────────────────────────

@admin_bp.route("/ai-chats")
@admin_required
def ai_chat_logs():
    from models import ChatbotSession
    users_with_chats = (
        db.session.query(User)
        .join(ChatbotSession, ChatbotSession.user_id == User.id)
        .distinct()
        .order_by(User.first_name)
        .all()
    )
    user_sessions = {}
    for u in users_with_chats:
        sessions = (ChatbotSession.query
                    .filter_by(user_id=u.id)
                    .order_by(ChatbotSession.created_at.asc())
                    .all())
        user_sessions[u.id] = {"user": u, "messages": sessions}
    return render_template("admin/ai_chats.html", user_sessions=user_sessions)


# ── MESSAGES ──────────────────────────────────────────────────────────────────

@admin_bp.route("/messages")
@admin_required
def admin_messages():
    msgs = AdminMessage.query.order_by(AdminMessage.created_at.asc()).all()
    user_ids = {m.user_id for m in msgs}
    users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}
    messages_list = [
        {
            "id": m.id,
            "user_id": m.user_id,
            "user": {
                "first_name": users[m.user_id].first_name if m.user_id in users else "Unknown",
                "last_name":  users[m.user_id].last_name  if m.user_id in users else "",
            },
            "sender_id":  m.sender_id,
            "content":    m.content,
            "is_read":    m.is_read,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]
    return render_template("admin/messages.html", messages=messages_list)


@admin_bp.route("/message/<int:user_id>/reply", methods=["POST"])
@admin_required
def admin_reply_message(user_id):
    from flask_login import current_user
    content = request.form.get("content", "").strip()
    if not content:
        return jsonify({"error": "Content required"}), 400
    User.query.get_or_404(user_id)
    db.session.add(AdminMessage(
        user_id=user_id,
        sender_id=current_user.id,
        content=content,
        is_warning=False,
    ))
    db.session.commit()
    return jsonify({"ok": True}), 200
