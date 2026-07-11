"""
Practice-quiz generation from study notes (SSM-1.0).

Takes pasted course material and asks the LLM to produce multiple-choice
questions with answers and short explanations, returned as strict JSON. Reuses
the same Groq provider as the chatbot; degrades gracefully (clear error, never
a crash) when no API key is configured or the model returns unparseable output.

Read-only and stateless — no persistence, so pasted material is never stored.
"""

import json
import logging
import re

import eventlet.tpool
import requests
from flask import current_app

logger = logging.getLogger(__name__)

MAX_INPUT_CHARS = 12000
MIN_INPUT_CHARS = 60
MAX_QUESTIONS = 10

_SYSTEM = (
    "You are SSM-1.0, a study assistant. From the user's course material, write "
    "{n} multiple-choice practice questions that test understanding (not trivia). "
    "Return ONLY valid JSON, no prose, in exactly this shape:\n"
    '{{"questions":[{{"q":"question text","options":["a","b","c","d"],'
    '"answer":0,"explanation":"why this answer is correct"}}]}}\n'
    "Each question must have exactly 4 options; 'answer' is the 0-based index of "
    "the correct option. Base every question strictly on the provided material."
)


class QuizError(RuntimeError):
    """Quiz generation failed in a way worth showing the user."""


def _extract_json(text):
    """Pull the first JSON object out of an LLM reply (handles code fences)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise QuizError("The model did not return a quiz. Please try again.")
    return json.loads(text[start:end + 1])


def _validate(data):
    """Coerce/validate the parsed JSON into a clean question list."""
    questions = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(questions, list) or not questions:
        raise QuizError("The model returned no questions. Try more detailed notes.")
    clean = []
    for q in questions:
        try:
            text = str(q["q"]).strip()
            options = [str(o).strip() for o in q["options"]]
            answer = int(q["answer"])
            explanation = str(q.get("explanation", "")).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if text and len(options) == 4 and 0 <= answer <= 3:
            clean.append({"q": text, "options": options,
                          "answer": answer, "explanation": explanation})
    if not clean:
        raise QuizError("Couldn't build a valid quiz from the notes. Try again.")
    return clean


def _call_groq(system, material, n):
    resp = eventlet.tpool.execute(
        requests.post,
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {current_app.config['GROQ_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": current_app.config.get("GROQ_MODEL", "llama-3.1-8b-instant"),
            "messages": [
                {"role": "system", "content": system.format(n=n)},
                {"role": "user", "content": material},
            ],
            "max_tokens": 2048,
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def generate_quiz(material, n=5):
    """Return a list of validated question dicts. Raises QuizError on failure
    or when the LLM provider isn't configured."""
    material = (material or "").strip()
    if len(material) < MIN_INPUT_CHARS:
        raise QuizError(f"Please paste at least {MIN_INPUT_CHARS} characters of notes.")
    material = material[:MAX_INPUT_CHARS]
    n = max(3, min(MAX_QUESTIONS, int(n)))

    if not current_app.config.get("GROQ_API_KEY"):
        raise QuizError("The quiz generator needs an AI provider key "
                        "(GROQ_API_KEY) configured on the server.")

    try:
        raw = _call_groq(_SYSTEM, material, n)
    except QuizError:
        raise
    except Exception as e:
        logger.exception("quiz generation provider call failed")
        raise QuizError("The AI provider is unavailable right now. Please try again.") from e

    return _validate(_extract_json(raw))
