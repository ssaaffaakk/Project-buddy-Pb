# ProjectBuddy: AI-Enhanced Collaborative Project Management Platform for Higher Education

**Author:** Safak Surmeli  
**Institution:** International University of Sarajevo (IUS)  
**Date:** July 2026  
**Version:** 3.0  
**Classification:** Public  
**License:** MIT  
**Contact:** surmeliisafak@gmail.com

---

## Abstract

University students routinely form project teams through unstructured channels — WhatsApp groups, hallway conversations, or random assignment — with no visibility into a potential partner's skills, reliability, or track record. The result is predictable: uneven contribution, missed deadlines, and grades that reflect team dysfunction rather than individual capability.

ProjectBuddy is an open-source, web-based platform designed to address the persistent challenges of team formation, project coordination, and peer assessment in higher education environments. Built on a modern Python/Flask technology stack with real-time communication capabilities, ProjectBuddy integrates AI-powered assistance (SSM-1.0), full WebRTC live collaboration (voice, video, and screen sharing), a **trained machine-learning recommender**, and a gamified badge system to foster meaningful student collaboration. Unlike general-purpose tools such as Trello, Slack, or GitHub Projects, ProjectBuddy integrates the complete student collaboration lifecycle into a single, cohesive environment: from team discovery and formation, through real-time communication and in-chat file sharing, to peer feedback, skill endorsement, and public profile pages.

Version 2.1 established three axes: (1) **live collaboration rooms** layering video, screen sharing, and a shared live-synced notepad on the voice mesh; (2) a **learned recommendation engine** — a logistic-regression model with an LSA (Latent Semantic Analysis) embedding tower, trained on the platform's own interaction signals and benchmarked leakage-free against a rule-based baseline, with a public model card; and (3) a **social and identity layer** (a 120-tag interdisciplinary interest taxonomy, first-run onboarding, public profile walls, and in-chat file attachments).

**Version 3.0** broadens ProjectBuddy from a feature-complete collaboration tool into a full-stack data platform, and adds a substantial product layer. On the engineering side it introduces: a versioned, OpenAPI-documented **JSON API** (`/api/v1`) with JWT authentication and schema validation; a **Celery task queue** (with a transparent in-process fallback) for retried background delivery and scheduled jobs; a nightly **ELT pipeline** that loads a star-schema **data warehouse** under data-quality gates; an **MLOps loop** around the recommender (artifact versioning and rollback, scheduled retraining, and feature-drift monitoring); production **observability** via Prometheus metrics and optional Sentry; a feature-flagged **React + TypeScript client** over the API; and **infrastructure-as-code** with a local Prometheus/Grafana stack. On the product side it adds nine features: a **teammate finder** (user-to-user matching), **explainable applicant fit scores**, a **weekly recommendation digest**, **semantic project search with duplicate detection**, public-profile **contribution analytics**, an **instructor team-health dashboard**, a per-project **kanban board**, an **AI quiz generator** from uploaded notes, and **AI meeting notes** (Whisper transcription plus LLM summarization) for study-group voice rooms. The codebase is covered by an automated test suite (120+ backend tests plus a frontend suite) gated in continuous integration. These additions are documented in Section 9.

The platform has been developed and deployed at the International University of Sarajevo, serving as both a functional tool and a research contribution to the field of Computer-Supported Collaborative Learning (CSCL).

**Live Platform:** [https://project-buddy-pb.onrender.com](https://project-buddy-pb.onrender.com)  
**Source Code:** [github.com/ssaaffaakk/Project-buddy-Pb](https://github.com/ssaaffaakk/Project-buddy-Pb)

---

## Table of Contents

1. [Introduction](#1-introduction)
   - 1.1 [Problem Statement](#11-problem-statement)
   - 1.2 [Objectives and Scope](#12-objectives-and-scope)
   - 1.3 [Target Audience](#13-target-audience)
2. [Literature Review and Related Work](#2-literature-review-and-related-work)
   - 2.1 [Computer-Supported Collaborative Learning](#21-computer-supported-collaborative-learning-cscl)
   - 2.2 [Existing Platforms and Gap Analysis](#22-existing-platforms-and-gap-analysis)
   - 2.3 [AI in Educational Technology](#23-ai-in-educational-technology)
3. [System Architecture and Design](#3-system-architecture-and-design)
   - 3.1 [Architectural Overview](#31-architectural-overview)
   - 3.2 [Technology Stack](#32-technology-stack)
   - 3.3 [Data Model](#33-data-model)
   - 3.4 [Application Factory Pattern](#34-application-factory-pattern)
   - 3.5 [Security Architecture](#35-security-architecture)
4. [Core Features and Implementation](#4-core-features-and-implementation)
   - 4.1 [User Management and Authentication](#41-user-management-and-authentication)
   - 4.2 [Project Lifecycle Management](#42-project-lifecycle-management)
   - 4.3 [Recommendation Engine](#43-recommendation-engine)
   - 4.4 [Community Learning Feed](#44-community-learning-feed)
   - 4.5 [Study Groups and Live Collaboration Rooms](#45-study-groups-and-live-collaboration-rooms)
   - 4.6 [SSM-1.0 AI Assistant](#46-ssm-10-ai-assistant)
   - 4.7 [Gamification and Badge System](#47-gamification-and-badge-system)
   - 4.8 [Administrative Dashboard](#48-administrative-dashboard)
   - 4.9 [Profiles, Onboarding, and the Social Layer](#49-profiles-onboarding-and-the-social-layer)
5. [Real-Time Communication Infrastructure](#5-real-time-communication-infrastructure)
   - 5.1 [WebSocket Architecture](#51-websocket-architecture)
   - 5.2 [WebRTC Media Implementation (Voice, Video, Screen)](#52-webrtc-media-implementation-voice-video-screen)
   - 5.3 [Scalability with Redis Message Queue](#53-scalability-with-redis-message-queue)
6. [Deployment and Operations](#6-deployment-and-operations)
   - 6.1 [Production Configuration](#61-production-configuration)
   - 6.2 [Cloud Storage Abstraction](#62-cloud-storage-abstraction)
   - 6.3 [Background Task Scheduling](#63-background-task-scheduling)
7. [Case Study: Origin and Motivation](#7-case-study-origin-and-motivation)
   - 7.1 [Why I Built This](#71-why-i-built-this)
   - 7.2 [Design Decisions Driven by the Problem](#72-design-decisions-driven-by-the-problem)
   - 7.3 [Implementation Timeline](#73-implementation-timeline)
8. [Evaluation and Discussion](#8-evaluation-and-discussion)
   - 8.1 [Functional Assessment (CSCL Framework)](#81-functional-assessment-cscl-framework)
   - 8.2 [Functional Completeness](#82-functional-completeness)
   - 8.3 [Security Assessment](#83-security-assessment)
   - 8.4 [Architectural Quality](#84-architectural-quality)
   - 8.5 [Scalability Considerations](#85-scalability-considerations)
9. [Version 3.0: Platform Engineering, Data, and Feature Expansion](#9-version-30-platform-engineering-data-and-feature-expansion)
   - 9.1 [JSON API and Task Queue](#91-json-api-and-task-queue)
   - 9.2 [Data Engineering: ELT and the Star-Schema Warehouse](#92-data-engineering-elt-and-the-star-schema-warehouse)
   - 9.3 [MLOps: Versioning, Retraining, and Drift](#93-mlops-versioning-retraining-and-drift)
   - 9.4 [Product Analytics and Experimentation](#94-product-analytics-and-experimentation)
   - 9.5 [Observability, CI/CD, and Infrastructure as Code](#95-observability-cicd-and-infrastructure-as-code)
   - 9.6 [React + TypeScript Client](#96-react--typescript-client)
   - 9.7 [Feature Expansion](#97-feature-expansion)
10. [Limitations and Future Work](#10-limitations-and-future-work)
    - 10.1 [Current Limitations](#101-current-limitations)
    - 10.2 [Planned Improvements](#102-planned-improvements)
11. [Conclusion](#11-conclusion)
12. [References](#12-references)

---

## 1. Introduction

The landscape of higher education has undergone a fundamental transformation in the 21st century. Collaborative project-based learning has emerged as a cornerstone pedagogical approach across computer science, engineering, and interdisciplinary programs worldwide. Research consistently demonstrates that students engaged in well-structured collaborative projects develop superior technical competencies, enhanced communication skills, and stronger professional networks compared to those in traditional lecture-based paradigms (Dillenbourg, 1999; Stahl et al., 2006).

However, the practical implementation of collaborative learning at scale presents persistent challenges that existing educational technology has failed to adequately address. Students struggle to find compatible teammates, project coordination often devolves into fragmented communication across multiple platforms, and meaningful peer assessment remains difficult to facilitate and verify.

The *mechanism* for forming these teams has not kept pace with the complexity of the work. At most universities, team formation still relies on informal channels: a message in a class WhatsApp group ("anyone want to team up?"), a post on a course forum, or — in the worst case — random instructor assignment. None of these methods give students meaningful information about a potential partner's technical skills, work habits, or reliability.

ProjectBuddy was conceived and developed to address these systemic gaps. It is an open-source, web-based collaborative project management platform purpose-built for the higher education context. It provides:

- **Structured project listings** with required skills, topic tags, team size caps, and deadlines.
- **Interest-based matching** that surfaces relevant projects to each student automatically.
- **A reputation layer** — peer ratings, skill endorsements, and achievement badges — that makes contribution history visible and persistent across semesters.
- **Built-in collaboration tools** — real-time team chat, study groups, WebRTC voice rooms, and an AI assistant — so teams can work without fragmenting across external platforms.
- **Administrative oversight** — moderation, reporting, analytics, and live support chat for platform governance.

### 1.1 Problem Statement

Through direct observation and student feedback at the International University of Sarajevo (IUS), we identified five critical pain points in collaborative academic projects:

1. **The Information Asymmetry Problem (Team Formation Friction):** When a student posts "looking for a partner for the database project" in a group chat, they are making a selection decision with almost zero relevant information. They cannot see what projects the respondent has completed, whether previous teammates rated them highly, which technical skills they possess, or whether they have a pattern of meeting or missing deadlines. Students rely on informal social networks to find project partners, creating information asymmetry where well-connected students form optimal teams while others are left with suboptimal matches or no team at all. A student who consistently underdelivers can simply move to a new group chat and start fresh — there is no persistent record of past performance.

2. **The Accountability Gap (Absence of Structured Feedback):** Even when teams form successfully, there is typically no structured mechanism for post-project accountability. Instructors see a final deliverable but cannot easily determine who contributed what. Most project courses lack mechanisms for intra-team peer assessment. Free-riding is difficult to detect, and high-performing team members receive no recognition for their disproportionate contributions. Peer evaluation forms, when they exist, are one-time paper exercises disconnected from future team formation.

3. **Platform Fragmentation:** A typical student project requires WhatsApp for messaging, Google Drive for documents, GitHub for code, email for formal communication, and Zoom/Discord for voice calls. This fragmentation leads to lost context, duplicated effort, coordination overhead, and means that no single platform captures a holistic view of a student's collaborative activity.

4. **Skill Visibility Gap:** Students have no standardized way to showcase project-validated skills to future teammates or instructors. Academic transcripts capture grades but not competencies.

5. **The Commitment Overload Problem (Limited Instructor Oversight):** Without enforcement, high-performing students are often recruited into too many simultaneous projects, leading to burnout and declining quality. Conversely, less visible students struggle to find any team at all. Faculty supervising 20+ project teams simultaneously lack tooling to monitor team health, identify struggling groups, and intervene proactively.

### 1.2 Objectives and Scope

ProjectBuddy aims to deliver a unified platform that addresses each of the identified pain points through the following design objectives:

- **O1 — Intelligent Team Formation:** Implement a skill-and-interest-based recommendation engine that surfaces compatible project opportunities to students, reducing the team formation search cost.
- **O2 — Unified Collaboration Environment:** Provide text chat, voice communication, file sharing, and project management within a single platform, eliminating the need for third-party tool fragmentation.
- **O3 — Structured Peer Assessment:** Enable post-project peer feedback with quantitative ratings (1–5) and qualitative comments, constrained by actual project membership to ensure assessment authenticity.
- **O4 — Skill Endorsement and Gamification:** Allow teammates to endorse specific skills after project completion, with an automated badge system that rewards sustained contribution.
- **O5 — AI-Powered Assistance:** Integrate an AI assistant (SSM-1.0) that provides contextual help for project planning, skill development, and platform navigation.
- **O6 — Administrative Tooling:** Equip instructors and administrators with dashboards for monitoring platform activity, managing reports, and overseeing AI chatbot interactions.

### 1.3 Target Audience

ProjectBuddy serves three distinct user roles, each with tailored functionality:

| Role | Description | Key Capabilities |
|------|-------------|-----------------|
| **Student** | Undergraduate and graduate students enrolled in project-based courses | Browse/apply to projects (max 3 active), post to community, join study groups, give/receive feedback, earn badges, use AI assistant |
| **Instructor** | Faculty members supervising project courses (auto-assigned via faculty email domain) | All student capabilities plus instructor-level project ratings, manage team members, and enhanced visibility |
| **Administrator** | Platform administrators with full moderation authority | User management (warn/ban/activate), report adjudication, project removal, AI chat log monitoring, platform statistics, live support chat |

Role assignment is automatic: registration with a faculty-domain email address grants the instructor role; all others default to student. Admin accounts are provisioned via environment configuration.

---

## 2. Literature Review and Related Work

### 2.1 Computer-Supported Collaborative Learning (CSCL)

Computer-Supported Collaborative Learning (CSCL) is a research paradigm that investigates how technology can facilitate group learning processes. Stahl, Koschmann, and Suthers (2006) define CSCL as the study of "how people can learn together with the help of computers," emphasizing that the unit of analysis is the group, not the individual. This distinction is fundamental to ProjectBuddy's design philosophy: every feature is evaluated against its impact on group dynamics, not merely individual productivity.

Dillenbourg (1999) established that effective collaborative learning requires four conditions: (1) a shared goal, (2) division of labor, (3) joint problem-solving, and (4) mutual knowledge construction. ProjectBuddy operationalizes each condition through its project lifecycle model: shared goals are defined at project creation, labor is divided through team role assignment, joint problem-solving is facilitated by real-time communication channels, and mutual knowledge construction is captured through skill endorsements and peer feedback.

More recently, Jeong and Hmelo-Silver (2016) proposed a framework for CSCL technology design that emphasizes seven affordances: (1) joint task performance, (2) communication, (3) resource sharing, (4) group awareness, (5) regulation, (6) engagement, and (7) assessment. ProjectBuddy's feature set maps directly to these affordances, as detailed in Section 8.1.

### 2.2 Existing Platforms and Gap Analysis

Several categories of software tools are currently used in academic collaborative settings. We conducted a comparative analysis to identify the specific gaps that motivated ProjectBuddy's development:

| Platform Category | Examples | Strengths | Gaps for Academia |
|-------------------|----------|-----------|-------------------|
| **Project Management** | Trello, Asana, Jira | Task tracking, kanban boards, deadline management | No team matching, no peer assessment, no academic role model, no voice chat |
| **Communication** | Slack, Discord, MS Teams | Real-time messaging, voice/video, channels | No project lifecycle, no skill tracking, no recommendation engine, no gamification |
| **Version Control** | GitHub, GitLab | Code collaboration, issue tracking, contribution graphs | Code-centric (excludes non-CS disciplines), no peer feedback system, steep learning curve |
| **LMS Platforms** | Moodle, Canvas, Blackboard | Course management, grading, content delivery | Weak collaboration features, no real-time communication, no AI assistance, monolithic architecture |
| **Social Academic** | ResearchGate, LinkedIn | Research networking, skill endorsements | Post-graduation focus, no project-level collaboration, no real-time features, endorsements are unverified |
| **Academic Q&A** | Piazza, Ed Discussion | Course Q&A, instructor integration | No team formation, no reputation system, read-only interaction model |
| **Academic Matching** | TeamUp (academic tools) | Some offer random/preference-based matching | Typically instructor-controlled, no student-facing reputation, no post-project feedback loop |

The analysis reveals that no existing platform provides a unified solution that combines intelligent team formation, real-time multi-modal communication, structured peer assessment, skill endorsement, AI assistance, and administrative oversight within a single, purpose-built educational environment. ProjectBuddy occupies this unique intersection — it combines the *listing and matching* functionality of a job board with the *reputation and accountability* mechanisms of a professional network, purpose-built for the academic project lifecycle.

### 2.3 AI in Educational Technology

The integration of Large Language Models (LLMs) into educational platforms represents a rapidly evolving frontier. Recent work by Kasneci et al. (2023) surveys the opportunities and challenges of ChatGPT in education, noting that AI assistants can provide personalized scaffolding, reduce instructor workload for routine queries, and make domain expertise more accessible. However, they caution against uncritical deployment without safeguards for accuracy and academic integrity.

ProjectBuddy's AI component (SSM-1.0) is designed with these considerations in mind. Rather than replacing human interaction, SSM-1.0 serves as a supplementary resource for project planning advice, skill development recommendations, and platform guidance. Its conversation history is persisted and visible to administrators, maintaining transparency and accountability. The multi-provider architecture (Groq/LLaMA, Anthropic, with keyword-based fallback) ensures service continuity while controlling costs.

---

## 3. System Architecture and Design

### 3.1 Architectural Overview

ProjectBuddy follows a modular monolithic architecture organized around the Flask application factory pattern. While microservices architectures are prevalent in industry, we deliberately chose a monolithic approach for several reasons: (1) reduced operational complexity for a university-hosted deployment, (2) simpler debugging and development workflow, (3) atomic database transactions across features, and (4) the application's scale (thousands of users, not millions) does not require horizontal service decomposition.

The architecture is organized into four logical layers:

1. **Presentation Layer:** Jinja2 server-rendered HTML templates with responsive CSS, vanilla JavaScript, and Socket.IO client for real-time updates.
2. **Application Layer:** Flask blueprints (9 modules) implementing RESTful API endpoints and server-side rendering routes, with cross-cutting concerns (authentication, rate limiting, CSRF protection) handled by middleware and decorators.
3. **Service Layer:** Business logic encapsulated in dedicated service modules (recommendation engine, badge system, deadline checker, file storage abstraction).
4. **Data Layer:** SQLAlchemy 2.0 ORM with 25 mapped models, PostgreSQL in production, SQLite for development, managed through Alembic migrations.

### 3.2 Technology Stack

The technology stack was selected to balance developer productivity, ecosystem maturity, deployment simplicity, and long-term maintainability:

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Web Framework | Flask | 3.1 | Lightweight, extensible, large ecosystem, well-suited for modular applications |
| ORM | SQLAlchemy | 2.0 | Industry-standard Python ORM with modern `mapped_column` syntax and type annotations |
| Database (Prod) | PostgreSQL | 15+ | ACID-compliant, robust JSON support, excellent concurrency handling |
| Database (Dev) | SQLite | 3.x | Zero-configuration, file-based, ideal for local development iteration |
| Real-Time | Flask-SocketIO + eventlet | 5.x | WebSocket abstraction with fallback, async worker integration |
| Message Queue | Redis | 7.x | Cross-worker event broadcast, rate-limit storage, voice room state |
| Authentication | Flask-Login | 0.6 | Session-based auth with remember-me, mature and battle-tested |
| Migrations | Flask-Migrate (Alembic) | 4.x | Versioned schema migrations, rollback capability |
| Rate Limiting | Flask-Limiter | 3.x | Per-route rate limiting with Redis backend for multi-worker support |
| CSRF Protection | Flask-WTF | 1.x | Token-based CSRF with configurable timeout |
| File Storage | boto3 (AWS S3) | 1.x | Abstracted behind LocalStorage/S3Storage interface for portability |
| AI (Primary) | Groq API (LLaMA 3.1 8B Instant) | — | Free-tier LLM inference (70B available via config), OpenAI-compatible API format |
| AI (Secondary) | Anthropic API (Claude) | — | Fallback provider for high-quality responses |
| Machine Learning | scikit-learn + NumPy + joblib | 1.6 / 2.0 / 1.5 | Trained recommender (logistic regression) and LSA embedding model; lightweight, no GPU/torch dependency, deploys anywhere |
| Live Collab (WebRTC) | Browser WebRTC + SocketIO signaling | — | Peer-to-peer audio, video, and screen sharing over one transceiver set, with TURN relay support (Xirsys) |
| Email | Brevo HTTP API | — | Transactional email, bypasses cloud SMTP restrictions |
| Deployment | Gunicorn + eventlet worker | — | Production WSGI server with async worker class for WebSocket support |
| Hosting | Render / Heroku | — | PaaS deployment via Procfile, managed PostgreSQL, Redis |

### 3.3 Data Model

The data model comprises 38 SQLAlchemy models organized into seven functional domains. All models use the modern SQLAlchemy 2.0 `mapped_column` / `Mapped[type]` declarative syntax with full type annotations. The final two domains — behavioural instrumentation and the analytics warehouse — were introduced in Version 3.0 and are discussed further in Sections 9.1 and 9.2.

| Domain | Models | Key Relationships |
|--------|--------|-------------------|
| **User Identity & Social** | User, UserInterest, UserSkill, UserCourse, ProfileComment, ProfileCommentLike | User has many interests, skills, and courses; student/instructor/admin roles; users carry an avatar and cover banner and an `onboarded` flag; public profile walls (comments + likes) let any member post on any profile |
| **Project Lifecycle** | Project, ProjectTag, ProjectSkill, ProjectMember, Application, ProjectMessage, ProjectVote, ProjectTask | Project owned by User; members join via Application; votes enable community ranking; ProjectTask backs the per-project Kanban board (todo / doing / done) |
| **Assessment** | Feedback, Endorsement, Badge, UserBadge | Feedback links giver/receiver/project with rating constraint (1–5); endorsements require shared project completion |
| **Communication & Community** | Chat, ChatMessage, StudyGroup, StudyGroupMember, StudyGroupMessage, StudyGroupNote, SharedFile, ChatbotSession, CommunityPost, CommunityComment, CommunityLike | Admin support chat; group chat with in-message file attachments and a live-synced shared note; AI chatbot session persistence; community feed with posts, comments, and likes |
| **Moderation & Delivery** | Report, AdminMessage, Notification, PushSubscription, PasswordReset | Report targets user or project (including profile-wall comments); admin can warn/ban/dismiss; notifications link to originating action; PushSubscription stores Web-Push endpoints for the weekly digest |
| **Instrumentation** | ActivityEvent | Append-only behavioural event log (actor, verb, target, timestamp) that feeds the ELT pipeline and product-analytics queries |
| **Analytics Warehouse** | DwDimUser, DwDimProject, DwFactDailyActivity, DwDailyMetrics | Star-schema dimension and fact tables populated by the nightly ELT job from `ActivityEvent`; source for dashboards and A/B read-outs |

### 3.4 Application Factory Pattern

ProjectBuddy uses the Flask application factory pattern (`create_app()`) to ensure testability, configuration flexibility, and clean extension initialization. The factory performs the following operations in sequence:

1. **Configuration Loading:** From environment-specific classes (DevelopmentConfig, ProductionConfig, TestingConfig).
2. **Proxy Fix:** Werkzeug ProxyFix middleware installation for correct header handling behind reverse proxies (Render, Heroku).
3. **Extension Initialization:** SQLAlchemy, Migrate, LoginManager, Limiter, CSRFProtect, SocketIO (with Redis message queue when available).
4. **Blueprint Registration:** 9 route modules plus SocketIO handlers for voice/video signaling, shared-note sync, and participant state relay.
5. **Security Middleware:** CSP nonce generation per request, comprehensive security headers on every response, cache-control policies per path.
6. **Error Handlers:** Custom 404/500 pages, graceful CSRF failure handling, rate-limit exceeded flash messages.
7. **Startup Tasks (OS Thread):** Schema migration, badge seeding, admin sync, avatar backfill, mock data seeding — run in a genuine OS thread to avoid eventlet hub conflicts.
8. **Background Scheduler:** Hourly deadline checker running in a genuine OS thread (not eventlet greenlet).

### 3.5 Security Architecture

Security is implemented as a defense-in-depth strategy with multiple overlapping controls. Every HTTP response includes a comprehensive set of security headers:

| Security Control | Implementation | Threat Mitigated |
|-----------------|----------------|------------------|
| **Content Security Policy** | `default-src 'self'`; script/style restricted to `'self'` + specific CDNs; `frame-ancestors 'none'`; per-request nonce via `secrets.token_urlsafe(16)` | XSS, code injection, clickjacking |
| **CSRF Protection** | Flask-WTF token with 1-hour expiry; CSRF error returns flash + redirect (not raw 400) | Cross-Site Request Forgery |
| **Rate Limiting** | Global: 200/day, 50/hour; Login: 20/min, 100/hour; Register: 10/hour; Admin login: 10/min, 30/hour; Chatbot: 20/min, 200/day | Brute force, credential stuffing, API abuse |
| **Password Security** | PBKDF2-SHA256 hashing via Werkzeug; min 8 chars + digit + special character | Credential theft, rainbow table attacks |
| **Session Security** | HttpOnly, Secure, SameSite=Lax cookies; 8-hour session lifetime; `__Host-` prefix in production | Session hijacking, cookie theft |
| **HSTS** | `max-age=63072000; includeSubDomains; preload` (production only) | SSL stripping, downgrade attacks |
| **OAuth CSRF** | HMAC-SHA256 signed timestamp state parameter (no session dependency); 10-minute window; `hmac.compare_digest` for constant-time comparison | OAuth state tampering, timing attacks |
| **Permissions Policy** | `camera=(), microphone=(self), geolocation=(), payment=(), usb=()` | Unauthorized browser API access |
| **COOP/CORP** | `Cross-Origin-Opener-Policy: same-origin`; `Cross-Origin-Resource-Policy: same-origin` | Cross-origin window attacks, resource embedding |
| **File Upload Validation** | Extension whitelist + Content-Type header check + magic-byte sniffing (JPEG, PNG, WebP, GIF) + size limit (50 MB); filenames sanitized with `secure_filename` + randomized with `secrets.token_hex` | Malicious file upload, MIME confusion, path traversal |
| **Information Disclosure** | Generic error messages, no email enumeration on password reset, server fingerprint header removed | User enumeration, fingerprinting |
| **SQL Injection** | SQLAlchemy ORM parameterizes all queries | SQL injection |
| **XSS** | Jinja2 auto-escapes all template variables by default | Cross-site scripting |

**Known CSP caveat:** The Content-Security-Policy header includes `'unsafe-inline'` for both scripts and styles because the frontend uses inline event handlers (`onclick=`) and inline style attributes. The CSP nonce infrastructure is in place, and removing `unsafe-inline` is a planned future improvement requiring a frontend refactor.

---

## 4. Core Features and Implementation

### 4.1 User Management and Authentication

ProjectBuddy supports two authentication pathways: traditional email/password registration and GitHub OAuth 2.0 single sign-on.

**Registration Flow:**
- Requires first name, last name, email, department, password (with confirmation), and exactly 5 interest tags from a predefined taxonomy.
- Interest tags serve dual purposes: (1) populating the user's interest profile for the recommendation engine, and (2) providing an initial signal for team compatibility matching.
- Password policies enforce a minimum of 8 characters with at least one digit and one special character (`!@#$%^&*`).
- Automatic role assignment: faculty domain emails receive instructor role; all others default to student.

**GitHub OAuth Flow:**
- Uses HMAC-signed timestamp-based state tokens rather than session-stored state, eliminating a class of bugs related to cross-site redirect cookie loss.
- State token includes a 10-minute expiry window and is verified using constant-time comparison (`hmac.compare_digest`) to prevent timing attacks.
- On first OAuth login, a new user account is created from GitHub profile data (name, email, avatar). GitHub users have no password — a random 64-char hex string is stored that will never match any real password because `check_password()` verifies against a PBKDF2 hash.

**Password Reset Flow:**
- A 256-character random token is generated, stored in the database with a creation timestamp, and sent to the user's email via the Brevo transactional email API.
- Tokens expire after a configurable period (default: 1 hour).
- The reset endpoint does not reveal whether an email exists in the system, preventing enumeration attacks.
- Old tokens are deleted before issuing new ones to prevent accumulation.

### 4.2 Project Lifecycle Management

Projects in ProjectBuddy follow a well-defined state machine with three states:

```
   [OPEN] ──── team full / owner closes ────> [CLOSED]
     │                                           │
     │         owner marks complete               │
     └──────── or deadline passes ──────────> [COMPLETED]
                                                  │
                                                  └── Enables: feedback, endorsements, badges
                                                      Disables: modifications, new applications
```

**Transition Rules:**
- **Open → Closed:** Triggered automatically when the team reaches capacity, or manually by the project owner.
- **Open/Closed → Completed:** Triggered manually by the project owner, or automatically by the background deadline checker when the deadline passes.
- **Completed:** Terminal state. Enables peer feedback and skill endorsement; disables project modification and new applications.

**Business Rules:**
- Each project creation requires exactly 5 topic tags, a team size specification, and an optional deadline.
- Hard limit of 3 concurrent active project memberships per student, preventing overcommitment.
- Application workflow includes applicant messaging, owner review (accept/reject), and automatic notifications.
- Community engagement through upvote/downvote system with unique constraint (one vote per user per project).

### 4.3 Recommendation Engine

ProjectBuddy ranks open projects for each student by predicted fit. The engine (`services/recommendation_service.py`, `services/ml/`) is a **two-model system**: a trained machine-learning recommender that serves whenever a model artifact is present, and a transparent rule-based scorer that acts as an automatic fallback. This design lets the platform ship a learned model without ever being unable to make a recommendation.

**Rule-based baseline (fallback).**
A content-based filter expands each user's interest tags through a curated `INTEREST_TO_TOPIC_MAP` (e.g. `"python" → {backend, data, ai / ml}`), filters out projects the user owns/joined/applied to, and scores each open project by the cardinality of the intersection between the user's expanded interests and the project's normalized tags. Simple, transparent, and vocabulary-bridging.

**Learned recommender (primary).**
The ML path (`services/ml/`) treats matching as supervised learning-to-rank over `(user, project)` pairs:

- **Labels from real signals.** Positive examples are genuine "this user fit this project" observations — active project memberships and submitted applications. Negatives are sampled non-interaction pairs (≈3× positives). No synthetic labels are used.
- **Feature engineering.** Fourteen features per pair: interest-topic overlap and Jaccard, skill overlap and Jaccard, course match, profile richness counts, project popularity (member count), recency, community vote score, and a **semantic-similarity** feature (below).
- **Semantic embedding tower.** Rather than a heavyweight transformer, ProjectBuddy builds its own embeddings with **LSA (TF-IDF + Truncated SVD)** — a dual-encoder ("two-tower") retriever that maps a user's text (bio, interests, skills, courses) and a project's text (title, description, tags, skills) into one shared latent space; match strength is their cosine similarity. LSA is a deliberate engineering choice: it captures semantic relatedness ("machine learning" ≈ "neural networks") without a GPU or a torch dependency, and deploys on commodity hosting.
- **Model.** A `StandardScaler` + `LogisticRegression` (class-balanced, `liblinear`) pipeline, preceded by a `VarianceThreshold` so degenerate constant features never destabilize the solver. The fitted pipeline is persisted with `joblib`.

**Leakage-free evaluation.**
Every approach is scored with the same out-of-fold 5-fold cross-validation. On the current dataset:

| Approach | ROC-AUC |
|----------|---------|
| Rule-based overlap (baseline) | 0.89 |
| Semantic embeddings only (retriever) | 0.58 |
| **Full hybrid (overlap + embeddings) — shipped** | **0.89** |

The results are reported honestly, including on a public **model card** (`/ml/recommender`): on this small corpus the embedding tower overlaps with the hand-crafted features and does not add aggregate lift, though it provides cold-start coverage (it can rank projects that share *no* exact tags with a user). This is a transparent negative result rather than an inflated claim — the ROC-AUC of 0.89 on 26 positive examples is a fragile estimate whose confidence interval widens with such little data, and the whitepaper states this plainly.

**Serving and retraining.**
The dashboard's "Recommended for you" ranks by the model's predicted fit percentage. A Flask CLI command (`flask train-recommender`) rebuilds the embedding space and retrains the model on current data, so the system improves automatically as the community grows — the intended trajectory for a data-scarce cold start.

### 4.4 Community Learning Feed

The community module provides a social learning feed modeled after educational discourse platforms:

- Students can publish posts with optional media attachments (images: JPG, PNG, WebP, GIF; videos: MP4, WebM, MOV) up to 50 MB.
- The upload pipeline implements **four-layer validation:** extension whitelist, Content-Type header verification, magic-byte signature sniffing (for images), and file size enforcement.
- Posts support a comment thread with @mention notifications. When a user comments on another user's post, the post author receives an in-app notification with a preview snippet.
- A like/unlike toggle provides lightweight engagement signaling.
- Both posts and comments can be deleted by their authors or by administrators, supporting content moderation.
- Filenames are sanitized and randomized to prevent collisions and path traversal.

### 4.5 Study Groups and Live Collaboration Rooms

Study groups provide persistent, topic-organized collaboration spaces. Each group room combines asynchronous messaging with a synchronous "live room" that layers voice, video, screen sharing, and shared notes on demand:

1. **Text-Based Group Messaging with In-Chat Files:** Real-time delivery over SocketIO — each message is broadcast to the group's room, with a reconnect/​fallback poll for resilience; the last 60 messages load on entry (2000-character limit). Files are attached directly to messages rather than through a separate upload flow — images render inline in the stream, other files appear as download cards. A read-only "Files" tab auto-collects every attachment shared in chat (25 MB limit, 40+ formats, UUID-named through the storage abstraction).
2. **Discord-style Live Room:** Joining voice turns the room into a call stage — a grid of equal participant tiles (video fills the tile, or a profile-photo/letter avatar when the camera is off), a floating control bar (mic, camera, screen share, notes, chat, leave), speaking indicators, and a slide-in chat drawer. Camera and screen share ride the existing peer connections via a pre-allocated video transceiver, so they start without renegotiation. A lightweight relay event broadcasts each participant's mute/camera/screen-share state so peers render the correct tile chrome.
3. **Shared Live Notes:** A per-group collaborative notepad synced over SocketIO with a 500 ms debounce and persisted server-side (`StudyGroupNote`), so a team can take notes together while on a call.
4. **Peer-to-Peer WebRTC Transport:** Full-mesh topology with SocketIO signaling (detailed in Section 5).

Groups can be public or private, and the creator automatically joins as the group admin. Live presence indicators show how many users are currently in voice for each group.

### 4.6 SSM-1.0 AI Assistant

SSM-1.0 is ProjectBuddy's integrated AI assistant, available both as a web-based chatbot within the platform and as a standalone CLI development tool.

**Web Chatbot — Multi-Provider Architecture:**

| Provider | Model | Tier | Characteristics |
|----------|-------|------|-----------------|
| **Groq (Primary)** | LLaMA 3.1 8B Instant | Free | Fast inference, OpenAI-compatible API, ~14,400 req/day free tier (70B configurable via `GROQ_MODEL`) |
| **Anthropic (Fallback)** | Claude 3 Haiku | Paid | High-quality responses, Anthropic Messages API format |
| **Built-in (Offline)** | Keyword matching | Free | Category-based response templates (project, team, deadline, skill, flask, git), zero API dependency |

The provider selector checks for API keys in order (Groq → Anthropic → built-in) and uses the first available provider. Each user's conversation history is persisted in the database (last 20 messages retained per user) and included in subsequent API calls to maintain conversational context.

**System Prompt:** SSM-1.0 is instructed to help with project planning, finding teammates, managing deadlines, skill development, and general study advice. Responses are kept under 150 words unless more detail is requested.

**Rate Limiting:** 20 requests/minute, 200/day per user. Input validated for length (max 1000 characters) and emptiness.

**Standalone CLI Agent (`ssm_agent.py`):**
- Implements a ReAct-style (Reasoning + Acting) agent loop over a local Ollama model.
- Tool registry supports: `read_file`, `write_file`, `run_shell`, `get_datetime`, `search_web`.
- Agent parses tool calls from model output as JSON, executes them, feeds results back for iterative reasoning.
- Maximum 10 tool-call rounds per user message to prevent infinite loops.
- Auto-detects available Ollama models, preferring LLaMA variants.

### 4.7 Gamification and Badge System

ProjectBuddy implements a badge-based gamification system (`services/badge_service.py`) designed to incentivize sustained engagement and recognize achievement milestones:

| Badge | Condition | Design Rationale |
|-------|-----------|------------------|
| **First Step** | Complete 1 project | Lower the activation barrier; reward initial participation |
| **Veteran** | Complete 5 projects | Recognize sustained commitment across multiple teams |
| **Expert** | Receive 10 skill endorsements | Validate peer-recognized expertise; require social proof |

**Award Mechanics:**
- Badges are automatically evaluated after two trigger events: project completion (for First Step and Veteran) and skill endorsement (for Expert).
- The evaluation is idempotent: if a badge has already been awarded, the check short-circuits without database modification.
- Endorsements are constrained to users who have completed at least one project together, ensuring that endorsements reflect genuine collaborative experience rather than social reciprocity.
- All feedback, endorsements, and badges appear on the user's public profile, visible to anyone considering them for a future project.

### 4.8 Administrative Dashboard

The admin module provides a dedicated interface for platform governance:

- **Report Adjudication:** Three-action workflow: **warn** (sends a warning AdminMessage to the target user), **ban** (disables login via `is_banned` flag), or **dismiss** (closes the report as invalid). Reports follow a strict `pending → resolved/warned/dismissed` state machine.
- **Platform Statistics:** Real-time aggregate metrics: total users, projects, applications, reports, and badges. Accessible via both the dashboard UI and a JSON API endpoint (`/admin/stats`).
- **AI Chat Monitoring:** Full read access to all users' chatbot conversation histories, organized by user. Enables quality assurance of AI responses and detection of potential misuse patterns.
- **Direct Messaging:** Admin-to-user communication channel for warnings, guidance, and follow-up on reported issues.
- **Project Removal:** Ability to remove fraudulent or misleading project listings, with cascading deletion of associated tags, members, and applications.

### 4.9 Profiles, Onboarding, and the Social Layer

Because ProjectBuddy serves a whole university rather than a single department, identity and expression are first-class:

- **Interdisciplinary interest taxonomy.** Interests are drawn from a single source of truth (`services/interests.py`): **120 tags across 13 fields** — Software & CS, AI & Data, Engineering, Mathematics, Natural Sciences, Health & Medicine, Psychology & Social Sciences, Business & Economics, Law & Policy, Arts & Design, Humanities & Languages, Media & Communication, and Education. A psychology, law, or design student finds themselves as readily as a CS major. Both registration and profile editing render the same categorized, searchable picker (users still select exactly five).
- **First-run onboarding.** After registration, a skippable `/welcome` step lets students pick a profile photo and a cover banner — either an uploaded image or one of several preset gradients — with a live preview. An `onboarded` flag routes new users through this once.
- **Public profile walls.** Every non-admin profile carries a wall where any member can leave a comment; comments support likes (a toggle) and can be deleted by the profile owner, the author, or an admin, and reported by anyone. Owners receive an in-app notification on new comments.
- **Cover banners** render across a user's own profile and public profile pages via a shared `banner_style()` helper that resolves either an uploaded image URL or a `preset:<key>` gradient token.

---

## 5. Real-Time Communication Infrastructure

### 5.1 WebSocket Architecture

ProjectBuddy's real-time layer is built on Flask-SocketIO with the eventlet async mode. The eventlet worker class patches Python's standard library to provide cooperative multitasking within a single OS process, allowing thousands of concurrent WebSocket connections without the thread-per-connection overhead of traditional WSGI servers.

**Eventlet Hub Constraint:**
A critical architectural decision is the use of genuine OS threads (via `eventlet.patcher.original('threading').Thread`) for background tasks such as the deadline scheduler and database startup routines. This is necessary because eventlet's hub-based scheduling raises "do not call blocking functions from the mainloop" when `hub.switch()` is invoked from the hub's own greenlet. By using unpatched OS threads, these tasks execute completely outside eventlet's cooperative scheduling, avoiding deadlocks while maintaining access to the Flask application context.

### 5.2 WebRTC Media Implementation (Voice, Video, Screen)

The live-room system implements a full-mesh peer-to-peer WebRTC topology with server-side signaling, carrying audio, camera video, and screen share. The implementation follows a five-phase connection lifecycle:

1. **Phase 1 — Room Join:** Client emits `join_voice` with `group_id`. Server joins the SocketIO room, retrieves the existing participant list, and sends it to the new joiner via `voice_existing_participants`.

2. **Phase 2 — Offer Exchange:** Existing participants receive `voice_user_joined` and initiate WebRTC offers. SDP offers are relayed through the server to the target peer identified by socket ID.

3. **Phase 3 — Answer Exchange:** The new joiner generates SDP answers and relays them back through the server. At this point, both peers have exchanged session descriptions.

4. **Phase 4 — ICE Candidate Exchange:** ICE (Interactive Connectivity Establishment) candidates are relayed between peers to negotiate the optimal network path. With TURN configured, this ensures connectivity even behind symmetric NATs and restrictive firewalls.

5. **Phase 5 — Teardown:** On `leave_voice` or `disconnect`, the participant is removed from the room state and all remaining peers are notified via `voice_user_left`.

**Media Tracks (Audio, Video, Screen Share):**
Audio is added on join. To support camera and screen sharing without costly SDP renegotiation, each peer connection pre-allocates a single `sendrecv` video transceiver at creation time; toggling the camera or screen calls `RTCRtpSender.replaceTrack()` on that slot, and turning it off replaces the track with `null`. Screen capture uses `getDisplayMedia()`; camera uses `getUserMedia({video})`. Because camera↔screen is the same transceiver, switching between them is a track swap, not a new negotiation. A dedicated `voice_state` signaling event relays each participant's mute/camera/screen-share state to the room so peers can render the correct tile chrome (muted-mic pill, "presenting" badge) without inspecting media directly. Browser media APIs require a secure context, so the feature is HTTPS-only in production.

**Voice Room State Storage:**
- **Redis (production):** Stored with 24-hour TTL, shared across multiple Gunicorn workers.
- **In-process dict (development):** Fallback for single-worker environments.

**ICE Server Configuration (Three Tiers):**

| Tier | Provider | Credentials | Use Case |
|------|----------|-------------|----------|
| 1 | **Xirsys API** | Fresh time-limited TURN credentials via API | Production (recommended) |
| 2 | **Static TURN** | Environment variables (TURN_URLS, TURN_USERNAME, TURN_CREDENTIAL) | Production (Metered, Twilio, Coturn) |
| 3 | **Google STUN** | None required | Development / same-LAN only |

The system logs a warning if no TURN relay is configured, as STUN alone is insufficient for production use behind NAT/firewalls.

### 5.3 Scalability with Redis Message Queue

In production, Gunicorn runs multiple eventlet worker processes to utilize multi-core hardware. This creates a challenge: SocketIO events emitted in one worker process must reach clients connected to other workers. ProjectBuddy solves this by configuring Flask-SocketIO with a Redis message queue (`message_queue=redis_url`), enabling cross-worker event broadcast.

Redis also serves as the backend for Flask-Limiter's rate limiting storage, ensuring that rate limits are enforced consistently across all worker processes. In development (single worker), the system gracefully degrades to in-process storage for both SocketIO events and rate limits.

---

## 6. Deployment and Operations

### 6.1 Production Configuration

ProjectBuddy uses a three-tier configuration hierarchy: base `Config`, `DevelopmentConfig`, and `ProductionConfig`. The production configuration enforces several critical settings:

| Setting | Development | Production |
|---------|------------|------------|
| `DEBUG` | `True` | `False` |
| `SESSION_COOKIE_SECURE` | `False` | `True` |
| `SEED_MOCK_DATA` | `True` | `False` |
| `HSTS` | Disabled | 2-year max-age with preload |
| `CORS` | `*` (all origins) | Restricted to deployment URL |
| `Cookie Name` | `session` | `pb-session` |
| `CSP nonce` | Generated | Generated |
| `Werkzeug unsafe` | Allowed | Blocked |

The deployment pipeline uses a Procfile-based configuration compatible with Render and Heroku. The WSGI entrypoint (`wsgi.py`) initializes the application with `ProductionConfig` and runs under Gunicorn with the eventlet worker class.

The platform handles cold starts gracefully — the first request after inactivity takes approximately 30 seconds as the Render instance spins up, applies migrations, seeds default data, and starts the scheduler.

### 6.2 Cloud Storage Abstraction

File storage is abstracted behind a pluggable interface (`services/file_storage.py`) with two implementations:

**LocalStorage:**
- Saves files to `static/uploads/<category>/` on the local filesystem.
- Returns relative URLs suitable for direct serving by the web server.
- Used in development and single-server deployments.

**S3Storage:**
- Uploads files to an AWS S3 bucket (or S3-compatible service via custom endpoint URL).
- Supports CloudFront CDN URL rewriting for optimized delivery.
- Generates pre-signed download URLs with configurable expiry for access-controlled file retrieval.
- Content-Type automatically detected via MIME type guessing.

The storage backend is selected at module import time based on the presence of the `AWS_S3_BUCKET` environment variable, with automatic fallback to local storage if S3 initialization fails. This design ensures zero-configuration development while supporting production cloud storage without code changes.

### 6.3 Background Task Scheduling

ProjectBuddy runs a single background task: the deadline checker, which executes hourly to identify overdue projects and automatically transition them to the "completed" state.

**Implementation Details:**
- Uses a genuine OS thread (not an eventlet greenlet) to avoid the "blocking from mainloop" hub conflict.
- Uses `eventlet.patcher.original('time').sleep` for real OS-level sleep, completely outside eventlet's scheduling.
- In Flask's debug mode with the Werkzeug reloader, the scheduler is conditionally started only in the child process (detected via `WERKZEUG_RUN_MAIN`) to prevent duplicate scheduler instances from competing over database access.

---

## 7. Case Study: Origin and Motivation

### 7.1 Why I Built This

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

### 7.2 Design Decisions Driven by the Problem

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

### 7.3 Implementation Timeline

The platform was built as a solo project over the course of one academic semester:

1. **Weeks 1–2:** Problem analysis, requirements gathering, data model design.
2. **Weeks 3–5:** Core backend — user auth, project CRUD, application workflow, database schema.
3. **Weeks 6–8:** Reputation system (feedback, endorsements, badges), recommendation engine.
4. **Weeks 9–10:** Real-time features — SocketIO chat, WebRTC voice rooms.
5. **Weeks 11–12:** Community feed, study groups, AI chatbot, admin panel.
6. **Weeks 13–14:** Security hardening (CSP, CSRF, rate limiting, file upload validation), deployment to Render, documentation.

---

## 8. Evaluation and Discussion

### 8.1 Functional Assessment (CSCL Framework)

We evaluate ProjectBuddy against the seven CSCL affordances framework proposed by Jeong and Hmelo-Silver (2016):

| CSCL Affordance | ProjectBuddy Implementation | Coverage |
|-----------------|----------------------------|----------|
| **Joint Task Performance** | Project lifecycle management with shared membership, role assignment, and state transitions | Full |
| **Communication** | Text messaging (study groups), WebRTC voice chat, admin messaging, AI chatbot | Full |
| **Resource Sharing** | File upload/download in study groups (40+ formats, 25 MB limit), community media posts (50 MB) | Full |
| **Group Awareness** | Live voice presence indicators, member lists, application status tracking, notification system | Partial |
| **Regulation** | Deadline enforcement (automatic), project membership limits (max 3), rate limiting | Partial |
| **Engagement** | Badge gamification, skill endorsements, community likes/comments, project voting | Full |
| **Assessment** | Peer feedback (1–5 rating + comment), skill endorsements, instructor ratings | Full |

**Group Awareness** is rated "Partial" because while the platform provides real-time voice presence and member status, it does not yet implement task progress dashboards or contribution analytics. **Regulation** is "Partial" because while deadlines and membership limits are enforced, the platform does not yet support instructor-defined milestones or automated progress gates.

### 8.2 Functional Completeness

| Requirement | Status | Notes |
|------------|--------|-------|
| Post projects with skills, tags, deadline | **Complete** | 5 topic tags required, skills optional |
| Browse and filter open projects | **Complete** | Filterable list + recommendation engine |
| Apply to join projects | **Complete** | With ownership, membership, and cap checks |
| Accept/reject applications | **Complete** | Owner-only, with auto-close on team full |
| Rate teammates after completion | **Complete** | 1–5 scale with DB-level `CheckConstraint` |
| Endorse specific skills | **Complete** | Gated by shared completed project |
| Badge system | **Complete** | 3 badges with idempotent award logic |
| Real-time team chat | **Complete** | SocketIO-based, per-project |
| Voice rooms | **Complete** | WebRTC peer-to-peer with SocketIO signaling |
| Community feed with media | **Complete** | Image/video upload with 4-layer validation |
| Study groups | **Complete** | Public/private, chat, file sharing |
| AI assistant | **Complete** | 3-tier provider fallback |
| Admin moderation | **Complete** | Warnings, bans, reports, analytics |
| Auto-complete past deadline | **Complete** | Hourly scheduler on OS thread |
| Max 3 active projects | **Complete** | Enforced on both create and apply |
| Email notifications | **Complete** | Password reset, application events |
| GitHub OAuth | **Complete** | HMAC-signed state, no session dependency |

### 8.3 Security Assessment

| Security Control | Implementation Quality | Notes |
|-----------------|----------------------|-------|
| Password hashing | **Strong** | `pbkdf2:sha256` with Werkzeug defaults |
| Session management | **Strong** | HttpOnly, SameSite, short lifetime, Secure in prod |
| CSRF protection | **Strong** | Global Flask-WTF, graceful failure handling |
| OAuth state | **Strong** | HMAC-signed, time-bounded, constant-time comparison |
| Rate limiting | **Strong** | Per-route limits, Redis-backed in production |
| CSP | **Moderate** | Nonces generated but `unsafe-inline` still present for legacy compatibility |
| File uploads | **Strong** | Extension + Content-Type + magic bytes + size cap |
| SQL injection | **Strong** | SQLAlchemy ORM parameterizes all queries |
| XSS | **Strong** | Jinja2 auto-escapes all template variables by default |
| Access control | **Strong** | Decorator-based with ownership verification |
| Information disclosure | **Strong** | Generic error messages, no email enumeration |
| Privacy | **Strong** | Email addresses hidden, profiles login-gated |

### 8.4 Architectural Quality

**Strengths:**
- Clean separation of concerns via Blueprints and a dedicated services layer.
- Application factory pattern enables test isolation and multiple configurations.
- SQLAlchemy 2.0 Mapped types provide type safety and IDE support.
- Eventlet threading handled correctly — startup tasks and the scheduler use real OS threads to avoid hub conflicts.
- Storage abstraction allows seamless local/S3 switching without code changes.
- Graceful degradation — chatbot falls back through three providers; storage falls back from S3 to local disk; rate limiting falls back from Redis to memory.

**Areas for Improvement:**
- No automated test suite — the application was manually tested, but unit and integration tests would improve confidence in future changes.
- No API documentation (OpenAPI / Swagger) — the JSON API endpoints are undocumented beyond code comments.
- No WebSocket authentication beyond `current_user.is_authenticated` — a malicious client could potentially forge SocketIO events if they obtain a valid session cookie.

### 8.5 Scalability Considerations

| Dimension | Current State | Scaling Path |
|-----------|--------------|-------------|
| Database | SQLite (dev) / PostgreSQL (prod) | PostgreSQL handles moderate loads; read replicas for high traffic |
| Real-time | Redis message queue for multi-worker SocketIO | Horizontally scalable with additional workers |
| File storage | S3 with CloudFront | Already cloud-native; scales independently |
| Rate limiting | Redis-backed | Shared state across workers |
| Voice | WebRTC P2P (mesh topology) | Works for small groups (2–6); larger groups need an SFU |
| Recommendation | Full table scan of open projects | Acceptable for hundreds; needs indexing/caching for thousands |

---

## 9. Version 3.0: Platform Engineering, Data, and Feature Expansion

Where Versions 1.x–2.1 built a feature-complete collaboration product, Version 3.0 hardens it into a production-grade, data-driven platform and extends it with a substantial product layer. The work is organized into six engineering tracks and a set of nine user-facing features, each implemented with the same discipline: security gating, automated tests, and — where relevant — leakage-free evaluation and honest reporting of negative results.

### 9.1 JSON API and Task Queue

**Versioned JSON API (`/api/v1`).** A `flask-smorest` blueprint exposes the platform's core resources — paginated and filterable project listings, project detail, personalized recommendations, the authenticated user profile, study groups, and the application action — as a versioned REST surface. Requests are validated against `marshmallow` schemas, so malformed input yields a structured `422` with per-field errors rather than an unhandled `500`. The specification is generated from the code and served as interactive Swagger UI at `/api/docs` (raw spec at `/api/openapi.json`).

**Authentication and CSRF discipline.** `POST /api/v1/auth/token` exchanges credentials for an HS256 JWT. Read endpoints additionally accept the browser session cookie; **write** endpoints require the Bearer token. This split is a deliberate security property: the API blueprint is CSRF-exempt, and because a cross-site page cannot attach an `Authorization` header, token-only writes cannot be forged — the exemption never reopens CSRF.

**Celery task queue.** Background delivery (web push, transactional email) and scheduled jobs run on a Celery worker with automatic retries. Crucially, when no broker is configured the queue degrades to **eager, in-process execution** identical to the pre-queue behavior — so a broker-less single-service deployment (such as the free Render tier) keeps working unchanged, while adding a worker enables true asynchronous delivery. The queue also carries the periodic jobs introduced below (nightly ELT, daily drift check, weekly retraining and digest). A defect where `REDIS_URL` was implicitly treated as a broker — which would have silently queued mail that nothing consumed — was caught and fixed before deployment.

### 9.2 Data Engineering: ELT and the Star-Schema Warehouse

An append-only **`ActivityEvent`** stream instruments every meaningful action (logins, signups, project views, applications, recommendation impressions and clicks, group and voice joins, chatbot use). Writes are strictly best-effort: a tracking failure can never break the request that triggered it.

A nightly **ELT pipeline** (`flask run-etl`, or Celery beat) transforms this stream and the operational tables into a dimensional **star schema** — `dw_dim_user`, `dw_dim_project`, `dw_fact_daily_activity`, and `dw_daily_metrics`. The load is idempotent (dimensions are full-refreshed; facts use a windowed delete-then-insert), and every run ends with **data-quality gates**: row-parity against the source tables, completeness of the fact table against the event stream, and value-bounds checks. A failed gate raises rather than publishing untrustworthy numbers. The admin analytics view reads warehouse freshness (last load, row counts) alongside product metrics computed directly from the event stream: DAU/WAU/MAU, stickiness, an activation funnel (signup → onboarded → applied → completed), and weekly retention cohorts.

### 9.3 MLOps: Versioning, Retraining, and Drift

The learned recommender (Section 4.3) is now operated, not merely trained. Every training run archives a **versioned artifact** and a metrics "model card"; a CLI (`flask model-versions`, `flask rollback-recommender <version>`) lists and restores prior versions. The trainer additionally reports **per-user ranking metrics** — recall@5 and NDCG@10 from out-of-fold scores — because ROC-AUC alone is the wrong yardstick for a ranking system; and it optionally logs runs to **MLflow**. Two scheduled jobs close the loop: a **weekly retraining** task rebuilds the model on accumulated interaction data, and a **daily feature-drift check** compares the live serving population's feature distribution against the training snapshot, exposing a standardized drift score as a Prometheus gauge and on a Grafana threshold panel.

### 9.4 Product Analytics and Experimentation

The recommender is served under a live **A/B experiment**: users are deterministically split 50/50 by hash between the learned "ml" arm and the rule-based "rules" arm. Each dashboard recommendation card logs an impression carrying its arm and model score; clicking through logs an attributed click. Click-through rate per arm is reported on the public model card and the admin dashboard, giving an online ground truth against which the offline ranking metrics can be judged.

### 9.5 Observability, CI/CD, and Infrastructure as Code

A Prometheus endpoint at `/metrics` exposes request rate, latency, and status **by route pattern** (bounded label cardinality) plus domain gauges and the model-drift score; it is default-deny in production unless a `METRICS_TOKEN` is configured. Optional Sentry error monitoring initializes from `SENTRY_DSN` with PII disabled. Continuous integration (GitHub Actions) runs `ruff` linting and the `pytest` suite on both Python 3.9 (development floor) and 3.11 (production runtime), plus the frontend typecheck/test/build, with a coverage floor. A `Dockerfile` and `docker-compose.yml` reproduce the full stack (web, PostgreSQL, Redis, worker) locally; a `render.yaml` Blueprint provisions the same topology on Render as infrastructure-as-code; and a `--profile observability` compose target brings up Prometheus and Grafana with a provisioned dashboard.

### 9.6 React + TypeScript Client

A **feature-flagged** single-page client (`/beta/projects`), built with React 18, TypeScript, and Vite, consumes the JSON API through typed clients with debounced search and pagination. It is gated twice — by login and by the `FEATURE_SPA` flag, which is off by default in production — so a new surface ships deliberately rather than by accident. Its typecheck, unit tests (Vitest), and build are enforced in CI. The client demonstrates that the API is a genuine second door into the same domain logic the server-rendered app uses.

### 9.7 Feature Expansion

Nine user-facing features extend the collaboration lifecycle, each grounded in a pain point from Section 1.1:

| Feature | What it does | Ties to |
|---|---|---|
| **Teammate Finder** | Ranks *people* whose skills, courses, and interests complement the user's, with explainable reasons; reuses the LSA embedding space (user-to-user cosine). Never exposes emails. | Information-asymmetry problem |
| **Applicant fit score** | Project owners see a fit percentage and the reasons behind it beside each applicant, sorted best-first. | Skill-visibility gap |
| **Weekly digest** | The recommender served on a schedule: each active student's top match is delivered as an in-app notification and web push, deduplicated to avoid spam. | Team-formation friction |
| **Semantic search + duplicate detection** | Browse-projects search ranks by meaning (embedding cosine), and the post form advises when a semantically similar open project already exists — "join instead of duplicating." | Platform fragmentation |
| **Contribution analytics** | Every public profile shows messages, posts, files shared, and voice sessions — making contribution history visible. | Accountability gap / free-riding |
| **Instructor dashboard** | An instructor/admin-gated view grouping active projects by course and flagging at-risk teams (no activity in 7+ days, deadline within 5 days, overdue). | Limited instructor oversight |
| **Kanban task board** | A per-project To-Do / In-Progress / Done board with drag-and-drop, touch-friendly move controls, and member assignment; every endpoint authorizes by project membership. | Joint task performance |
| **AI quiz generator** | Students paste or upload notes (`.txt`/`.md`/`.pdf`); SSM-1.0 returns a validated multiple-choice practice quiz with instant client-side scoring and explanations. Notes are processed in memory and never stored. | Study support |
| **AI meeting notes** | An opt-in recording in a study-group room is transcribed with Whisper (`whisper-large-v3`) and summarized by the LLM into the group's live-synced shared notes and broadcast to members. Audio is never stored. | Communication / resource sharing |

Every feature was built to the same bar: locked to the existing design system (palette, typography, components), responsive to mobile and tablet, authorized by the appropriate gate (login, role, membership, or ownership), rate-limited on expensive LLM and search paths, XSS-safe in every client-rendered fragment, and covered by tests. A subsequent performance review of the ML-backed read paths found and fixed an N+1 / one-at-a-time embedding pattern by batching embeddings and eager-loading relationships.

---

## 10. Limitations and Future Work

### 10.1 Current Limitations

1. **Full-Mesh Voice Topology:** The peer-to-peer WebRTC mesh topology has O(n²) connection complexity, making it unsuitable for rooms with more than 6–8 participants. A selective forwarding unit (SFU) architecture would be needed for larger rooms.

2. **Single-Worker Real-Time Fan-Out:** Group chat now delivers messages in real time over SocketIO — a v3.x change that replaced the former 3-second HTTP polling — with a slow reconnect/​fallback poll for resilience. The broadcast, however, relies on a single eventlet worker holding every room member in-process; scaling SocketIO across multiple workers would require a shared message queue (e.g., Redis) to fan events out between processes.

3. **Single-Server Recommendation Engine:** The recommender scores all open projects on each request (O(n) projects). A v3.0 performance pass batched the embedding transforms and eager-loaded relationships to remove an N+1 pattern, but for very large deployments this path would still need indexing, caching, or an approximate-nearest-neighbour index over the embedding space.

4. **Recommender Data Scarcity:** The learned recommender is trained on a small number of interaction pairs (memberships and applications). Its reported ROC-AUC, while measured leakage-free, rests on few positive examples and is therefore a fragile estimate; the semantic embedding tower adds no aggregate lift at this corpus size. Model quality is expected to improve substantially only as interaction data accumulates and the model is retrained. This is disclosed transparently on the public model card rather than obscured.

5. **Partial Test Coverage:** Version 3.0 introduced an automated suite (120+ backend `pytest` tests plus a frontend suite) gated in CI with a coverage floor, resolving the earlier absence of testing. Coverage is concentrated on business logic, authorization gates, and the data/ML pipelines rather than being exhaustive; broad template-rendering and end-to-end (Playwright) coverage remain future work.

6. **CSP `unsafe-inline`:** The nonce infrastructure exists but is not fully utilized due to inline event handlers in templates. Removing `unsafe-inline` requires a frontend refactor.

7. **Limited Accessibility:** While the UI is responsive, it has not undergone formal WCAG 2.1 accessibility auditing.

8. **AI Response Quality:** The free-tier Groq/LLaMA models may produce lower-quality responses compared to commercial alternatives. The keyword-based fallback provides minimal utility.

9. **No Email Verification:** Users can register with any email address without confirming ownership.

10. **Single-Institution Design:** The platform assumes a single university context. Multi-institution support would require tenant isolation.

### 10.2 Planned Improvements

**Delivered since v2.1.** Several items previously listed here were implemented in Version 3.0 (Section 9): a comprehensive test suite and CI; OpenAPI/Swagger documentation with a versioned JSON API; contribution analytics and the instructor dashboard; AI-powered exam preparation (the quiz generator, including PDF upload); multi-language support (English, Turkish, Bosnian); real-time SocketIO group chat (replacing the former polling); and the MLOps, data-warehouse, and observability infrastructure. The roadmap below reflects what remains outstanding.


1. **SFU-Based Voice Architecture:** Migrate from full-mesh WebRTC to a Selective Forwarding Unit (e.g., mediasoup or Janus) to support voice rooms with 20+ concurrent participants while reducing client-side bandwidth requirements.

2. **Chat Presence and Receipts:** Build on the SocketIO delivery now powering group chat (which replaced the former polling) with presence signals such as typing indicators and read receipts, and a shared message queue to fan events across multiple workers.

3. **Deeper Recommender Modelling:** The trained recommender (Section 4.3) ships in v2.1 with a logistic-regression + LSA-embedding hybrid. As interaction volume grows, planned work includes contrastive fine-tuning of the embedding towers on real interaction pairs, transformer-based embeddings (served via a lightweight ONNX runtime to avoid a torch dependency), and collaborative-filtering signals from completion rates and feedback scores.

4. **End-to-End Testing and Higher Coverage:** Add Playwright end-to-end tests for critical user flows and raise the coverage floor toward 80%, complementing the existing unit and integration suite.

5. **CSP Hardening:** Refactor inline event handlers to external scripts with nonce attributes, remove `unsafe-inline` from CSP.

6. **Email Verification:** Confirmation link on registration to prevent impersonation.

7. **WCAG 2.1 AA Compliance:** Conduct a formal accessibility audit and remediate identified issues including keyboard navigation, screen reader compatibility, and color contrast ratios.

8. **Mobile Application:** Develop a React Native or Flutter companion application for native push notifications, offline access, and optimized voice chat on mobile networks.

9. **Persistent File Storage in Production:** Route avatar and banner uploads through the S3 storage abstraction by default so user-uploaded imagery survives redeploys on ephemeral-disk hosts.

10. **LTI Integration:** Implement Learning Tools Interoperability (LTI 1.3) to enable seamless embedding within institutional LMS platforms (Moodle, Canvas) and automated grade passback.

11. **Team-Success Prediction:** Train a model on the accumulating warehouse data to predict whether a project will complete on time from team composition and activity, surfacing at-risk teams to instructors ahead of the rule-based flags in Section 9.7.

12. **Mid-Project Check-Ins:** Periodic teammate pulse surveys during active projects to surface issues before completion.

---

## 11. Conclusion

This white paper has presented ProjectBuddy, an open-source web-based platform that addresses the fundamental challenges of collaborative project-based learning in higher education. By integrating intelligent team formation, real-time multi-modal communication, structured peer assessment, skill endorsement, AI-powered assistance, and administrative tooling into a single cohesive environment, ProjectBuddy represents a significant contribution to the Computer-Supported Collaborative Learning (CSCL) technology landscape. Version 3.0 further demonstrates that a student-built product can be operated with production-grade engineering practice — a versioned API, a data warehouse under quality gates, an MLOps loop with drift monitoring and online experimentation, observability, and CI — without abandoning the honest reporting of negative results (for instance, the recommender's fragile small-sample estimates and the semantic tower's lack of aggregate lift, both disclosed on the public model card).

The platform's technical architecture demonstrates that modern web technologies — Flask, SQLAlchemy 2.0, WebRTC, Redis, scikit-learn, and large language models — can be composed into a robust, secure, and maintainable system suitable for university-scale deployment. The defense-in-depth security approach, with its comprehensive header suite, rate limiting, CSRF protection, and multi-layer file validation, establishes a security baseline appropriate for handling student data in an educational context.

The platform's core contribution is not any single feature but the *combination* of structured listings, gated reputation mechanisms, and consolidated collaboration tools into a single system. A project listing alone is a job board; peer feedback alone is a survey; chat alone is Discord. The value emerges from connecting these elements into a lifecycle: **post → match → form → collaborate → complete → review → carry reputation forward**.

The broader lesson is that tools shape behavior. When team formation is invisible and unaccountable, students optimize for convenience — picking whoever responds first. When it is visible and reputation-bearing, they optimize for quality — picking teammates with a demonstrated track record. ProjectBuddy provides the infrastructure for the second mode.

ProjectBuddy is deployed and actively used at the International University of Sarajevo, where it continues to evolve based on student and faculty feedback. The codebase is maintained as an open-source project, inviting contributions from the educational technology community. We believe that purpose-built collaboration platforms, informed by CSCL research and implemented with production-grade engineering practices, can meaningfully improve the collaborative learning experience for students worldwide.

---

## 12. References

[1] Dillenbourg, P. (1999). *Collaborative Learning: Cognitive and Computational Approaches.* Elsevier Science. ISBN: 978-0-08-043073-7.

[2] Stahl, G., Koschmann, T., & Suthers, D. (2006). Computer-supported collaborative learning: An historical perspective. In R. K. Sawyer (Ed.), *Cambridge Handbook of the Learning Sciences* (pp. 409–426). Cambridge University Press.

[3] Jeong, H., & Hmelo-Silver, C. E. (2016). Seven affordances of computer-supported collaborative learning: How to support collaborative learning? How can technologies help? *Educational Psychologist, 51*(2), 247–265. doi:10.1080/00461520.2016.1158654.

[4] Kasneci, E., Sessler, K., Kuchemann, S., et al. (2023). ChatGPT for good? On opportunities and challenges of large language models for education. *Learning and Individual Differences, 103*, 102274. doi:10.1016/j.lindif.2023.102274.

[5] Oakley, B., Felder, R.M., Brent, R., & Elhajj, I. (2004). Turning Student Groups into Effective Teams. *Journal of Student Centered Learning, 2*(1), 9–34.

[6] Aggarwal, P., & O'Brien, C.L. (2008). Social Loafing on Group Projects: Structural Antecedents and Effect on Student Satisfaction. *Journal of Marketing Education, 30*(3), 255–264.

[7] Yew, E. H. J., & Goh, K. (2016). Problem-based learning: An overview of its process and impact on learning. *Health Professions Education, 2*(2), 75–79. doi:10.1016/j.hpe.2016.01.004.

[8] OWASP Foundation. (2021). *OWASP Top 10 — 2021.* Available at: https://owasp.org/www-project-top-ten/.

[9] Grinberg, M. (2018). *Flask Web Development: Developing Web Applications with Python* (2nd ed.). O'Reilly Media. ISBN: 978-1-491-99173-2.

[10] Bayer, M. (2023). SQLAlchemy 2.0 Documentation: Mapped Column Declarations. Available at: https://docs.sqlalchemy.org/en/20/.

[11] Mozilla Developer Network. (2024). WebRTC API Reference. Available at: https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API.

[12] Flask-SocketIO Documentation. (2024). Flask-SocketIO: Socket.IO integration for Flask applications. Available at: https://flask-socketio.readthedocs.io/.

[13] OWASP Foundation. (2021). *Secure Coding Practices Quick Reference Guide.* Available at: https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/.

[14] Flask Documentation. Available at: https://flask.palletsprojects.com/.

---

*ProjectBuddy is open source under the MIT License. Source code: [github.com/ssaaffaakk/Project-buddy-Pb](https://github.com/ssaaffaakk/Project-buddy-Pb)*
