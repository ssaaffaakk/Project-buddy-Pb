"""add data-warehouse star schema (dw_dim_user, dw_dim_project,
dw_fact_daily_activity, dw_daily_metrics) — written only by services/etl.py

Revision ID: b7f3d19c8e42
Revises: a1c9e7d24b31
Create Date: 2026-07-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7f3d19c8e42'
down_revision = 'a1c9e7d24b31'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'dw_dim_user',
        sa.Column('user_id', sa.Integer(), nullable=False, autoincrement=False),
        sa.Column('full_name', sa.String(length=161), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('department', sa.String(length=100), nullable=True),
        sa.Column('signup_date', sa.Date(), nullable=True),
        sa.Column('onboarded', sa.Boolean(), nullable=False),
        sa.Column('is_banned', sa.Boolean(), nullable=False),
        sa.Column('n_interests', sa.Integer(), nullable=False),
        sa.Column('n_skills', sa.Integer(), nullable=False),
        sa.Column('loaded_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
    )
    op.create_table(
        'dw_dim_project',
        sa.Column('project_id', sa.Integer(), nullable=False, autoincrement=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('course', sa.String(length=100), nullable=True),
        sa.Column('team_size', sa.Integer(), nullable=False),
        sa.Column('created_date', sa.Date(), nullable=True),
        sa.Column('completed_date', sa.Date(), nullable=True),
        sa.Column('n_tags', sa.Integer(), nullable=False),
        sa.Column('n_skills', sa.Integer(), nullable=False),
        sa.Column('n_members', sa.Integer(), nullable=False),
        sa.Column('loaded_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('project_id'),
    )
    op.create_table(
        'dw_fact_daily_activity',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('events_total', sa.Integer(), nullable=False),
        sa.Column('logins', sa.Integer(), nullable=False),
        sa.Column('project_views', sa.Integer(), nullable=False),
        sa.Column('applications', sa.Integer(), nullable=False),
        sa.Column('rec_impressions', sa.Integer(), nullable=False),
        sa.Column('rec_clicks', sa.Integer(), nullable=False),
        sa.Column('chatbot_messages', sa.Integer(), nullable=False),
        sa.Column('voice_joins', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date', 'user_id', name='uq_dw_fact_day_user'),
    )
    op.create_index(op.f('ix_dw_fact_daily_activity_date'),
                    'dw_fact_daily_activity', ['date'])
    op.create_index(op.f('ix_dw_fact_daily_activity_user_id'),
                    'dw_fact_daily_activity', ['user_id'])
    op.create_table(
        'dw_daily_metrics',
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('dau', sa.Integer(), nullable=False),
        sa.Column('signups', sa.Integer(), nullable=False),
        sa.Column('applications', sa.Integer(), nullable=False),
        sa.Column('projects_created', sa.Integer(), nullable=False),
        sa.Column('posts', sa.Integer(), nullable=False),
        sa.Column('rec_impressions', sa.Integer(), nullable=False),
        sa.Column('rec_clicks', sa.Integer(), nullable=False),
        sa.Column('rec_ctr', sa.Float(), nullable=False),
        sa.Column('loaded_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('date'),
    )


def downgrade():
    op.drop_table('dw_daily_metrics')
    op.drop_index(op.f('ix_dw_fact_daily_activity_user_id'),
                  table_name='dw_fact_daily_activity')
    op.drop_index(op.f('ix_dw_fact_daily_activity_date'),
                  table_name='dw_fact_daily_activity')
    op.drop_table('dw_fact_daily_activity')
    op.drop_table('dw_dim_project')
    op.drop_table('dw_dim_user')
