"""
SSM-1.0 assistant — platform tools and retrieval (the RAG layer).

Two capabilities, both provider-agnostic and unit-testable without an LLM:

1. Retrieval: semantic search over live platform data (open projects, study
   groups) using the in-house LSA embedding space from services/ml/embeddings,
   with a keyword fallback when no embedding artifact exists.

2. Tools: a typed registry the chatbot exposes to the LLM via function
   calling (OpenAI-format, supported by Groq). run_tool() is the single
   dispatch point — it validates the tool name/args and always returns a
   JSON-serializable dict.
"""

import logging
import re
from datetime import datetime, timezone

from models import Project, ProjectMember, StudyGroup

logger = logging.getLogger(__name__)

MIN_SEMANTIC_SCORE = 0.05   # below this cosine, semantic hits are noise


# ── helpers ───────────────────────────────────────────────────────────────────

def _project_dict(project):
    spots_left = max(0, project.team_size - project.current_member_count())
    return {
        "id": project.id,
        "title": project.title,
        "description": (project.description or "")[:200],
        "tags": [t.tag for t in project.topic_tags],
        "required_skills": [s.skill for s in project.required_skills],
        "spots_left": spots_left,
        "deadline": project.deadline.strftime("%Y-%m-%d") if project.deadline else None,
        "url": f"/project/{project.id}",
    }


def _group_dict(group):
    return {
        "id": group.id,
        "name": group.name,
        "topic": group.topic,
        "description": (group.description or "")[:200],
        "members": group.member_count(),
        "url": f"/study-groups/{group.id}",
    }


def _keyword_score(text, terms):
    text = text.lower()
    return sum(text.count(t) for t in terms)


# ── retrieval ─────────────────────────────────────────────────────────────────

def search_projects(query, limit=3):
    """Rank open projects by relevance to a free-text query.

    Semantic path: embed the query and every open project into the shared LSA
    space, rank by cosine. Falls back to keyword matching when the embedding
    artifact is missing or nothing clears the similarity floor.
    """
    query = (query or "").strip()
    if not query:
        return []
    projects = Project.query.filter_by(status="open").all()
    if not projects:
        return []

    try:
        from services.ml import embeddings
        q_vec = embeddings.embed(query)
        if q_vec is not None:
            scored = []
            for p in projects:
                p_vec = embeddings.embed(embeddings.project_text(p))
                scored.append((p, embeddings.cosine(q_vec, p_vec)))
            scored.sort(key=lambda t: t[1], reverse=True)
            hits = [p for p, score in scored[:limit] if score > MIN_SEMANTIC_SCORE]
            if hits:
                return [_project_dict(p) for p in hits]
    except Exception:
        logger.exception("semantic project search failed; using keyword fallback")

    terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
    if not terms:
        return []
    scored = []
    for p in projects:
        blob = " ".join([p.title or "", p.description or ""]
                        + [t.tag for t in p.topic_tags]
                        + [s.skill for s in p.required_skills])
        score = _keyword_score(blob, terms)
        if score > 0:
            scored.append((p, score))
    scored.sort(key=lambda t: t[1], reverse=True)
    return [_project_dict(p) for p, _ in scored[:limit]]


def search_study_groups(query, limit=3):
    """Keyword search over study groups (name, topic, description)."""
    terms = [t for t in re.split(r"\W+", (query or "").lower()) if len(t) > 2]
    if not terms:
        return []
    scored = []
    for g in StudyGroup.query.all():
        blob = " ".join([g.name or "", g.topic or "", g.description or ""])
        score = _keyword_score(blob, terms)
        if score > 0:
            scored.append((g, score))
    scored.sort(key=lambda t: t[1], reverse=True)
    return [_group_dict(g) for g, _ in scored[:limit]]


def get_my_deadlines(user_id):
    """Deadlines for projects the user owns or is an active member of."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    member_ids = {m.project_id for m in ProjectMember.query
                  .filter_by(user_id=user_id, removed=False).all()}
    projects = (Project.query
                .filter(Project.status.in_(["open", "closed"]))
                .filter(Project.deadline.isnot(None))
                .all())
    out = []
    for p in projects:
        if p.owner_id != user_id and p.id not in member_ids:
            continue
        days_left = (p.deadline - now).days
        out.append({
            "title": p.title,
            "deadline": p.deadline.strftime("%Y-%m-%d"),
            "days_left": days_left,
            "overdue": days_left < 0,
            "url": f"/project/{p.id}",
        })
    out.sort(key=lambda d: d["deadline"])
    return out


def recommend_projects(user_id, limit=3):
    """Top personalized recommendations (same engine as the dashboard)."""
    from services.recommendation_service import get_recommended_projects
    recs = get_recommended_projects(user_id)[:limit]
    return [{**_project_dict(p), "fit_percent": score} for p, score in recs]


# ── RAG context for the system prompt ─────────────────────────────────────────

def platform_context(user_message, user_id):
    """Ground the assistant: retrieve projects relevant to the user's message
    and format them as context the model can cite. Empty string if nothing
    relevant is found — never breaks the chat on failure."""
    try:
        hits = search_projects(user_message, limit=3)
        if not hits:
            return ""
        lines = []
        for h in hits:
            tags = ", ".join(h["tags"][:5])
            lines.append(
                f"- \"{h['title']}\" (tags: {tags}; {h['spots_left']} spots left; link: {h['url']})"
            )
        return (
            "\n\nLive platform context — open projects relevant to the user's message "
            "(cite the link when you mention one):\n" + "\n".join(lines)
        )
    except Exception:
        logger.exception("platform_context failed")
        return ""


# ── function-calling registry (OpenAI tool format — used by Groq) ─────────────

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "search_projects",
            "description": "Search the platform's open projects by topic, skill, or free text. "
                           "Use when the user asks to find projects or teammates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_study_groups",
            "description": "Search study groups by name or topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_deadlines",
            "description": "Get the current user's project deadlines (their own and joined projects).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_projects",
            "description": "Get the top personalized project recommendations for the current user.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def run_tool(name, args, user_id):
    """Dispatch one LLM tool call. Always returns a JSON-serializable dict;
    unknown tools and internal errors come back as {'error': ...} so the
    model can recover instead of the request 500ing."""
    try:
        if name == "search_projects":
            return {"results": search_projects(str(args.get("query", "")))}
        if name == "search_study_groups":
            return {"results": search_study_groups(str(args.get("query", "")))}
        if name == "get_my_deadlines":
            return {"deadlines": get_my_deadlines(user_id)}
        if name == "recommend_projects":
            return {"recommendations": recommend_projects(user_id)}
        return {"error": f"unknown tool: {name}"}
    except Exception as e:
        logger.exception("tool %s failed", name)
        return {"error": f"tool failed: {e}"}
