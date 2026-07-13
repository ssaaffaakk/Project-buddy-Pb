"""add project_tasks.due_date

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-13

Idempotent: guarded on introspection (create_all may already have added the
column on a fresh DB).
"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def _has_column(insp, table, column):
    if table not in set(insp.get_table_names()):
        return False
    return column in {c['name'] for c in insp.get_columns(table)}


def upgrade():
    insp = sa.inspect(op.get_bind())
    if not _has_column(insp, 'project_tasks', 'due_date'):
        with op.batch_alter_table('project_tasks', schema=None) as batch_op:
            batch_op.add_column(sa.Column('due_date', sa.DateTime(), nullable=True))


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _has_column(insp, 'project_tasks', 'due_date'):
        with op.batch_alter_table('project_tasks', schema=None) as batch_op:
            batch_op.drop_column('due_date')
