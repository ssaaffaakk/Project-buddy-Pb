"""
SSM-1.0 — ProjectBuddy AI assistant.

Provider priority (first key found in .env wins):
  1. Groq       — free tier, fast LLaMA 3 models  (GROQ_API_KEY)
  2. Fallback   — built-in keyword-based responses (no key needed)

Groq = LLaMA running in the cloud for free. No Ollama needed on the server.
Get your key at: https://console.groq.com/keys
"""

import random
import logging
import requests
import eventlet.tpool
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from extensions import db, limiter
from models import ChatbotSession

logger = logging.getLogger(__name__)

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")

HISTORY_LIMIT = 20   # keep last 20 turns per user

_SYSTEM_PROMPT = (
    "You are SSM-1.0, the AI assistant built into ProjectBuddy — "
    "a collaboration platform for university students. "
    "Your name is SSM-1.0. If asked who you are, say: "
    "'I'm SSM-1.0, the AI assistant powering ProjectBuddy.' "
    "Help users with project planning, finding teammates, managing deadlines, "
    "skill development, and general study advice. "
    "Be concise, warm, and practical. Keep replies under 150 words unless asked for more."
)


# ── MOCK RESPONSES ────────────────────────────────────────────────────────────
_MOCK = {
    "project": [
        "Start with a clear README and break the work into weekly milestones. What's the core feature you want to ship first?",
        "Make sure each team member owns a specific module — it avoids merge conflicts and keeps accountability clear.",
        "Have you set up a shared GitHub repo yet? I can help you think through the branch strategy.",
    ],
    "team": [
        "Finding the right teammates is half the battle. Look for people whose skills complement yours.",
        "A weekly 15-minute standup keeps teams aligned: what did you do, what will you do, what's blocking you.",
        "Conflict in teams usually comes from unclear responsibilities. Write down who owns what early on.",
    ],
    "deadline": [
        "Break your deadline into 3 checkpoints: 30% (core structure), 70% (features working), 100% (polish + docs).",
        "If time is tight, scope down — a working MVP beats an unfinished full product every time.",
        "Work in 90-minute deep-work blocks with 15-minute breaks. Sustainable pace wins over sprints.",
    ],
    "skill": [
        "The fastest way to learn a new skill is to build something small with it first — a tiny prototype.",
        "Pair-programming with a teammate on something unfamiliar speeds up learning dramatically.",
        "Official docs beat YouTube for depth. Tutorials are great for the first hour, docs for everything after.",
    ],
    "flask": [
        "Flask tip: use Blueprints to keep routes organised by feature. Your codebase already does this well!",
        "Always use `db.session.flush()` before `commit()` when you need a new row's ID in the same request.",
        "Flask-Login's `@login_required` is your friend — put it on every route that needs authentication.",
    ],
    "git": [
        "Git tip: commit small and often. A commit message like 'fix login bug' is more useful than 'stuff'.",
        "Use feature branches — never commit directly to main. Open a PR even for solo projects; it builds good habits.",
        "Struggling with merge conflicts? Rebase instead of merge to keep a clean, linear history.",
    ],
    "default": [
        "That's a great question! I'm here to help with project planning, team coordination, and academic collaboration. Tell me more?",
        "Consistent communication and small daily progress beat big last-minute pushes.",
        "Focus on the deliverable first, then optimise. What's your current blocker?",
        "Have you checked the Projects board on ProjectBuddy? There might be teammates looking for exactly what you need.",
    ],
}

def _mock_reply(message: str) -> str:
    msg = message.lower()
    for keyword, replies in _MOCK.items():
        if keyword in msg:
            return random.choice(replies)
    return random.choice(_MOCK["default"])


# ── GROQ (free) ───────────────────────────────────────────────────────────────
def _groq_reply(history: list, user_message: str) -> str:
    """
    Groq uses the OpenAI-compatible chat completions format.
    Free tier: ~14,400 requests/day on llama-3.1-8b-instant.
    """
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages += history
    messages.append({"role": "user", "content": user_message})

    resp = eventlet.tpool.execute(
        requests.post,
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {current_app.config['GROQ_API_KEY']}",
            "Content-Type":  "application/json",
        },
        json={
            "model":       current_app.config.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "messages":    messages,
            "max_tokens":  512,
            "temperature": 0.7,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ── SECONDARY PROVIDER ────────────────────────────────────────────────────────
def _anthropic_reply(history: list, user_message: str) -> str:
    messages = history + [{"role": "user", "content": user_message}]

    resp = eventlet.tpool.execute(
        requests.post,
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         current_app.config["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        json={
            "model":      current_app.config.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
            "max_tokens": 512,
            "system":     _SYSTEM_PROMPT,
            "messages":   messages,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"].strip()


# ── PROVIDER SELECTOR ─────────────────────────────────────────────────────────
def _get_reply(history: list, user_message: str) -> str:
    if current_app.config.get("GROQ_API_KEY"):
        logger.info("chatbot: using Groq provider")
        return _groq_reply(history, user_message)
    if current_app.config.get("ANTHROPIC_API_KEY"):
        logger.info("chatbot: using Anthropic provider")
        return _anthropic_reply(history, user_message)
    logger.warning("chatbot: no API key found (GROQ_API_KEY / ANTHROPIC_API_KEY) — using mock responses")
    return _mock_reply(user_message)


# ── ROUTES ────────────────────────────────────────────────────────────────────
@chatbot_bp.route("/")
@login_required
def page():
    history = (ChatbotSession.query
               .filter_by(user_id=current_user.id)
               .order_by(ChatbotSession.created_at.desc())
               .limit(HISTORY_LIMIT).all())
    history = list(reversed(history))
    return render_template(
        "chat/chatbot.html",
        history=history,
        user=current_user,
    )


@chatbot_bp.route("/ask", methods=["POST"])
@login_required
@limiter.limit("20 per minute; 200 per day")
def ask():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()

    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400
    if len(user_message) > 1000:
        return jsonify({"error": "Message too long (max 1000 chars)."}), 400

    # Load recent history for context
    recent = (ChatbotSession.query
              .filter_by(user_id=current_user.id)
              .order_by(ChatbotSession.created_at.desc())
              .limit(HISTORY_LIMIT).all())
    history = [{"role": r.role, "content": r.content} for r in reversed(recent)]

    try:
        reply = _get_reply(history, user_message)
    except Exception as e:
        logger.exception("chatbot: provider call failed — %s", e)
        reply = "Sorry, I'm having trouble connecting to the AI right now. Please try again in a moment."

    # Persist both turns
    db.session.add(ChatbotSession(user_id=current_user.id, role="user",      content=user_message))
    db.session.add(ChatbotSession(user_id=current_user.id, role="assistant", content=reply))

    # Trim to HISTORY_LIMIT * 2 rows per user
    all_rows = (ChatbotSession.query
                .filter_by(user_id=current_user.id)
                .order_by(ChatbotSession.created_at.desc()).all())
    for old in all_rows[HISTORY_LIMIT * 2:]:
        db.session.delete(old)

    db.session.commit()
    return jsonify({"reply": reply})


@chatbot_bp.route("/clear", methods=["POST"])
@login_required
def clear_history():
    ChatbotSession.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"ok": True})
