"""
Main page routes — renders all HTML templates.
"""

import os
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models import (
    User, Project, ProjectMember, Application, Feedback, Endorsement,
    UserBadge, Badge, Report, Chat, AdminMessage, UserInterest, UserSkill, UserCourse,
    ProjectMessage, ProjectVote, CommunityPost, CommunityComment, CommunityLike,
    Notification
)
from services.recommendation_service import get_recommended_projects
from services.badge_service import check_and_award_badges
from services.file_storage import storage

ALLOWED_AVATAR_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 MB


def _allowed_avatar(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS


def create_notification(user_id, message, link=None, type=None):
    """Create a notification for a user. Call db.session.commit() after."""
    if not user_id or not message:
        return
    n = Notification(user_id=user_id, message=message, link=link, type=type)
    db.session.add(n)


main_bp = Blueprint("main", __name__)


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
    return render_template("index.html")


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

    # Recommendations
    try:
        recommendations = get_recommended_projects(user.id)[:6]
    except Exception:
        recommendations = []

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
    query = Project.query.filter_by(status="open")
    if search_query:
        query = query.filter(Project.title.ilike(f"%{search_query}%"))
    projects = query.order_by(Project.created_at.desc()).all()

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


# ── MY PROJECTS ───────────────────────────────────────────────────────────────
@main_bp.route("/my-projects")
@login_required
def my_projects():
    # Projects owned by user, with pending applications
    owned = Project.query.filter_by(owner_id=current_user.id).order_by(
        Project.created_at.desc()
    ).all()
    owned_projects_with_apps = []
    for project in owned:
        apps = Application.query.filter_by(
            project_id=project.id, status="pending"
        ).all()
        owned_projects_with_apps.append({"project": project, "pending_apps": apps})

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
        db.session.commit()
        flash("Application submitted successfully!", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("projects/apply_confirm.html", project=project)


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
    if current_user.is_authenticated:
        is_owner = project.owner_id == current_user.id
        is_member = any(
            m.user_id == current_user.id and not m.removed
            for m in project.members
        )
        has_applied = Application.query.filter_by(
            project_id=project_id, applicant_id=current_user.id
        ).first() is not None

    vote_score = project.vote_score
    user_vote = None
    existing_vote = ProjectVote.query.filter_by(
        project_id=project_id, user_id=current_user.id
    ).first()
    if existing_vote:
        user_vote = existing_vote.direction

    return render_template(
        "projects/detail.html",
        project=project,
        messages=proj_messages,
        team_members=team_members,
        is_owner=is_owner,
        is_member=is_member,
        has_applied=has_applied,
        vote_score=vote_score,
        user_vote=user_vote,
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

    return render_template(
        "user/profile_view.html",
        profile_user=profile_user,
        user_stats=user_stats,
        reviews=feedbacks,
        can_leave_review=can_leave_review,
        can_endorse=can_endorse,
        already_endorsed_skills=already_endorsed_skills,
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
    user = User.query.get(current_user.id)
    avatar_file = request.files.get("avatar")

    if not avatar_file or not avatar_file.filename:
        flash("No file selected.", "error")
        return redirect(url_for("main.edit_profile"))

    if not _allowed_avatar(avatar_file.filename):
        flash("Invalid file type. Please upload a JPG, PNG, or WebP image.", "error")
        return redirect(url_for("main.edit_profile"))

    avatar_file.seek(0, 2)
    file_size = avatar_file.tell()
    avatar_file.seek(0)

    if file_size > MAX_AVATAR_BYTES:
        flash("Image must be under 2 MB.", "error")
        return redirect(url_for("main.edit_profile"))

    ext      = avatar_file.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"user_{user.id}.{ext}")
    data     = avatar_file.read()
    user.avatar_url = storage.save(data, filename, category="avatars")
    db.session.commit()

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

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("main.profile"))

    return render_template("user/edit_profile.html", user=user)


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
    from datetime import timedelta

    # --- USER COUNTS ---
    total_users   = User.query.count()  # User.query.count()
    total_students = User.query.filter_by(role="student").count()

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
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
    new_posts_30d  = CommunityPost.query.filter(CommunityPost.created_at >= thirty_days_ago).count()

    # --- VOTE / LIKE COUNTS ---
    total_votes = ProjectVote.query.count()
    total_likes = CommunityLike.query.count()

    # --- TOP VOTED PROJECTS ---
    all_projects = Project.query.all()
    top_projects = list(enumerate(
        sorted(all_projects, key=lambda p: p.vote_score, reverse=True)[:8]
    ))

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

    # --- RENDER ---
    return render_template("admin/analytics.html",
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
