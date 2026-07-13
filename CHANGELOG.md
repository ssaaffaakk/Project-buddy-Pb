# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Real-time group chat over SocketIO, replacing the former 3-second HTTP polling.
- Group-chat presence: live typing indicators and an online-member count.
- Jump-to-latest pill so incoming messages don't yank readers away from history.
- Delete a chat message (author, group creator, or admin), removed for everyone live.
- Idle-session timeout: users are signed out after 30 minutes of inactivity
  (`SESSION_IDLE_TIMEOUT_MIN`); background polls don't keep an AFK session alive.
- Email-address confirmation flow scaffolding was explored and reverted (see history).
- Accessibility pass: skip-to-content link, keyboard focus ring, `#main-content` landmark.

### Changed
- Documentation moved under `docs/` (white paper, architecture); added community
  health files (`CONTRIBUTING`, `SECURITY`, this changelog, GitHub templates).

## [3.0.0]

### Added
- Versioned, OpenAPI-documented JSON API (`/api/v1`) with JWT auth and schema validation.
- Celery task queue with a transparent in-process fallback (no broker required).
- Nightly ELT pipeline loading a star-schema data warehouse under data-quality gates.
- MLOps loop for the recommender: artifact versioning/rollback, scheduled retraining,
  and feature-drift monitoring; ranking metrics and optional MLflow tracking.
- Product analytics (DAU/WAU/MAU, funnel, retention) and a live A/B experiment for the recommender.
- Observability via Prometheus `/metrics` and optional Sentry; CI, Docker, and `render.yaml` IaC.
- Feature-flagged React + TypeScript projects explorer over the API.
- Nine product features: teammate finder, applicant fit score, weekly digest, semantic
  project search with duplicate detection, contribution analytics, instructor dashboard,
  per-project kanban board, AI quiz generator, and AI meeting notes.

## [2.1.0]

### Added
- Live collaboration rooms (WebRTC voice/video/screen share) with a live-synced shared notepad.
- A trained machine-learning recommender (logistic regression + LSA embeddings) with a public model card.
- Social/identity layer: interdisciplinary interest taxonomy, first-run onboarding,
  public profile walls, and in-chat file attachments.

## [1.x]

### Added
- Initial platform: project posting and applications, team formation, peer feedback and
  endorsements, badges, community feed, study groups, admin/moderation, and an AI chatbot.
