"""
Database Models
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Text, Boolean, DateTime, CheckConstraint
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default="student")
    department: Mapped[Optional[str]] = mapped_column(String(100))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    # Profile cover image — an uploaded URL, or a "preset:<key>" gradient token
    banner_url: Mapped[Optional[str]] = mapped_column(String(500))
    # False until the user finishes (or skips) the first-run profile setup
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    interest_tags = db.relationship("UserInterest", lazy=True, cascade="all, delete-orphan")
    skills = db.relationship("UserSkill", lazy=True, cascade="all, delete-orphan")
    courses = db.relationship("UserCourse", lazy=True, cascade="all, delete-orphan")
    projects_owned = db.relationship("Project", foreign_keys="Project.owner_id", lazy=True)
    memberships = db.relationship("ProjectMember", foreign_keys="ProjectMember.user_id", lazy=True)
    applications_sent = db.relationship("Application", foreign_keys="Application.applicant_id", lazy=True)
    feedback_received = db.relationship("Feedback", foreign_keys="Feedback.receiver_id", lazy=True)
    endorsements_received = db.relationship("Endorsement", foreign_keys="Endorsement.receiver_id", lazy=True)
    badges = db.relationship("UserBadge", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def is_instructor(self) -> bool:
        return self.role == "instructor"

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_student_or_instructor(self) -> bool:
        return self.role in ("student", "instructor")

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def get_profile_url(self) -> str:
        return f"/profile/{self.id}"


class UserInterest(db.Model):
    __tablename__ = "user_interests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    tag: Mapped[str] = mapped_column(String(50))


class UserSkill(db.Model):
    __tablename__ = "user_skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    skill: Mapped[str] = mapped_column(String(80))
    level: Mapped[str] = mapped_column(String(20), default="beginner")


class UserCourse(db.Model):
    __tablename__ = "user_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    course: Mapped[str] = mapped_column(String(100))


class Project(db.Model):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    course: Mapped[Optional[str]] = mapped_column(String(100))
    team_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="open")
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    owner = db.relationship("User", foreign_keys="Project.owner_id", lazy=True, overlaps="projects_owned")
    topic_tags = db.relationship("ProjectTag", lazy=True, cascade="all, delete-orphan")
    required_skills = db.relationship("ProjectSkill", lazy=True, cascade="all, delete-orphan")
    members = db.relationship("ProjectMember", lazy=True, cascade="all, delete-orphan", overlaps="memberships")
    applications = db.relationship("Application", lazy=True, cascade="all, delete-orphan", overlaps="applications_sent")
    votes = db.relationship("ProjectVote", lazy='dynamic', cascade="all, delete-orphan")

    def active_members(self):
        return [member for member in self.members if not member.removed]

    def is_full(self) -> bool:
        return self.current_member_count() >= self.team_size

    def current_member_count(self) -> int:
        return len(self.active_members())

    def mark_complete(self) -> None:
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)

    def close(self) -> None:
        self.status = "closed"

    @property
    def vote_score(self) -> int:
        ups = self.votes.filter_by(direction="up").count()
        downs = self.votes.filter_by(direction="down").count()
        return ups - downs


class ProjectTag(db.Model):
    __tablename__ = "project_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(db.ForeignKey("projects.id"))
    tag: Mapped[str] = mapped_column(String(50))


class ProjectSkill(db.Model):
    __tablename__ = "project_skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(db.ForeignKey("projects.id"))
    skill: Mapped[str] = mapped_column(String(80))


class ProjectMember(db.Model):
    __tablename__ = "project_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(db.ForeignKey("projects.id"))
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(50), default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    removed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    project = db.relationship("Project", lazy=True, overlaps="members")
    user = db.relationship("User", lazy=True, overlaps="memberships")


class Application(db.Model):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(db.ForeignKey("projects.id"))
    applicant_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    message: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    project = db.relationship("Project", lazy=True, overlaps="applications")
    applicant = db.relationship("User", foreign_keys="Application.applicant_id", lazy=True, overlaps="applications_sent")


class ProjectMessage(db.Model):
    __tablename__ = "project_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(db.ForeignKey("projects.id"))
    sender_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = db.relationship("Project", lazy=True)
    sender = db.relationship("User", lazy=True)


class AdminMessage(db.Model):
    __tablename__ = "admin_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    sender_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Feedback(db.Model):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("projects.id"))
    giver_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    receiver_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column(Integer, CheckConstraint("rating BETWEEN 1 AND 5"))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    is_instructor_rating: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    giver = db.relationship("User", foreign_keys="Feedback.giver_id", lazy=True)
    receiver = db.relationship("User", foreign_keys="Feedback.receiver_id", lazy=True, overlaps="feedback_received")


class Endorsement(db.Model):
    __tablename__ = "endorsements"

    id: Mapped[int] = mapped_column(primary_key=True)
    giver_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    receiver_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    skill: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Badge(db.Model):
    __tablename__ = "badges"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    icon: Mapped[Optional[str]] = mapped_column(String(200))
    condition: Mapped[Optional[str]] = mapped_column(String(100))


class UserBadge(db.Model):
    __tablename__ = "user_badges"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    badge_id: Mapped[int] = mapped_column(db.ForeignKey("badges.id"))
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    badge = db.relationship("Badge", lazy=True)


class Report(db.Model):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    target_user_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("users.id"))
    target_project_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("projects.id"))
    reason: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    reporter = db.relationship("User", foreign_keys="Report.reporter_id")
    target_user = db.relationship("User", foreign_keys="Report.target_user_id")
    target_project = db.relationship("Project", foreign_keys="Report.target_project_id")


class Chat(db.Model):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    subject: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="open")
    admin_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user = db.relationship("User", foreign_keys="Chat.user_id", lazy=True)
    admin = db.relationship("User", foreign_keys="Chat.admin_id", lazy=True)
    messages = db.relationship("ChatMessage", lazy=True, order_by="ChatMessage.id")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(db.ForeignKey("chats.id"))
    sender_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    chat = db.relationship("Chat", lazy=True, overlaps="messages")
    sender = db.relationship("User", lazy=True)


class CommunityPost(db.Model):
    __tablename__ = "community_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    title: Mapped[Optional[str]] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    media_url: Mapped[Optional[str]] = mapped_column(String(500))
    media_type: Mapped[Optional[str]] = mapped_column(String(10))  # 'image' | 'video'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    author = db.relationship("User", foreign_keys="CommunityPost.author_id", lazy=True)
    comments = db.relationship("CommunityComment", lazy=True, cascade="all, delete-orphan",
                               order_by="CommunityComment.created_at")
    likes = db.relationship("CommunityLike", lazy=True, cascade="all, delete-orphan")


class CommunityComment(db.Model):
    __tablename__ = "community_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(db.ForeignKey("community_posts.id"))
    author_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    author = db.relationship("User", foreign_keys="CommunityComment.author_id", lazy=True)


class CommunityLike(db.Model):
    __tablename__ = "community_likes"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(db.ForeignKey("community_posts.id"))
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("post_id", "user_id"),)


class ProjectVote(db.Model):
    __tablename__ = "project_votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(db.ForeignKey("projects.id"))
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    direction: Mapped[str] = mapped_column(String(4))  # "up" or "down"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("project_id", "user_id", name="unique_project_vote"),)


class Notification(db.Model):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    type: Mapped[Optional[str]] = mapped_column(String(30))  # 'comment' | 'apply' | 'accepted' | 'rejected' | 'mention'
    message: Mapped[str] = mapped_column(String(300))
    link: Mapped[Optional[str]] = mapped_column(String(200))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class PasswordReset(db.Model):
    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    token: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", lazy=True)

    def is_expired(self, expiry_seconds: int = 86400) -> bool:
        expiry_time = self.created_at + timedelta(seconds=expiry_seconds)
        return datetime.now(timezone.utc).replace(tzinfo=None) > expiry_time


# ── SHARED FILES ─────────────────────────────────────────────────────────────

class SharedFile(db.Model):
    __tablename__ = "shared_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(db.ForeignKey("study_groups.id"))
    uploader_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(120), default='application/octet-stream')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    uploader = db.relationship("User", lazy=True)


# ── STUDY GROUPS ─────────────────────────────────────────────────────────────

class StudyGroup(db.Model):
    __tablename__ = "study_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    topic: Mapped[Optional[str]] = mapped_column(String(80))  # e.g. "Python", "ML", "Web Dev"
    description: Mapped[Optional[str]] = mapped_column(Text)
    creator_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    creator = db.relationship("User", foreign_keys="StudyGroup.creator_id", lazy=True)
    members = db.relationship("StudyGroupMember", lazy=True, cascade="all, delete-orphan")
    messages = db.relationship("StudyGroupMessage", lazy=True, cascade="all, delete-orphan",
                               order_by="StudyGroupMessage.created_at")

    def member_count(self) -> int:
        return len(self.members)

    def is_member(self, user_id: int) -> bool:
        return any(m.user_id == user_id for m in self.members)


class StudyGroupMember(db.Model):
    __tablename__ = "study_group_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(db.ForeignKey("study_groups.id"))
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20), default="member")  # "admin" | "member"
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", lazy=True)

    __table_args__ = (db.UniqueConstraint("group_id", "user_id"),)


class StudyGroupMessage(db.Model):
    __tablename__ = "study_group_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(db.ForeignKey("study_groups.id"))
    author_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    # Optional file dropped straight into the chat (rendered inline in the stream)
    attachment_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("shared_files.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    author = db.relationship("User", lazy=True)
    attachment = db.relationship("SharedFile", lazy=True, foreign_keys=[attachment_id])


class StudyGroupNote(db.Model):
    """One shared collaborative note per study group, live-synced over SocketIO."""
    __tablename__ = "study_group_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(db.ForeignKey("study_groups.id"), unique=True)
    content: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[Optional[int]] = mapped_column(db.ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ProfileComment(db.Model):
    """A public wall post left on someone's profile. Anyone may post; the
    profile owner (or an admin) can delete; anyone can report or like."""
    __tablename__ = "profile_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), index=True)  # whose wall
    author_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))               # who wrote it
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    author = db.relationship("User", lazy=True, foreign_keys=[author_id])
    likes = db.relationship("ProfileCommentLike", lazy=True, cascade="all, delete-orphan")

    def like_count(self) -> int:
        return len(self.likes)

    def liked_by(self, user_id: int) -> bool:
        return any(l.user_id == user_id for l in self.likes)


class ProfileCommentLike(db.Model):
    __tablename__ = "profile_comment_likes"

    id: Mapped[int] = mapped_column(primary_key=True)
    comment_id: Mapped[int] = mapped_column(db.ForeignKey("profile_comments.id"))
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))

    __table_args__ = (db.UniqueConstraint("comment_id", "user_id"),)


# ── AI CHATBOT ────────────────────────────────────────────────────────────────

class ChatbotSession(db.Model):
    """Stores per-user chatbot conversation history (last 20 messages kept)."""
    __tablename__ = "chatbot_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(10))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
