"""
Teammate finder — user↔user matching.

ProjectBuddy already ranks projects for a user; this ranks *people*. It reuses
the same signals the recommender is built on: expanded interest topics, exact
skill overlap, shared courses, same department, and the in-house LSA text
embeddings (the "two-tower" retriever, here user-vs-user). Every match carries
human-readable reasons, so the score is explainable rather than a black box.

Privacy: emails are never returned; banned/admin/inactive users are excluded.
Scale: O(n) over users — fine for a single campus; note in ARCHITECTURE for
the indexing/ANN path if it ever needs to scale to many thousands.
"""

import logging

from models import User, UserCourse, UserInterest, UserSkill
from services.recommendation_service import expand_user_interests, normalize_tag

logger = logging.getLogger(__name__)

# Score weights (sum of the maxes ≈ 100 before the semantic bonus).
_W_INTEREST = 9      # per shared expanded-interest topic
_W_SKILL = 12        # per shared skill (rarer signal → weighted higher)
_W_COURSE = 10       # per shared course
_W_DEPARTMENT = 8    # same department
_W_SEMANTIC = 40     # cosine similarity of LSA text embeddings, scaled


def _profile(user_id):
    interests = [normalize_tag(i.tag)
                 for i in UserInterest.query.filter_by(user_id=user_id).all()]
    skills = {normalize_tag(s.skill)
              for s in UserSkill.query.filter_by(user_id=user_id).all() if s.skill}
    courses = {normalize_tag(c.course)
               for c in UserCourse.query.filter_by(user_id=user_id).all() if c.course}
    return {
        "topics": {normalize_tag(t) for t in expand_user_interests(interests)},
        "skills": skills,
        "courses": courses,
    }


def _embed_user(user, interests, skills, courses):
    try:
        from services.ml import embeddings
        return embeddings.embed(embeddings.user_text(user, interests, skills, courses))
    except Exception:
        logger.debug("teammate embedding unavailable", exc_info=True)
        return None


def find_teammates(user_id, limit=12):
    """Return [{user, score, reasons, shared_skills, shared_courses}, ...]
    ranked best-first. `user` is a plain dict (no email)."""
    me = User.query.get(user_id)
    if me is None:
        return []

    my = _profile(user_id)
    my_interests = UserInterest.query.filter_by(user_id=user_id).all()
    my_skills = UserSkill.query.filter_by(user_id=user_id).all()
    my_courses = UserCourse.query.filter_by(user_id=user_id).all()
    my_vec = _embed_user(me, my_interests, my_skills, my_courses)

    # Pre-bucket other users' interests/skills/courses in bulk to avoid N queries.
    others = (User.query
              .filter(User.id != user_id,
                      User.role != "admin",
                      User.is_banned == False,      # noqa: E712
                      User.is_active == True)       # noqa: E712
              .all())
    if not others:
        return []

    interests_by_user, skills_by_user, courses_by_user = {}, {}, {}
    for i in UserInterest.query.all():
        interests_by_user.setdefault(i.user_id, []).append(i)
    for s in UserSkill.query.all():
        skills_by_user.setdefault(s.user_id, []).append(s)
    for c in UserCourse.query.all():
        courses_by_user.setdefault(c.user_id, []).append(c)

    results = []
    for other in others:
        o_interests = interests_by_user.get(other.id, [])
        o_skills = skills_by_user.get(other.id, [])
        o_courses = courses_by_user.get(other.id, [])

        o_topics = {normalize_tag(t)
                    for t in expand_user_interests([i.tag for i in o_interests])}
        o_skill_set = {normalize_tag(s.skill) for s in o_skills if s.skill}
        o_course_set = {normalize_tag(c.course) for c in o_courses if c.course}

        shared_topics = my["topics"] & o_topics
        shared_skills = my["skills"] & o_skill_set
        shared_courses = my["courses"] & o_course_set
        same_dept = bool(me.department and me.department == other.department)

        score = (_W_INTEREST * len(shared_topics)
                 + _W_SKILL * len(shared_skills)
                 + _W_COURSE * len(shared_courses)
                 + (_W_DEPARTMENT if same_dept else 0))

        if my_vec is not None:
            o_vec = _embed_user(other, o_interests, o_skills, o_courses)
            if o_vec is not None:
                from services.ml.embeddings import cosine
                score += _W_SEMANTIC * max(0.0, cosine(my_vec, o_vec))

        if score <= 0:
            continue

        reasons = []
        if shared_skills:
            reasons.append(f"{len(shared_skills)} shared skill"
                           f"{'s' if len(shared_skills) != 1 else ''}")
        if shared_courses:
            reasons.append(f"{len(shared_courses)} shared course"
                           f"{'s' if len(shared_courses) != 1 else ''}")
        if shared_topics:
            reasons.append(f"{len(shared_topics)} matching interest"
                           f"{'s' if len(shared_topics) != 1 else ''}")
        if same_dept:
            reasons.append("same department")

        results.append({
            "user": {
                "id": other.id,
                "name": other.get_full_name(),
                "first_name": other.first_name,
                "last_name": other.last_name,
                "department": other.department,
                "avatar_url": other.avatar_url,
                "role": other.role,
                "initials": (other.first_name[:1] + other.last_name[:1]).upper(),
            },
            "raw_score": score,
            "reasons": reasons,
            "shared_skills": sorted(shared_skills),
            "shared_courses": sorted(shared_courses),
        })

    results.sort(key=lambda r: r["raw_score"], reverse=True)
    top = results[:limit]

    # Normalize to a 0–100 "match %" relative to the best match on this run, so
    # the UI shows a comparative strength (never a misleading absolute).
    if top:
        best = top[0]["raw_score"] or 1
        for r in top:
            r["match_percent"] = max(5, min(99, round(r["raw_score"] / best * 100)))
            del r["raw_score"]
    return top
