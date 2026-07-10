import logging

from models import Application, Project, ProjectMember, UserInterest

logger = logging.getLogger(__name__)


INTEREST_TO_TOPIC_MAP = {
    "react": {"frontend"},
    "python": {"backend", "data", "ai / ml"},
    "sql / db": {"databases", "data"},
    "machine learning": {"ai / ml", "data", "research"},
    "mobile dev": {"mobile", "frontend"},
    "ui/ux design": {"design", "frontend"},
    "cloud computing": {"cloud", "backend"},
    "cybersecurity": {"security", "backend"},
    "devops": {"cloud", "backend"},
    "web scraping": {"backend", "data", "research"},
    "data analysis": {"data", "research"},
    "blockchain": {"backend", "security", "research"},
    "game development": {"game dev", "frontend"},
    "networks": {"networking", "security"},
    "business": {"design", "data", "research"},
}


def get_recommended_projects(user_id):
    """Return [(project, fit_percent), ...] ranked best-first.

    Uses the trained ML recommender when a model artifact is available;
    otherwise falls back to the rule-based tag-overlap scorer.
    """
    # ── ML path (learned recommender) ────────────────────────────────────────
    try:
        from services.ml.recommender import rank_open_projects
        ranked = rank_open_projects(user_id)
        if ranked is not None:
            return ranked  # [(project, fit_percent_float)]
    except Exception:
        logger.exception("ML recommender failed; falling back to rule-based scorer")

    # ── Rule-based fallback ──────────────────────────────────────────────────
    user_interests = UserInterest.query.filter_by(user_id=user_id).all()
    if not user_interests:
        return []

    normalized_interests = expand_user_interests([ui.tag for ui in user_interests])
    active_project_ids = {
        member.project_id
        for member in ProjectMember.query.filter_by(user_id=user_id, removed=False).all()
    }
    applied_project_ids = {
        application.project_id
        for application in Application.query.filter_by(applicant_id=user_id).all()
    }

    recommendations = []
    for project in Project.query.filter_by(status="open").all():
        if project.owner_id == user_id or project.id in active_project_ids or project.id in applied_project_ids:
            continue

        project_tags = {normalize_tag(tag.tag) for tag in project.topic_tags}
        matches = normalized_interests.intersection(project_tags)
        if matches:
            recommendations.append((project, len(matches)))

    recommendations.sort(
        key=lambda item: (
            item[1],
            item[0].created_at,
        ),
        reverse=True,
    )
    # Express the tag-overlap count as a rough fit % so the UI is consistent
    # with the ML path (which returns a probability-based percentage).
    return [(project, min(99, round(count / 5 * 100))) for project, count in recommendations]


def expand_user_interests(tags):
    expanded_tags = set()
    for tag in tags:
        normalized_tag = normalize_tag(tag)
        expanded_tags.add(normalized_tag)
        expanded_tags.update(INTEREST_TO_TOPIC_MAP.get(normalized_tag, set()))
    return expanded_tags


def normalize_tag(tag):
    return tag.strip().lower()
