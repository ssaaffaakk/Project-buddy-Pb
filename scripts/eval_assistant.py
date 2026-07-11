"""
Live end-to-end eval for the SSM-1.0 assistant.

Sends a golden set of questions through the real provider chain (Groq → the
same code path production uses, including RAG context and tools) and scores
each reply against expected keywords. Deterministic retrieval/tool evals run
in CI (tests/test_assistant.py); this script measures the full LLM loop and
therefore needs GROQ_API_KEY in .env.

Usage:
    python -m scripts.eval_assistant
Exit code 0 when the pass rate is >= PASS_THRESHOLD.
"""

import sys

PASS_THRESHOLD = 0.7

# (question, [any of these keywords must appear in the reply])
GOLDEN = [
    ("Who are you?", ["ssm-1.0", "ssm 1.0", "projectbuddy"]),
    ("Find me an open project about machine learning", ["/project/", "project"]),
    ("What deadlines do I have coming up?", ["deadline", "no ", "project"]),
    ("Recommend some projects for me", ["project", "recommend", "fit"]),
    ("How should I split work in a 4-person team?", ["team", "task", "role", "milestone"]),
]


def main():
    from app import create_app
    from models import User
    from routes.chatbot import _get_reply

    app = create_app()
    with app.app_context():
        if not app.config.get("GROQ_API_KEY"):
            print("SKIP: GROQ_API_KEY not set — live eval needs a provider key.")
            sys.exit(0)

        user = User.query.filter(User.role != "admin").first()
        if not user:
            print("SKIP: no non-admin user in the database to evaluate as.")
            sys.exit(0)

        passed = 0
        with app.test_request_context():
            for question, keywords in GOLDEN:
                try:
                    reply = _get_reply([], question, user.id)
                except Exception as e:
                    print(f"FAIL  {question!r} → provider error: {e}")
                    continue
                ok = any(k.lower() in reply.lower() for k in keywords)
                passed += ok
                print(f"{'PASS' if ok else 'FAIL'}  {question!r}")
                print(f"      → {reply[:140]!r}")

        rate = passed / len(GOLDEN)
        print(f"\npass rate: {passed}/{len(GOLDEN)} ({rate:.0%}, threshold {PASS_THRESHOLD:.0%})")
        sys.exit(0 if rate >= PASS_THRESHOLD else 1)


if __name__ == "__main__":
    main()
