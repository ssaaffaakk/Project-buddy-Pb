"""add users.is_demo + users.demo_expires_at (demo sandbox accounts)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-12

Idempotent: guarded on introspection (the boot-time column backfill or a fresh
create_all() may already have added the columns). is_demo is nullable on
purpose — real users keep NULL and every demo filter uses
`is_demo IS NULL OR is_demo = false`, so no backfill UPDATE is needed.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def _has_column(insp, table, column):
    return column in {c['name'] for c in insp.get_columns(table)}


def _has_index(insp, table, index):
    return index in {ix['name'] for ix in insp.get_indexes(table)}


def upgrade():
    insp = sa.inspect(op.get_bind())
    if not _has_column(insp, 'users', 'is_demo'):
        op.add_column('users', sa.Column('is_demo', sa.Boolean(), nullable=True))
    if not _has_column(insp, 'users', 'demo_expires_at'):
        op.add_column('users', sa.Column('demo_expires_at', sa.DateTime(), nullable=True))
    insp = sa.inspect(op.get_bind())
    if not _has_index(insp, 'users', 'ix_users_is_demo'):
        op.create_index('ix_users_is_demo', 'users', ['is_demo'])


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _has_index(insp, 'users', 'ix_users_is_demo'):
        op.drop_index('ix_users_is_demo', table_name='users')
    if _has_column(insp, 'users', 'demo_expires_at'):
        op.drop_column('users', 'demo_expires_at')
    if _has_column(insp, 'users', 'is_demo'):
        op.drop_column('users', 'is_demo')
