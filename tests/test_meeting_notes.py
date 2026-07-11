"""Tests for AI meeting notes (services/meeting_notes.py + transcribe route).

The Groq audio + chat calls are faked; these cover validation, graceful
no-key behavior, and the route's membership gate + note-append.
"""
import io

import pytest

from extensions import db
from models import StudyGroup, StudyGroupMember, StudyGroupNote, User
from services import meeting_notes
from services.meeting_notes import MeetingNotesError, transcribe_and_summarize


def test_requires_key(app, monkeypatch):
    with app.test_request_context():
        monkeypatch.setitem(app.config, "GROQ_API_KEY", "")
        with pytest.raises(MeetingNotesError) as e:
            transcribe_and_summarize(b"x" * 5000)
        assert "GROQ_API_KEY" in str(e.value)


def test_rejects_empty_audio(app, monkeypatch):
    with app.test_request_context():
        monkeypatch.setitem(app.config, "GROQ_API_KEY", "fake")
        with pytest.raises(MeetingNotesError):
            transcribe_and_summarize(b"")


def test_rejects_too_short_transcript(app, monkeypatch):
    with app.test_request_context():
        monkeypatch.setitem(app.config, "GROQ_API_KEY", "fake")
        monkeypatch.setattr(meeting_notes, "_transcribe", lambda a, f: "hi")
        with pytest.raises(MeetingNotesError):
            transcribe_and_summarize(b"x" * 5000)


def test_happy_path(app, monkeypatch):
    with app.test_request_context():
        monkeypatch.setitem(app.config, "GROQ_API_KEY", "fake")
        monkeypatch.setattr(meeting_notes, "_transcribe",
                            lambda a, f: "We agreed Ali writes the API by Friday.")
        monkeypatch.setattr(meeting_notes, "_summarize",
                            lambda t: "Summary: API work assigned.\nAction items:\n- Ali: API by Friday")
        summary, transcript = transcribe_and_summarize(b"x" * 5000)
        assert "Action items" in summary
        assert "Ali" in transcript


# ── Route ───────────────────────────────────────────────────────────────────────

def _group_with_member(app, member_email):
    with app.app_context():
        u = User(first_name="M", last_name="e", email=member_email, role="student")
        u.set_password("Test1234!")
        db.session.add(u)
        db.session.flush()
        g = StudyGroup(name="G", creator_id=u.id)
        db.session.add(g)
        db.session.flush()
        db.session.add(StudyGroupMember(group_id=g.id, user_id=u.id))
        db.session.commit()
        return g.id


def _audio():
    return {"audio": (io.BytesIO(b"\x1aE\xdf\xa3" + b"0" * 4000), "meeting.webm", "audio/webm")}


def test_route_blocks_non_member(app, client, make_user, login):
    gid = _group_with_member(app, "mn-member@example.com")
    make_user("mn-outsider@example.com")
    login("mn-outsider@example.com")
    resp = client.post(f"/study-groups/{gid}/transcribe",
                       data=_audio(), content_type="multipart/form-data")
    assert resp.status_code == 403


def test_route_requires_audio(app, client, login):
    gid = _group_with_member(app, "mn-m2@example.com")
    login("mn-m2@example.com")
    resp = client.post(f"/study-groups/{gid}/transcribe",
                       data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_route_appends_summary_to_notes(app, client, login, monkeypatch):
    gid = _group_with_member(app, "mn-m3@example.com")
    login("mn-m3@example.com")
    monkeypatch.setattr(
        "services.meeting_notes.transcribe_and_summarize",
        lambda audio, filename: ("Summary: we planned the sprint.\nAction items:\n- None", "transcript"),
    )
    resp = client.post(f"/study-groups/{gid}/transcribe",
                       data=_audio(), content_type="multipart/form-data")
    assert resp.status_code == 200
    assert "planned the sprint" in resp.get_json()["summary"]
    with app.app_context():
        note = StudyGroupNote.query.filter_by(group_id=gid).first()
        assert note is not None
        assert "AI meeting notes" in note.content
        assert "planned the sprint" in note.content
