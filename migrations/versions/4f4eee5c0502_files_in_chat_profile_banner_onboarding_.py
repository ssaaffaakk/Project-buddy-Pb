"""files-in-chat, profile banner/onboarding, profile walls

Revision ID: 4f4eee5c0502
Revises: 68ce403fbd55
Create Date: 2026-07-10 13:45:30.038589

Idempotent: the app's boot-time create_all() safety net may already have
created the new tables, so we guard every DDL statement on introspection.
"""
from alembic import op
import sqlalchemy as sa


revision = '4f4eee5c0502'
down_revision = '68ce403fbd55'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # users: banner_url + onboarded
    ucols = {c['name'] for c in insp.get_columns('users')}
    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'banner_url' not in ucols:
            batch_op.add_column(sa.Column('banner_url', sa.String(length=500), nullable=True))
        if 'onboarded' not in ucols:
            # server_default so the NOT NULL column can be added to existing rows
            batch_op.add_column(sa.Column('onboarded', sa.Boolean(), nullable=False,
                                          server_default=sa.false()))

    # study_group_messages: attachment_id
    mcols = {c['name'] for c in insp.get_columns('study_group_messages')}
    if 'attachment_id' not in mcols:
        with op.batch_alter_table('study_group_messages', schema=None) as batch_op:
            batch_op.add_column(sa.Column('attachment_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_sgm_attachment', 'shared_files',
                                        ['attachment_id'], ['id'])

    tables = set(insp.get_table_names())
    if 'profile_comments' not in tables:
        op.create_table(
            'profile_comments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('profile_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_profile_comments_profile_id', 'profile_comments', ['profile_id'])
    if 'profile_comment_likes' not in tables:
        op.create_table(
            'profile_comment_likes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('comment_id', sa.Integer(), sa.ForeignKey('profile_comments.id'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.UniqueConstraint('comment_id', 'user_id', name='uq_profile_comment_like'),
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if 'profile_comment_likes' in tables:
        op.drop_table('profile_comment_likes')
    if 'profile_comments' in tables:
        op.drop_table('profile_comments')
    mcols = {c['name'] for c in insp.get_columns('study_group_messages')}
    if 'attachment_id' in mcols:
        with op.batch_alter_table('study_group_messages', schema=None) as batch_op:
            batch_op.drop_column('attachment_id')
    ucols = {c['name'] for c in insp.get_columns('users')}
    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'onboarded' in ucols:
            batch_op.drop_column('onboarded')
        if 'banner_url' in ucols:
            batch_op.drop_column('banner_url')
