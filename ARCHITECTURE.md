# ProjectBuddy - System Architecture

## Project Overview

ProjectBuddy is a university project collaboration platform where students and instructors can post projects, form teams, communicate, and provide peer feedback.

**Tech Stack:**
- Backend: Flask (Python)
- Database: SQLAlchemy ORM (SQLite/PostgreSQL)
- Frontend: HTML + CSS + JavaScript
- Authentication: Flask-Login + werkzeug

---

## System Architecture Diagram

```mermaid
architecture-beta
    group client(internet)[Client Layer]
    group app(cloud)[Flask Application]
    group services(cloud)[Services Layer]
    group data(database)[Data Layer]

    service web(internet)[Web Browser] in client

    service auth(server)[Auth Routes] in app
    service admin(server)[Admin Routes] in app
    service projects_route(server)[Projects Routes] in app
    service chat_route(server)[Chat Routes] in app
    service users_route(server)[Users Routes] in app
    service main_route(server)[Main Routes] in app

    service badge_svc(server)[Badge Service] in services
    service recommend_svc(server)[Recommendation Service] in services
    service deadline_svc(server)[Deadline Checker] in services
    service email_svc(server)[Email Service] in services

    service db(database)[SQLAlchemy Database] in data
    service cache(disk)[Session Storage] in data

    web:R --> L:main_route
    web:R --> L:auth
    web:R --> L:projects_route
    web:R --> L:chat_route
    web:R --> L:admin
    web:R --> L:users_route

    auth:B --> T:db
    projects_route:B --> T:db
    chat_route:B --> T:db
    users_route:B --> T:db
    admin:B --> T:db

    projects_route:R --> L:recommend_svc
    projects_route:R --> L:badge_svc
    users_route:R --> L:badge_svc
    deadline_svc:B --> T:db

    auth:R --> L:email_svc
    users_route:R --> L:email_svc

    admin:B --> T:cache
```

---

## Layer 1: Client Layer

The frontend user interface running in web browsers.

- templates/ - HTML pages (Jinja2 templating)
- static/css/ - Styling and layout
- static/js/ - Interactive functionality
- static/images/ - UI assets

---

## Layer 2: Flask Routes (Business Logic)

| Route Module | Responsibility |
|---|---|
| auth.py | User registration, login, password reset |
| main.py | Home page, navigation, public endpoints |
| projects.py | Create, browse, apply to projects |
| users.py | User profiles, skill endorsements, feedback |
| chat.py | Real-time messaging between users and support |
| admin.py | Admin dashboard, user management, reports |
| email.py | Transactional and notification emails |

---

## Layer 3: Services Layer (Business Processes)

| Service | Function |
|---|---|
| Badge Service | Award achievements based on user activity |
| Recommendation Service | Suggest projects based on user interests |
| Deadline Checker | Monitor project deadlines and send reminders |
| Email Service | Send notifications and transactional emails |

---

## Layer 4: Data Layer (Database & Models)

**Core Database Models:**

- User - Account info, roles (student/instructor/admin), profile
- Project - Project listings with details, deadline, team size
- ProjectMember - Team membership tracking
- Application - User applications to join projects
- Feedback - Peer feedback and ratings
- Endorsement - Skill endorsements from peers
- UserBadge - Earned achievements
- UserInterest - Interest tags for recommendations
- UserSkill - Skills and expertise tracking
- Message - Chat messages within projects

**Database:** SQLite (development) or PostgreSQL (production)

---

## Data Flow Example: Applying to a Project

```mermaid
flowchart TD
    A[User Browses Projects] --> B[Projects Route]
    B --> C[Query Database]
    C --> D{Apply to Project?}
    D -->|Yes| E[Create Application Record]
    E --> F[Store in Database]
    F --> G[Notify Project Owner]
    G --> H[Email Service Sends Notification]
    H --> I[Project Owner Reviews Application]
    I --> J{Accept or Reject?}
    J -->|Accept| K[Create ProjectMember Record]
    K --> L[Badge Service Awards Achievement]
    L --> M[Send Acceptance Email]
    M --> N[Add to Recommendations Cache]
```

---

## User Roles and Permissions

**Admin**
- User management
- Report handling and moderation
- System-wide warnings and bans
- Analytics and statistics

**Instructor**
- Post and manage projects
- Manage team members
- Give peer feedback
- View project analytics

**Student**
- Browse projects
- Apply to projects
- Join teams
- Give and receive feedback
- Earn badges

---

## Key Architecture Features

**Authentication and Authorization**
- Password hashing with werkzeug
- Flask-Login session management
- Role-based access control (RBAC)
- Email-based identity verification

**Project Management**
- Project creation and posting
- Application system for joining
- Team member management
- Project deadline tracking with automated reminders
- Team chat for collaboration

**Reputation and Social Features**
- Badge system for achievements
- Skill endorsements from peers
- Project completion feedback and ratings
- User profile reputation scores

**Support and Moderation**
- Admin support chat
- Report submission system
- User warnings and account restrictions
- Content moderation dashboard

---

## Project File Structure

```
ProjectBuddy/
├── app.py                  # Flask app factory and initialization
├── config.py               # Environment configuration
├── extensions.py           # Flask extensions setup
├── models.py               # Database models
├── requirements.txt        # Python dependencies
│
├── routes/                 # Route handlers
│   ├── __init__.py
│   ├── auth.py            # Authentication endpoints
│   ├── main.py            # Home and navigation
│   ├── projects.py        # Project CRUD operations
│   ├── users.py           # User profiles and endorsements
│   ├── chat.py            # Messaging system
│   ├── admin.py           # Admin dashboard
│   └── email.py           # Email sending
│
├── services/              # Business logic services
│   ├── badge_service.py       # Badge award logic
│   ├── recommendation_service.py  # Project recommendations
│   ├── deadline_checker.py    # Deadline monitoring
│   ├── bootstrap_service.py   # System initialization
│   └── mock_data.py           # Sample data for testing
│
├── templates/             # HTML templates
│   ├── base.html          # Base template
│   ├── auth.html          # Login and Registration
│   ├── dashboard.html     # User dashboard
│   ├── projects.html      # Project listings
│   ├── project_detail.html
│   ├── admin_dashboard.html
│   └── ... (16 total templates)
│
├── static/                # Static assets
│   ├── css/
│   │   └── style.css      # Stylesheet
│   ├── js/
│   │   └── main.js        # JavaScript functionality
│   └── images/            # UI images
│
├── scripts/               # Utility scripts
│   ├── init_db.py         # Initialize database
│   ├── create_admin.py    # Create admin user
│   └── mock.py            # Load sample data
│
├── logs/                  # Application logs
├── instance/              # Instance-specific files
└── README.md              # Project documentation
```

---

## Getting Started

1. Clone or download the project
2. `python -m venv venv` and activate it
3. `pip install -r requirements.txt`
4. `cp .env.example .env` and fill in secrets (never commit `.env`)
5. Run: `python app.py` (creates DB, admin, optional mock data on first start)
6. Open: `http://localhost:5001` (or your `PORT` in `.env`)

Optional: `flask db upgrade` after pulling new migrations; `python scripts/create_admin.py` if admin was not created.

---

## Key Dependencies

- Flask - Web framework
- SQLAlchemy - ORM for database
- Flask-Login - User session management
- Flask-Mail - Email sending
- Werkzeug - Utilities for authentication
