"""Tests for the quiz generator (services/quiz_service.py + route).

The LLM call is faked; these cover input validation, JSON parsing/coercion,
graceful failure without a key, and the route's auth + error handling.
"""
import pytest

from services import quiz_service
from services.quiz_service import QuizError, _extract_json, _validate, generate_quiz

NOTES = ("Photosynthesis is the process by which green plants convert light "
         "energy into chemical energy stored in glucose. It occurs in the "
         "chloroplasts and requires carbon dioxide and water.")

GOOD_JSON = {
    "questions": [
        {"q": "Where does photosynthesis occur?",
         "options": ["Nucleus", "Chloroplast", "Mitochondria", "Ribosome"],
         "answer": 1, "explanation": "Chloroplasts contain chlorophyll."},
    ]
}


def test_extract_json_handles_code_fences():
    raw = '```json\n{"questions": []}\n```'
    assert _extract_json(raw) == {"questions": []}


def test_validate_accepts_good_quiz():
    qs = _validate(GOOD_JSON)
    assert len(qs) == 1
    assert qs[0]["answer"] == 1
    assert len(qs[0]["options"]) == 4


def test_validate_drops_malformed_questions():
    data = {"questions": [
        {"q": "ok", "options": ["a", "b", "c", "d"], "answer": 0},
        {"q": "bad — 3 options", "options": ["a", "b", "c"], "answer": 0},
        {"q": "bad — answer oob", "options": ["a", "b", "c", "d"], "answer": 9},
    ]}
    qs = _validate(data)
    assert len(qs) == 1


def test_validate_rejects_empty():
    with pytest.raises(QuizError):
        _validate({"questions": []})


def test_generate_requires_min_length(app):
    with app.test_request_context():
        with pytest.raises(QuizError):
            generate_quiz("too short")


def test_generate_without_key_is_graceful(app, monkeypatch):
    with app.test_request_context():
        monkeypatch.setitem(app.config, "GROQ_API_KEY", "")
        with pytest.raises(QuizError) as e:
            generate_quiz(NOTES)
        assert "GROQ_API_KEY" in str(e.value)


def test_generate_happy_path(app, monkeypatch):
    import json
    with app.test_request_context():
        monkeypatch.setitem(app.config, "GROQ_API_KEY", "fake")
        monkeypatch.setattr(quiz_service, "_call_groq",
                            lambda system, material, n: json.dumps(GOOD_JSON))
        qs = generate_quiz(NOTES, n=1)
        assert qs[0]["q"].startswith("Where")


# ── Route ───────────────────────────────────────────────────────────────────────

# ── File upload ─────────────────────────────────────────────────────────────────

class _Upload:
    """Minimal stand-in for a Werkzeug FileStorage."""
    def __init__(self, filename, data):
        self.filename = filename
        self._data = data
    def read(self):
        return self._data


def test_extract_txt():
    from services.quiz_service import extract_text_from_upload
    text, err = extract_text_from_upload(_Upload("notes.txt", NOTES.encode()))
    assert err is None
    assert "Photosynthesis" in text


def test_extract_rejects_unknown_ext():
    from services.quiz_service import extract_text_from_upload
    text, err = extract_text_from_upload(_Upload("malware.exe", b"MZ"))
    assert text is None and "supported" in err


def test_extract_rejects_oversize():
    from services.quiz_service import extract_text_from_upload, MAX_UPLOAD_BYTES
    text, err = extract_text_from_upload(_Upload("big.txt", b"x" * (MAX_UPLOAD_BYTES + 1)))
    assert text is None and "too large" in err.lower()


def test_extract_real_pdf():
    """Round-trip a generated PDF through pypdf extraction."""
    import io
    from pypdf import PdfWriter, PdfReader  # noqa: F401
    try:
        from reportlab.pdfgen import canvas  # optional; skip if unavailable
    except Exception:
        import pytest
        pytest.skip("reportlab not installed")
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Mitochondria are the powerhouse of the cell.")
    c.save()
    from services.quiz_service import extract_text_from_upload
    text, err = extract_text_from_upload(_Upload("cell.pdf", buf.getvalue()))
    assert err is None
    assert "Mitochondria" in text


def test_generate_endpoint_accepts_file_upload(app, client, make_user, login, monkeypatch):
    import io
    import json
    make_user("quizfile@example.com")
    login("quizfile@example.com")
    monkeypatch.setitem(app.config, "GROQ_API_KEY", "fake")
    monkeypatch.setattr(quiz_service, "_call_groq",
                        lambda system, material, n: json.dumps(GOOD_JSON))
    data = {"count": "3", "file": (io.BytesIO(NOTES.encode()), "notes.txt")}
    resp = client.post("/quiz/generate", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert len(resp.get_json()["questions"]) == 1


def test_quiz_page_requires_login(client):
    assert client.get("/quiz").status_code == 302


def test_quiz_page_renders(client, make_user, login):
    make_user("quiz@example.com")
    login("quiz@example.com")
    assert "Quiz Generator" in client.get("/quiz").get_data(as_text=True)


def test_generate_endpoint_returns_error_without_key(app, client, make_user, login, monkeypatch):
    make_user("quizgen@example.com")
    login("quizgen@example.com")
    monkeypatch.setitem(app.config, "GROQ_API_KEY", "")
    resp = client.post("/quiz/generate", json={"material": NOTES})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_generate_endpoint_happy_path(app, client, make_user, login, monkeypatch):
    import json
    make_user("quizgen2@example.com")
    login("quizgen2@example.com")
    monkeypatch.setitem(app.config, "GROQ_API_KEY", "fake")
    monkeypatch.setattr(quiz_service, "_call_groq",
                        lambda system, material, n: json.dumps(GOOD_JSON))
    resp = client.post("/quiz/generate", json={"material": NOTES, "count": 1})
    assert resp.status_code == 200
    assert len(resp.get_json()["questions"]) == 1
