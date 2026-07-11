**What It Is**
A university team-matching web app for IUS students. Students post projects, others apply, teams form. It also has community posts, study groups, real-time chat, and an AI chatbot. Built solo as a full-stack Flask project.
**Stack:** Python 3.9, Flask 3.1, SQLAlchemy 2.0, SQLite (dev) / Postgres (prod), Flask-SocketIO + eventlet, Gunicorn, Flask-Migrate.

---

**Architecture**
Application factory pattern (`create_app()` in `app.py`). Extensions are initialized in `extensions.py` and bound to the app inside `create_app()` — avoids circular imports. Routes are split into 9 blueprints, each handling one domain. Production entry point is `wsgi.py` — calls `eventlet.monkey_patch()` before any other imports, then picks the right config class based on `FLASK_ENV`. Config is split into 3 classes: `DevelopmentConfig`, `TestingConfig`, `ProductionConfig`. `SECRET_KEY` raises a `ValueError` at startup if missing from `.env`.

---

**Database & Models**
25 models, fully on SQLAlchemy 2.0 `mapped_column` / `Mapped[type]` syntax — no legacy `Column()` anywhere. All datetime defaults are timezone-aware. Notable constraints:
- `Feedback.rating` has a `CheckConstraint("rating BETWEEN 1 AND 5")` enforced at DB level
- `CommunityLike`, `ProjectVote`, `StudyGroupMember` all have `UniqueConstraint` to prevent double-likes/votes at DB level
- FK relationships use `cascade="all, delete-orphan"` where appropriate

Schema migrations handled by Flask-Migrate (Alembic).

---

**Security**
HTTP Security Headers on every response:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN` + `frame-ancestors 'none'` (double-blocks clickjacking)
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy` — `default-src self`, scripts allowed from jsdelivr CDN only, no wildcards
- `Strict-Transport-Security` — production only, HSTS with preload, 2-year max-age
- `Server` header removed (no fingerprinting)

Authentication:
- Passwords hashed with `pbkdf2:sha256` via Werkzeug
- Login rate-limited: 20/min, 100/hour. Registration: 10/hour. Admin login: 10/min, 30/hour
- Banned users are blocked before any session is created
- Password reset tokens: `secrets.token_hex(32)`, expire in 1 hour, deleted after use
- Forgot-password returns the same flash message whether the email exists or not — no user enumeration

GitHub OAuth:
- CSRF prevented with an HMAC-signed state token (timestamp + HMAC-SHA256). No session dependency. `hmac.compare_digest` used for constant-time comparison
- GitHub users get a random 64-char hex `password_hash` that can never verify against `check_password()` — no accidental password login path

CSRF:
- Flask-WTF `CSRFProtect` is global. CSRF failures return a user-friendly flash+redirect instead of a raw 400
- `WTF_CSRF_SSL_STRICT = True` in production

Session cookies:
- `__Host-` prefix in production (strongest cookie binding)
- `HttpOnly=True`, `SameSite=Lax`, `Secure=True` in prod
- Session lifetime: 8 hours

Rate Limiting:
- Flask-Limiter with global defaults (200/day, 50/hour per IP) and tighter per-route limits on auth endpoints
- Rate limit exceeded returns a flash+redirect, not raw JSON

Access control:
- `admin_required` and `instructor_required` decorators wrap privileged routes
- Admin panel badge counts injected via context processor, only when the current user is admin

---

**Chatbot (Multi-Provider AI)**
Provider waterfall:
1. Groq (primary) — free tier, Llama 3.1 8B, ~14,400 req/day
2. Anthropic Claude (fallback) — if no Groq key
3. Keyword mock (last resort) — zero-dependency fallback

All three share the same interface — swapping providers is invisible to the route. Conversation history persisted in `ChatbotSession` rows, last 20 turns sent as context on every request, old rows beyond 40 deleted in the same transaction. Message length capped at 1000 chars server-side. Any provider exception degrades to a friendly error string instead of a 500.

---

**Voice Chat (WebRTC over SocketIO)**
Signaling server only — doesn't carry audio, just relays the handshake.
1. User joins → server puts them in SocketIO room `voice_{group_id}`, sends list of existing participants
2. Existing participants get `voice_user_joined` and initiate WebRTC offers
3. SDP offers/answers and ICE candidates are relayed through the server
4. On disconnect or leave, they're removed and peers are notified

---

**File Uploads (Community & Study Groups)**
4 layers of validation before writing a file:
1. Extension whitelist
2. Content-Type header check
3. Magic-byte sniff — reads first 12 bytes and checks actual file signatures. A `.jpg` with a PHP script inside gets rejected here
4. Size check — reads to EOF, rejects above 50MB

Saved filenames: `{random_token}_{secure_filename(original)}` — not guessable, not enumerable. Study groups support a broader set (code files, archives, docs, audio/video) up to 25MB.

---

**Projects — Business Logic**
- 3-project cap per user (checked on both create and apply)
- Apply guards — can't apply to your own project, can't apply twice, can't apply to closed/completed/full projects
- Auto-closes the listing when the team fills up
- Feedback rules — both giver and receiver must have been active members, can't rate yourself, one feedback per giver-receiver-project pair
- Endorsements — you can only endorse someone you've completed at least one project with (enforced with a subquery join)
- Badge hooks fire after `complete_project` and after `endorse_skill`

---

**Badge Service**
Three badges, event-driven, idempotent — `already_has_badge()` prevents duplicates. Rules live in a dict so adding a new badge is a one-liner. No cron job needed.

---

**Admin Panel**
List reports, warn user, ban user, dismiss report, delete project, platform stats, view AI chatbot logs per user, send messages to users.