"""The chatbot's provider chain: Groq → Anthropic → mock replies.

Every provider with a configured key is tried in order; one that raises or
returns an empty reply hands the request to the next. No network: the
provider calls are replaced with fakes.
"""
import pytest

import routes.chatbot as chatbot


def _raise(*_a, **_k):
    raise RuntimeError("provider down")


@pytest.fixture
def keys(app, monkeypatch):
    """Configure provider keys for one test (monkeypatch restores them)."""
    def _set(groq="", anthropic=""):
        monkeypatch.setitem(app.config, "GROQ_API_KEY", groq)
        monkeypatch.setitem(app.config, "ANTHROPIC_API_KEY", anthropic)
    return _set


@pytest.fixture
def mock_reply(monkeypatch):
    monkeypatch.setattr(chatbot, "_mock_reply", lambda message: "mock answer")


def _ask(app):
    with app.test_request_context():
        return chatbot._get_reply([], "help me plan my project", user_id=1)


def test_groq_answers_when_it_works(app, keys, monkeypatch):
    keys(groq="g", anthropic="a")
    monkeypatch.setattr(chatbot, "_groq_reply", lambda *a: "groq answer")
    monkeypatch.setattr(chatbot, "_anthropic_reply", _raise)  # must not be reached
    assert _ask(app) == "groq answer"


def test_groq_failure_falls_back_to_anthropic(app, keys, monkeypatch):
    keys(groq="g", anthropic="a")
    monkeypatch.setattr(chatbot, "_groq_reply", _raise)
    monkeypatch.setattr(chatbot, "_anthropic_reply", lambda *a: "claude answer")
    assert _ask(app) == "claude answer"


def test_empty_groq_reply_falls_back_to_anthropic(app, keys, monkeypatch):
    keys(groq="g", anthropic="a")
    monkeypatch.setattr(chatbot, "_groq_reply", lambda *a: "")
    monkeypatch.setattr(chatbot, "_anthropic_reply", lambda *a: "claude answer")
    assert _ask(app) == "claude answer"


def test_every_provider_failing_falls_back_to_mock(app, keys, mock_reply, monkeypatch):
    keys(groq="g", anthropic="a")
    monkeypatch.setattr(chatbot, "_groq_reply", _raise)
    monkeypatch.setattr(chatbot, "_anthropic_reply", _raise)
    assert _ask(app) == "mock answer"


def test_only_configured_providers_are_tried(app, keys, monkeypatch):
    keys(anthropic="a")
    monkeypatch.setattr(chatbot, "_groq_reply", _raise)  # no Groq key: never called
    monkeypatch.setattr(chatbot, "_anthropic_reply", lambda *a: "claude answer")
    assert _ask(app) == "claude answer"


def test_no_keys_uses_mock(app, keys, mock_reply):
    keys()
    assert _ask(app) == "mock answer"
