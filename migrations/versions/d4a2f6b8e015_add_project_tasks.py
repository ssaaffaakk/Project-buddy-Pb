"""add project_tasks (kanban board)

Revision ID: d4a2f6b8e015
Revises: c3e8f5a71d29
Create Date: 2026-07-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4a2f6b8e015'
down_revision = 'c3e8f5a71d29'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'project_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('assignee_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['assignee_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_project_tasks_project_id'), 'project_tasks', ['project_id'])


def downgrade():
    op.drop_index(op.f('ix_project_tasks_project_id'), table_name='project_tasks')
    op.drop_table('project_tasks')
