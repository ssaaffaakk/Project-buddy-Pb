"""
Database Models
"""

from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    department = db.Column(db.String(100))
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    is_banned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # Relationships
    interest_tags = db.relationship("UserInterest", lazy=True, cascade="all, delete-orphan")
    skills = db.relationship("UserSkill", lazy=True, cascade="all, delete-orphan")
    courses = db.relationship("UserCourse", lazy=True, cascade="all, delete-orphan")
    projects_owned = db.relationship("Project", foreign_keys="Project.owner_id", lazy=True)
    memberships = db.relationship("ProjectMember", foreign_keys="ProjectMember.user_id", lazy=True)
    applications_sent = db.relationship("Application", foreign_keys="Application.applicant_id", lazy=True)
    feedback_received = db.relationship("Feedback", foreign_keys="Feedback.receiver_id", lazy=True)
    endorsements_received = db.relationship("Endorsement", foreign_keys="Endorsement.receiver_id", lazy=True)
    badges = db.relationship("UserBadge", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_instructor(self):
        return self.role == "instructor"

    def is_admin(self):
        return self.role == "admin"

    def is_student_or_instructor(self):
        return self.role in ("student", "instructor")

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_profile_url(self):
        return f"/profile/{self.id}"


class UserInterest(db.Model):
    __tablename__ = "user_interests"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tag = db.Column(db.String(50), nullable=False)


class UserSkill(db.Model):
    __tablename__ = "user_skills"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    skill = db.Column(db.String(80), nullable=False)
    level = db.Column(db.String(20), default="beginner")


class UserCourse(db.Model):
    __tablename__ = "user_courses"
    __allow_unmapped__ = True

    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course  = db.Column(db.String(100), nullable=False)


class Project(db.Model):
    __tablename__ = "projects"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course = db.Column(db.String(100))
    team_size = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="open")
    deadline = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)

    owner = db.relationship("User", foreign_keys=[owner_id], lazy=True, overlaps="projects_owned")
    topic_tags = db.relationship("ProjectTag", lazy=True, cascade="all, delete-orphan")
    required_skills = db.relationship("ProjectSkill", lazy=True, cascade="all, delete-orphan")
    members = db.relationship("ProjectMember", lazy=True, cascade="all, delete-orphan", overlaps="memberships")
    applications = db.relationship("Application", lazy=True, cascade="all, delete-orphan", overlaps="applications_sent")
    votes=db.relationship("ProjectVote", lazy='dynamic', cascade="all, delete-orphan")

    def active_members(self):
        return [member for member in self.members if not member.removed]

    def is_full(self):
        return self.current_member_count() >= self.team_size

    def current_member_count(self):
        return len(self.active_members())

    def mark_complete(self):
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)()

    def close(self):
        self.status = "closed"
    
    @property
    def vote_score(self):
        from sqlalchemy import func
        ups = self.votes.filter_by(direction="up").count()
        downs = self.votes.filter_by(direction="down").count()
        return ups - downs


class ProjectTag(db.Model):
    __tablename__ = "project_tags"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    tag = db.Column(db.String(50), nullable=False)


class ProjectSkill(db.Model):
    __tablename__ = "project_skills"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    skill = db.Column(db.String(80), nullable=False)


class ProjectMember(db.Model):
    __tablename__ = "project_members"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(50), default="member")
    joined_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    removed = db.Column(db.Boolean, default=False)
    removed_at = db.Column(db.DateTime)

    project = db.relationship("Project", lazy=True, overlaps="members")
    user = db.relationship("User", lazy=True, overlaps="memberships")


class Application(db.Model):
    __tablename__ = "applications"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    reviewed_at = db.Column(db.DateTime)

    project = db.relationship("Project", lazy=True, overlaps="applications")
    applicant = db.relationship("User", foreign_keys=[applicant_id], lazy=True, overlaps="applications_sent")


class ProjectMessage(db.Model):
    __tablename__ = "project_messages"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    project = db.relationship("Project", lazy=True)
    sender = db.relationship("User", lazy=True)


class AdminMessage(db.Model):
    __tablename__ = "admin_messages"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    is_warning = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))


class Feedback(db.Model):
    __tablename__ = "feedbacks"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    giver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    is_instructor_rating = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    giver = db.relationship("User", foreign_keys=[giver_id], lazy=True)
    receiver = db.relationship("User", foreign_keys=[receiver_id], lazy=True, overlaps="feedback_received")


class Endorsement(db.Model):
    __tablename__ = "endorsements"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    giver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    skill = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))


class Badge(db.Model):
    __tablename__ = "badges"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text)
    icon = db.Column(db.String(200))
    condition = db.Column(db.String(100))


class UserBadge(db.Model):
    __tablename__ = "user_badges"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey("badges.id"), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    badge = db.relationship("Badge", lazy=True)


class Report(db.Model):
    __tablename__ = "reports"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    target_project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    reason = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    resolved_at = db.Column(db.DateTime)

    reporter = db.relationship("User", foreign_keys=[reporter_id])
    target_user = db.relationship("User", foreign_keys=[target_user_id])
    target_project = db.relationship("Project", foreign_keys=[target_project_id])


class Chat(db.Model):
    __tablename__ = "chats"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject = db.Column(db.String(200))
    status = db.Column(db.String(20), default="open")
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    closed_at = db.Column(db.DateTime)

    user = db.relationship("User", foreign_keys=[user_id], lazy=True)
    admin = db.relationship("User", foreign_keys=[admin_id], lazy=True)
    messages = db.relationship("ChatMessage", lazy=True, order_by="ChatMessage.id")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey("chats.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    chat = db.relationship("Chat", lazy=True, overlaps="messages")
    sender = db.relationship("User", lazy=True)


class CommunityPost(db.Model):
    __tablename__ = "community_posts"
    __allow_unmapped__ = True

    id         = db.Column(db.Integer, primary_key=True)
    author_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title      = db.Column(db.String(200))
    body       = db.Column(db.Text, nullable=False)
    media_url  = db.Column(db.String(500))
    media_type = db.Column(db.String(10))   # 'image' | 'video'
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    author   = db.relationship("User", foreign_keys=[author_id], lazy=True)
    comments = db.relationship("CommunityComment", lazy=True, cascade="all, delete-orphan",
                               order_by="CommunityComment.created_at")
    likes    = db.relationship("CommunityLike", lazy=True, cascade="all, delete-orphan")


class CommunityComment(db.Model):
    __tablename__ = "community_comments"
    __allow_unmapped__ = True

    id         = db.Column(db.Integer, primary_key=True)
    post_id    = db.Column(db.Integer, db.ForeignKey("community_posts.id"), nullable=False)
    author_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body       = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    author = db.relationship("User", foreign_keys=[author_id], lazy=True)


class CommunityLike(db.Model):
    __tablename__ = "community_likes"
    __allow_unmapped__ = True

    id         = db.Column(db.Integer, primary_key=True)
    post_id    = db.Column(db.Integer, db.ForeignKey("community_posts.id"), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("post_id", "user_id"),)


class ProjectVote(db.Model):
    __tablename__ = "project_votes"
    __allow_unmapped__ = True

    id         = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"),    nullable=False)
    direction  = db.Column(db.String(4), nullable=False)  # "up" or "down"
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("project_id", "user_id", name="unique_project_vote"),)


class Notification(db.Model):
    __tablename__ = "notifications"
    __allow_unmapped__ = True

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type       = db.Column(db.String(30))   # 'comment' | 'apply' | 'accepted' | 'rejected' | 'mention'
    message    = db.Column(db.String(300), nullable=False)
    link       = db.Column(db.String(200))  # URL to go to when clicked
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))


class PasswordReset(db.Model):
    __tablename__ = "password_resets"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token = db.Column(db.String(256), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    user = db.relationship("User", lazy=True)

    def is_expired(self, expiry_seconds=86400):
        expiry_time = self.created_at + timedelta(seconds=expiry_seconds)
        return datetime.now(timezone.utc)() > expiry_time


# ── SHARED FILES ─────────────────────────────────────────────────────────────

class SharedFile(db.Model):
    __tablename__ = "shared_files"
    __allow_unmapped__ = True

    id          = db.Column(db.Integer, primary_key=True)
    group_id    = db.Column(db.Integer, db.ForeignKey("study_groups.id"), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename    = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    file_size   = db.Column(db.Integer, default=0)
    mime_type   = db.Column(db.String(120), default='application/octet-stream')
    created_at  = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    uploader = db.relationship("User", lazy=True)


# ── STUDY GROUPS ─────────────────────────────────────────────────────────────

class StudyGroup(db.Model):
    __tablename__ = "study_groups"
    __allow_unmapped__ = True

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False)
    topic       = db.Column(db.String(80))          # e.g. "Python", "ML", "Web Dev"
    description = db.Column(db.Text)
    creator_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_private  = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    creator  = db.relationship("User", foreign_keys=[creator_id], lazy=True)
    members  = db.relationship("StudyGroupMember", lazy=True, cascade="all, delete-orphan")
    messages = db.relationship("StudyGroupMessage", lazy=True, cascade="all, delete-orphan",
                               order_by="StudyGroupMessage.created_at")

    def member_count(self):
        return len(self.members)

    def is_member(self, user_id):
        return any(m.user_id == user_id for m in self.members)


class StudyGroupMember(db.Model):
    __tablename__ = "study_group_members"
    __allow_unmapped__ = True

    id         = db.Column(db.Integer, primary_key=True)
    group_id   = db.Column(db.Integer, db.ForeignKey("study_groups.id"), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role       = db.Column(db.String(20), default="member")   # "admin" | "member"
    joined_at  = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    user = db.relationship("User", lazy=True)

    __table_args__ = (db.UniqueConstraint("group_id", "user_id"),)


class StudyGroupMessage(db.Model):
    __tablename__ = "study_group_messages"
    __allow_unmapped__ = True

    id         = db.Column(db.Integer, primary_key=True)
    group_id   = db.Column(db.Integer, db.ForeignKey("study_groups.id"), nullable=False)
    author_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body       = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    author = db.relationship("User", lazy=True)


# ── AI CHATBOT ────────────────────────────────────────────────────────────────

class ChatbotSession(db.Model):
    """Stores per-user chatbot conversation history (last 20 messages kept)."""
    __tablename__ = "chatbot_sessions"
    __allow_unmapped__ = True

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role       = db.Column(db.String(10), nullable=False)   # "user" | "assistant"
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
