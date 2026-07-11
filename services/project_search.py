"""
Project search & duplicate detection (semantic).

Two callers, one embedding space (the in-house LSA model in services/ml):
  - semantic_search(): ranks open projects by relevance to a free-text query,
    powering the Browse Projects search box. Falls back to substring matching
    when embeddings aren't available or nothing clears the floor.
  - similar_projects(): given a draft title+description, finds existing open
    projects that overlap — so the post form can warn "3 similar already exist,
    join instead?" before a duplicate is created.

Read-only and defensive: any embedding failure degrades to keyword matching
rather than raising.
"""

import logging
import re

from models import Project

logger = logging.getLogger(__name__)

_MIN_SEMANTIC = 0.05     # cosine floor below which a hit is noise
_SIMILAR_FLOOR = 0.18    # stricter: only surface genuinely close duplicates


def _keyword_rank(projects, query, limit):
    terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
    if not terms:
        # No usable terms → most recent open projects (stable default).
        return projects[:limit]
    scored = []
    for p in projects:
        blob = " ".join([p.title or "", p.description or ""]
                        + [t.tag for t in p.topic_tags]).lower()
        score = sum(blob.count(t) for t in terms)
        if score > 0:
            scored.append((p, score))
    scored.sort(key=lambda t: t[1], reverse=True)
    return [p for p, _ in scored[:limit]]


def semantic_search(query, limit=40):
    """Return open Project objects ranked by relevance to `query`."""
    query = (query or "").strip()
    open_projects = Project.query.filter_by(status="open").all()
    if not query or not open_projects:
        return open_projects[:limit]

    try:
        from services.ml import embeddings
        q_vec = embeddings.embed(query)
        if q_vec is not None:
            scored = []
            for p in open_projects:
                p_vec = embeddings.embed(embeddings.project_text(p))
                scored.append((p, embeddings.cosine(q_vec, p_vec)))
            hits = [(p, s) for p, s in scored if s > _MIN_SEMANTIC]
            if hits:
                hits.sort(key=lambda t: t[1], reverse=True)
                return [p for p, _ in hits[:limit]]
    except Exception:
        logger.exception("semantic search failed; using keyword fallback")

    return _keyword_rank(open_projects, query, limit)


def similar_projects(title, description="", limit=3, exclude_id=None):
    """Return [{id, title, similarity, spots_left, url}, ...] for open projects
    that closely match the given draft text. Empty when nothing is close."""
    text = f"{title or ''} . {description or ''}".strip(" .")
    if len(text) < 4:
        return []
    candidates = Project.query.filter_by(status="open").all()
    candidates = [p for p in candidates if p.id != exclude_id]
    if not candidates:
        return []

    try:
        from services.ml import embeddings
        q_vec = embeddings.embed(text)
    except Exception:
        q_vec = None

    scored = []
    if q_vec is not None:
        from services.ml.embeddings import cosine
        for p in candidates:
            sim = cosine(q_vec, embeddings.embed(embeddings.project_text(p)))
            if sim >= _SIMILAR_FLOOR:
                scored.append((p, sim))
    else:
        # Keyword fallback: Jaccard over word sets, same floor semantics.
        q_words = {w for w in re.split(r"\W+", text.lower()) if len(w) > 2}
        for p in candidates:
            p_words = {w for w in re.split(r"\W+", (p.title + " " + (p.description or "")).lower())
                       if len(w) > 2}
            if not q_words or not p_words:
                continue
            sim = len(q_words & p_words) / len(q_words | p_words)
            if sim >= _SIMILAR_FLOOR:
                scored.append((p, sim))

    scored.sort(key=lambda t: t[1], reverse=True)
    return [{
        "id": p.id,
        "title": p.title,
        "similarity": round(float(sim) * 100),
        "spots_left": max(0, p.team_size - p.current_member_count()),
        "url": f"/project/{p.id}",
    } for p, sim in scored[:limit]]
