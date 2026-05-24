# ProjectBuddy

**Find the right teammates. Build real projects. Earn your reputation.**

ProjectBuddy is a web platform built for university students to find project collaborators, form teams, and build a verified reputation — without the chaos of WhatsApp groups.

---

## 🚀 Live Demo

**[https://project-buddy-pb.onrender.com](https://project-buddy-pb.onrender.com)**

> First load may take ~30 seconds (Render free tier spins down after inactivity).

---

## 🎬 Video Demo

[![ProjectBuddy Demo](https://img.youtube.com/vi/X3tt5sjE_ns/maxresdefault.jpg)](https://youtu.be/X3tt5sjE_ns)

---

## Why I Built This
Last semester, a project I worked on got rejected. Not because of my work — but because my partner didn't deliver. The semester before that, I couldn't find a partner at all, and my professor refused to accept a solo submission.
Two projects. Two failures. Neither one was about my ability. Both were about a broken system for forming teams.
Finding project partners at university still means posting "anyone want to join?" in a WhatsApp group. You pick someone based on nothing — no visibility into their skills, their work ethic, or how they perform under pressure. When that goes wrong, it doesn't just slow you down. It costs you grades.
I went to my professor, explained the problem, and told him I was going to build the solution. He didn't just listen — he let me submit it as my project.
So I built ProjectBuddy.
Not a tutorial clone. Not a homework assignment. A real platform, built out of frustration, designed to make sure no student ever loses marks because of a partner mismatch again.
The smart matching engine surfaces projects that fit your skills. The reputation system means every completed project leaves a trail — ratings, endorsements, badges. Next time, you don't pick a stranger. You pick someone with a track record.
I didn't want to work with just anyone anymore. So I built the tool that makes sure no one has to.
I build things because I run into problems and refuse to accept that they can't be solved.

The Problem
Finding project partners at university still means posting "anyone want to join?" in group chats. Nobody knows what anyone else can actually do, and there's no way to see who contributed what in past projects. ProjectBuddy fixes that.

Features
Projects
	∙	Post a project — set a title, description, required skills, topic tags, team size, course, and deadline
	∙	Browse open projects — filterable list of all active projects on the platform
	∙	Smart recommendations — dashboard surfaces projects that match your skills and interests
	∙	Upvote / downvote — community can vote on projects to highlight the best ones
	∙	Apply to join — submit a message with your application; owner reviews and accepts or rejects
	∙	Auto-close — when the team is full, the listing closes automatically
	∙	Mark complete — owner marks the project done when it's finished; triggers badge awards for all members
	∙	Auto-complete — projects past their deadline are automatically marked complete every hour
	∙	Max 3 active projects — prevents commitment overload; enforced on both create and apply
Team Management
	∙	Accept or reject incoming applications
	∙	Remove members from your project
	∙	Real-time team chat per project (powered by SocketIO)
Reputation System
	∙	Peer feedback — after project completion, teammates rate and review each other
	∙	Skill endorsements — endorse specific skills of your teammates, visible on their public profile
	∙	Badges — automatically awarded based on activity (e.g. completing projects, receiving endorsements)
	∙	Public profile — every user has a profile page showing their skills, projects, feedback, endorsements, and badges
Community Feed
	∙	Post updates, ideas, or questions to the community
	∙	Attach images or videos to posts
	∙	Like and comment on posts
	∙	Notifications for comments and mentions
Study Groups
	∙	Create public or private study groups by topic
	∙	Real-time group chat
	∙	Voice rooms — WebRTC peer-to-peer voice calls inside study groups (no external service needed)
	∙	Share files within the group
AI Chatbot
	∙	Built-in assistant to help navigate the platform
	∙	Powered by Groq API (falls back to Anthropic, then built-in mock responses)
	∙	Conversation history persisted per user (last 20 messages)
Notifications
	∙	In-app notifications for: application received, accepted, rejected, new comment, mention
	∙	Email notifications for key events (requires Gmail setup)
Auth
	∙	Email/password registration
	∙	GitHub OAuth — sign in with GitHub in one click
	∙	Password reset via email
	∙	Student, instructor, and admin roles
Admin Panel
	∙	Full user management — search, view, warn, ban, activate/deactivate
	∙	Report handling and moderation queue
	∙	Live support chat (admin ↔ user)
	∙	Platform-wide statistics and analytics
	∙	View AI chatbot conversation logs

Quick Start

git clone https://github.com/ssaaffaakk/Project-buddy-Pb.git
cd Project-buddy-Pb
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in the required values below
flask db upgrade       # apply database migrations
python app.py          # open http://localhost:5001


On first run, the database, admin account, and (optionally) demo users are created automatically.
Minimum .env to get running:

SECRET_KEY=        # python -c "import secrets; print(secrets.token_hex(32))"
ADMIN_EMAIL=       # your admin login email
ADMIN_PASSWORD=    # strong password
FLASK_APP=app:create_app


Demo Accounts
Set SEED_MOCK_DATA=true in .env before first run:



|Role   |Email                      |Password                 |
|-------|---------------------------|-------------------------|
|Admin  |value of `ADMIN_EMAIL`     |value of `ADMIN_PASSWORD`|
|Student|`amir.kovacevic@ius.edu.ba`|value of `MOCK_PASSWORD` |
|Student|`leila.hadzic@ius.edu.ba`  |value of `MOCK_PASSWORD` |

Admin panel: http://localhost:5001/auth/admin-login
Set SEED_MOCK_DATA=false in production.

Configuration



|Variable                  |Required       |Description                                                                   |
|--------------------------|---------------|------------------------------------------------------------------------------|
|`SECRET_KEY`              |Yes            |Random hex string for sessions and CSRF                                       |
|`FLASK_APP`               |Yes            |`app:create_app`                                                              |
|`ADMIN_EMAIL`             |Yes            |Admin login email                                                             |
|`ADMIN_PASSWORD`          |Yes            |Admin login password                                                          |
|`FLASK_ENV`               |No             |`development` (default) or `production`                                       |
|`PORT`                    |No             |Server port (default `5001`)                                                  |
|`SQLALCHEMY_DATABASE_URI` |No             |DB URL — defaults to SQLite                                                   |
|`MAIL_USERNAME`           |Email features |Gmail address                                                                 |
|`MAIL_PASSWORD`           |Email features |Gmail [App Password](https://myaccount.google.com/apppasswords)               |
|`SEED_MOCK_DATA`          |No             |`true` to load demo users on first run                                        |
|`MOCK_PASSWORD`           |No             |Password for demo accounts                                                    |
|`GITHUB_CLIENT_ID`        |OAuth          |From [github.com/settings/developers](http://github.com/settings/developers)  |
|`GITHUB_CLIENT_SECRET`    |OAuth          |GitHub OAuth secret                                                           |
|`GITHUB_REDIRECT_URI`     |OAuth          |Must match your GitHub app callback URL                                       |
|`GROQ_API_KEY`            |Chatbot        |Optional — falls back to Anthropic then mock responses                        |
|`ANTHROPIC_API_KEY`       |Chatbot        |Optional — used if GROQ_API_KEY is not set                                    |
|`CORS_ORIGINS`            |Production     |Comma-separated allowed origins for SocketIO                                  |
|`REDIS_URL`               |Production     |Redis connection URL — required for multi-worker rate limiting and voice rooms |
|`AWS_S3_BUCKET`           |Production     |S3 bucket name for file uploads — falls back to local disk if not set         |
|`AWS_S3_REGION`           |Production     |S3 region (default: `us-east-1`)                                              |
|`AWS_ACCESS_KEY_ID`       |Production     |AWS IAM key                                                                   |
|`AWS_SECRET_ACCESS_KEY`   |Production     |AWS IAM secret                                                                |
|`AWS_CLOUDFRONT_URL`      |Production     |Optional CDN prefix for uploaded files                                        |

Tech Stack



|Layer       |Technology                                                     |
|------------|---------------------------------------------------------------|
|Backend     |Python 3.9 · Flask 3.1                                         |
|Database    |SQLAlchemy 2.0 ORM · SQLite (dev) / PostgreSQL (prod)          |
|Migrations  |Flask-Migrate (Alembic)                                        |
|Frontend    |Jinja2 · HTML · CSS · JavaScript                               |
|Real-time   |Flask-SocketIO · eventlet · WebRTC (voice) · Xirsys TURN       |
|Auth        |Flask-Login · GitHub OAuth · HMAC-signed state                 |
|Email       |smtplib · STARTTLS (Gmail)                                     |
|AI          |Groq API (Llama 3) · Anthropic API (Claude) · built-in mock    |
|Scheduler   |APScheduler (deadline auto-complete, runs every 1h)            |
|File Storage|Local disk (dev) · AWS S3 / S3-compatible (prod)               |
|Deployment  |Render (hosting) · PostgreSQL (prod DB)                        |
|Rate Limiting|Flask-Limiter · Redis (prod) / in-memory (dev)               |
|Security    |CSRF (Flask-WTF) · CSP nonces · HSTS · security headers        |

Project Structure

ProjectBuddy/
├── app.py                  # App factory, security headers, scheduler startup
├── config.py               # Environment configuration (Dev / Test / Prod)
├── extensions.py           # Flask extensions + admin_required decorator
├── models.py               # 25 SQLAlchemy 2.0 models
├── wsgi.py                 # Production entry point (gunicorn + eventlet)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
│
├── routes/                 # Blueprint route handlers
│   ├── auth.py             # Register, login, GitHub OAuth, password reset
│   ├── main.py             # Dashboard, profiles, project UI
│   ├── projects.py         # Project CRUD, applications, feedback, endorsements
│   ├── users.py            # User search, public profiles
│   ├── chat.py             # User ↔ admin support chat
│   ├── community.py        # Community feed, posts, comments, likes
│   ├── study_groups.py     # Study groups, file sharing
│   ├── voice.py            # WebRTC signaling (SocketIO events)
│   ├── chatbot.py          # AI assistant (Groq / Anthropic / mock)
│   ├── admin.py            # Admin dashboard and moderation
│   └── email.py            # Transactional email (SMTP)
│
├── services/
│   ├── badge_service.py          # Badge award logic (event-driven)
│   ├── recommendation_service.py # Interest-based project recommendations
│   ├── deadline_checker.py       # Auto-complete overdue projects (scheduled)
│   ├── file_storage.py           # Local / S3 file storage abstraction
│   └── mock_data.py              # Seed realistic demo data
│
├── templates/              # Jinja2 HTML templates (CSP nonce-aware)
├── static/                 # CSS, JS, images
├── migrations/             # Alembic database migrations
└── logs/                   # Rotating application logs


License
MIT — Safak Surmeli
