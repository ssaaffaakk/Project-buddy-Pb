"""
Main page routes — renders all HTML templates.
"""

import os
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db, limiter
from models import (
    User, Project, ProjectMember, Application, Feedback, Endorsement,
    UserBadge, Report, Chat, AdminMessage, UserInterest, UserSkill, UserCourse,
    ProjectMessage, ProjectVote, CommunityPost, CommunityComment, CommunityLike,
    Notification, ProfileComment, ProfileCommentLike, PushSubscription
)
from services.recommendation_service import get_recommendations_with_variant
from services.badge_service import check_and_award_badges
from services.file_storage import storage
from services import analytics

ALLOWED_AVATAR_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 MB


def _allowed_avatar(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS


def _save_user_avatar(user, avatar_file):
    """Persist avatar file and set user.avatar_url. Raises ValueError on validation failure."""
    if not avatar_file or not avatar_file.filename:
        return None

    if not _allowed_avatar(avatar_file.filename):
        raise ValueError("Invalid file type. Please upload a JPG, PNG, or WebP image.")

    avatar_file.seek(0, 2)
    file_size = avatar_file.tell()
    avatar_file.seek(0)

    if file_size > MAX_AVATAR_BYTES:
        raise ValueError("Image must be under 2 MB.")

    ext = avatar_file.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"user_{user.id}.{ext}")
    data = avatar_file.read()
    url = storage.save(data, filename, category="avatars")
    cache_bust = int(datetime.now(timezone.utc).timestamp())
    user.avatar_url = f"{url}?v={cache_bust}"
    return user.avatar_url


# ── PROFILE BANNERS ───────────────────────────────────────────────────────────
ALLOWED_BANNER_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_BANNER_BYTES = 4 * 1024 * 1024  # 4 MB

# Preset cover gradients (banner_url is stored as "preset:<key>")
BANNER_PRESETS = [
    {"key": "aurora", "css": "linear-gradient(120deg,#7C9BFF 0%,#A78BFF 52%,#FF6B6B 100%)"},
    {"key": "dusk",   "css": "linear-gradient(120deg,#141d3a 0%,#3a2b56 100%)"},
    {"key": "mint",   "css": "linear-gradient(120deg,#3AD17A 0%,#7C9BFF 100%)"},
    {"key": "ember",  "css": "linear-gradient(120deg,#FF6B6B 0%,#A78BFF 100%)"},
    {"key": "steel",  "css": "linear-gradient(120deg,#0A1128 0%,#2b3a66 100%)"},
    {"key": "sky",    "css": "linear-gradient(120deg,#B7CCFF 0%,#7C9BFF 60%,#4A5BA8 100%)"},
]
BANNER_CSS = {p["key"]: p["css"] for p in BANNER_PRESETS}
# Default cover for users who haven't picked a banner. The old default
# (#141d3a → #0a1024) was nearly identical to the page background (#060B1A),
# so a bannerless profile looked like an empty/broken box. This on-brand
# navy → steel → dusk gradient is clearly visible while staying subtle.
DEFAULT_BANNER_CSS = "linear-gradient(120deg,#141d3a 0%,#243b6b 52%,#3a2b56 100%)"


def banner_style(banner_url):
    """Inline CSS 'background' declaration for a user's profile banner."""
    if banner_url and banner_url.startswith("preset:"):
        return "background:" + BANNER_CSS.get(banner_url.split(":", 1)[1], DEFAULT_BANNER_CSS) + ";"
    if banner_url:
        return ("background-image:url('" + banner_url + "');"
                "background-size:cover;background-position:center;")
    return "background:" + DEFAULT_BANNER_CSS + ";"


def _save_user_banner(user, banner_file):
    """Persist an uploaded banner image and set user.banner_url. Raises ValueError."""
    if not banner_file or not banner_file.filename:
        return None
    if ("." not in banner_file.filename
            or banner_file.filename.rsplit(".", 1)[1].lower() not in ALLOWED_BANNER_EXTENSIONS):
        raise ValueError("Invalid file type. Please upload a JPG, PNG, or WebP image.")
    banner_file.seek(0, 2)
    size = banner_file.tell()
    banner_file.seek(0)
    if size > MAX_BANNER_BYTES:
        raise ValueError("Banner must be under 4 MB.")
    ext = banner_file.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"banner_{user.id}.{ext}")
    data = banner_file.read()
    url = storage.save(data, filename, category="banners")
    cache_bust = int(datetime.now(timezone.utc).timestamp())
    user.banner_url = f"{url}?v={cache_bust}"
    return user.banner_url


def create_notification(user_id, message, link=None, type=None):
    """Create a notification for a user. Call db.session.commit() after."""
    if not user_id or not message:
        return
    n = Notification(user_id=user_id, message=message, link=link, type=type)
    db.session.add(n)
    _dispatch_push(user_id, message, link)


def _dispatch_push(user_id, message, link):
    """Fire a Web Push for this notification in the background — via the
    Celery queue when a broker is configured (with retries), or an OS thread
    otherwise. Fully best-effort: any failure (incl. push disabled) is
    swallowed."""
    try:
        from services.tasks import dispatch_push
        dispatch_push(user_id, "ProjectBuddy", message, url=link or "/dashboard")
    except Exception:
        pass


main_bp = Blueprint("main", __name__)


@main_bp.app_context_processor
def _inject_profile_helpers():
    """Make banner_style(), the preset list, and the interest taxonomy
    available to every template (registration + edit-profile share them)."""
    from services.interests import INTEREST_CATEGORIES
    return {
        "banner_style": banner_style,
        "BANNER_PRESETS": BANNER_PRESETS,
        "INTEREST_CATEGORIES": INTEREST_CATEGORIES,
    }


def _wall_comment_json(c):
    return {
        "id":              c.id,
        "body":            c.body,
        "author_id":       c.author_id,
        "author_name":     c.author.get_full_name(),
        "author_avatar":   c.author.avatar_url or "",
        "author_initials": (c.author.first_name[0] + c.author.last_name[0]).upper(),
        "time":            c.created_at.strftime("%b %d, %H:%M"),
        "likes":           c.like_count(),
        "liked":           c.liked_by(current_user.id),
        "can_delete":      c.author_id == current_user.id or c.profile_id == current_user.id or current_user.role == "admin",
    }


# ── HEALTHCHECK ───────────────────────────────────────────────────────────────
@main_bp.route("/health")
def health():
    """Deployment platform healthcheck — returns 200 OK when the app is up."""
    return jsonify({"status": "ok"}), 200


# ── HOME ──────────────────────────────────────────────────────────────────────
@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("main.admin_dashboard"))
        return redirect(url_for("main.dashboard"))
    total_users = User.query.count()
    active_projects = Project.query.filter_by(status="open").count()
    return render_template("index.html", total_users=total_users, active_projects=active_projects)


# ── ROBOTS.TXT ────────────────────────────────────────────────────────────────
@main_bp.route("/robots.txt")
def robots():
    from flask import Response
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /auth/login\n"
        "Allow: /auth/register\n"
        "Allow: /auth/forgot-password\n"
        "Allow: /privacy\n"
        "Allow: /static/\n"
        "\n"
        "Disallow: /dashboard\n"
        "Disallow: /admin\n"
        "Disallow: /profile\n"
        "Disallow: /edit-profile\n"
        "Disallow: /projects-page\n"
        "Disallow: /my-projects\n"
        "Disallow: /post-project-page\n"
        "Disallow: /project/\n"
        "Disallow: /community\n"
        "Disallow: /study-groups\n"
        "Disallow: /chatbot\n"
        "Disallow: /chat/\n"
        "Disallow: /report-issue\n"
        "Disallow: /auth/reset-password\n"
        "Disallow: /auth/logout\n"
        "\n"
        "Sitemap: https://project-buddy-pb.onrender.com/sitemap.xml\n"
    )
    return Response(content, mimetype="text/plain")


# ── PWA: service worker + manifest ────────────────────────────────────────────
@main_bp.route("/sw.js")
def service_worker():
    """Serve the service worker from the site root so its scope covers the whole
    app (a worker served from /static/ could only control /static/ URLs)."""
    from flask import send_from_directory, current_app
    resp = send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "sw.js",
        mimetype="application/javascript",
    )
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@main_bp.route("/manifest.webmanifest")
def manifest():
    from flask import send_from_directory, current_app
    return send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "manifest.webmanifest",
        mimetype="application/manifest+json",
    )


# ── PUSH NOTIFICATIONS ─────────────────────────────────────────────────────────
@main_bp.route("/push/public-key")
@login_required
def push_public_key():
    """Expose the VAPID public key so the browser can subscribe. `enabled` tells
    the frontend whether push is configured at all."""
    key = current_app.config.get("VAPID_PUBLIC_KEY", "")
    return jsonify({"publicKey": key, "enabled": bool(key)})


@main_bp.route("/push/subscribe", methods=["POST"])
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = (data.get("endpoint") or "").strip()
    keys = data.get("keys") or {}
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "Invalid subscription."}), 400

    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        # Re-subscribe / device switched user → keep it pointed at current user.
        existing.user_id = current_user.id
        existing.p256dh = p256dh
        existing.auth = auth
    else:
        db.session.add(PushSubscription(
            user_id=current_user.id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=(request.headers.get("User-Agent") or "")[:300],
        ))
    db.session.commit()
    return jsonify({"ok": True})


@main_bp.route("/push/unsubscribe", methods=["POST"])
@login_required
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = (data.get("endpoint") or "").strip()
    if endpoint:
        PushSubscription.query.filter_by(
            endpoint=endpoint, user_id=current_user.id
        ).delete()
        db.session.commit()
    return jsonify({"ok": True})


# ── SECURITY.TXT ──────────────────────────────────────────────────────────────
@main_bp.route("/.well-known/security.txt")
def security_txt():
    from flask import Response
    content = (
        "Contact: mailto:surmeliisafak@gmail.com\n"
        "Expires: 2027-01-01T00:00:00.000Z\n"
        "Preferred-Languages: en, tr\n"
        "Scope: https://project-buddy-pb.onrender.com/\n"
    )
    return Response(content, mimetype="text/plain")


# ── PRIVACY POLICY ───────────────────────────────────────────────────────────
@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ── SITEMAP ───────────────────────────────────────────────────────────────────
@main_bp.route("/sitemap.xml")
def sitemap():
    from flask import Response
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://project-buddy-pb.onrender.com/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://project-buddy-pb.onrender.com/auth/login</loc>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>https://project-buddy-pb.onrender.com/auth/forgot-password</loc>
    <changefreq>monthly</changefreq>
    <priority>0.3</priority>
  </url>
  <url>
    <loc>https://project-buddy-pb.onrender.com/privacy</loc>
    <changefreq>yearly</changefreq>
    <priority>0.2</priority>
  </url>
</urlset>"""
    return Response(xml, mimetype="application/xml")


# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@main_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        return redirect(url_for("main.admin_dashboard"))

    user = current_user

    # Active project memberships (open/closed)
    active_memberships = (
        ProjectMember.query
        .join(Project)
        .filter(
            ProjectMember.user_id == user.id,
            ProjectMember.removed == False,
            Project.status.in_(["open", "closed"])
        ).all()
    )
    active_projects = [m.project for m in active_memberships]

    # Completed projects count
    completed_count = (
        ProjectMember.query
        .join(Project)
        .filter(
            ProjectMember.user_id == user.id,
            Project.status == "completed"
        ).count()
    )

    # Pending applications for projects the user OWNS
    pending_apps = []
    for project in user.projects_owned:
        if project.status in ("open", "closed"):
            apps = Application.query.filter_by(
                project_id=project.id, status="pending"
            ).all()
            pending_apps.extend(apps)

    # Average rating
    feedbacks = Feedback.query.filter_by(receiver_id=user.id).all()
    avg_rating = None
    if feedbacks:
        avg_rating = round(sum(f.rating for f in feedbacks) / len(feedbacks), 1)

    # Endorsement count
    endorsement_count = Endorsement.query.filter_by(receiver_id=user.id).count()

    # Recommendations (A/B: 'ml' vs 'rules' arm — see recommendation_service)
    try:
        recommendations, rec_variant = get_recommendations_with_variant(user.id)
        recommendations = recommendations[:6]
    except Exception:
        recommendations, rec_variant = [], None

    # Log one impression per shown card so CTR per arm is measurable.
    for rec_project, rec_score in recommendations:
        analytics.track("rec_impression", user.id, "project", rec_project.id,
                        variant=rec_variant, value=rec_score)
    analytics.commit_quietly()

    # Badges
    user_badges = (
        UserBadge.query
        .filter_by(user_id=user.id)
        .all()
    )
    badges = [ub.badge for ub in user_badges if ub.badge]

    # Open support chat
    open_support_chat = Chat.query.filter_by(
        user_id=user.id, status="open"
    ).first()

    # Unread warnings (admin messages that are warnings)
    warnings = AdminMessage.query.filter_by(
        user_id=user.id, is_warning=True, is_read=False
    ).all()

    return render_template(
        "user/dashboard.html",
        user=user,
        active_projects=active_projects,
        completed_count=completed_count,
        pending_apps=pending_apps,
        avg_rating=avg_rating,
        endorsement_count=endorsement_count,
        recommendations=recommendations,
        rec_variant=rec_variant,
        badges=badges,
        open_support_chat=open_support_chat,
        warnings=warnings,
    )


# ── DISMISS WARNINGS ──────────────────────────────────────────────────────────
@main_bp.route("/warnings/dismiss", methods=["POST"])
@login_required
def dismiss_warnings():
    AdminMessage.query.filter_by(
        user_id=current_user.id, is_warning=True, is_read=False
    ).update({"is_read": True})
    db.session.commit()
    flash("Warning dismissed.", "success")
    return redirect(url_for("main.dashboard"))


# ── PROJECTS PAGE ─────────────────────────────────────────────────────────────
@main_bp.route("/projects-page")
@login_required
def projects_page():
    search_query = request.args.get("q", "").strip()
    if search_query:
        # Semantic ranking (falls back to keyword/substring inside the service)
        from services.project_search import semantic_search
        projects = semantic_search(search_query, limit=60)
    else:
        projects = (Project.query.filter_by(status="open")
                    .order_by(Project.created_at.desc()).all())

    user_votes = {}
    if current_user.is_authenticated:
        votes = ProjectVote.query.filter_by(user_id=current_user.id).all()
        user_votes = {v.project_id: v.direction for v in votes}

    return render_template("projects/list.html", projects=projects, search_query=search_query, user_votes=user_votes)


# ── POST PROJECT PAGE ─────────────────────────────────────────────────────────
@main_bp.route("/post-project-page")
@login_required
def post_project_page():
    return render_template("projects/post.html")


@main_bp.route("/projects/check-similar", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def check_similar_projects():
    """Return open projects similar to a draft title/description, so the post
    form can warn about duplicates. Read-only; input length-capped."""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()[:200]
    description = (data.get("description") or "").strip()[:2000]
    if len(title) < 4:
        return jsonify({"similar": []})
    from services.project_search import similar_projects
    try:
        similar = similar_projects(title, description, limit=3)
    except Exception:
        current_app.logger.exception("similar-project check failed")
        similar = []
    return jsonify({"similar": similar})


# ── MY PROJECTS ───────────────────────────────────────────────────────────────
@main_bp.route("/my-projects")
@login_required
def my_projects():
    # Projects owned by user, with pending applications
    owned = Project.query.filter_by(owner_id=current_user.id).order_by(
        Project.created_at.desc()
    ).all()
    from services.applicant_fit import score_applicant
    owned_projects_with_apps = []
    for project in owned:
        apps = Application.query.filter_by(
            project_id=project.id, status="pending"
        ).all()
        # Attach an explainable fit score to each applicant, best-first.
        scored = []
        for app in apps:
            try:
                fit = score_applicant(app.applicant, project)
            except Exception:
                fit = {"percent": None, "reasons": [], "shared_skills": []}
            scored.append({"app": app, "fit": fit})
        scored.sort(key=lambda s: (s["fit"]["percent"] or 0), reverse=True)
        owned_projects_with_apps.append({"project": project, "pending_apps": scored})

    # Projects user is a member of (not owner)
    memberships = (
        ProjectMember.query
        .filter(
            ProjectMember.user_id == current_user.id,
            ProjectMember.removed == False
        ).all()
    )
    joined_projects = [
        m.project for m in memberships
        if m.project and m.project.owner_id != current_user.id
    ]

    return render_template(
        "projects/my_projects.html",
        owned_projects_with_apps=owned_projects_with_apps,
        joined_projects=joined_projects,
    )


# ── ACCEPT / REJECT APPLICATIONS (from my-projects buttons) ──────────────────
@main_bp.route("/applications/<int:app_id>/accept", methods=["POST"])
@login_required
def accept_application_page(app_id):
    app = Application.query.get_or_404(app_id)
    project = Project.query.get_or_404(app.project_id)

    if project.owner_id != current_user.id:
        flash("Only the project owner can accept applications.", "error")
        return redirect(url_for("main.my_projects"))

    if project.is_full():
        flash("Project team is already full.", "error")
        return redirect(url_for("main.my_projects"))

    applicant_id = app.applicant_id
    member = ProjectMember(project_id=project.id, user_id=applicant_id)
    db.session.add(member)
    db.session.delete(app)
    db.session.flush()

    if project.is_full() and project.status == "open":
        project.status = "closed"

    create_notification(
        user_id = applicant_id,
        type    = "accepted",
        message = f"🎉 Your application to \"{project.title}\" was accepted!",
        link    = f"/project/{project.id}",
    )
    db.session.commit()
    flash("Application accepted!", "success")
    return redirect(url_for("main.my_projects"))


@main_bp.route("/applications/<int:app_id>/reject", methods=["POST"])
@login_required
def reject_application_page(app_id):
    app = Application.query.get_or_404(app_id)
    project = Project.query.get_or_404(app.project_id)

    if project.owner_id != current_user.id:
        flash("Only the project owner can reject applications.", "error")
        return redirect(url_for("main.my_projects"))

    applicant_id = app.applicant_id
    create_notification(
        user_id = applicant_id,
        type    = "rejected",
        message = f"Your application to \"{project.title}\" was not accepted this time.",
        link    = "/projects-page",
    )
    db.session.delete(app)
    db.session.commit()
    flash("Application rejected.", "success")
    return redirect(url_for("main.my_projects"))


# ── APPLY TO PROJECT ──────────────────────────────────────────────────────────
@main_bp.route("/projects/<int:project_id>/apply", methods=["GET", "POST"])
@login_required
def apply_to_project(project_id):
    project = Project.query.get_or_404(project_id)

    if project.owner_id == current_user.id:
        flash("You cannot apply to your own project.", "error")
        return redirect(url_for("main.projects_page"))

    if project.status in ("closed", "completed"):
        flash("This project is not accepting applications.", "error")
        return redirect(url_for("main.projects_page"))

    existing = Application.query.filter_by(
        project_id=project_id, applicant_id=current_user.id
    ).first()
    if existing:
        flash("You have already applied to this project.", "error")
        return redirect(url_for("main.projects_page"))

    active_count = (
        ProjectMember.query.join(Project)
        .filter(
            ProjectMember.user_id == current_user.id,
            ProjectMember.removed == False,
            Project.status.in_(["open", "closed"])
        ).count()
    )
    if active_count >= 3:
        flash("You are already in 3 active projects (maximum).", "error")
        return redirect(url_for("main.projects_page"))

    if request.method == "POST":
        application = Application(
            project_id=project_id,
            applicant_id=current_user.id
        )
        db.session.add(application)
        create_notification(
            user_id = project.owner_id,
            type    = "apply",
            message = f"📬 {current_user.first_name} {current_user.last_name} applied to your project \"{project.title}\"",
            link    = "/my-projects",
        )
        analytics.track("application_sent", current_user.id, "project", project_id)
        db.session.commit()
        flash("Application submitted successfully!", "success")
        return redirect(url_for("main.dashboard"))

    # Attribution: the dashboard rec cards link here with ?src=rec&v=<arm>
    if request.args.get("src") == "rec":
        variant = request.args.get("v")
        analytics.track("rec_click", current_user.id, "project", project_id,
                        variant=variant if variant in ("ml", "rules") else None,
                        commit=True)
    return render_template("projects/apply_confirm.html", project=project)


# ── WITHDRAW A PENDING APPLICATION ────────────────────────────────────────────
@main_bp.route("/projects/<int:project_id>/withdraw", methods=["POST"])
@login_required
def withdraw_application(project_id):
    """Let an applicant retract a still-pending application. This frees up their
    "max 3 active projects" slot and removes the applicant from the owner's
    review list. Accepted applications aren't touched here — that's 'leave'."""
    application = Application.query.filter_by(
        project_id=project_id, applicant_id=current_user.id
    ).first()
    if application is None:
        flash("You have no application to withdraw for this project.", "error")
    elif application.status != "pending":
        flash("This application has already been reviewed and can't be withdrawn.", "error")
    else:
        db.session.delete(application)
        analytics.track("application_withdrawn", current_user.id, "project", project_id)
        db.session.commit()
        flash("Application withdrawn.", "success")
    # Prefer returning to wherever the user clicked from.
    return redirect(request.referrer or url_for("main.project_detail", project_id=project_id))


# ── PROJECT DETAIL ────────────────────────────────────────────────────────────
@main_bp.route("/project/<int:project_id>")
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    proj_messages = ProjectMessage.query.filter_by(
        project_id=project_id
    ).order_by(ProjectMessage.created_at.asc()).all()

    # Active members excluding the owner
    team_members = [
        m for m in project.active_members()
        if m.user_id != project.owner_id
    ]

    is_owner = False
    is_member = False
    has_applied = False
    has_pending = False
    is_saved = False
    if current_user.is_authenticated:
        from models import SavedProject
        is_owner = project.owner_id == current_user.id
        is_member = any(
            m.user_id == current_user.id and not m.removed
            for m in project.members
        )
        my_application = Application.query.filter_by(
            project_id=project_id, applicant_id=current_user.id
        ).first()
        has_applied = my_application is not None
        has_pending = bool(my_application and my_application.status == "pending")
        is_saved = SavedProject.query.filter_by(
            user_id=current_user.id, project_id=project_id
        ).first() is not None

    vote_score = project.vote_score
    user_vote = None
    existing_vote = ProjectVote.query.filter_by(
        project_id=project_id, user_id=current_user.id
    ).first()
    if existing_vote:
        user_vote = existing_vote.direction

    analytics.track("project_view", current_user.id, "project", project_id, commit=True)

    # Members assignable to board tasks (owner + active members)
    assignable = []
    if project.owner:
        assignable.append({"id": project.owner.id, "name": project.owner.get_full_name()})
    for m in team_members:
        if m.user:
            assignable.append({"id": m.user.id, "name": m.user.get_full_name()})

    # Team meeting-time overlap: how many of the owner+members are free per slot.
    team_ids = [project.owner_id] + [m.user_id for m in team_members]
    avail_grid, avail_people = _team_availability(team_ids)

    return render_template(
        "projects/detail.html",
        project=project,
        messages=proj_messages,
        team_members=team_members,
        assignable_members=assignable,
        is_owner=is_owner,
        is_member=is_member,
        has_applied=has_applied,
        has_pending=has_pending,
        is_saved=is_saved,
        vote_score=vote_score,
        user_vote=user_vote,
        avail_grid=avail_grid,
        avail_people=avail_people,
        weekdays=WEEKDAYS,
        blocks=BLOCKS,
    )

# ── PROJECT VOTE ──────────────────────────────────────────────────────────────
@main_bp.route("/projects/<int:project_id>/vote", methods=["POST"])
@login_required
def vote_project(project_id):
    data      = request.get_json()
    direction = data.get("direction")

    if direction not in ("up", "down"):
        return jsonify({"error": "invalid direction"}), 400

    existing = ProjectVote.query.filter_by(
        project_id=project_id,
        user_id=current_user.id
    ).first()

    if existing:
        if existing.direction == direction:
            # Same vote again → remove (toggle off)
            db.session.delete(existing)
            user_vote = None
        else:
            # Opposite direction → flip
            existing.direction = direction
            user_vote = direction
    else:
        # First time voting
        new_vote = ProjectVote(
            project_id=project_id,
            user_id=current_user.id,
            direction=direction
        )
        db.session.add(new_vote)
        user_vote = direction

    db.session.commit()

    project = Project.query.get_or_404(project_id)
    return jsonify({"score": project.vote_score, "user_vote": user_vote})


# Mark project complete (only owner, only if not already completed)
@main_bp.route("/project/<int:project_id>/complete", methods=["POST"])
@login_required
def complete_project_page(project_id):
    project = Project.query.get_or_404(project_id)
    if project.owner_id != current_user.id:
        flash("Only the project owner can mark it complete.", "error")
        return redirect(url_for("main.project_detail", project_id=project_id))
    if project.status == "completed":
        flash("Project is already completed.", "error")
        return redirect(url_for("main.project_detail", project_id=project_id))
    project.status = "completed"
    project.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    for member in project.members:
        check_and_award_badges(member.user_id)
    flash("Project marked as complete! Badges awarded.", "success")
    return redirect(url_for("main.project_detail", project_id=project_id))

# Send message to project chat (only members)
@main_bp.route("/project/<int:project_id>/message", methods=["POST"])
@login_required
def send_project_message(project_id):
    project = Project.query.get_or_404(project_id)
    is_member = any(
        m.user_id == current_user.id and not m.removed
        for m in project.members
    )
    if not is_member and project.owner_id != current_user.id:
        return jsonify({"error": "Not a project member"}), 403
    data = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Message cannot be empty"}), 400
    msg = ProjectMessage(
        project_id=project_id,
        sender_id=current_user.id,
        content=content
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({"message": "Message sent"}), 201


# ── PROJECT TASK BOARD (kanban) ───────────────────────────────────────────────
_TASK_STATUSES = ("todo", "doing", "done")


def _project_if_member(project_id):
    """Return the project if the current user is its owner or an active member,
    else None. The single authorization gate for every task endpoint."""
    project = Project.query.get(project_id)
    if project is None:
        return None
    if project.owner_id == current_user.id:
        return project
    is_member = any(m.user_id == current_user.id and not m.removed
                    for m in project.members)
    return project if is_member else None


def _task_json(t):
    due = t.due_date.date() if t.due_date else None
    return {
        "id": t.id,
        "title": t.title,
        "status": t.status,
        "assignee_id": t.assignee_id,
        "assignee_name": t.assignee.get_full_name() if t.assignee else None,
        "assignee_initials": ((t.assignee.first_name[:1] + t.assignee.last_name[:1]).upper()
                              if t.assignee else None),
        "due_date": due.isoformat() if due else None,
        # Overdue only matters while the task is still open.
        "overdue": bool(due and t.status != "done" and due < datetime.now(timezone.utc).date()),
        "can_delete": t.created_by == current_user.id or _is_owner_of(t.project_id),
    }


def _parse_due(raw):
    """Parse a 'YYYY-MM-DD' string into a datetime (midnight), or None. Raises
    ValueError on a malformed non-empty value."""
    raw = (raw or "").strip()
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d")


def _is_owner_of(project_id):
    p = Project.query.get(project_id)
    return bool(p and p.owner_id == current_user.id)


@main_bp.route("/project/<int:project_id>/tasks", methods=["GET"])
@login_required
def list_tasks(project_id):
    from models import ProjectTask
    if _project_if_member(project_id) is None:
        return jsonify({"error": "Not a member of this project."}), 403
    tasks = (ProjectTask.query.filter_by(project_id=project_id)
             .order_by(ProjectTask.position, ProjectTask.id).all())
    return jsonify({"tasks": [_task_json(t) for t in tasks]})


@main_bp.route("/project/<int:project_id>/tasks", methods=["POST"])
@login_required
@limiter.limit("60 per minute")
def create_task(project_id):
    from models import ProjectTask
    if _project_if_member(project_id) is None:
        return jsonify({"error": "Not a member of this project."}), 403
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    status = data.get("status") if data.get("status") in _TASK_STATUSES else "todo"
    if not title:
        return jsonify({"error": "Task title required."}), 400
    if len(title) > 200:
        return jsonify({"error": "Title too long (max 200)."}), 400
    try:
        due = _parse_due(data.get("due_date"))
    except ValueError:
        return jsonify({"error": "Invalid due date."}), 400
    task = ProjectTask(project_id=project_id, title=title, status=status,
                       created_by=current_user.id, due_date=due)
    db.session.add(task)
    db.session.commit()
    return jsonify({"task": _task_json(task)}), 201


@main_bp.route("/project/<int:project_id>/tasks/<int:task_id>/due", methods=["POST"])
@login_required
def set_task_due(project_id, task_id):
    """Set or clear a task's due date. Any project member may adjust it."""
    from models import ProjectTask
    if _project_if_member(project_id) is None:
        return jsonify({"error": "Not a member of this project."}), 403
    task = ProjectTask.query.filter_by(id=task_id, project_id=project_id).first()
    if task is None:
        return jsonify({"error": "Task not found."}), 404
    data = request.get_json(silent=True) or {}
    try:
        task.due_date = _parse_due(data.get("due_date"))
    except ValueError:
        return jsonify({"error": "Invalid due date."}), 400
    db.session.commit()
    return jsonify({"task": _task_json(task)})


@main_bp.route("/project/<int:project_id>/tasks/<int:task_id>/move", methods=["POST"])
@login_required
def move_task(project_id, task_id):
    from models import ProjectTask
    if _project_if_member(project_id) is None:
        return jsonify({"error": "Not a member of this project."}), 403
    task = ProjectTask.query.filter_by(id=task_id, project_id=project_id).first()
    if task is None:
        return jsonify({"error": "Task not found."}), 404
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in _TASK_STATUSES:
        return jsonify({"error": "Invalid status."}), 400
    task.status = status
    db.session.commit()
    return jsonify({"task": _task_json(task)})


@main_bp.route("/project/<int:project_id>/tasks/<int:task_id>/assign", methods=["POST"])
@login_required
def assign_task(project_id, task_id):
    from models import ProjectTask
    project = _project_if_member(project_id)
    if project is None:
        return jsonify({"error": "Not a member of this project."}), 403
    task = ProjectTask.query.filter_by(id=task_id, project_id=project_id).first()
    if task is None:
        return jsonify({"error": "Task not found."}), 404
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if user_id in (None, "", "null"):
        task.assignee_id = None
    else:
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid user."}), 400
        # Only the owner or an active member may be assigned.
        valid = uid == project.owner_id or any(
            m.user_id == uid and not m.removed for m in project.members)
        if not valid:
            return jsonify({"error": "Assignee must be a project member."}), 400
        task.assignee_id = uid
    db.session.commit()
    return jsonify({"task": _task_json(task)})


@main_bp.route("/project/<int:project_id>/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(project_id, task_id):
    from models import ProjectTask
    if _project_if_member(project_id) is None:
        return jsonify({"error": "Not a member of this project."}), 403
    task = ProjectTask.query.filter_by(id=task_id, project_id=project_id).first()
    if task is None:
        return jsonify({"error": "Task not found."}), 404
    # Only the task's creator or the project owner may delete it.
    if task.created_by != current_user.id and not _is_owner_of(project_id):
        return jsonify({"error": "Not authorized to delete this task."}), 403
    db.session.delete(task)
    db.session.commit()
    return jsonify({"ok": True})


# ── SAVED PROJECTS (bookmarks) ────────────────────────────────────────────────
@main_bp.route("/projects/<int:project_id>/save", methods=["POST"])
@login_required
def toggle_saved_project(project_id):
    """Toggle a bookmark on a project. Returns the new saved state."""
    from models import SavedProject
    Project.query.get_or_404(project_id)
    existing = SavedProject.query.filter_by(
        user_id=current_user.id, project_id=project_id
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"saved": False})
    db.session.add(SavedProject(user_id=current_user.id, project_id=project_id))
    db.session.commit()
    return jsonify({"saved": True})


@main_bp.route("/saved")
@login_required
def saved_projects():
    """The user's bookmarked projects, newest bookmark first."""
    from models import SavedProject
    rows = (SavedProject.query
            .filter_by(user_id=current_user.id)
            .order_by(SavedProject.created_at.desc())
            .all())
    projects = [r.project for r in rows if r.project is not None]
    return render_template("projects/saved.html", projects=projects, user=current_user)


# ── WEEKLY AVAILABILITY + TEAM MEETING-TIME OVERLAP ───────────────────────────
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
BLOCKS = ["Morning", "Afternoon", "Evening"]  # index 0,1,2


def _my_availability_set(user_id):
    """Set of (weekday, block) cells the user marked free."""
    from models import UserAvailability
    return {(a.weekday, a.block)
            for a in UserAvailability.query.filter_by(user_id=user_id).all()}


@main_bp.route("/availability")
@login_required
def availability():
    """Edit my weekly availability grid (which half-days I'm free to meet)."""
    cells = _my_availability_set(current_user.id)
    grid = [[(d, b) in cells for b in range(len(BLOCKS))] for d in range(len(WEEKDAYS))]
    return render_template(
        "user/availability.html",
        grid=grid, weekdays=WEEKDAYS, blocks=BLOCKS,
        user=current_user, tz=current_user.timezone or "",
    )


@main_bp.route("/availability", methods=["POST"])
@login_required
def save_availability():
    """Replace my availability with the posted cells. Body: {cells: [[d,b],...],
    timezone: "Europe/Sarajevo"}."""
    from models import UserAvailability
    data = request.get_json(silent=True) or {}
    raw = data.get("cells", [])
    if not isinstance(raw, list) or len(raw) > 21:
        return jsonify({"error": "Invalid payload."}), 400

    valid = set()
    for pair in raw:
        try:
            d, b = int(pair[0]), int(pair[1])
        except (TypeError, ValueError, IndexError):
            return jsonify({"error": "Invalid cell."}), 400
        if 0 <= d < len(WEEKDAYS) and 0 <= b < len(BLOCKS):
            valid.add((d, b))

    tz = (data.get("timezone") or "").strip()[:64]
    current_user.timezone = tz or None

    UserAvailability.query.filter_by(user_id=current_user.id).delete()
    for d, b in valid:
        db.session.add(UserAvailability(user_id=current_user.id, weekday=d, block=b))
    db.session.commit()
    return jsonify({"ok": True, "count": len(valid)})


def _team_availability(user_ids):
    """Overlap grid for a set of users: for each (weekday, block) cell, how many
    of them are free. Returns (grid, n_people) where grid[d][b] = count."""
    from models import UserAvailability
    user_ids = list(user_ids)
    grid = [[0] * len(BLOCKS) for _ in range(len(WEEKDAYS))]
    if not user_ids:
        return grid, 0
    rows = UserAvailability.query.filter(UserAvailability.user_id.in_(user_ids)).all()
    for a in rows:
        if 0 <= a.weekday < len(WEEKDAYS) and 0 <= a.block < len(BLOCKS):
            grid[a.weekday][a.block] += 1
    return grid, len(user_ids)


# ── CALENDAR EXPORT (.ics) ────────────────────────────────────────────────────
def _ics_escape(text):
    return (str(text or "")
            .replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def _ics_event(uid, dt, summary, description=""):
    """One all-day VEVENT on the date of `dt`."""
    day = dt.strftime("%Y%m%d")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "\r\n".join([
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{day}",
        f"SUMMARY:{_ics_escape(summary)}",
        f"DESCRIPTION:{_ics_escape(description)}",
        "END:VEVENT",
    ])


def _ics_response(events, filename):
    from flask import Response
    body = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ProjectBuddy//Deadlines//EN",
        "CALSCALE:GREGORIAN",
        *events,
        "END:VCALENDAR",
    ]) + "\r\n"
    return Response(body, mimetype="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@main_bp.route("/project/<int:project_id>/deadline.ics")
@login_required
def project_deadline_ics(project_id):
    """Download a project's deadline as a calendar event."""
    project = Project.query.get_or_404(project_id)
    if not project.deadline:
        flash("This project has no deadline set.", "error")
        return redirect(url_for("main.project_detail", project_id=project_id))
    ev = _ics_event(f"project-{project.id}@projectbuddy", project.deadline,
                    f"Deadline: {project.title}",
                    f"ProjectBuddy project deadline for “{project.title}”.")
    return _ics_response([ev], f"project-{project.id}-deadline.ics")


@main_bp.route("/calendar.ics")
@login_required
def my_calendar_ics():
    """Download every deadline across the projects I own or belong to."""
    owned = Project.query.filter(Project.owner_id == current_user.id,
                                 Project.deadline.isnot(None)).all()
    member_projects = (Project.query
                       .join(ProjectMember, ProjectMember.project_id == Project.id)
                       .filter(ProjectMember.user_id == current_user.id,
                               ProjectMember.removed == False,  # noqa: E712
                               Project.deadline.isnot(None))
                       .all())
    seen, events = set(), []
    for p in [*owned, *member_projects]:
        if p.id in seen:
            continue
        seen.add(p.id)
        events.append(_ics_event(f"project-{p.id}@projectbuddy", p.deadline,
                                 f"Deadline: {p.title}",
                                 f"ProjectBuddy project deadline for “{p.title}”."))
    return _ics_response(events, "projectbuddy-deadlines.ics")


# ── MY PROFILE ────────────────────────────────────────────────────────────────
@main_bp.route("/profile")
@login_required # Redirect to user profile page (which shows more details and allows reviews/endorsements)
def profile():
    user = current_user
    return _render_profile(user)


@main_bp.route("/user/<int:user_id>")
@login_required # View another user's profile (with reviews/endorsements and option to leave review/endorsement if applicable)
def user_profile(user_id):
    profile_user = User.query.get_or_404(user_id)

    # Collect stats
    feedbacks = Feedback.query.filter_by(receiver_id=profile_user.id).all()
    avg_rating = None
    if feedbacks:
        avg_rating = round(sum(f.rating for f in feedbacks) / len(feedbacks), 1)

    projects_count = (
        ProjectMember.query.join(Project)
        .filter(ProjectMember.user_id == profile_user.id, ProjectMember.removed == False)
        .count()
    )

    user_stats = {
        "projects_count": projects_count,
        "avg_rating": avg_rating,
        "reviews_count": len(feedbacks),
    }

    # Can current user leave a review?
    # Must share a completed project and not have already reviewed them
    can_leave_review = False
    if current_user.id != profile_user.id and profile_user.role != "admin":
        shared_completed = (
            db.session.query(ProjectMember)
            .join(Project, Project.id == ProjectMember.project_id)
            .filter(
                ProjectMember.user_id == current_user.id,
                ProjectMember.removed == False,
                Project.status == "completed",
                Project.id.in_(
                    db.session.query(ProjectMember.project_id)
                    .filter(ProjectMember.user_id == profile_user.id, ProjectMember.removed == False)
                )
            ).count()
        )
        already_reviewed = Feedback.query.filter_by(
            giver_id=current_user.id, receiver_id=profile_user.id
        ).first()
        can_leave_review = shared_completed > 0 and not already_reviewed

    # Can current user endorse?
    # Must share any project (active or completed)
    can_endorse = False
    already_endorsed_skills = []
    if current_user.id != profile_user.id and profile_user.role != "admin":
        shared_any = (
            db.session.query(ProjectMember)
            .filter(
                ProjectMember.user_id == current_user.id,
                ProjectMember.removed == False,
                ProjectMember.project_id.in_(
                    db.session.query(ProjectMember.project_id)
                    .filter(ProjectMember.user_id == profile_user.id, ProjectMember.removed == False)
                )
            ).count()
        )
        can_endorse = shared_any > 0
        already_endorsed_skills = [
            e.skill for e in Endorsement.query.filter_by(
                giver_id=current_user.id, receiver_id=profile_user.id
            ).all()
        ]

    wall = (ProfileComment.query
            .filter_by(profile_id=profile_user.id)
            .order_by(ProfileComment.created_at.desc())
            .limit(100).all())
    wall_comments = [_wall_comment_json(c) for c in wall]

    from services.contribution_stats import contribution_stats
    contributions = contribution_stats(profile_user.id)

    return render_template(
        "user/profile_view.html",
        profile_user=profile_user,
        user_stats=user_stats,
        contributions=contributions,
        reviews=feedbacks,
        can_leave_review=can_leave_review,
        can_endorse=can_endorse,
        already_endorsed_skills=already_endorsed_skills,
        wall_comments=wall_comments,
    )


@main_bp.route("/user/<int:user_id>/review", methods=["POST"])
@login_required # Submit review for another user (only if shared completed project and not already reviewed)
def submit_review(user_id):
    profile_user = User.query.get_or_404(user_id)

    if current_user.id == profile_user.id:
        flash("You cannot review yourself.", "error")
        return redirect(url_for("main.user_profile", user_id=user_id))

    rating = request.form.get("rating", "").strip()
    comment = request.form.get("comment", "").strip()

    if not rating or not comment:
        flash("Rating and comment are required.", "error")
        return redirect(url_for("main.user_profile", user_id=user_id))

    if not rating.isdigit() or int(rating) not in range(1, 6):
        flash("Rating must be between 1 and 5.", "error")
        return redirect(url_for("main.user_profile", user_id=user_id))

    if len(comment) < 10:
        flash("Comment must be at least 10 characters.", "error")
        return redirect(url_for("main.user_profile", user_id=user_id))

    already = Feedback.query.filter_by(giver_id=current_user.id, receiver_id=profile_user.id).first()
    if already:
        flash("You have already reviewed this user.", "error")
        return redirect(url_for("main.user_profile", user_id=user_id))

    # Find a shared completed project to attach the feedback to
    shared = (
        db.session.query(ProjectMember)
        .join(Project, Project.id == ProjectMember.project_id)
        .filter(
            ProjectMember.user_id == current_user.id,
            ProjectMember.removed == False,
            Project.status == "completed",
            Project.id.in_(
                db.session.query(ProjectMember.project_id)
                .filter(ProjectMember.user_id == profile_user.id, ProjectMember.removed == False)
            )
        ).first()
    )

    project_id = shared.project_id if shared else None

    feedback = Feedback(
        project_id=project_id,
        giver_id=current_user.id,
        receiver_id=profile_user.id,
        rating=int(rating),
        comment=comment,
    )
    db.session.add(feedback)
    db.session.commit()
    check_and_award_badges(profile_user.id)
    flash("Review submitted successfully!", "success")
    return redirect(url_for("main.user_profile", user_id=user_id))


@main_bp.route("/user/<int:user_id>/endorse", methods=["POST"])
@login_required# Submit endorsement for another user (only if shared any project and not already endorsed that skill)
def submit_endorse(user_id):
    profile_user = User.query.get_or_404(user_id)

    if current_user.id == profile_user.id:
        flash("You cannot endorse yourself.", "error")
        return redirect(url_for("main.user_profile", user_id=user_id))

    skill = request.form.get("skill", "").strip()
    if not skill:
        flash("Skill is required.", "error")
        return redirect(url_for("main.user_profile", user_id=user_id))

    already = Endorsement.query.filter_by(
        giver_id=current_user.id, receiver_id=profile_user.id, skill=skill
    ).first()
    if already:
        flash(f"You already endorsed '{skill}' for this user.", "error")
        return redirect(url_for("main.user_profile", user_id=user_id))

    endorsement = Endorsement(
        giver_id=current_user.id,
        receiver_id=profile_user.id,
        skill=skill,
    )
    db.session.add(endorsement)
    db.session.commit()
    check_and_award_badges(profile_user.id)
    flash(f"Endorsed '{skill}' successfully!", "success")
    return redirect(url_for("main.user_profile", user_id=user_id))

# Helper function to render profile page (used for both own profile and viewing others)
def _render_profile(user):
    completed_memberships = (
        ProjectMember.query.join(Project)
        .filter(
            ProjectMember.user_id == user.id,
            ProjectMember.removed == False,
            Project.status == "completed"
        ).all()
    )
    active_memberships = (
        ProjectMember.query.join(Project)
        .filter(
            ProjectMember.user_id == user.id,
            ProjectMember.removed == False,
            Project.status.in_(["open", "closed"])
        ).all()
    )
    feedbacks = Feedback.query.filter_by(receiver_id=user.id).all()
    avg_rating = None
    if feedbacks:
        avg_rating = round(sum(f.rating for f in feedbacks) / len(feedbacks), 1)

    endorsements = Endorsement.query.filter_by(receiver_id=user.id).all()

    user_badges = UserBadge.query.filter_by(user_id=user.id).all()
    badges = [ub.badge for ub in user_badges if ub.badge]

    return render_template(
        "user/profile.html",
        user=user,
        completed_projects=completed_memberships,
        active_projects=active_memberships,
        avg_rating=avg_rating,
        feedbacks=feedbacks,
        endorsements=endorsements,
        badges=badges,
    )


# ── AVATAR UPLOAD (standalone — never blocked by other form fields) ───────────
@main_bp.route("/profile/avatar", methods=["POST"])
@login_required
def upload_avatar():
    user = db.session.get(User, current_user.id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("main.edit_profile"))

    avatar_file = request.files.get("avatar")
    if not avatar_file or not avatar_file.filename:
        flash("No file selected.", "error")
        return redirect(url_for("main.edit_profile"))

    try:
        _save_user_avatar(user, avatar_file)
        db.session.commit()
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.edit_profile"))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Avatar upload failed for user %s", current_user.id)
        flash("Could not save profile photo. Please try again.", "error")
        return redirect(url_for("main.edit_profile"))

    flash("Profile photo updated!", "success")
    return redirect(url_for("main.edit_profile"))


# ── EDIT PROFILE ──────────────────────────────────────────────────────────────
@main_bp.route("/edit-profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = User.query.get(current_user.id)

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        department = request.form.get("department", "").strip()
        bio = request.form.get("bio", "").strip()
        skills = request.form.getlist("skills")
        interest_tags = request.form.getlist("interest_tags")
        courses = request.form.getlist("courses")

        if not first_name or not last_name:
            flash("First and last name are required.", "error")
            return redirect(url_for("main.edit_profile"))

        if len(interest_tags) != 5:
            flash("Please select exactly 5 interest tags.", "error")
            return redirect(url_for("main.edit_profile"))

        user.first_name = first_name
        user.last_name = last_name
        user.department = department or None
        user.bio = bio or None

        # Handle avatar upload
        avatar_file = request.files.get("avatar")
        if avatar_file and avatar_file.filename:
            if not _allowed_avatar(avatar_file.filename):
                flash("Invalid file type. Please upload a JPG, PNG, or WebP image.", "error")
                return redirect(url_for("main.edit_profile"))
            avatar_file.seek(0, 2)
            file_size = avatar_file.tell()
            avatar_file.seek(0)
            if file_size > MAX_AVATAR_BYTES:
                flash("Avatar image must be under 2MB.", "error")
                return redirect(url_for("main.edit_profile"))
            ext      = avatar_file.filename.rsplit(".", 1)[1].lower()
            filename = secure_filename(f"user_{user.id}.{ext}")
            data     = avatar_file.read()
            user.avatar_url = storage.save(data, filename, category="avatars")

        # Update skills
        UserSkill.query.filter_by(user_id=user.id).delete()
        for skill in skills:
            skill = skill.strip()
            if skill:
                db.session.add(UserSkill(user_id=user.id, skill=skill))

        # Update interests
        UserInterest.query.filter_by(user_id=user.id).delete()
        for tag in interest_tags:
            db.session.add(UserInterest(user_id=user.id, tag=tag))

        # Update courses
        UserCourse.query.filter_by(user_id=user.id).delete()
        for course in courses:
            course = course.strip()
            if course:
                db.session.add(UserCourse(user_id=user.id, course=course))

        # Handle banner (preset key or uploaded image)
        banner_preset = request.form.get("banner_preset", "").strip()
        banner_file = request.files.get("banner")
        try:
            if banner_file and banner_file.filename:
                _save_user_banner(user, banner_file)
            elif banner_preset and banner_preset in BANNER_CSS:
                user.banner_url = f"preset:{banner_preset}"
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.edit_profile"))

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("main.profile"))

    return render_template("user/edit_profile.html", user=user)


# ── LANGUAGE SWITCH ───────────────────────────────────────────────────────────
@main_bp.route("/set-lang/<lang>")
def set_language(lang):
    """Persist the chosen UI language in the session and return where we came from."""
    from flask import session
    from services.i18n import LANGUAGES
    if lang in LANGUAGES:
        session["lang"] = lang
    return redirect(request.referrer or url_for("main.dashboard"))


# ── QUIZ GENERATOR (study tool) ───────────────────────────────────────────────
@main_bp.route("/quiz")
@login_required
def quiz_page():
    return render_template("user/quiz.html")


@main_bp.route("/quiz/generate", methods=["POST"])
@login_required
@limiter.limit("6 per minute; 40 per day")
def quiz_generate():
    """Generate a practice quiz from pasted notes. LLM-backed, rate-limited,
    input length-capped; notes are never persisted."""
    from services.quiz_service import generate_quiz, QuizError, extract_text_from_upload

    # Notes can arrive as an uploaded file (.txt/.md/.pdf) or pasted JSON text.
    upload = request.files.get("file")
    if upload and upload.filename:
        material, err = extract_text_from_upload(upload)
        if err:
            return jsonify({"error": err}), 400
        try:
            count = int(request.form.get("count", 5))
        except (TypeError, ValueError):
            count = 5
    else:
        data = request.get_json(silent=True) or {}
        material = (data.get("material") or "")
        try:
            count = int(data.get("count", 5))
        except (TypeError, ValueError):
            count = 5
    try:
        questions = generate_quiz(material, n=count)
    except QuizError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("quiz generation failed")
        return jsonify({"error": "Something went wrong generating the quiz."}), 500
    analytics.track("quiz_generated", current_user.id, value=len(questions), commit=True)
    return jsonify({"questions": questions})


# ── INSTRUCTOR DASHBOARD ──────────────────────────────────────────────────────
@main_bp.route("/instructor")
@login_required
def instructor_dashboard():
    """Course-level team-health oversight. Instructors and admins only."""
    if current_user.role not in ("instructor", "admin"):
        flash("This page is only available to instructors.", "error")
        return redirect(url_for("main.dashboard"))
    from services.instructor_view import course_overview
    try:
        overview = course_overview()
    except Exception:
        current_app.logger.exception("instructor overview failed")
        overview = []
    totals = {
        "risk": sum(c["risk_count"] for c in overview),
        "watch": sum(c["watch_count"] for c in overview),
        "projects": sum(len(c["projects"]) for c in overview),
        "courses": len(overview),
    }
    return render_template("user/instructor.html", overview=overview, totals=totals)


# ── TEAMMATE FINDER ───────────────────────────────────────────────────────────
@main_bp.route("/teammates")
@login_required
def teammates_page():
    """Find people whose skills/interests complement the current user."""
    from services.teammate_service import find_teammates
    try:
        matches = find_teammates(current_user.id, limit=12)
    except Exception:
        current_app.logger.exception("teammate finder failed")
        matches = []
    analytics.track("teammates_view", current_user.id, commit=True)
    return render_template("user/teammates.html", matches=matches)


# ── BETA: React projects explorer (feature-flagged) ──────────────────────────
@main_bp.route("/beta/projects")
@login_required
def beta_projects():
    """React + TypeScript explorer over /api/v1. Gated by FEATURE_SPA so it
    only ships to production deliberately (flag is off there by default)."""
    if not current_app.config.get("FEATURE_SPA"):
        from flask import abort
        abort(404)
    return render_template("beta/projects.html")


# ── ML MODEL CARD (recommender metrics) ───────────────────────────────────────
@main_bp.route("/ml/recommender")
@login_required
def ml_model_card():
    from services.ml.recommender import load_metrics, model_available
    try:
        ab_summary = analytics.rec_ab_summary()
    except Exception:
        ab_summary = []
    return render_template(
        "ml/model_card.html",
        metrics=load_metrics(),
        available=model_available(),
        ab_summary=ab_summary,
    )


# ── FIRST-RUN ONBOARDING (pick avatar + banner) ───────────────────────────────
@main_bp.route("/welcome", methods=["GET", "POST"])
@login_required
def welcome():
    user = db.session.get(User, current_user.id)

    if request.method == "POST":
        if request.form.get("action") == "skip":
            user.onboarded = True
            db.session.commit()
            return redirect(url_for("main.dashboard"))

        try:
            avatar_file = request.files.get("avatar")
            if avatar_file and avatar_file.filename:
                _save_user_avatar(user, avatar_file)

            banner_file = request.files.get("banner")
            banner_preset = request.form.get("banner_preset", "").strip()
            if banner_file and banner_file.filename:
                _save_user_banner(user, banner_file)
            elif banner_preset and banner_preset in BANNER_CSS:
                user.banner_url = f"preset:{banner_preset}"
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.welcome"))

        user.onboarded = True
        db.session.commit()
        flash("You're all set — welcome to ProjectBuddy!", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("user/welcome.html", user=user)


# ── PROFILE WALL (public comments) ────────────────────────────────────────────
@main_bp.route("/user/<int:user_id>/wall", methods=["POST"])
@login_required
def post_wall_comment(user_id):
    profile_user = User.query.get_or_404(user_id)
    payload = request.get_json(silent=True) or {}
    body = (payload.get("body") or request.form.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Comment cannot be empty."}), 400
    if len(body) > 1000:
        return jsonify({"error": "Too long (max 1000 chars)."}), 400

    c = ProfileComment(profile_id=profile_user.id, author_id=current_user.id, body=body)
    db.session.add(c)
    if profile_user.id != current_user.id:
        create_notification(
            profile_user.id,
            f"{current_user.get_full_name()} left a comment on your profile.",
            link=f"/user/{profile_user.id}",
        )
    db.session.commit()
    return jsonify(_wall_comment_json(c))


@main_bp.route("/wall/<int:comment_id>/like", methods=["POST"])
@login_required
def like_wall_comment(comment_id):
    ProfileComment.query.get_or_404(comment_id)
    existing = ProfileCommentLike.query.filter_by(comment_id=comment_id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(ProfileCommentLike(comment_id=comment_id, user_id=current_user.id))
        liked = True
    db.session.commit()
    return jsonify({"liked": liked,
                    "likes": ProfileCommentLike.query.filter_by(comment_id=comment_id).count()})


@main_bp.route("/wall/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_wall_comment(comment_id):
    c = ProfileComment.query.get_or_404(comment_id)
    if not (c.author_id == current_user.id or c.profile_id == current_user.id
            or current_user.role == "admin"):
        return jsonify({"error": "Not authorized."}), 403
    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})


@main_bp.route("/wall/<int:comment_id>/report", methods=["POST"])
@login_required
def report_wall_comment(comment_id):
    c = ProfileComment.query.get_or_404(comment_id)
    if c.author_id == current_user.id:
        return jsonify({"error": "You can't report your own comment."}), 400
    payload = request.get_json(silent=True) or {}
    reason = (payload.get("reason") or "Inappropriate profile comment").strip()
    db.session.add(Report(
        reporter_id=current_user.id,
        target_user_id=c.author_id,
        reason="profile_comment",
        description=f"Comment #{c.id}: {c.body[:300]}\n\nReason: {reason}",
    ))
    db.session.commit()
    return jsonify({"ok": True})


# ── REPORT ISSUE ──────────────────────────────────────────────────────────────
@main_bp.route("/report-issue", methods=["GET", "POST"])
@login_required
def report_issue():
    if request.method == "POST":
        target_type = request.form.get("target_type", "")
        target_id = request.form.get("target_id", "").strip()
        reason = request.form.get("reason", "").strip()
        description = request.form.get("description", "").strip()

        if not target_id or not reason:
            flash("Please select a target and provide a reason.", "error")
            return redirect(url_for("main.report_issue"))

        try:
            target_id = int(target_id)
        except ValueError:
            flash("Invalid target selected.", "error")
            return redirect(url_for("main.report_issue"))

        report_kwargs = dict(
            reporter_id=current_user.id,
            reason=reason,
            description=description or None,
        )

        if target_type == "user":
            if current_user.id == target_id:
                flash("You cannot report yourself.", "error")
                return redirect(url_for("main.report_issue"))
            report_kwargs["target_user_id"] = target_id
        elif target_type == "project":
            report_kwargs["target_project_id"] = target_id
        else:
            flash("Invalid report type.", "error")
            return redirect(url_for("main.report_issue"))

        db.session.add(Report(**report_kwargs))
        db.session.commit()
        flash("Report submitted. Thank you for keeping the community safe.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("report_issue.html")


# ── ADMIN DASHBOARD ───────────────────────────────────────────────────────────
@main_bp.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        flash("Access denied. Admins only.", "error")
        return redirect(url_for("main.dashboard"))

    total_users = User.query.filter(User.role != "admin").count()
    total_projects = Project.query.count()
    open_projects = Project.query.filter_by(status="open").count()
    completed_projects = Project.query.filter_by(status="completed").count()
    pending_reports = Report.query.filter_by(status="pending").count()
    banned_users = User.query.filter_by(is_banned=True).count()

    open_chat_count = Chat.query.filter_by(status="open").count()
    unassigned_chat_count = Chat.query.filter_by(
        status="open", admin_id=None
    ).count()

    # Build reports data
    reports = Report.query.filter_by(status="pending").order_by(
        Report.created_at.desc()
    ).all()
    reports_data = []
    for r in reports:
        reports_data.append({
            "report": r,
            "target_user": r.target_user,
            "target_project": r.target_project,
            "reporter": r.reporter,
        })

    all_users = User.query.filter(User.role != "admin").order_by(
        User.created_at.desc()
    ).all()
    recent_projects = Project.query.order_by(Project.created_at.desc()).limit(50).all()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_projects=total_projects,
        open_projects=open_projects,
        completed_projects=completed_projects,
        pending_reports=pending_reports,
        banned_users=banned_users,
        open_chat_count=open_chat_count,
        unassigned_chat_count=unassigned_chat_count,
        reports_data=reports_data,
        all_users=all_users,
        recent_projects=recent_projects,
    )


# ── ADMIN: PROCESS REPORT ─────────────────────────────────────────────────────
@main_bp.route("/admin/report/<int:report_id>/process", methods=["POST"])
@login_required
def process_report(report_id):
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("main.dashboard"))

    report = Report.query.get_or_404(report_id)
    action = request.form.get("action", "")

    if action == "warn":
        report.status = "warned"
        report.resolved_at = datetime.now(timezone.utc)
        if report.target_user_id:
            db.session.add(AdminMessage(
                user_id=report.target_user_id,
                sender_id=current_user.id,
                content=f"You have received a warning regarding: {report.reason}",
                is_warning=True,
            ))
        flash("Warning issued.", "success")

    elif action == "ban":
        report.status = "banned"
        report.resolved_at = datetime.now(timezone.utc)
        if report.target_user_id:
            user = User.query.get(report.target_user_id)
            if user:
                user.is_banned = True
        flash("User banned.", "success")

    elif action == "dismiss":
        report.status = "dismissed"
        report.resolved_at = datetime.now(timezone.utc)
        flash("Report dismissed.", "success")

    else:
        flash("Unknown action.", "error")
        return redirect(url_for("main.admin_dashboard"))

    db.session.commit()
    return redirect(url_for("main.admin_dashboard"))


# ── ADMIN: BAN / UNBAN USER ───────────────────────────────────────────────────
@main_bp.route("/admin/user/<int:user_id>/ban", methods=["POST"])
@login_required
def admin_ban_user(user_id):
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("main.dashboard"))
    user = User.query.get_or_404(user_id)
    user.is_banned = True
    db.session.commit()
    flash(f"{user.first_name} {user.last_name} has been banned.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main_bp.route("/admin/user/<int:user_id>/unban", methods=["POST"])
@login_required
def admin_unban_user(user_id):
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("main.dashboard"))
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    db.session.commit()
    flash(f"{user.first_name} {user.last_name} has been unbanned.", "success")
    return redirect(url_for("main.admin_dashboard"))


# ── ADMIN: REMOVE PROJECT ─────────────────────────────────────────────────────
@main_bp.route("/admin/project/<int:project_id>/remove", methods=["POST"])
@login_required
def admin_remove_project(project_id):
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("main.dashboard"))
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Project removed.", "success")
    return redirect(url_for("main.admin_dashboard"))


# ── NOTIFICATIONS ─────────────────────────────────────────────────────────────
@main_bp.route("/notifications/unread")
@limiter.exempt  # fetched on every page load — must not eat the rate budget
@login_required
def get_notifications():
    notifs = (Notification.query
              .filter_by(user_id=current_user.id)
              .order_by(Notification.created_at.desc())
              .limit(20).all())
    unread_count = (Notification.query
                    .filter_by(user_id=current_user.id, is_read=False).count())
    items = [{
        "id":       n.id,
        "message":  n.message,
        "link":     n.link or "/dashboard",
        "is_read":  n.is_read,
        "time_ago": n.created_at.strftime("%b %d · %H:%M") if n.created_at else "",
    } for n in notifs]
    return jsonify({"count": unread_count, "notifications": items})


@main_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all_notifications():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"ok": True})


@main_bp.route("/notifications/<int:notif_id>/read", methods=["POST"])
@login_required
def read_notification(notif_id):
    n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if n:
        n.is_read = True
        db.session.commit()
    return jsonify({"ok": True})


# ── ADMIN: ANALYTICS ──────────────────────────────────────────────────────────
@main_bp.route("/admin/analytics")
@login_required
def admin_analytics():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("main.dashboard"))

    from sqlalchemy import func

    # --- USER COUNTS ---
    total_users   = User.query.count()  # User.query.count()
    total_students = User.query.filter_by(role="student").count()

    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).replace(tzinfo=None)
    new_users_30d = User.query.filter(User.created_at >= thirty_days_ago).count()

    # --- PROJECT COUNTS ---
    total_projects     = Project.query.count()
    open_projects      = Project.query.filter_by(status="open").count()
    closed_projects    = Project.query.filter_by(status="closed").count()
    completed_projects = Project.query.filter_by(status="completed").count()
    total_applications = Application.query.count()

    # --- COMMUNITY COUNTS ---
    total_posts    = CommunityPost.query.count()
    total_comments = CommunityComment.query.count()
    new_posts_30d  = CommunityPost.query.filter(CommunityPost.created_at >= thirty_days_ago).count()  # thirty_days_ago already naive

    # --- VOTE / LIKE COUNTS ---
    total_votes = ProjectVote.query.count()
    total_likes = CommunityLike.query.count()

    # --- TOP VOTED PROJECTS (single SQL aggregation — no full-table Python sort) ---
    from sqlalchemy import case
    vote_sum = func.coalesce(
        func.sum(case((ProjectVote.direction == "up", 1), else_=-1)), 0
    ).label("score")
    top_rows = (
        db.session.query(Project, vote_sum)
        .outerjoin(ProjectVote, ProjectVote.project_id == Project.id)
        .group_by(Project.id)
        .order_by(vote_sum.desc())
        .limit(8)
        .all()
    )
    top_projects = list(enumerate([p for p, _score in top_rows]))

    # --- DEPARTMENT BREAKDOWN ---
    dept_breakdown = db.session.query(
        User.department, func.count(User.id)
    ).group_by(User.department).order_by(func.count(User.id).desc()).all()

    # --- MONTHLY SIGNUP CHART (last 6 months) ---
    signup_labels = []
    signup_data   = []

    db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    is_postgres = db_url.startswith('postgresql') or db_url.startswith('postgres')

    for i in range(5, -1, -1):
        target = datetime.now(timezone.utc) - timedelta(days=30 * i)
        label  = target.strftime("%b")
        ym     = target.strftime('%Y-%m')
        if is_postgres:
            count = User.query.filter(
                func.to_char(User.created_at, 'YYYY-MM') == ym
            ).count()
        else:
            count = User.query.filter(
                func.strftime('%Y-%m', User.created_at) == ym
            ).count()
        signup_labels.append(label)
        signup_data.append(count)

    # --- RECENT ACTIVITY FEED ---
    recent_users    = User.query.order_by(User.created_at.desc()).limit(8).all()
    recent_projects = Project.query.order_by(Project.created_at.desc()).limit(8).all()
    recent_posts    = CommunityPost.query.order_by(CommunityPost.created_at.desc()).limit(8).all()

    activity_raw = []

    for u in recent_users:
        activity_raw.append({
            "type": "user",
            "text": f"{u.first_name} {u.last_name} joined as {u.role}",
            "time": u.created_at.strftime("%b %d, %Y · %H:%M") if u.created_at else "",
            "sort": u.created_at
        })

    for p in recent_projects:
        activity_raw.append({
            "type": "project",
            "text": f"Project posted: \"{p.title}\"",
            "time": p.created_at.strftime("%b %d, %Y · %H:%M") if p.created_at else "",
            "sort": p.created_at
        })

    for post in recent_posts:
        activity_raw.append({
            "type": "post",
            "text": f"{post.author.first_name} shared in Community: \"{post.title or post.body[:50]}\"",
            "time": post.created_at.strftime("%b %d, %Y · %H:%M") if post.created_at else "",
            "sort": post.created_at
        })

    recent_activity = sorted(
        activity_raw, key=lambda x: x["sort"] or datetime.min, reverse=True
    )[:15]

    # --- PRODUCT METRICS (event stream: services/analytics.py) ---
    try:
        dau = analytics.active_users(1)
        wau = analytics.active_users(7)
        mau = analytics.active_users(30)
        funnel = analytics.activation_funnel()
        retention = analytics.retention_cohorts(weeks=6)
        rec_ab = analytics.rec_ab_summary()
    except Exception:
        current_app.logger.exception("product metrics failed")
        dau = wau = mau = 0
        funnel, retention, rec_ab = [], [], []

    # --- DATA WAREHOUSE FRESHNESS (admin-only visibility of the ETL) ---
    from services.etl import freshness
    warehouse = freshness()

    # --- RENDER ---
    return render_template("admin/analytics.html",
        warehouse=warehouse,
        dau=dau,
        wau=wau,
        mau=mau,
        stickiness=round(dau / mau * 100) if mau else 0,
        funnel=funnel,
        retention=retention,
        rec_ab=rec_ab,
        total_users=total_users,
        total_students=total_students,
        new_users_30d=new_users_30d,
        total_projects=total_projects,
        open_projects=open_projects,
        closed_projects=closed_projects,
        completed_projects=completed_projects,
        total_applications=total_applications,
        total_posts=total_posts,
        total_comments=total_comments,
        new_posts_30d=new_posts_30d,
        total_votes=total_votes,
        total_likes=total_likes,
        top_projects=top_projects,
        dept_breakdown=dept_breakdown,
        signup_labels=signup_labels,
        signup_data=signup_data,
        recent_activity=recent_activity,
    )
