"""
Feature engineering for the teammate/project recommender.

A single training/serving example is a (user, project) pair. We turn each pair
into a fixed-length numeric vector describing how well the user fits the
project — overlap of interests, overlap of skills, course match, and a few
project-side popularity/recency signals.

The same code path is used at train time (over many pairs) and at serve time
(ranking open projects for one user), so the model never sees a distribution
it wasn't trained on.
"""

from datetime import datetime, timezone

import numpy as np

# Reuse the exact interest→topic expansion the rule-based recommender uses,
# so the learned model and the heuristic speak the same vocabulary.
from services.recommendation_service import expand_user_interests, normalize_tag

# Order matters — this is the column order of every feature vector.
FEATURE_NAMES = [
    "interest_topic_overlap",   # count of shared (expanded) interest topics
    "interest_topic_jaccard",   # jaccard of expanded interests vs project tags
    "skill_overlap",            # count of shared skills
    "skill_jaccard",            # jaccard of user skills vs project skills
    "course_match",             # 1 if the project's course is one the user took
    "user_n_interests",         # how many interests the user declared
    "user_n_skills",            # how many skills the user listed
    "proj_n_tags",              # breadth of the project's topics
    "proj_n_skills",            # how many skills the project asks for
    "proj_team_size",           # target team size
    "proj_member_count",        # current members (popularity)
    "proj_age_days",            # days since the project was posted (recency)
    "proj_vote_score",          # community upvotes minus downvotes
    "semantic_sim",             # cosine of LSA text embeddings (user tower vs project tower)
]


def _norm_set(values):
    return {normalize_tag(v) for v in values if v and v.strip()}


def build_user_profile(user, interests, skills, courses, vec=None):
    """Precompute the user-side sets once so pair features are cheap.

    `vec` is the optional LSA embedding of the user's text (the user tower)."""
    raw_interests = [i.tag for i in interests]
    return {
        "interest_topics": {normalize_tag(t) for t in expand_user_interests(raw_interests)},
        "n_interests":     len(raw_interests),
        "skills":          _norm_set(s.skill for s in skills),
        "courses":         _norm_set(c.course for c in courses),
        "vec":             vec,
    }


def build_project_profile(project, now=None, vec=None):
    """Precompute the project-side sets/scalars once.

    `vec` is the optional LSA embedding of the project's text (project tower)."""
    now = now or datetime.now(timezone.utc)
    created = project.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - created).total_seconds() / 86400.0) if created else 0.0
    try:
        vote_score = project.vote_score
    except Exception:
        vote_score = 0
    return {
        "tags":         _norm_set(t.tag for t in project.topic_tags),
        "skills":       _norm_set(s.skill for s in project.required_skills),
        "team_size":    float(project.team_size or 0),
        "member_count": float(project.current_member_count()),
        "age_days":     float(age_days),
        "vote_score":   float(vote_score or 0),
        "course":       normalize_tag(project.course) if project.course else "",
        "vec":          vec,
    }


def pair_features(u, p):
    """Return the feature vector (list of floats) for one (user, project) pair."""
    it, pt = u["interest_topics"], p["tags"]
    inter = it & pt
    it_union = it | pt

    us, ps = u["skills"], p["skills"]
    sk = us & ps
    sk_union = us | ps

    uv, pv = u.get("vec"), p.get("vec")
    semantic_sim = float(np.dot(uv, pv)) if (uv is not None and pv is not None) else 0.0

    return [
        float(len(inter)),
        len(inter) / len(it_union) if it_union else 0.0,
        float(len(sk)),
        len(sk) / len(sk_union) if sk_union else 0.0,
        1.0 if (p["course"] and p["course"] in u["courses"]) else 0.0,
        float(u["n_interests"]),
        float(len(us)),
        float(len(pt)),
        float(len(ps)),
        p["team_size"],
        p["member_count"],
        p["age_days"],
        p["vote_score"],
        semantic_sim,
    ]
