# ProjectBuddy: A Reputation-Driven Platform for University Project Collaboration

**Author:** Safak Surmeli  
**Date:** June 2026  
**Version:** 1.0  
**License:** MIT  

---

## Abstract

University students routinely form project teams through unstructured channels — WhatsApp groups, hallway conversations, or random assignment — with no visibility into a potential partner's skills, reliability, or track record. The result is predictable: uneven contribution, missed deadlines, and grades that reflect team dysfunction rather than individual capability.

ProjectBuddy is a web platform that replaces this ad-hoc process with structured team formation, skill-based matching, and a persistent reputation system. Students post project listings with required skills and deadlines, apply to join teams that match their interests, and — after completion — rate teammates and endorse specific skills. Every interaction leaves a verifiable trail: ratings, endorsements, and badges that future teammates and instructors can inspect.

This paper describes the problem space, the platform's design and architecture, and evaluates the system against its stated goals.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Problem Statement](#2-problem-statement)
3. [Related Work](#3-related-work)
4. [System Design](#4-system-design)
5. [Architecture](#5-architecture)
6. [Key Algorithms and Services](#6-key-algorithms-and-services)
7. [Security Architecture](#7-security-architecture)
8. [Case Study](#8-case-study)
9. [Evaluation](#9-evaluation)
10. [Limitations and Future Work](#10-limitations-and-future-work)
11. [Conclusion](#11-conclusion)
12. [References](#12-references)

---

## 1. Introduction

Collaborative project work is a cornerstone of university education. Courses in computer science, engineering, business, and the sciences routinely assign team-based deliverables — capstone projects, lab reports, design challenges — that require students to coordinate across skill sets and schedules. The pedagogical rationale is sound: real-world work is collaborative, and students benefit from practicing communication, task division, and conflict resolution in a structured environment.

The *mechanism* for forming these teams, however, has not kept pace with the complexity of the work. At most universities, team formation still relies on informal channels: a message in a class WhatsApp group ("anyone want to team up?"), a post on a course forum, or — in the worst case — random instructor assignment. None of these methods give students meaningful information about a potential partner's technical skills, work habits, or reliability.

ProjectBuddy was built to solve this problem. It provides:

- **Structured project listings** with required skills, topic tags, team size caps, and deadlines.
- **Interest-based matching** that surfaces relevant projects to each student automatically.
- **A reputation layer** — peer ratings, skill endorsements, and achievement badges — that makes contribution history visible and persistent across semesters.
- **Built-in collaboration tools** — real-time team chat, study groups, WebRTC voice rooms, and an AI assistant — so teams can work without fragmenting across external platforms.
- **Administrative oversight** — moderation, reporting, analytics, and live support chat for platform governance.

The platform is live at [https://project-buddy-pb.onrender.com](https://project-buddy-pb.onrender.com) and the source code is publicly available under the MIT license.

---

## 2. Problem Statement

### 2.1 The Information Asymmetry Problem

When a student posts "looking for a partner for the database project" in a group chat, they are making a selection decision with almost zero relevant information. They cannot see:

- What projects the respondent has completed before.
- Whether previous teammates rated them highly or poorly.
- Which specific technical skills they possess and at what level.
- Whether they have a pattern of meeting or missing deadlines.

This information asymmetry is the root cause of most team dysfunction. A student who consistently underdelivers can simply move to a new group chat and start fresh — there is no persistent record of past performance.

### 2.2 The Accountability Gap

Even when teams form successfully, there is typically no structured mechanism for post-project accountability. Instructors see a final deliverable but cannot easily determine who contributed what. Peer evaluation forms, when they exist, are one-time paper exercises disconnected from future team formation.

### 2.3 The Fragmentation Problem

A typical university project team uses:
- WhatsApp or Telegram for general communication
- Google Docs or Notion for documentation
- GitHub for code
- Email for instructor communication
- Zoom or Discord for voice calls

This fragmentation creates overhead, makes it harder for instructors to monitor progress, and means that no single platform captures a holistic view of a student's collaborative activity.

### 2.4 The Commitment Overload Problem

Without enforcement, high-performing students are often recruited into too many simultaneous projects, leading to burnout and declining quality. Conversely, less visible students struggle to find any team at all.

---

## 3. Related Work

| Platform | Strengths | Gaps |
|----------|-----------|------|
| **GitHub** | Code hosting, pull requests, contribution graphs | No team-matching, no peer ratings, not designed for academic workflows |
| **LinkedIn** | Professional profiles, skill endorsements | Not academic-focused, no project matching, endorsements are unverified |
| **Piazza / Ed Discussion** | Course Q&A, instructor integration | No team formation, no reputation system, read-only interaction model |
| **Discord / Slack** | Real-time communication, channels | No structured listings, no matching, no accountability layer |
| **TeamUp (academic tools)** | Some offer random assignment or preference-based matching | Typically instructor-controlled, no student-facing reputation, no post-project feedback loop |

ProjectBuddy occupies a gap in this landscape: it combines the *listing and matching* functionality of a job board with the *reputation and accountability* mechanisms of a professional network, purpose-built for the academic project lifecycle.

---

## 4. System Design

### 4.1 Core Entities

The data model comprises 25 SQLAlchemy 2.0 models organised around five domains:

**Identity and Reputation**
- `User` — account with role (student / instructor / admin), profile, skills, interests, and courses.
- `Feedback` — per-project peer rating (1–5 scale, enforced by database-level `CheckConstraint`).
- `Endorsement` — skill-specific endorsement, gated by shared project completion.
- `Badge` / `UserBadge` — achievement milestones (e.g., "First Step" for completing a first project, "Expert" for receiving 10 endorsements).

**Project Lifecycle**
- `Project` — listing with title, description, required skills, topic tags, team size, course, deadline, and status (open → closed → completed).
- `ProjectMember` — team membership with soft-delete (removed flag + timestamp) for audit trail.
- `Application` — join request with status (pending / accepted / rejected) and optional message.
- `ProjectVote` — community upvote/downvote on project listings.

**Communication**
- `ProjectMessage` — per-project team chat.
- `Chat` / `ChatMessage` — user-to-admin support channel.
- `StudyGroup` / `StudyGroupMember` / `StudyGroupMessage` — topic-based study rooms with real-time chat and voice.
- `CommunityPost` / `CommunityComment` / `CommunityLike` — social feed for ideas, updates, and questions.
- `Notification` — in-app notification feed for applications, comments, mentions, and moderation events.

**AI and Assistance**
- `ChatbotSession` — per-user conversation history for the built-in AI assistant (last 20 turns retained).

**Security and Administration**
- `PasswordReset` — token-based password recovery with configurable expiry.
- `Report` — user/project reports with moderation status and resolution tracking.

### 4.2 User Roles and Permissions

| Role | Capabilities |
|------|-------------|
| **Student** | Browse/apply to projects (max 3 active), post to community, join study groups, give/receive feedback, earn badges |
| **Instructor** | All student capabilities + post projects, manage team members, give instructor-weighted feedback |
| **Admin** | Full platform access: user management (warn, ban, activate), report handling, live support chat, analytics, chatbot log inspection |

Role assignment is automatic: registration with a faculty-domain email address grants the instructor role; all others default to student. Admin accounts are provisioned via environment configuration.

### 4.3 Key Workflows

**Team Formation Flow:**
1. Owner posts a project with title, description, 5 topic tags, required skills, team size, course, and deadline.
2. The recommendation engine surfaces the project to students whose interest tags overlap with the project's topic tags (see Section 6.1).
3. Interested students apply with an optional message.
4. Owner reviews applications and accepts or rejects each one.
5. On acceptance, the applicant becomes a `ProjectMember`. If the team reaches capacity, the listing auto-closes.
6. A hard cap of 3 active projects per student prevents commitment overload.

**Reputation Flow:**
1. Owner marks the project as completed (or the deadline checker auto-completes it after the deadline passes).
2. Teammates rate and review each other via peer feedback (1–5 scale + optional comment).
3. Teammates endorse specific skills of their collaborators — but only skills the receiver has listed, and only after sharing a completed project.
4. Badges are awarded automatically when milestones are reached (1 completed project, 5 completed projects, 10 endorsements received).
5. All feedback, endorsements, and badges appear on the user's public profile, visible to anyone considering them for a future project.

---

## 5. Architecture

### 5.1 Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9, Flask 3.1 |
| ORM | SQLAlchemy 2.0 (Mapped types) |
| Database | SQLite (development) / PostgreSQL (production) |
| Migrations | Flask-Migrate (Alembic) |
| Real-time | Flask-SocketIO + eventlet (WebSocket) |
| Voice | WebRTC peer-to-peer with SocketIO signaling |
| Authentication | Flask-Login, GitHub OAuth (HMAC-signed state) |
| Email | Brevo HTTP API (transactional) |
| AI | Groq API (Llama 3) → Anthropic API (Claude) → built-in keyword fallback |
| File Storage | Local disk (dev) / AWS S3 (prod) with optional CloudFront CDN |
| Scheduling | OS-thread-based scheduler (1-hour interval) for deadline auto-completion |
| Rate Limiting | Flask-Limiter with Redis backend (prod) / in-memory (dev) |
| Deployment | Render (hosting), PostgreSQL (managed DB), Redis (rate limiting + SocketIO + voice state) |

### 5.2 Application Factory Pattern

The application uses Flask's factory pattern (`create_app()`) to support multiple configurations (development, testing, production) from a single codebase. Extensions are initialised without binding to a specific app instance, enabling clean test isolation.

### 5.3 Blueprint Organisation

Business logic is split across 11 Flask Blueprints, each responsible for a single domain:

| Blueprint | URL Prefix | Responsibility |
|-----------|-----------|---------------|
| `auth` | `/auth` | Registration, login, GitHub OAuth, password reset |
| `main` | `/` | Dashboard, profiles, avatar upload |
| `projects` | `/projects` | CRUD, applications, feedback, endorsements |
| `users` | `/users` | Search, public profiles |
| `chat` | `/chat` | User-admin support |
| `community` | `/community` | Social feed, media upload, comments, likes |
| `study_groups` | `/study-groups` | Groups, real-time chat, file sharing |
| `voice` | (SocketIO) | WebRTC signaling |
| `chatbot` | `/chatbot` | AI assistant |
| `admin` | `/admin` | Moderation, analytics |
| `email` | (internal) | Transactional email |

### 5.4 Real-Time Communication

Flask-SocketIO provides WebSocket-based real-time messaging for:
- Project team chat
- Study group chat
- Admin support chat
- WebRTC voice signaling

In production, a Redis message queue ensures events are broadcast across multiple Gunicorn workers. Voice room state (which users are in which room) is stored in Redis with a 24-hour TTL, falling back to an in-process dictionary in development.

### 5.5 Eventlet Considerations

The application uses `eventlet` as its async I/O layer for SocketIO compatibility. This introduces a specific constraint: `eventlet.sleep()` and any hub-dependent call cannot be made from the main greenlet before the hub loop starts. The deadline scheduler and startup tasks (schema migration, badge seeding, admin sync, mock data) therefore run on genuine OS threads obtained via `eventlet.patcher.original('threading')`, completely outside eventlet's hub.

---

## 6. Key Algorithms and Services

### 6.1 Recommendation Engine

The recommendation service matches students to projects through interest-tag expansion and set intersection:

1. **Tag Normalisation:** All tags are lowercased and whitespace-trimmed for consistent comparison.

2. **Interest Expansion:** Each user interest tag is expanded into a set of related topic categories via a static mapping. For example, `"python"` expands to `{"backend", "data", "ai / ml"}`, and `"cybersecurity"` expands to `{"security", "backend"}`.

3. **Candidate Filtering:** Projects where the user is already an owner, member, or applicant are excluded.

4. **Scoring:** For each remaining open project, the algorithm computes the size of the intersection between the user's expanded interest set and the project's normalised topic tags. Projects with zero overlap are discarded.

5. **Ranking:** Results are sorted by match count (descending), then by creation date (newest first) as a tiebreaker.

This approach is intentionally simple and transparent. It avoids collaborative filtering or machine learning, which would require usage data that a new platform does not have. The static mapping can be extended as the platform grows.

### 6.2 Badge Service

Badges are awarded through an event-driven check triggered after two events: project completion and skill endorsement. The service evaluates three rules:

| Badge | Condition |
|-------|-----------|
| First Step | ≥ 1 completed project |
| Veteran | ≥ 5 completed projects |
| Expert | ≥ 10 endorsements received |

The check is idempotent — it queries current counts and only awards badges the user does not already have. This design allows new badge rules to be added without migrating historical data.

### 6.3 Deadline Checker

An OS-thread-based scheduler runs every hour and automatically marks projects as completed if their deadline has passed. This prevents stale listings from cluttering the platform and ensures that post-completion workflows (feedback, endorsements, badges) can proceed even if the project owner forgets to manually close the project.

### 6.4 AI Chatbot

The chatbot provides in-platform assistance with a three-tier provider fallback:
1. **Groq API** (Llama 3, free tier) — primary provider.
2. **Anthropic API** (Claude) — secondary if Groq key is not configured.
3. **Keyword-based mock responses** — built-in fallback requiring no external API.

Conversation history (last 20 turns) is persisted per user and included in API calls for contextual responses. Rate limiting (20 requests/minute, 200/day) prevents abuse.

### 6.5 File Storage Abstraction

A storage service abstracts local disk and AWS S3 behind a common interface (`save`, `delete`, `download_url`). In development, files are saved to `static/uploads/`; in production, they are uploaded to S3 with optional CloudFront CDN URLs. The abstraction is initialised once at module import time as a singleton.

---

## 7. Security Architecture

Security is implemented as defense-in-depth across multiple layers:

### 7.1 Authentication

- **Passwords:** Hashed with `pbkdf2:sha256` via Werkzeug. Registration enforces minimum 8 characters, at least one digit, and at least one special character.
- **Sessions:** `HttpOnly`, `SameSite=Lax`, 8-hour lifetime. Production uses `Secure` flag. Cookie names use the `__Host-` prefix in environments where it is supported (requires HTTPS, no Domain attribute).
- **GitHub OAuth:** State parameter is HMAC-SHA256 signed with a timestamp, verified with `hmac.compare_digest` — constant-time comparison to prevent timing attacks. No session dependency, so it survives cross-site redirects reliably.
- **Password Reset:** Token-based with configurable expiry (default 24 hours). Old tokens are deleted before issuing new ones to prevent accumulation.

### 7.2 Authorization

- `@login_required` on all authenticated routes.
- `@admin_required` decorator on all admin routes — checks both authentication and role.
- Project operations (update, close, complete, accept/reject applications) verify ownership.
- Endorsements require a shared completed project — preventing drive-by endorsement spam.

### 7.3 Input Validation and Output Safety

- **CSRF:** Global protection via Flask-WTF with 1-hour token validity. Failures redirect with a user-friendly flash message rather than a raw 400 error.
- **Content Security Policy:** Per-request nonce generated with `secrets.token_urlsafe(16)`. Script and style sources restricted to `'self'` and specific CDNs. `object-src 'none'`, `base-uri 'self'`, `frame-ancestors 'none'`.
- **File Uploads:** Four-layer validation — extension whitelist, Content-Type header check, magic-byte sniffing (JPEG, PNG, WebP, GIF headers), and size cap (50 MB). Filenames are sanitised with `werkzeug.utils.secure_filename` and randomised with `secrets.token_hex`.

### 7.4 Transport and Headers

- **HSTS:** `max-age=63072000; includeSubDomains; preload` in production.
- **X-Content-Type-Options:** `nosniff`
- **X-Frame-Options:** `SAMEORIGIN`
- **Referrer-Policy:** `strict-origin-when-cross-origin`
- **Permissions-Policy:** Camera, geolocation, payment, and USB disabled. Microphone allowed for WebRTC voice.
- **Cross-Origin-Opener-Policy:** `same-origin`
- **Cross-Origin-Resource-Policy:** `same-origin`
- Server fingerprint header removed on every response.

### 7.5 Rate Limiting

- Global defaults: 200 requests/day, 50/hour per IP.
- Login: 20/minute, 100/hour.
- Admin login: 10/minute, 30/hour.
- Registration: 10/hour.
- Chatbot: 20/minute, 200/day.
- Production uses Redis as the rate-limit backend for consistency across multiple workers.

### 7.6 Privacy

- User search does not expose email addresses.
- Public profiles are login-gated — no unauthenticated scraping.
- Password reset responses do not reveal whether an email exists in the system ("If an account exists with that email...").

---

## 8. Case Study

### 8.1 Why I Built This

> Last semester, a project I worked on got rejected. Not because of my work — but because my partner didn't deliver. The semester before that, I couldn't find a partner at all, and my professor refused to accept a solo submission.
>
> Two projects. Two failures. Neither one was about my ability. Both were about a broken system for forming teams.
>
> Finding project partners at university still means posting "anyone want to join?" in a WhatsApp group. You pick someone based on nothing — no visibility into their skills, their work ethic, or how they perform under pressure. When that goes wrong, it doesn't just slow you down. It costs you grades.
>
> I went to my professor, explained the problem, and told him I was going to build the solution. He didn't just listen — he let me submit it as my project.
>
> So I built ProjectBuddy. Not a tutorial clone. Not a homework assignment. A real platform, built out of frustration, designed to make sure no student ever loses marks because of a partner mismatch again.
>
> The smart matching engine surfaces projects that fit your skills. The reputation system means every completed project leaves a trail — ratings, endorsements, badges. Next time, you don't pick a stranger. You pick someone with a track record.
>
> I didn't want to work with just anyone anymore. So I built the tool that makes sure no one has to.
>
> I build things because I run into problems and refuse to accept that they can't be solved.

### 8.2 Design Decisions Driven by the Problem

Each major feature maps directly to a pain point observed in real university project work:

| Pain Point | Feature Response |
|-----------|-----------------|
| "I picked a partner who didn't contribute" | Peer feedback (1–5 rating) + public profile history |
| "I couldn't tell if they had the right skills" | Skill endorsements (gated by shared project completion) |
| "I'm in too many projects and can't keep up" | Hard cap of 3 active projects per student |
| "I can't find projects that match my interests" | Interest-based recommendation engine |
| "Our team chat is scattered across 4 apps" | Built-in project chat, study groups, voice rooms |
| "The deadline passed and nobody noticed" | Auto-complete scheduler (hourly check) |
| "There's no incentive to be a good teammate" | Badge system rewarding completion and endorsements |
| "Abusive or inactive users face no consequences" | Admin moderation: warnings, bans, report queue |

### 8.3 Implementation Timeline

The platform was built as a solo project over the course of one academic semester. Key milestones:

1. **Weeks 1–2:** Problem analysis, requirements gathering, data model design.
2. **Weeks 3–5:** Core backend — user auth, project CRUD, application workflow, database schema.
3. **Weeks 6–8:** Reputation system (feedback, endorsements, badges), recommendation engine.
4. **Weeks 9–10:** Real-time features — SocketIO chat, WebRTC voice rooms.
5. **Weeks 11–12:** Community feed, study groups, AI chatbot, admin panel.
6. **Weeks 13–14:** Security hardening (CSP, CSRF, rate limiting, file upload validation), deployment to Render, documentation.

### 8.4 Deployment

The production deployment runs on Render's free tier:
- **Web service:** Gunicorn with eventlet workers, behind Render's reverse proxy.
- **Database:** Managed PostgreSQL instance.
- **Redis:** Used for rate limiting, SocketIO message queue, and voice room state.
- **File storage:** AWS S3 with optional CloudFront CDN.
- **Email:** Brevo HTTP API for transactional email (bypasses cloud SMTP restrictions).

The platform handles cold starts gracefully — the first request after inactivity takes approximately 30 seconds as the Render instance spins up, applies migrations, seeds default data, and starts the scheduler.

---

## 9. Evaluation

### 9.1 Functional Completeness

The platform was evaluated against its original requirements:

| Requirement | Status | Notes |
|------------|--------|-------|
| Post projects with skills, tags, deadline | Complete | 5 topic tags required, skills optional |
| Browse and filter open projects | Complete | Filterable list + recommendation engine |
| Apply to join projects | Complete | With ownership, membership, and cap checks |
| Accept/reject applications | Complete | Owner-only, with auto-close on team full |
| Rate teammates after completion | Complete | 1–5 scale with DB-level constraint |
| Endorse specific skills | Complete | Gated by shared completed project |
| Badge system | Complete | 3 badges with idempotent award logic |
| Real-time team chat | Complete | SocketIO-based, per-project |
| Voice rooms | Complete | WebRTC peer-to-peer with SocketIO signaling |
| Community feed with media | Complete | Image/video upload with 4-layer validation |
| Study groups | Complete | Public/private, chat, file sharing |
| AI assistant | Complete | 3-tier provider fallback |
| Admin moderation | Complete | Warnings, bans, reports, analytics |
| Auto-complete past deadline | Complete | Hourly scheduler on OS thread |
| Max 3 active projects | Complete | Enforced on both create and apply |
| Email notifications | Complete | Password reset, application events |
| GitHub OAuth | Complete | HMAC-signed state, no session dependency |

### 9.2 Security Assessment

| Security Control | Implementation Quality |
|-----------------|----------------------|
| Password hashing | Strong — `pbkdf2:sha256` with Werkzeug defaults |
| Session management | Strong — HttpOnly, SameSite, short lifetime, Secure in prod |
| CSRF protection | Strong — global Flask-WTF, graceful failure handling |
| OAuth state | Strong — HMAC-signed, time-bounded, constant-time comparison |
| Rate limiting | Strong — per-route limits, Redis-backed in production |
| CSP | Moderate — nonces generated but `unsafe-inline` still present for legacy compatibility |
| File uploads | Strong — extension + Content-Type + magic bytes + size cap |
| SQL injection | Strong — SQLAlchemy ORM parameterises all queries |
| XSS | Strong — Jinja2 auto-escapes all template variables by default |
| Access control | Strong — decorator-based with ownership verification |
| Information disclosure | Strong — generic error messages, no email enumeration |

**Known CSP caveat:** The Content-Security-Policy header includes `'unsafe-inline'` for both scripts and styles because the frontend uses inline event handlers (`onclick=`) and inline style attributes. The CSP nonce infrastructure is in place, and removing `unsafe-inline` is a planned future improvement requiring a frontend refactor.

### 9.3 Architectural Quality

**Strengths:**
- Clean separation of concerns via Blueprints and a dedicated services layer.
- Application factory pattern enables test isolation and multiple configurations.
- SQLAlchemy 2.0 Mapped types provide type safety and IDE support.
- Eventlet threading handled correctly — startup tasks and the scheduler use real OS threads to avoid hub conflicts.
- Storage abstraction allows seamless local/S3 switching without code changes.
- Graceful degradation — chatbot falls back through three providers; storage falls back from S3 to local disk; rate limiting falls back from Redis to memory.

**Areas for improvement:**
- No automated test suite. The application was manually tested during development, but unit and integration tests would improve confidence in future changes.
- The recommendation algorithm is tag-based and does not learn from user behavior. Collaborative filtering could improve recommendations as usage data accumulates.
- No API documentation (OpenAPI / Swagger). The JSON API endpoints are undocumented beyond code comments.
- No WebSocket authentication beyond `current_user.is_authenticated` — a malicious client could potentially forge SocketIO events if they obtain a valid session cookie.

### 9.4 Scalability Considerations

| Dimension | Current State | Scaling Path |
|-----------|--------------|-------------|
| Database | SQLite (dev) / PostgreSQL (prod) | PostgreSQL handles moderate loads; read replicas for high traffic |
| Real-time | Redis message queue for multi-worker SocketIO | Horizontally scalable with additional workers |
| File storage | S3 with CloudFront | Already cloud-native; scales independently |
| Rate limiting | Redis-backed | Shared state across workers |
| Voice | WebRTC P2P (mesh topology) | Works for small groups (2–6); larger groups would need an SFU |
| Recommendation | Full table scan of open projects | Acceptable for hundreds of projects; would need indexing or caching for thousands |

### 9.5 Comparison with Initial Goals

The platform was built to ensure "no student ever loses marks because of a partner mismatch again." Evaluating against this mission:

1. **Visibility:** Achieved. Every user has a public profile showing projects, ratings, endorsements, and badges. A student evaluating a potential partner can see their track record before committing.

2. **Accountability:** Achieved. Peer feedback after project completion creates a persistent record. Poor performance is visible; good performance is rewarded with endorsements and badges.

3. **Fair matching:** Partially achieved. The recommendation engine surfaces relevant projects, and the 3-project cap prevents overcommitment. However, the system does not yet detect or prevent free-riding *during* a project — it only captures post-completion assessments.

4. **Reduced fragmentation:** Achieved. Chat, voice, file sharing, and project management are consolidated in one platform.

5. **Administrative oversight:** Achieved. The admin panel provides user management, report handling, analytics, and live support.

---

## 10. Limitations and Future Work

### 10.1 Current Limitations

- **No automated tests.** The codebase lacks unit and integration tests. Manual testing was performed during development, but regression detection depends on developer vigilance.
- **CSP `unsafe-inline`.** The nonce infrastructure exists but is not fully utilised due to inline event handlers in templates.
- **Recommendation simplicity.** Tag-based matching with a static expansion map. Does not account for schedule compatibility, past collaboration history, or geographic proximity.
- **Voice room scalability.** WebRTC mesh topology works for small groups but degrades with more than 5–6 participants. A Selective Forwarding Unit (SFU) would be needed for larger rooms.
- **No email verification.** Users can register with any email address without confirming ownership.
- **Single-institution design.** The platform assumes a single university context. Multi-institution support would require tenant isolation.

### 10.2 Planned Improvements

- **Automated test suite** — pytest with fixtures for each Blueprint, covering happy paths and edge cases.
- **CSP hardening** — refactor inline handlers to external scripts with nonce attributes, remove `unsafe-inline`.
- **Email verification** — confirmation link on registration to prevent impersonation.
- **Collaborative filtering** — learn from which projects users apply to and complete, supplementing the tag-based engine.
- **Mid-project check-ins** — periodic teammate pulse surveys during active projects to surface issues before completion.
- **Instructor dashboard** — per-course view of team formation, progress, and peer feedback for course supervisors.
- **Mobile-responsive redesign** — the current UI is functional on mobile but not optimised for touch interactions.
- **API documentation** — OpenAPI specification for all JSON endpoints.

---

## 11. Conclusion

ProjectBuddy demonstrates that the university team-formation problem can be addressed with relatively straightforward technology — a Flask web application, a relational database, and a tag-based matching algorithm — when the design is anchored in the actual pain points students experience.

The platform's core contribution is not any single feature but the *combination* of structured listings, gated reputation mechanisms, and consolidated collaboration tools into a single system. A project listing alone is a job board; peer feedback alone is a survey; chat alone is Discord. The value emerges from connecting these elements into a lifecycle: post → match → form → collaborate → complete → review → carry reputation forward.

The system is not perfect. It lacks automated tests, its recommendation engine is simplistic, and its CSP could be tighter. These are engineering debts, not design failures — they reflect the constraints of a solo developer building a working platform in one semester. The architecture is modular enough that each limitation has a clear remediation path.

The broader lesson is that tools shape behavior. When team formation is invisible and unaccountable, students optimize for convenience — picking whoever responds first. When it is visible and reputation-bearing, they optimize for quality — picking teammates with a demonstrated track record. ProjectBuddy provides the infrastructure for the second mode.

---

## 12. References

1. Oakley, B., Felder, R.M., Brent, R., & Elhajj, I. (2004). "Turning Student Groups into Effective Teams." *Journal of Student Centered Learning*, 2(1), 9–34.
2. Aggarwal, P., & O'Brien, C.L. (2008). "Social Loafing on Group Projects: Structural Antecedents and Effect on Student Satisfaction." *Journal of Marketing Education*, 30(3), 255–264.
3. Flask Documentation. https://flask.palletsprojects.com/
4. SQLAlchemy 2.0 Documentation. https://docs.sqlalchemy.org/en/20/
5. WebRTC API. https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API
6. OWASP Secure Coding Practices. https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/

---

*ProjectBuddy is open source under the MIT License. Source code: [github.com/ssaaffaakk/Project-buddy-Pb](https://github.com/ssaaffaakk/Project-buddy-Pb)*
