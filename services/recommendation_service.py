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

    Backward-compatible wrapper around get_recommendations_with_variant().
    """
    recommendations, _variant = get_recommendations_with_variant(user_id)
    return recommendations


def get_recommendations_with_variant(user_id):
    """Return ([(project, fit_percent), ...], variant).

    A/B experiment ('rec_ranker'): when a trained model artifact is available,
    users are deterministically split 50/50 — the 'ml' arm is ranked by the
    learned recommender, the 'rules' arm by the tag-overlap heuristic. Logged
    impressions/clicks carry the arm so CTR per arm is directly comparable.

    variant is None when the experiment is inactive (no model artifact), so
    fallback traffic never contaminates the experiment's metrics.
    """
    try:
        from services.ml.recommender import model_available, rank_open_projects
        if model_available():
            from services.analytics import ab_variant
            variant = ab_variant(user_id, experiment="rec_ranker")
            if variant == "ml":
                ranked = rank_open_projects(user_id)
                if ranked is not None:
                    return ranked, "ml"
                # Model vanished between the check and the call — no experiment.
                return _rule_based_recommendations(user_id), None
            return _rule_based_recommendations(user_id), "rules"
    except Exception:
        logger.exception("ML recommender failed; falling back to rule-based scorer")
    return _rule_based_recommendations(user_id), None


def _rule_based_recommendations(user_id):
    """Tag-overlap heuristic: [(project, rough_fit_percent), ...]."""
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

    # Eager-load tags so the per-project tag read below doesn't N+1 (dashboard path).
    from sqlalchemy.orm import joinedload
    open_projects = (Project.query.filter_by(status="open")
                     .options(joinedload(Project.topic_tags)).all())

    recommendations = []
    for project in open_projects:
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


def match_reason(user, project):
    """One short, human sentence explaining why `project` fits `user`.

    Deterministic and built from the same overlap signals the recommender
    scores on — shared skills, interests/topics, and course — so it needs no
    LLM call and is instant/free to render on every recommendation card.
    Returns a plain English phrase (falls back to a generic line).
    """
    def _norm(value):
        return value.strip().lower()

    user_skills = {_norm(s.skill) for s in user.skills}
    shared_skills = [ps.skill for ps in project.required_skills if _norm(ps.skill) in user_skills]

    user_courses = {_norm(c.course) for c in user.courses}
    course_match = bool(project.course) and _norm(project.course) in user_courses

    user_topics = expand_user_interests([ui.tag for ui in user.interest_tags])
    shared_topics = [normalize_tag(t.tag) for t in project.topic_tags
                     if normalize_tag(t.tag) in user_topics]

    if shared_skills:
        names = shared_skills[:2]
        return "Matches your {} skill{}".format(" and ".join(names), "s" if len(names) > 1 else "")
    if course_match:
        return f"From your course {project.course}"
    if shared_topics:
        names = [t.title() for t in shared_topics[:2]]
        return "Fits your interest in {}".format(" and ".join(names))
    return "Picked from your profile"
