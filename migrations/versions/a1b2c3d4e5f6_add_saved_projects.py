"""add saved_projects (bookmarks)

Revision ID: a1b2c3d4e5f6
Revises: d4a2f6b8e015
Create Date: 2026-07-13

Idempotent (same as revision 4f4eee5c0502): the app's boot-time create_all()
safety net may already have created the table, so DDL is guarded on
introspection.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'd4a2f6b8e015'
branch_labels = None
depends_on = None


def _has_table(insp, name):
    return name in set(insp.get_table_names())


def upgrade():
    insp = sa.inspect(op.get_bind())
    if not _has_table(insp, 'saved_projects'):
        op.create_table(
            'saved_projects',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'project_id', name='uq_saved_project'),
        )
        op.create_index(op.f('ix_saved_projects_user_id'), 'saved_projects', ['user_id'])
        op.create_index(op.f('ix_saved_projects_project_id'), 'saved_projects', ['project_id'])


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _has_table(insp, 'saved_projects'):
        op.drop_index(op.f('ix_saved_projects_project_id'), table_name='saved_projects')
        op.drop_index(op.f('ix_saved_projects_user_id'), table_name='saved_projects')
        op.drop_table('saved_projects')
