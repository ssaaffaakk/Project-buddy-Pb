from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import User, UserSkill, UserInterest, Report, Project

users_bp = Blueprint("users", __name__, url_prefix="/users")


# ── SEARCH USERS & PROJECTS ────────────────────────────────────────────────
@users_bp.route("/search", methods=["GET"])
@login_required
def search():
    """Search for users and projects by name"""
    query = request.args.get("q", "").strip()
    target_type = request.args.get("type", "").strip()  # "user" or "project"
    
    if not query or len(query) < 2:
        return jsonify({"results": []}), 200
    
    results = []
    
    if target_type in ["", "user"]:
        # Search users
        users = User.query.filter(
            (User.first_name.ilike(f"%{query}%")) | 
            (User.last_name.ilike(f"%{query}%")) |
            (User.email.ilike(f"%{query}%"))
        ).limit(10).all()
        
        for user in users:
            results.append({
                "id": user.id,
                "type": "user",
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "display": f"{user.first_name} {user.last_name} ({user.role})"
            })
    
    if target_type in ["", "project"]:
        # Search projects
        projects = Project.query.filter(
            Project.title.ilike(f"%{query}%")
        ).limit(10).all()
        
        for project in projects:
            results.append({
                "id": project.id,
                "type": "project",
                "name": project.title,
                "owner": f"{project.owner.first_name} {project.owner.last_name}",
                "display": project.title
            })
    
    return jsonify({"results": results}), 200


@users_bp.route("/<int:user_id>", methods=["GET"])
def get_profile(user_id):
    try:
        user = User.query.get_or_404(user_id)
        # Return public profile info (exclude email, bio, department)
        profile_data = {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "department": user.department,
            "bio": user.bio,
            "created_at": str(user.created_at),
            "interest_tags": [interest.tag for interest in user.interest_tags],
            "skills": [{"skill": skill.skill, "level": skill.level} for skill in user.skills],
            "badges": [ub.badge_id for ub in user.badges],
            "projects_owned": [{"id": p.id, "title": p.title} for p in user.projects_owned],
            "memberships": [{"project_id": m.project_id} for m in user.memberships],
            "applications_sent": [{"project_id": a.project_id, "status": a.status} for a in user.applications_sent],
            "feedback_received": [{"giver_id": f.giver_id, "rating": f.rating} for f in user.feedback_received],
            "endorsements_received": [{"giver_id": e.giver_id, "skill": e.skill} for e in user.endorsements_received]
        }
        return jsonify(profile_data), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while fetching the profile."}), 500


@users_bp.route("/me", methods=["GET"])
@login_required
def get_my_profile():
    try:
        user = current_user
        profile_data = {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": user.role,
            "department": user.department,
            "bio": user.bio,
            "is_active": user.is_active,
            "is_banned": user.is_banned,
            "created_at": str(user.created_at),
            "interest_tags": [i.tag for i in user.interest_tags],
            "skills": [{"skill": s.skill, "level": s.level} for s in user.skills],
        }
        return jsonify(profile_data), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while fetching the profile."}), 500

@users_bp.route("/me", methods=["PUT"])
@login_required
def update_profile():
    try:
        user = User.query.get(current_user.id)
        if not user:
            return jsonify({"error": "User not found."}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided."}), 400
        
        updatable_fields = ["bio", "skills", "department", "interest_tags"]
        for field in updatable_fields:
            if field in data:
                if field == "skills":
                    user.skills = [UserSkill(user_id=user.id, skill=skill) for skill in data["skills"]]
                elif field == "interest_tags":
                    user.interest_tags = [UserInterest(user_id=user.id, tag=tag) for tag in data["interest_tags"]]
                elif field == "department":
                    user.department = data["department"]
                elif field == "bio":
                    user.bio = data["bio"]
        
        db.session.commit()
        return jsonify({"message": "Profile updated successfully."}), 200
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": f"Invalid data: {str(e)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "An error occurred while updating the profile."}), 500


@users_bp.route("/me/interests", methods=["PUT"])
@login_required
def update_interests():
    """
    Update the current user's 5 interest tags.
    - Must submit exactly 5 tags
    - Replace all existing interests
    """
    try:
        user = User.query.get(current_user.id)
        if not user:
            return jsonify({"error": "User not found."}), 404
        
        data = request.get_json()
        if not data or "interest_tags" not in data:
            return jsonify({"error": "interest_tags field is required."}), 400
        
        interest_tags = data.get("interest_tags", [])
        
        if len(interest_tags) != 5:
            return jsonify({"error": "Exactly 5 tags required"}), 400
        
        # Delete existing interests and create new ones
        UserInterest.query.filter_by(user_id=user.id).delete()
        user.interest_tags = [UserInterest(user_id=user.id, tag=tag) for tag in interest_tags]
        db.session.commit()
        
        return jsonify({"message": "Interests updated successfully."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "An error occurred while updating interests."}), 500


@users_bp.route("/<int:user_id>/report", methods=["POST"])
@login_required
def report_user(user_id):
    """Report a user for inappropriate behavior.
    - Must include a reason category
    - Cannot report yourself
    """
    try:
        if current_user.id == user_id:
            return jsonify({"error": "You cannot report yourself."}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found."}), 404
        
        data = request.get_json()
        if not data or "reason" not in data:
            return jsonify({"error": "Reason is required."}), 400
        
        report = Report(
            reporter_id=current_user.id,
            target_user_id=user_id,
            reason=data.get("reason"),
            description=data.get("description", "")
        )
        db.session.add(report)
        db.session.commit()
        return jsonify({"message": "Report submitted"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "An error occurred while submitting the report."}), 500


@users_bp.route("/projects/<int:project_id>/report", methods=["POST"])
@login_required
def report_project(project_id):
    """
    Report a project listing as fake or misleading.
    - Must include a reason category
    """
    try:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({"error": "Project not found."}), 404
        
        data = request.get_json()
        if not data or "reason" not in data:
            return jsonify({"error": "Reason is required."}), 400
        
        report = Report(
            reporter_id=current_user.id,
            target_project_id=project_id,
            reason=data.get("reason"),
            description=data.get("description", "")
        )
        db.session.add(report)
        db.session.commit()

        return jsonify({"message": "Project report submitted"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "An error occurred while submitting the report."}), 500
