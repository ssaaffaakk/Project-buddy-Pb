from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from extensions import db
from models import Application, Endorsement, Feedback, Project, ProjectMember, ProjectSkill, ProjectTag, User
from services.badge_service import check_and_award_badges
from services.recommendation_service import get_recommended_projects

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


@projects_bp.route("/", methods=["GET"])
@login_required
def list_projects():
    try:
        projects = Project.query.filter(Project.status == "open").all()
        return jsonify([{"id": p.id, "title": p.title, "description": p.description,
                         "team_size": p.team_size, "status": p.status,
                         "deadline": p.deadline.isoformat() if p.deadline else None}
                        for p in projects]), 200
    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"error": "An error occurred while fetching projects."}), 500


@projects_bp.route("/recommended", methods=["GET"])
@login_required
def recommended():
    try:
        results = get_recommended_projects(current_user.id)
        return jsonify([
            {"project_id": p.id, "title": p.title, "match_count": m}
            for p, m in results
        ]), 200
    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"error": "An error occurred while fetching recommended projects."}), 500


@projects_bp.route("/<int:project_id>", methods=["GET"])
@login_required
def get_project(project_id):
    try:
        project = Project.query.get_or_404(project_id)
        return jsonify({
            "id": project.id,
            "title": project.title,
            "description": project.description,
            "owner_id": project.owner_id,
            "course": project.course,
            "team_size": project.team_size,
            "status": project.status,
            "deadline": project.deadline.isoformat() if project.deadline else None,
            "tags": [t.tag for t in project.topic_tags],
            "skills": [s.skill for s in project.required_skills],
            "member_count": project.current_member_count()
        })
    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"error": "An error occurred while fetching project details."}), 500


@projects_bp.route("/", methods=["POST"])
@login_required
def create_project():
    from flask import flash, redirect, url_for
    try:
        data = request.form

        title = data.get("title", "").strip()
        description = data.get("description", "").strip()
        if not title or not description:
            flash("Title and description are required.", "error")
            return redirect(url_for("main.post_project_page"))

        tags = request.form.getlist("topic_tags")
        if len(tags) != 5:
            flash("Please select exactly 5 topic tags.", "error")
            return redirect(url_for("main.post_project_page"))

        active_count = ProjectMember.query.join(Project).filter(
            ProjectMember.user_id == current_user.id,
            ProjectMember.removed == False,
            Project.status.in_(["open", "closed"])
        ).count()
        if active_count >= 3:
            flash("You are already in 3 active projects (maximum).", "error")
            return redirect(url_for("main.post_project_page"))

        deadline_str = data.get("deadline")
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d") if deadline_str else None
        except ValueError:
            flash("Invalid deadline format.", "error")
            return redirect(url_for("main.post_project_page"))

        project = Project(
            title=title,
            description=description,
            owner_id=current_user.id,
            course=data.get("course") or None,
            team_size=int(data.get("team_size", 3)),
            deadline=deadline
        )
        db.session.add(project)
        db.session.flush()

        db.session.add(ProjectMember(project_id=project.id, user_id=current_user.id))

        for tag in tags:
            db.session.add(ProjectTag(project_id=project.id, tag=tag.strip()))

        for skill in request.form.getlist("required_skills"):
            skill = skill.strip()
            if skill:
                db.session.add(ProjectSkill(project_id=project.id, skill=skill))

        from services.analytics import track
        track("project_created", current_user.id, "project", project.id)
        db.session.commit()

        flash("Project posted successfully!", "success")
        return redirect(url_for("main.dashboard"))

    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        import traceback
        traceback.print_exc()
        flash("An error occurred while creating the project. Please try again.", "error")
        return redirect(url_for("main.post_project_page"))


@projects_bp.route("/<int:project_id>", methods=["PUT"])
@login_required
def update_project(project_id):
    """
    Update project details (title, description, skills, deadline).
    - Only the owner can update
    - Cannot update a completed project
    """
    try:
        project = Project.query.get_or_404(project_id)
        
        if project.owner_id != current_user.id:
            return jsonify({"error": "Only the project owner can update the project."}), 403
        
        if project.status == "completed":
            return jsonify({"error": "Cannot update a completed project."}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided."}), 400
        
        project.title = data.get("title", project.title)
        project.description = data.get("description", project.description)
        project.course = data.get("course", project.course)
        project.team_size = data.get("team_size", project.team_size)
        project.deadline = data.get("deadline", project.deadline)
        
        db.session.commit()
        return jsonify({"message": "Project updated successfully"}), 200
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        return jsonify({"error": "An error occurred while updating the project."}), 500


@projects_bp.route("/<int:project_id>/close", methods=["POST"])
@login_required
def close_project(project_id):
    """
    Close a project listing (no more applications accepted).
    - Only the owner can close
    - Cannot close if already completed
    """
    try:
        project = Project.query.get_or_404(project_id)
        
        if project.owner_id != current_user.id:
            return jsonify({"error": "Only the project owner can close the project."}), 403
        
        if project.status == "completed":
            return jsonify({"error": "Cannot close a completed project."}), 400
        
        project.status = "closed"
        db.session.commit()
        return jsonify({"message": "Project closed successfully"}), 200
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        return jsonify({"error": "An error occurred while closing the project."}), 500


@projects_bp.route("/<int:project_id>/complete", methods=["POST"])
@login_required
def complete_project(project_id):
    """
    Mark a project as completed.
    - Only the owner can do this
    - Sets status to 'completed' and records completed_at timestamp
    - Trigger badge checks after completion (via badge_service)
    """
    try:
        project = Project.query.get_or_404(project_id)
        
        if project.owner_id != current_user.id:
            return jsonify({"error": "Only the project owner can mark the project as completed."}), 403
        
        if project.status == "completed":
            return jsonify({"error": "Project is already completed."}), 400
        
        project.status = "completed"
        project.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # Award badges to all members
        for member in project.members:
            check_and_award_badges(member.user_id)
        
        return jsonify({"message": "Project marked as completed successfully"}), 200
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        return jsonify({"error": "An error occurred while marking the project as completed."}), 500


# ── APPLICATIONS ─────────────────────────────────────────────────────────────

@projects_bp.route("/<int:project_id>/apply-api", methods=["POST"])
@login_required
def apply(project_id):
    """
    Apply to join a project.
    - Cannot apply to own project
    - Cannot apply more than once
    - Cannot apply if project is closed/full/completed
    - Cannot apply if already in MAX_ACTIVE_PROJECTS projects
    - For course projects: check user is enrolled in that course
    """
    try:
        user_id = current_user.id
        project = Project.query.get_or_404(project_id)
        
        if project.owner_id == user_id:
            return jsonify({"error": "You cannot apply to your own project."}), 400

        if project.status in ["closed", "completed"]:
            return jsonify({"error": "You cannot apply to a closed or completed project."}), 400

        already_member = ProjectMember.query.filter_by(
            project_id=project_id, user_id=user_id, removed=False
        ).first()
        if already_member:
            return jsonify({"error": "You are already a member of this project."}), 400

        existing_application = Application.query.filter_by(project_id=project_id, applicant_id=user_id).first()
        if existing_application:
            return jsonify({"error": "You have already applied to this project."}), 400

        active_projects = ProjectMember.query.join(Project).filter(
            ProjectMember.user_id == user_id,
            ProjectMember.removed == False,
            Project.status.in_(["open", "closed"])
        ).count()
        if active_projects >= 3:
            return jsonify({"error": "You cannot be in more than 3 active projects."}), 400

        data = request.get_json(silent=True) or {}
        application = Application(
            project_id=project_id,
            applicant_id=user_id,
            message=data.get("message", "").strip() or None,
        )
        db.session.add(application)
        db.session.commit()
        return jsonify({"message": "Application submitted successfully"}), 201
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        return jsonify({"error": "An error occurred while submitting the application."}), 500


@projects_bp.route("/<int:project_id>/applications", methods=["GET"])
@login_required
def get_applications(project_id):
    """
    Get all applications for a project.
    - Only the project owner can see this
    """
    try:
        user_id = current_user.id
        project = Project.query.get_or_404(project_id)
        
        if project.owner_id != user_id:
            return jsonify({"error": "Only the project owner can view applications."}), 403
        
        applications = Application.query.filter_by(project_id=project_id).all()
        return jsonify({"applications": [
            {"app_id": app.id, "applicant_id": app.applicant_id,
             "applicant_name": f"{app.applicant.first_name} {app.applicant.last_name}" if app.applicant else "Unknown"}
            for app in applications
        ]}), 200
    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"error": "An error occurred while fetching applications."}), 500


@projects_bp.route("/<int:project_id>/applications/<int:app_id>/accept", methods=["POST"])
@login_required
def accept_application(project_id, app_id):
    """
    Accept an application.
    - Only project owner can accept
    - Add user to ProjectMember
    - If team is now full, auto-close the listing
    """
    try:
        user_id = current_user.id
        application = Application.query.get_or_404(app_id)
        
        if application.project_id != project_id:
            return jsonify({"error": "Application does not belong to this project."}), 400
        
        project = Project.query.get_or_404(project_id)
        
        if project.owner_id != user_id:
            return jsonify({"error": "Only the project owner can accept applications."}), 403
        
        if ProjectMember.query.filter_by(project_id=project_id, removed=False).count() >= project.team_size:
            return jsonify({"error": "Project team is already full."}), 400
        
        if project.status in ["closed", "completed"]:
            return jsonify({"error": "Cannot accept applications for a closed or completed project."}), 400
        
        member = ProjectMember(project_id=project_id, user_id=application.applicant_id)
        db.session.add(member)
        db.session.delete(application)
        db.session.flush()

        filled = ProjectMember.query.filter_by(project_id=project_id, removed=False).count()
        if filled >= project.team_size and project.status == "open":
            project.status = "closed"

        db.session.commit()
        return jsonify({"message": "Application accepted successfully"}), 200
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        return jsonify({"error": "An error occurred while accepting the application."}), 500


@projects_bp.route("/<int:project_id>/applications/<int:app_id>/reject", methods=["POST"])
@login_required
def reject_application(project_id, app_id):
    """
    Reject an application.
    - Only project owner can reject
    """
    try:
        user_id = current_user.id
        application = Application.query.get_or_404(app_id)
        
        if application.project_id != project_id:
            return jsonify({"error": "Application does not belong to this project."}), 400
        
        project = Project.query.get_or_404(project_id)
        
        if project.owner_id != user_id:
            return jsonify({"error": "Only the project owner can reject applications."}), 403
        
        db.session.delete(application)
        db.session.commit()
        return jsonify({"message": "Application rejected successfully"}), 200
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        return jsonify({"error": "An error occurred while rejecting the application."}), 500


# ── MEMBERS ───────────────────────────────────────────────────────────────────

@projects_bp.route("/<int:project_id>/members/<int:user_id>/remove", methods=["POST"])
@login_required
def remove_member(project_id, user_id):
    """
    Remove a member from a project.
    - For instructor-created projects: only instructor can remove
    - Cannot remove after project is completed
    - Removed user cannot re-apply to the same project
    """
    try:
        project = Project.query.get_or_404(project_id)
        
        if project.owner_id != current_user.id:
            return jsonify({"error": "Only the project owner can remove members."}), 403
        
        if user_id == current_user.id:
            return jsonify({"error": "You cannot remove yourself."}), 400
        
        remove_user = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id, removed=False).first()
        if not remove_user:
            return jsonify({"error": "User is not an active member."}), 400
        
        remove_user.removed = True
        remove_user.removed_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({"message": "Member removed successfully"}), 200
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        return jsonify({"error": "An error occurred while removing the member."}), 500


# ── FEEDBACK ─────────────────────────────────────────────────────────────────

@projects_bp.route("/<int:project_id>/feedback", methods=["POST"])
@login_required
def submit_feedback(project_id):
    """
    Submit feedback + rating for a teammate.
    - Project must be completed
    - Giver and receiver must both have been members of this project
    - Cannot rate yourself
    - Rating must be 1-5
    - One feedback per giver-receiver-project combination
    """
    try:
        user_id = current_user.id
        project = Project.query.get_or_404(project_id)
        
        data = request.get_json()
        if not data or "receiver_id" not in data or "rating" not in data:
            return jsonify({"error": "receiver_id and rating are required."}), 400
        
        receiver_id = data.get("receiver_id")
        rating = data.get("rating")
        
        if project.status != "completed":
            return jsonify({"error": "Feedback can only be submitted for completed projects."}), 400
        
        if receiver_id == user_id:
            return jsonify({"error": "You cannot rate yourself."}), 400
        
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return jsonify({"error": "Rating must be between 1 and 5."}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Rating must be a valid integer."}), 400
        
        member = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id, removed=False).first()
        receiver_member = ProjectMember.query.filter_by(project_id=project_id, user_id=receiver_id, removed=False).first()
        
        if not member or not receiver_member:
            return jsonify({"error": "Both giver and receiver must have been members of this project."}), 400
        
        existing_feedback = Feedback.query.filter_by(project_id=project_id, giver_id=user_id, receiver_id=receiver_id).first()
        if existing_feedback:
            return jsonify({"error": "You have already submitted feedback for this user on this project."}), 400
        
        new_feedback = Feedback(
            project_id=project_id,
            giver_id=user_id,
            receiver_id=receiver_id,
            rating=rating,
            comment=data.get("comment", ""),
            is_instructor_rating=False
        )
        db.session.add(new_feedback)
        db.session.commit()
        return jsonify({"message": "Feedback submitted successfully"}), 201
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        return jsonify({"error": "An error occurred while submitting feedback."}), 500


# ── ENDORSEMENTS ─────────────────────────────────────────────────────────────

@projects_bp.route("/endorse", methods=["POST"])
@login_required
def endorse_skill():
    """
    Endorse a skill of another user.
    - Both users must have completed at least 1 project together
    - Cannot endorse yourself
    - Trigger badge check after endorsement (via badge_service)
    """
    try:
        user_id = current_user.id
        data = request.get_json()
        
        if not data or "user_id" not in data or "skill" not in data:
            return jsonify({"error": "user_id and skill are required."}), 400
        
        user_id_to_endorse = data.get("user_id")
        skill_to_endorse = data.get("skill")
        
        if user_id == user_id_to_endorse:
            return jsonify({"error": "You cannot endorse yourself."}), 400
        
        # Verify user exists
        user_to_endorse = User.query.get(user_id_to_endorse)
        if not user_to_endorse:
            return jsonify({"error": "User not found."}), 404
        
        shared_projects = db.session.query(ProjectMember.project_id).join(
            Project, Project.id == ProjectMember.project_id
        ).filter(
            ProjectMember.user_id == user_id,
            ProjectMember.removed == False,
            Project.status == "completed"
        ).subquery()
        
        common_projects = db.session.query(ProjectMember).filter(
            ProjectMember.user_id == user_id_to_endorse,
            ProjectMember.removed == False,
            ProjectMember.project_id.in_(shared_projects)
        ).count()
        
        if common_projects == 0:
            return jsonify({"error": "You can only endorse users you have completed a project with."}), 400
        
        endorsement = Endorsement(
            giver_id=user_id,
            receiver_id=user_id_to_endorse,
            skill=skill_to_endorse
        )
        db.session.add(endorsement)
        db.session.commit()
        
        # Award badges after endorsement
        check_and_award_badges(user_id_to_endorse)
        
        return jsonify({"message": "Skill endorsed successfully"}), 201
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        return jsonify({"error": "An error occurred while endorsing the skill."}), 500
