from datetime import datetime, timedelta
from sqlalchemy import or_

from extensions import db
from models import (
    Application,
    Chat,
    ChatMessage,
    Endorsement,
    Feedback,
    Project,
    ProjectMember,
    ProjectMessage,
    ProjectSkill,
    ProjectTag,
    Report,
    User,
    UserBadge,
    UserInterest,
    UserSkill,
)
from config import Config
from services.badge_service import check_and_award_badges


MOCK_PASSWORD = Config.MOCK_PASSWORD
ADMIN_EMAIL = Config.ADMIN_EMAIL
MOCK_EMAIL_SUFFIX = Config.MOCK_EMAIL_SUFFIX

MOCK_USERS = [
    {
        "key": "milena",
        "first_name": "Milena",
        "last_name": "Petrovic",
        "email": "milena.petrovic@mock.projectbuddy.local",
        "role": "instructor",
        "department": "Software Engineering",
        "bio": "Instructor supervising product-focused campus software teams.",
        "created_days_ago": 240,
        "interests": ["React", "Python", "Cloud Computing", "UI/UX Design", "Data Analysis"],
        "skills": [
            ("React", "advanced"),
            ("REST API", "advanced"),
            ("SQL / Database", "advanced"),
            ("UI/UX Design", "intermediate"),
        ],
    },
    {
        "key": "denis",
        "first_name": "Denis",
        "last_name": "Kovacic",
        "email": "denis.kovacic@mock.projectbuddy.local",
        "role": "instructor",
        "department": "Computer Science",
        "bio": "AI-focused instructor helping students turn research ideas into products.",
        "created_days_ago": 210,
        "interests": ["Python", "Machine Learning", "Cloud Computing", "Data Analysis", "Web Scraping"],
        "skills": [
            ("Python", "advanced"),
            ("Machine Learning", "advanced"),
            ("Flask / Django", "advanced"),
            ("Data Analysis", "advanced"),
        ],
    },
    {
        "key": "aya",
        "first_name": "Aya",
        "last_name": "Demir",
        "email": "aya.demir@mock.projectbuddy.local",
        "role": "student",
        "department": "Software Engineering",
        "bio": "Frontend-heavy builder who likes polished interfaces and campus tools.",
        "created_days_ago": 120,
        "interests": ["React", "Mobile Dev", "UI/UX Design", "Cloud Computing", "Data Analysis"],
        "skills": [
            ("React", "advanced"),
            ("Flutter", "intermediate"),
            ("Firebase", "intermediate"),
            ("UI/UX Design", "advanced"),
        ],
    },
    {
        "key": "emir",
        "first_name": "Emir",
        "last_name": "Hodzic",
        "email": "emir.hodzic@mock.projectbuddy.local",
        "role": "student",
        "department": "Computer Science",
        "bio": "Backend student building practical tools for campus operations.",
        "created_days_ago": 150,
        "interests": ["Python", "SQL / DB", "Cloud Computing", "DevOps", "Cybersecurity"],
        "skills": [
            ("Python", "advanced"),
            ("Node.js", "intermediate"),
            ("SQL / Database", "advanced"),
            ("DevOps / Docker", "intermediate"),
        ],
    },
    {
        "key": "selma",
        "first_name": "Selma",
        "last_name": "Karic",
        "email": "selma.karic@mock.projectbuddy.local",
        "role": "student",
        "department": "Computer Science",
        "bio": "Security-minded full-stack student who enjoys research-backed projects.",
        "created_days_ago": 95,
        "interests": ["Cybersecurity", "React", "Machine Learning", "Data Analysis", "Networks"],
        "skills": [
            ("React", "intermediate"),
            ("Cybersecurity", "advanced"),
            ("REST API", "intermediate"),
            ("Data Analysis", "intermediate"),
        ],
    },
    {
        "key": "faris",
        "first_name": "Faris",
        "last_name": "Salic",
        "email": "faris.salic@mock.projectbuddy.local",
        "role": "student",
        "department": "Electrical Engineering",
        "bio": "Enjoys data-heavy dashboards, sensors, and real-world automation ideas.",
        "created_days_ago": 110,
        "interests": ["Data Analysis", "Machine Learning", "Python", "Cloud Computing", "Networks"],
        "skills": [
            ("Python", "advanced"),
            ("Data Analysis", "advanced"),
            ("Machine Learning", "intermediate"),
            ("REST API", "intermediate"),
        ],
    },
    {
        "key": "lejla",
        "first_name": "Lejla",
        "last_name": "Mesic",
        "email": "lejla.mesic@mock.projectbuddy.local",
        "role": "student",
        "department": "Business Administration",
        "bio": "Product-minded teammate who pairs design thinking with user research.",
        "created_days_ago": 80,
        "interests": ["Business", "UI/UX Design", "Mobile Dev", "React", "Data Analysis"],
        "skills": [
            ("UI/UX Design", "advanced"),
            ("Figma", "advanced"),
            ("React", "beginner"),
            ("Firebase", "intermediate"),
        ],
    },
    {
        "key": "tarik",
        "first_name": "Tarik",
        "last_name": "Brkic",
        "email": "tarik.brkic@mock.projectbuddy.local",
        "role": "student",
        "department": "Software Engineering",
        "bio": "Generalist who likes shipping MVPs fast and tightening them later.",
        "created_days_ago": 70,
        "interests": ["React", "Python", "SQL / DB", "Cloud Computing", "DevOps"],
        "skills": [
            ("Node.js", "intermediate"),
            ("React", "intermediate"),
            ("SQL / Database", "intermediate"),
            ("DevOps / Docker", "intermediate"),
        ],
    },
]

MOCK_PROJECTS = [
    {
        "title": "Course Planner Rebuild",
        "owner": "milena",
        "description": (
            "Rebuilding the semester planning experience with prerequisite checks, "
            "smart conflict warnings, and a clean UI for students."
        ),
        "course": "CS401 - Software Engineering",
        "team_size": 4,
        "status": "open",
        "created_days_ago": 12,
        "deadline_days_from": 14,
        "tags": ["Frontend", "Backend", "Databases", "Cloud", "Security"],
        "skills": ["React", "Node.js", "SQL / Database", "REST API"],
        "members": ["milena", "aya", "emir"],
        "applications": [
            {"applicant": "lejla", "message": "I can handle UX flows and usability testing."},
        ],
        "messages": [
            ("milena", "I pushed the latest planning flow notes.", 11),
            ("aya", "I can take the calendar and drag-drop interactions.", 10),
            ("emir", "I will map the prerequisite data model tonight.", 9),
        ],
    },
    {
        "title": "Lecture Summarizer with AI",
        "owner": "denis",
        "description": (
            "A campus tool that turns lecture notes into concise summaries, quiz prompts, "
            "and revision cards for students."
        ),
        "course": "CS415 - Machine Learning",
        "team_size": 4,
        "status": "open",
        "created_days_ago": 9,
        "deadline_days_from": 10,
        "tags": ["AI / ML", "Backend", "Data", "Research", "Cloud"],
        "skills": ["Python", "Machine Learning", "Flask / Django", "Data Analysis"],
        "members": ["denis", "faris"],
        "applications": [
            {"applicant": "tarik", "message": "Happy to help with APIs and deployment."},
            {"applicant": "selma", "message": "I can cover evaluation and prompt safety."},
        ],
        "messages": [
            ("denis", "Please review the baseline summarization metrics.", 8),
            ("faris", "Uploaded the notebook for the first evaluation batch.", 7),
        ],
    },
    {
        "title": "Campus Events Mobile App",
        "owner": "aya",
        "description": (
            "Mobile-first app for student clubs to publish events, collect RSVPs, and push reminders "
            "without relying on scattered social posts."
        ),
        "course": None,
        "team_size": 4,
        "status": "open",
        "created_days_ago": 6,
        "deadline_days_from": 21,
        "tags": ["Mobile", "Frontend", "Design", "Cloud", "Backend"],
        "skills": ["Flutter", "Firebase", "UI/UX Design", "REST API"],
        "members": ["aya", "lejla"],
        "applications": [
            {"applicant": "emir", "message": "I can connect the auth and event APIs."},
        ],
        "messages": [
            ("aya", "Design direction is warm, simple, and student-friendly.", 5),
            ("lejla", "I finished the onboarding wireframes.", 4),
        ],
    },
    {
        "title": "Cybersecurity Awareness Portal",
        "owner": "selma",
        "description": (
            "Interactive portal with short awareness modules, phishing simulations, "
            "and a reporting area for suspicious activity."
        ),
        "course": None,
        "team_size": 4,
        "status": "open",
        "created_days_ago": 4,
        "deadline_days_from": 16,
        "tags": ["Frontend", "Backend", "Security", "Design", "Research"],
        "skills": ["React", "Cybersecurity", "UI/UX Design", "REST API"],
        "members": ["selma"],
        "applications": [
            {"applicant": "faris", "message": "I can help with analytics and reporting views."},
            {"applicant": "tarik", "message": "I can help with the API and deployment side."},
        ],
        "messages": [
            ("selma", "I want the first module to focus on phishing red flags.", 3),
        ],
    },
    {
        "title": "Lab Equipment Booking Platform",
        "owner": "milena",
        "description": (
            "Scheduling platform for lab gear reservations, availability tracking, "
            "and approval workflows for assistants."
        ),
        "course": "CS306 - Database Management",
        "team_size": 4,
        "status": "closed",
        "created_days_ago": 18,
        "deadline_days_from": 2,
        "tags": ["Backend", "Databases", "Design", "Security", "Data"],
        "skills": ["SQL / Database", "React", "REST API", "Node.js"],
        "members": ["milena", "tarik", "lejla"],
        "applications": [],
        "messages": [
            ("milena", "The booking rules changed after the last staff meeting.", 17),
            ("tarik", "I updated the reservation conflict checks.", 15),
            ("lejla", "I polished the empty states and booking confirmations.", 14),
        ],
    },
    {
        "title": "IUS Bus Tracker Dashboard",
        "owner": "emir",
        "description": (
            "Web dashboard for bus ETAs, route delays, and occupancy estimates so commuting "
            "students can plan around busy periods."
        ),
        "course": None,
        "team_size": 4,
        "status": "completed",
        "created_days_ago": 30,
        "completed_days_ago": 3,
        "tags": ["Frontend", "Mobile", "Data", "Cloud", "Design"],
        "skills": ["React", "Data Analysis", "Firebase", "REST API"],
        "members": ["emir", "selma", "faris"],
        "applications": [],
        "messages": [
            ("emir", "Realtime ETA polling is stable now.", 24),
            ("faris", "I added occupancy trend charts.", 20),
            ("selma", "Accessibility pass is complete on the main dashboard.", 18),
        ],
    },
    {
        "title": "Smart Study Group Matcher",
        "owner": "denis",
        "description": (
            "Matching service that groups students by availability, course overlap, "
            "and complementary skill profiles."
        ),
        "course": "CS401 - Software Engineering",
        "team_size": 4,
        "status": "completed",
        "created_days_ago": 42,
        "completed_days_ago": 9,
        "tags": ["Backend", "Data", "Research", "Cloud", "Design"],
        "skills": ["Python", "Data Analysis", "REST API", "React"],
        "members": ["denis", "aya", "tarik"],
        "applications": [],
        "messages": [
            ("denis", "The matching weights look balanced now.", 35),
            ("tarik", "I finished the profile scoring API.", 31),
            ("aya", "The recommendation cards are ready for review.", 28),
        ],
    },
]

MOCK_FEEDBACK = [
    {
        "project": "IUS Bus Tracker Dashboard",
        "giver": "selma",
        "receiver": "emir",
        "rating": 5,
        "comment": "Emir kept the backend stable and always shared progress clearly.",
    },
    {
        "project": "IUS Bus Tracker Dashboard",
        "giver": "faris",
        "receiver": "selma",
        "rating": 5,
        "comment": "Selma caught UI issues early and improved the dashboard structure a lot.",
    },
    {
        "project": "Smart Study Group Matcher",
        "giver": "tarik",
        "receiver": "aya",
        "rating": 5,
        "comment": "Aya turned rough requirements into a polished and friendly interface.",
    },
    {
        "project": "Smart Study Group Matcher",
        "giver": "aya",
        "receiver": "tarik",
        "rating": 4,
        "comment": "Tarik moved quickly and handled the matching API without drama.",
    },
    {
        "project": "Smart Study Group Matcher",
        "giver": "denis",
        "receiver": "aya",
        "rating": 5,
        "comment": "Aya combined good product judgment with clean implementation details.",
        "is_instructor_rating": True,
    },
]

MOCK_ENDORSEMENTS = [
    ("emir", "aya", "React"),
    ("emir", "aya", "REST API"),
    ("selma", "aya", "UI/UX Design"),
    ("selma", "aya", "Firebase"),
    ("faris", "aya", "Data Analysis"),
    ("lejla", "aya", "Flutter"),
    ("tarik", "aya", "Product Thinking"),
    ("milena", "aya", "Leadership"),
    ("denis", "aya", "Python"),
    ("denis", "aya", "Machine Learning"),
    ("aya", "emir", "Python"),
    ("milena", "emir", "SQL / Database"),
    ("denis", "faris", "Data Analysis"),
    ("lejla", "selma", "Cybersecurity"),
]

MOCK_REPORTS = [
    {
        "reporter": "tarik",
        "target_user": "faris",
        "reason": "spam",
        "description": "Posted duplicate invite links in the project chat while testing the announcements flow.",
    },
    {
        "reporter": "lejla",
        "target_project": "Cybersecurity Awareness Portal",
        "reason": "fake_listing",
        "description": "The project page lacked enough implementation detail and looked suspicious at first glance.",
    },
]

MOCK_SUPPORT_CHATS = [
    {
        "user": "lejla",
        "subject": "Cannot update application status",
        "status": "open",
        "admin": None,
        "created_days_ago": 2,
        "messages": [
            ("lejla", "I accepted an applicant but the page still shows it as pending.", 2),
        ],
    },
    {
        "user": "tarik",
        "subject": "Question about report review time",
        "status": "open",
        "admin": "admin",
        "created_days_ago": 5,
        "messages": [
            ("tarik", "How long does it usually take for a project report to be reviewed?", 5),
            ("admin", "Usually within one business day unless we need more context.", 4),
        ],
    },
    {
        "user": "aya",
        "subject": "Need help removing a duplicate application",
        "status": "closed",
        "admin": "admin",
        "created_days_ago": 11,
        "closed_days_ago": 8,
        "messages": [
            ("aya", "A teammate managed to submit the same application twice in testing.", 11),
            ("admin", "I removed the duplicate and double-checked the record.", 10),
            ("aya", "Perfect, thanks for the quick help.", 9),
        ],
    },
]


def seed_mock_data():
    now = datetime.utcnow()
    admin = _ensure_admin_user(now)
    if _mock_data_is_seeded():
        return

    users = _seed_mock_users(now)
    projects = _seed_mock_projects(users, now)
    _seed_feedback(users, projects, now)
    _seed_endorsements(users, now)
    _seed_reports(users, projects, now)
    _seed_support_chats(admin, users, now)
    _seed_badges_for_mock_users(users)
    db.session.commit()


def _mock_data_is_seeded():
    mock_user_count = User.query.filter(User.email.like(f"%{MOCK_EMAIL_SUFFIX}")).count()
    mock_project_count = (
        Project.query.join(User, Project.owner_id == User.id)
        .filter(User.email.like(f"%{MOCK_EMAIL_SUFFIX}"))
        .count()
    )
    mock_chat_count = (
        Chat.query.join(User, Chat.user_id == User.id)
        .filter(User.email.like(f"%{MOCK_EMAIL_SUFFIX}"))
        .count()
    )

    return (
        mock_user_count >= len(MOCK_USERS)
        and mock_project_count >= len(MOCK_PROJECTS)
        and mock_chat_count >= len(MOCK_SUPPORT_CHATS)
    )


def _ensure_admin_user(now):
    admin = User.query.filter_by(email=ADMIN_EMAIL).first()
    if not admin:
        admin = User(
            first_name="Admin",
            last_name="User",
            email=ADMIN_EMAIL,
            role="admin",
            department="ProjectBuddy",
            created_at=now - timedelta(days=365),
        )
        admin.set_password(Config.ADMIN_PASSWORD or Config.MOCK_PASSWORD)
        db.session.add(admin)
    db.session.flush()
    return admin


def _seed_mock_users(now):
    users = {}

    for spec in MOCK_USERS:
        user = User.query.filter_by(email=spec["email"]).first()
        if not user:
            user = User(email=spec["email"])
            db.session.add(user)

        user.first_name = spec["first_name"]
        user.last_name = spec["last_name"]
        user.role = spec["role"]
        user.department = spec["department"]
        user.bio = spec["bio"]
        user.is_active = True
        user.is_banned = False
        user.created_at = now - timedelta(days=spec["created_days_ago"])
        user.set_password(MOCK_PASSWORD)

        db.session.flush()
        users[spec["key"]] = user

        UserInterest.query.filter_by(user_id=user.id).delete()
        UserSkill.query.filter_by(user_id=user.id).delete()

        for tag in spec["interests"]:
            db.session.add(UserInterest(user_id=user.id, tag=tag))

        for skill, level in spec["skills"]:
            db.session.add(UserSkill(user_id=user.id, skill=skill, level=level))

    return users


def _seed_mock_projects(users, now):
    projects = {}

    for spec in MOCK_PROJECTS:
        owner = users[spec["owner"]]
        project = Project.query.filter_by(title=spec["title"], owner_id=owner.id).first()
        if not project:
            project = Project(title=spec["title"], owner_id=owner.id)
            db.session.add(project)

        project.description = spec["description"]
        project.course = spec["course"]
        project.team_size = spec["team_size"]
        project.status = spec["status"]
        project.created_at = now - timedelta(days=spec["created_days_ago"])
        project.deadline = (
            now + timedelta(days=spec["deadline_days_from"])
            if "deadline_days_from" in spec
            else None
        )
        project.completed_at = (
            now - timedelta(days=spec["completed_days_ago"])
            if spec["status"] == "completed"
            else None
        )

        db.session.flush()
        projects[spec["title"]] = project
        _sync_project_activity(project, spec, users, now)

    return projects


def _sync_project_activity(project, spec, users, now):
    ProjectTag.query.filter_by(project_id=project.id).delete()
    ProjectSkill.query.filter_by(project_id=project.id).delete()
    ProjectMember.query.filter_by(project_id=project.id).delete()
    Application.query.filter_by(project_id=project.id).delete()
    ProjectMessage.query.filter_by(project_id=project.id).delete()

    for tag in spec["tags"]:
        db.session.add(ProjectTag(project_id=project.id, tag=tag))

    for skill in spec["skills"]:
        db.session.add(ProjectSkill(project_id=project.id, skill=skill))

    for member_key in spec["members"]:
        db.session.add(
            ProjectMember(
                project_id=project.id,
                user_id=users[member_key].id,
                joined_at=now - timedelta(days=max(spec["created_days_ago"] - 1, 1)),
                removed=False,
            )
        )

    for application in spec["applications"]:
        db.session.add(
            Application(
                project_id=project.id,
                applicant_id=users[application["applicant"]].id,
                message=application["message"],
                status="pending",
                created_at=now - timedelta(days=max(spec["created_days_ago"] - 1, 1)),
            )
        )

    for sender_key, content, days_ago in spec["messages"]:
        db.session.add(
            ProjectMessage(
                project_id=project.id,
                sender_id=users[sender_key].id,
                content=content,
                created_at=now - timedelta(days=days_ago),
            )
        )


def _seed_feedback(users, projects, now):
    Feedback.query.filter(Feedback.project_id.in_([project.id for project in projects.values()])).delete(
        synchronize_session=False
    )

    for spec in MOCK_FEEDBACK:
        db.session.add(
            Feedback(
                project_id=projects[spec["project"]].id,
                giver_id=users[spec["giver"]].id,
                receiver_id=users[spec["receiver"]].id,
                rating=spec["rating"],
                comment=spec["comment"],
                is_instructor_rating=spec.get("is_instructor_rating", False),
                created_at=now - timedelta(days=2),
            )
        )


def _seed_endorsements(users, now):
    user_ids = [user.id for user in users.values()]
    Endorsement.query.filter(
        or_(
            Endorsement.giver_id.in_(user_ids),
            Endorsement.receiver_id.in_(user_ids),
        )
    ).delete(synchronize_session=False)

    for giver_key, receiver_key, skill in MOCK_ENDORSEMENTS:
        db.session.add(
            Endorsement(
                giver_id=users[giver_key].id,
                receiver_id=users[receiver_key].id,
                skill=skill,
                created_at=now - timedelta(days=1),
            )
        )


def _seed_reports(users, projects, now):
    user_ids = [user.id for user in users.values()]
    project_ids = [project.id for project in projects.values()]

    Report.query.filter(
        or_(
            Report.reporter_id.in_(user_ids),
            Report.target_user_id.in_(user_ids),
            Report.target_project_id.in_(project_ids),
        )
    ).delete(synchronize_session=False)

    for spec in MOCK_REPORTS:
        report = Report(
            reporter_id=users[spec["reporter"]].id,
            reason=spec["reason"],
            description=spec["description"],
            status="pending",
            created_at=now - timedelta(days=1),
        )

        if "target_user" in spec:
            report.target_user_id = users[spec["target_user"]].id
        if "target_project" in spec:
            report.target_project_id = projects[spec["target_project"]].id

        db.session.add(report)


def _seed_support_chats(admin, users, now):
    user_ids = [user.id for user in users.values()]
    chat_ids = [
        chat.id
        for chat in Chat.query.filter(Chat.user_id.in_(user_ids)).all()
    ]

    if chat_ids:
        ChatMessage.query.filter(ChatMessage.chat_id.in_(chat_ids)).delete(synchronize_session=False)
        Chat.query.filter(Chat.id.in_(chat_ids)).delete(synchronize_session=False)

    for spec in MOCK_SUPPORT_CHATS:
        chat = Chat(
            user_id=users[spec["user"]].id,
            admin_id=admin.id if spec["admin"] == "admin" else None,
            subject=spec["subject"],
            status=spec["status"],
            created_at=now - timedelta(days=spec["created_days_ago"]),
            closed_at=(
                now - timedelta(days=spec["closed_days_ago"])
                if spec["status"] == "closed"
                else None
            ),
        )
        db.session.add(chat)
        db.session.flush()

        for sender_key, message, days_ago in spec["messages"]:
            sender_id = admin.id if sender_key == "admin" else users[sender_key].id
            db.session.add(
                ChatMessage(
                    chat_id=chat.id,
                    sender_id=sender_id,
                    message=message,
                    created_at=now - timedelta(days=days_ago),
                )
            )


def _seed_badges_for_mock_users(users):
    user_ids = [user.id for user in users.values()]
    UserBadge.query.filter(UserBadge.user_id.in_(user_ids)).delete(synchronize_session=False)
    db.session.flush()

    for user in users.values():
        check_and_award_badges(user.id)
