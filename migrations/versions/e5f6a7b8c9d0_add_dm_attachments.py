"""add dm_attachments + direct_messages.attachment_id (file sharing in DMs)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-13

Idempotent: guarded on introspection (create_all / the boot-time column
backfill may already have created the table/column on a fresh DB).
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def _has_table(insp, name):
    return name in set(insp.get_table_names())


def _has_column(insp, table, column):
    return column in {c['name'] for c in insp.get_columns(table)}


def upgrade():
    insp = sa.inspect(op.get_bind())
    if not _has_table(insp, 'dm_attachments'):
        op.create_table(
            'dm_attachments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('conversation_id', sa.Integer(), nullable=False),
            sa.Column('uploader_id', sa.Integer(), nullable=False),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('stored_name', sa.String(length=255), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('mime_type', sa.String(length=120), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
            sa.ForeignKeyConstraint(['uploader_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_dm_attachments_conversation_id'), 'dm_attachments', ['conversation_id'])

    if _has_table(insp, 'direct_messages') and not _has_column(insp, 'direct_messages', 'attachment_id'):
        # No FK constraint on the ALTER: SQLite can't add one in place, and the
        # boot-time backfill adds the same bare column. App-level integrity only.
        op.add_column('direct_messages', sa.Column('attachment_id', sa.Integer(), nullable=True))


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _has_table(insp, 'direct_messages') and _has_column(insp, 'direct_messages', 'attachment_id'):
        op.drop_column('direct_messages', 'attachment_id')
    if _has_table(insp, 'dm_attachments'):
        op.drop_index(op.f('ix_dm_attachments_conversation_id'), table_name='dm_attachments')
        op.drop_table('dm_attachments')
