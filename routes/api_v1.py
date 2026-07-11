"""
JSON API v1 — versioned, schema-validated, OpenAPI-documented.

Interactive docs: GET /api/docs (Swagger UI) · Spec: GET /api/openapi.json
Auth: POST /api/v1/auth/token → Bearer token. Reads also accept the browser
session; writes require the Bearer token (see services/api_auth.py).
"""

from flask import g
from flask_smorest import Blueprint, abort
from sqlalchemy import or_

from extensions import db, limiter
from models import Application, Project, ProjectMember, ProjectTag, StudyGroup, User
from schemas import (
    ApplyArgsSchema, MeSchema, MessageSchema, ProjectDetailSchema,
    ProjectListArgsSchema, ProjectPageSchema, PaginationArgsSchema,
    RecommendationsResponseSchema, StudyGroupPageSchema,
    TokenRequestSchema, TokenResponseSchema,
)
from services import analytics
from services.api_auth import auth_required, issue_token

blp = Blueprint(
    "api_v1", __name__, url_prefix="/api/v1",
    description="ProjectBuddy JSON API",
)

_BEARER = [{"bearerAuth": []}]


def _page_payload(pagination):
    return {
        "items": pagination.items,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }


# ── Auth ──────────────────────────────────────────────────────────────────────

@blp.route("/auth/token", methods=["POST"])
@limiter.limit("10 per minute; 50 per hour")
@blp.arguments(TokenRequestSchema)
@blp.response(200, TokenResponseSchema)
def create_token(args):
    """Exchange email + password for a Bearer access token."""
    user = User.query.filter_by(email=args["email"].strip().lower()).first()
    if user is None or not user.check_password(args["password"]):
        abort(401, message="Invalid email or password.")
    if user.is_banned:
        abort(403, message="This account is banned.")
    analytics.track("login", user.id, commit=True)
    return issue_token(user)


# ── Me ────────────────────────────────────────────────────────────────────────

@blp.route("/me", methods=["GET"])
@blp.doc(security=_BEARER)
@blp.response(200, MeSchema)
@auth_required()
def get_me():
    """The authenticated user's own profile."""
    return g.api_user


# ── Projects ──────────────────────────────────────────────────────────────────

@blp.route("/projects", methods=["GET"])
@blp.doc(security=_BEARER)
@blp.arguments(ProjectListArgsSchema, location="query")
@blp.response(200, ProjectPageSchema)
@auth_required()
def list_projects(args):
    """Paginated project list, filterable by status, tag, and free-text search."""
    query = Project.query.filter_by(status=args["status"])
    if args["q"]:
        needle = f"%{args['q']}%"
        query = query.filter(or_(Project.title.ilike(needle),
                                 Project.description.ilike(needle)))
    if args["tag"]:
        query = (query.join(ProjectTag, ProjectTag.project_id == Project.id)
                      .filter(ProjectTag.tag.ilike(args["tag"])))
    pagination = (query.order_by(Project.created_at.desc())
                       .paginate(page=args["page"], per_page=args["per_page"],
                                 error_out=False))
    return _page_payload(pagination)


@blp.route("/projects/<int:project_id>", methods=["GET"])
@blp.doc(security=_BEARER)
@blp.response(200, ProjectDetailSchema)
@auth_required()
def get_project(project_id):
    """One project with team status and vote score."""
    project = Project.query.get(project_id)
    if project is None:
        abort(404, message="Project not found.")
    analytics.track("project_view", g.api_user.id, "project", project.id, commit=True)
    return project


@blp.route("/projects/<int:project_id>/apply", methods=["POST"])
@blp.doc(security=_BEARER)
@blp.arguments(ApplyArgsSchema)
@blp.response(201, MessageSchema)
@auth_required(write=True)
def apply_to_project(args, project_id):
    """Apply to join a project (same rules as the web flow)."""
    user = g.api_user
    project = Project.query.get(project_id)
    if project is None:
        abort(404, message="Project not found.")
    if project.owner_id == user.id:
        abort(400, message="You cannot apply to your own project.")
    if project.status != "open" or project.is_full():
        abort(400, message="This project is not accepting applications.")
    if Application.query.filter_by(project_id=project_id, applicant_id=user.id).first():
        abort(409, message="You have already applied to this project.")

    active_count = (ProjectMember.query.join(Project)
                    .filter(ProjectMember.user_id == user.id,
                            ProjectMember.removed == False,  # noqa: E712
                            Project.status.in_(["open", "closed"]))
                    .count())
    if active_count >= 3:
        abort(400, message="You are already in 3 active projects (maximum).")

    db.session.add(Application(project_id=project_id, applicant_id=user.id,
                               message=args["message"]))
    from routes.main import create_notification
    create_notification(
        user_id=project.owner_id,
        type="apply",
        message=(f"📬 {user.first_name} {user.last_name} applied to your project "
                 f"\"{project.title}\""),
        link="/my-projects",
    )
    analytics.track("application_sent", user.id, "project", project_id)
    db.session.commit()
    return {"message": "Application submitted."}


# ── Recommendations ───────────────────────────────────────────────────────────

@blp.route("/recommendations", methods=["GET"])
@blp.doc(security=_BEARER)
@blp.response(200, RecommendationsResponseSchema)
@auth_required()
def get_recommendations():
    """Personalized project recommendations (same engine as the dashboard).

    Impressions are NOT logged here — the A/B experiment only counts
    recommendations actually rendered to the user (the dashboard does that).
    """
    from services.recommendation_service import get_recommendations_with_variant
    ranked, variant = get_recommendations_with_variant(g.api_user.id)
    items = [{"project": project, "fit_percent": score} for project, score in ranked[:10]]
    return {"items": items, "variant": variant}


# ── Study groups ──────────────────────────────────────────────────────────────

@blp.route("/study-groups", methods=["GET"])
@blp.doc(security=_BEARER)
@blp.arguments(PaginationArgsSchema, location="query")
@blp.response(200, StudyGroupPageSchema)
@auth_required()
def list_study_groups(args):
    """Paginated public study groups."""
    pagination = (StudyGroup.query.filter_by(is_private=False)
                  .order_by(StudyGroup.created_at.desc())
                  .paginate(page=args["page"], per_page=args["per_page"],
                            error_out=False))
    return _page_payload(pagination)
