"""Evals for the SSM-1.0 assistant's RAG + tool layer.

Deterministic (no LLM, no network): retrieval quality on a golden set, tool
dispatch correctness, and the Groq tool-calling loop driven by a faked model.
The live end-to-end eval (real Groq) lives in scripts/eval_assistant.py.
"""
import json

import pytest

from extensions import db
from models import Project, ProjectSkill, ProjectTag, UserInterest
from services import assistant_tools


@pytest.fixture
def force_keyword_search(monkeypatch):
    """Pin retrieval to the keyword path so golden assertions don't depend on
    whatever LSA artifact happens to be on disk."""
    from services.ml import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda text: None)


@pytest.fixture
def seed_projects(app, make_user):
    """Three distinguishable open projects for retrieval golden tests."""
    owner = make_user("owner-golden@example.com")
    specs = [
        ("Campus ML Classifier", "Train a machine learning model to classify campus events",
         ["ai / ml", "data"], ["python", "scikit-learn"]),
        ("React Course Portal", "A React frontend for browsing course material",
         ["frontend", "web dev"], ["react", "javascript"]),
        ("Psychology Survey Study", "Design and run a survey on student stress",
         ["psychology", "research"], ["statistics"]),
    ]
    ids = {}
    with app.app_context():
        for title, desc, tags, skills in specs:
            p = Project(title=title, description=desc, owner_id=owner, team_size=4, status="open")
            db.session.add(p)
            db.session.flush()
            for t in tags:
                db.session.add(ProjectTag(project_id=p.id, tag=t))
            for s in skills:
                db.session.add(ProjectSkill(project_id=p.id, skill=s))
            ids[title] = p.id
        db.session.commit()
    return {"owner": owner, "ids": ids}


# ── Retrieval golden set ────────────────────────────────────────────────────────

GOLDEN_QUERIES = [
    ("I need teammates for a machine learning project", "Campus ML Classifier"),
    ("looking for a react frontend project", "React Course Portal"),
    ("anything about psychology research?", "Psychology Survey Study"),
]


@pytest.mark.parametrize("query,expected_title", GOLDEN_QUERIES)
def test_retrieval_golden(app, seed_projects, force_keyword_search, query, expected_title):
    with app.app_context():
        results = assistant_tools.search_projects(query)
        assert results, f"no results for {query!r}"
        assert results[0]["title"] == expected_title


def test_retrieval_returns_citable_links(app, seed_projects, force_keyword_search):
    with app.app_context():
        results = assistant_tools.search_projects("machine learning")
        assert results[0]["url"] == f"/project/{seed_projects['ids']['Campus ML Classifier']}"


def test_platform_context_grounds_the_prompt(app, seed_projects, force_keyword_search):
    with app.app_context():
        ctx = assistant_tools.platform_context("help me find a machine learning team", user_id=1)
        assert "Campus ML Classifier" in ctx
        assert "/project/" in ctx


# ── Tool dispatch ───────────────────────────────────────────────────────────────

def test_run_tool_unknown_tool_is_recoverable(app):
    with app.app_context():
        result = assistant_tools.run_tool("drop_database", {}, user_id=1)
        assert "error" in result


def test_run_tool_deadlines(app, make_user, make_project):
    from datetime import datetime, timedelta
    owner = make_user("dl@example.com")
    with app.app_context():
        p = Project(title="Deadline Project", description="x", owner_id=owner,
                    team_size=3, status="open",
                    deadline=datetime.utcnow() + timedelta(days=5))
        db.session.add(p)
        db.session.commit()
        result = assistant_tools.run_tool("get_my_deadlines", {}, user_id=owner)
        assert result["deadlines"][0]["title"] == "Deadline Project"
        assert result["deadlines"][0]["days_left"] in (4, 5)
        assert result["deadlines"][0]["overdue"] is False


def test_run_tool_recommendations(app, make_user, seed_projects, force_keyword_search):
    uid = make_user("rec-tool@example.com")
    with app.app_context():
        db.session.add(UserInterest(user_id=uid, tag="machine learning"))
        db.session.commit()
        result = assistant_tools.run_tool("recommend_projects", {}, user_id=uid)
        titles = [r["title"] for r in result["recommendations"]]
        assert "Campus ML Classifier" in titles


# ── Groq tool-calling loop (faked model) ────────────────────────────────────────

def test_groq_tool_loop(app, seed_projects, force_keyword_search, monkeypatch):
    """The agent loop executes a requested tool and returns the final answer."""
    import routes.chatbot as chatbot

    calls = []

    def fake_groq_chat(payload):
        calls.append(payload)
        if len(calls) == 1:
            return {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "search_projects",
                             "arguments": json.dumps({"query": "machine learning"})},
            }]}
        # Second round: the tool result must be in the transcript.
        tool_msgs = [m for m in payload["messages"] if m.get("role") == "tool"]
        assert tool_msgs and "Campus ML Classifier" in tool_msgs[0]["content"]
        return {"role": "assistant",
                "content": "Try 'Campus ML Classifier' — it matches your skills."}

    monkeypatch.setattr(chatbot, "_groq_chat", fake_groq_chat)

    with app.test_request_context():
        app.config["GROQ_API_KEY"] = "fake-key-for-test"
        try:
            reply = chatbot._get_reply([], "find me a machine learning project", user_id=1)
        finally:
            app.config["GROQ_API_KEY"] = ""

    assert "Campus ML Classifier" in reply
    assert len(calls) == 2
    assert calls[0].get("tools"), "first call must offer the tool specs"
