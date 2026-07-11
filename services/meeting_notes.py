"""
AI meeting notes — transcribe a recorded voice snippet and summarize it.

Pipeline (both stages via Groq, the same provider as the chatbot):
  1. audio bytes → transcript   (Whisper large-v3, /audio/transcriptions)
  2. transcript → summary       (chat model: TL;DR + action items)

Used by the study-group room's opt-in "record & summarize" control. The audio
is processed in-memory and never stored. Degrades gracefully (raises
MeetingNotesError with a user-facing message) when no key is configured or a
provider call fails.
"""

import logging

import eventlet.tpool
import requests
from flask import current_app

logger = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 25 * 1024 * 1024   # Groq's transcription limit
MIN_TRANSCRIPT_CHARS = 15

_SUMMARY_SYSTEM = (
    "You are SSM-1.0. Summarize this study-group meeting transcript into concise, "
    "well-structured notes. Output plain text with two short sections:\n"
    "Summary: 2-4 sentences capturing what was discussed.\n"
    "Action items: a short bullet list (use '- '), or 'None' if there were none.\n"
    "Base everything strictly on the transcript; do not invent details."
)


class MeetingNotesError(RuntimeError):
    """Transcription/summarization failed in a user-facing way."""


def _transcribe(audio_bytes, filename):
    resp = eventlet.tpool.execute(
        requests.post,
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {current_app.config['GROQ_API_KEY']}"},
        files={"file": (filename or "audio.webm", audio_bytes, "application/octet-stream")},
        data={"model": current_app.config.get("WHISPER_MODEL", "whisper-large-v3"),
              "response_format": "text"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.text.strip()


def _summarize(transcript):
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
                {"role": "system", "content": _SUMMARY_SYSTEM},
                {"role": "user", "content": transcript},
            ],
            "max_tokens": 700,
            "temperature": 0.3,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def transcribe_and_summarize(audio_bytes, filename="audio.webm"):
    """Return (summary_text, transcript). Raises MeetingNotesError on failure."""
    if not audio_bytes:
        raise MeetingNotesError("No audio was recorded.")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise MeetingNotesError("Recording too large (max 25 MB).")
    if not current_app.config.get("GROQ_API_KEY"):
        raise MeetingNotesError("AI meeting notes need a provider key "
                                "(GROQ_API_KEY) configured on the server.")

    try:
        transcript = _transcribe(audio_bytes, filename)
    except MeetingNotesError:
        raise
    except Exception as e:
        logger.exception("transcription failed")
        raise MeetingNotesError("Couldn't transcribe the audio. Please try again.") from e

    if len(transcript) < MIN_TRANSCRIPT_CHARS:
        raise MeetingNotesError("The recording was too short or silent to summarize.")

    try:
        summary = _summarize(transcript)
    except Exception as e:
        logger.exception("summarization failed")
        raise MeetingNotesError("Couldn't summarize the transcript. Please try again.") from e

    return summary, transcript
