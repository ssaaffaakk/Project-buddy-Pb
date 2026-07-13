"""add direct_messages.shared_post_id (share a community post into a DM)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-13

Idempotent: guarded on introspection (the boot-time column backfill may already
have added the column on a fresh DB). No FK on purpose — a shared post that is
later deleted degrades gracefully to an "unavailable" card.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def _has_table(insp, name):
    return name in set(insp.get_table_names())


def _has_column(insp, table, column):
    return column in {c['name'] for c in insp.get_columns(table)}


def upgrade():
    insp = sa.inspect(op.get_bind())
    if _has_table(insp, 'direct_messages') and not _has_column(insp, 'direct_messages', 'shared_post_id'):
        op.add_column('direct_messages', sa.Column('shared_post_id', sa.Integer(), nullable=True))


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _has_table(insp, 'direct_messages') and _has_column(insp, 'direct_messages', 'shared_post_id'):
        op.drop_column('direct_messages', 'shared_post_id')
