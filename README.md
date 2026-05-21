ProjectBuddy
Find the right teammates. Build real projects. Earn your reputation.
ProjectBuddy is a web platform built for university students to find project collaborators, form teams, and build a verified reputation — without the chaos of WhatsApp groups.

Demo


Why I Built This
Last semester, a project I worked on got rejected. Not because of my work — but because my partner didn’t deliver. The semester before that, I couldn’t find a partner at all, and my professor refused to accept a solo submission.
Two projects. Two failures. Neither one was about my ability. Both were about a broken system for forming teams.
Finding project partners at university still means posting “anyone want to join?” in a WhatsApp group. You pick someone based on nothing — no visibility into their skills, their work ethic, or how they perform under pressure. When that goes wrong, it doesn’t just slow you down. It costs you grades.
I went to my professor, explained the problem, and told him I was going to build the solution. He didn’t just listen — he let me submit it as my project.
So I built ProjectBuddy.
Not a tutorial clone. Not a homework assignment. A real platform, built out of frustration, designed to make sure no student ever loses marks because of a partner mismatch again.
The smart matching engine surfaces projects that fit your skills. The reputation system means every completed project leaves a trail — ratings, endorsements, badges. Next time, you don’t pick a stranger. You pick someone with a track record.
I didn’t want to work with just anyone anymore. So I built the tool that makes sure no one has to.
I build things because I run into problems and refuse to accept that they can’t be solved.

The Problem
Finding project partners at university still means posting “anyone want to join?” in group chats. Nobody knows what anyone else can actually do, and there’s no way to see who contributed what in past projects. ProjectBuddy fixes that.

Features
Projects
	∙	Post a project — set a title, description, required skills, topic tags, team size, course, and deadline
	∙	Browse open projects — filterable list of all active projects on the platform
	∙	Smart recommendations — dashboard surfaces projects that match your skills and interests
	∙	Upvote / downvote — community can vote on projects to highlight the best ones
	∙	Apply to join — submit a message with your application; owner reviews and accepts or rejects
	∙	Auto-close — when the team is full, the listing closes automatically
	∙	Mark complete — owner marks the project done when it’s finished; triggers badge awards for all members
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
	∙	Invite-based private groups
AI Chatbot
	∙	Built-in assistant to help navigate the platform
	∙	Powered by Groq API (leave GROQ_API_KEY blank for mock responses)
	∙	Conversation history persisted per user (last 20 messages)
Notifications
	∙	In-app notifications for: application received, accepted, rejected, new comment, mention
	∙	Email notifications for key events (requires Gmail setup)
Auth
	∙	Email/password registration with email verification
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



|Variable                 |Required      |Description                                                                 |
|-------------------------|--------------|----------------------------------------------------------------------------|
|`SECRET_KEY`             |Yes           |Random hex string for sessions and CSRF                                     |
|`FLASK_APP`              |Yes           |`app:create_app`                                                            |
|`ADMIN_EMAIL`            |Yes           |Admin login email                                                           |
|`ADMIN_PASSWORD`         |Yes           |Admin login password                                                        |
|`FLASK_ENV`              |No            |`development` (default) or `production`                                     |
|`PORT`                   |No            |Server port (default `5001`)                                                |
|`SQLALCHEMY_DATABASE_URI`|No            |DB URL — defaults to SQLite                                                 |
|`MAIL_USERNAME`          |Email features|Gmail address                                                               |
|`MAIL_PASSWORD`          |Email features|Gmail [App Password](https://myaccount.google.com/apppasswords)             |
|`SEED_MOCK_DATA`         |No            |`true` to load demo users on first run                                      |
|`MOCK_PASSWORD`          |No            |Password for demo accounts                                                  |
|`GITHUB_CLIENT_ID`       |OAuth         |From [github.com/settings/developers](http://github.com/settings/developers)|
|`GITHUB_CLIENT_SECRET`   |OAuth         |GitHub OAuth secret                                                         |
|`GITHUB_REDIRECT_URI`    |OAuth         |Must match your GitHub app callback URL                                     |
|`GROQ_API_KEY`           |Chatbot       |Optional — leave blank for mock responses                                   |
|`CORS_ORIGINS`           |Production    |Comma-separated allowed origins for SocketIO                                |

Tech Stack



|Layer    |Technology                                       |
|---------|-------------------------------------------------|
|Backend  |Python · Flask                                   |
|Database |SQLAlchemy ORM · SQLite (dev) / PostgreSQL (prod)|
|Frontend |Jinja2 · HTML · CSS · JavaScript                 |
|Real-time|Flask-SocketIO                                   |
|Auth     |Flask-Login · GitHub OAuth                       |
|Email    |Flask-Mail                                       |
|AI       |Groq API                                         |

Project Structure

ProjectBuddy/
├── app.py                  # App factory and startup
├── config.py               # Environment configuration
├── models.py               # All database models
├── extensions.py           # Flask extensions
├── routes/                 # Route handlers
│   ├── auth.py             # Register, login, OAuth, password reset
│   ├── main.py             # Home, dashboard, navigation
│   ├── projects.py         # Projects, applications, feedback
│   ├── users.py            # Profiles, skills, endorsements
│   ├── chat.py             # Real-time messaging
│   ├── community.py        # Community feed, posts, comments
│   ├── study_groups.py     # Study groups and file sharing
│   ├── chatbot.py          # AI assistant
│   ├── admin.py            # Admin dashboard
│   └── email.py            # Email sending
├── services/
│   ├── badge_service.py        # Badge award logic
│   ├── recommendation_service.py  # Project recommendations
│   ├── deadline_checker.py     # Deadline monitoring + reminders
│   └── bootstrap_service.py    # First-run initialization
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS, JS, images
└── migrations/             # Alembic database migrations


License
MIT — Safak Surmeli​​​​​​​​​​​​​​​​