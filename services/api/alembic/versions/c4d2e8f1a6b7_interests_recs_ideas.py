"""interests import, recommendations + feedback, idea notes, watch time, comment threads, publish kinds

Revision ID: c4d2e8f1a6b7
Revises: a3c1f0d2e9b4
Create Date: 2026-10-23 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d2e8f1a6b7'
down_revision: Union[str, Sequence[str], None] = 'a3c1f0d2e9b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('content_ideas', schema=None) as b:
        b.add_column(sa.Column('notes', sa.Text(), nullable=True))
    with op.batch_alter_table('media_snapshots', schema=None) as b:
        b.add_column(sa.Column('total_watch_time_ms', sa.BigInteger(), nullable=True))
    with op.batch_alter_table('comments', schema=None) as b:
        b.add_column(sa.Column('parent_ig_id', sa.String(length=64), nullable=True))
        b.add_column(sa.Column('from_owner', sa.Boolean(), nullable=False, server_default=sa.false()))
        b.create_index('ix_comments_parent_ig_id', ['parent_ig_id'])
    op.create_table(
        'interest_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('creator', sa.String(length=120), nullable=True),
        sa.Column('url', sa.String(length=1000), nullable=True),
        sa.Column('title', sa.String(length=300), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('collection', sa.String(length=200), nullable=True),
        sa.Column('happened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('origin', sa.String(length=20), nullable=False),
        sa.Column('dedupe_key', sa.String(length=300), nullable=False),
        sa.Column('is_demo', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('is_demo', 'dedupe_key', name='uq_interest_item'),
    )
    op.create_index('ix_interest_items_source', 'interest_items', ['source'])
    op.create_index('ix_interest_items_is_demo', 'interest_items', ['is_demo'])
    op.create_table(
        'recommendations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('topic', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('feedback', sa.String(length=20), nullable=True),
        sa.Column('feedback_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('idea_id', sa.Integer(), sa.ForeignKey('content_ideas.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_demo', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_recommendations_is_demo', 'recommendations', ['is_demo'])


def downgrade() -> None:
    op.drop_table('recommendations')
    op.drop_table('interest_items')
    with op.batch_alter_table('comments', schema=None) as b:
        b.drop_index('ix_comments_parent_ig_id')
        b.drop_column('from_owner')
        b.drop_column('parent_ig_id')
    with op.batch_alter_table('media_snapshots', schema=None) as b:
        b.drop_column('total_watch_time_ms')
    with op.batch_alter_table('content_ideas', schema=None) as b:
        b.drop_column('notes')
