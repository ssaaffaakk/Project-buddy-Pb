"""add hot-path indexes (DBA pass)

Foreign keys and filter columns used by the busiest queries: dashboards join
project_members/applications per user, project pages load tags/skills/messages
per project, notification polling filters user_id+is_read.

Revision ID: c3e8f5a71d29
Revises: b7f3d19c8e42
Create Date: 2026-07-11

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'c3e8f5a71d29'
down_revision = 'b7f3d19c8e42'
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_projects_owner_id", "projects", ["owner_id"]),
    ("ix_projects_status", "projects", ["status"]),
    ("ix_project_tags_project_id", "project_tags", ["project_id"]),
    ("ix_project_skills_project_id", "project_skills", ["project_id"]),
    ("ix_project_members_project_id", "project_members", ["project_id"]),
    ("ix_project_members_user_id", "project_members", ["user_id"]),
    ("ix_applications_project_id", "applications", ["project_id"]),
    ("ix_applications_applicant_id", "applications", ["applicant_id"]),
    ("ix_project_messages_project_id", "project_messages", ["project_id"]),
    ("ix_feedbacks_receiver_id", "feedbacks", ["receiver_id"]),
    ("ix_endorsements_receiver_id", "endorsements", ["receiver_id"]),
    ("ix_community_comments_post_id", "community_comments", ["post_id"]),
    ("ix_study_group_messages_group_id", "study_group_messages", ["group_id"]),
    ("ix_shared_files_group_id", "shared_files", ["group_id"]),
    ("ix_chatbot_sessions_user_id", "chatbot_sessions", ["user_id"]),
    ("ix_notifications_user_id", "notifications", ["user_id"]),
]


def upgrade():
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade():
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
