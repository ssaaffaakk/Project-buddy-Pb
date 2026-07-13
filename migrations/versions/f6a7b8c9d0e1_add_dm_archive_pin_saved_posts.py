"""add conversation archive/pin flags + saved_posts (bookmark logic for the feed)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-13

Idempotent: guarded on introspection (create_all / the boot-time column
backfill may already have created the table/columns on a fresh DB).
"""
from alembic import op
import sqlalchemy as sa


revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def _has_table(insp, name):
    return name in set(insp.get_table_names())


def _has_column(insp, table, column):
    return column in {c['name'] for c in insp.get_columns(table)}


CONV_FLAGS = ('a_archived', 'b_archived', 'a_pinned', 'b_pinned')


def upgrade():
    insp = sa.inspect(op.get_bind())

    if _has_table(insp, 'conversations'):
        for col in CONV_FLAGS:
            if not _has_column(insp, 'conversations', col):
                # Nullable on purpose: matches the model (NULL is read as False)
                # and the boot-time backfill, which can't add NOT NULL in place.
                op.add_column('conversations', sa.Column(col, sa.Boolean(), nullable=True))

    if not _has_table(insp, 'saved_posts'):
        op.create_table(
            'saved_posts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('post_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['post_id'], ['community_posts.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'post_id', name='uq_saved_post'),
        )
        op.create_index(op.f('ix_saved_posts_user_id'), 'saved_posts', ['user_id'])
        op.create_index(op.f('ix_saved_posts_post_id'), 'saved_posts', ['post_id'])


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _has_table(insp, 'saved_posts'):
        op.drop_index(op.f('ix_saved_posts_post_id'), table_name='saved_posts')
        op.drop_index(op.f('ix_saved_posts_user_id'), table_name='saved_posts')
        op.drop_table('saved_posts')
    if _has_table(insp, 'conversations'):
        for col in reversed(CONV_FLAGS):
            if _has_column(insp, 'conversations', col):
                op.drop_column('conversations', col)
