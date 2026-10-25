"""reel planner: saved reel plans

Revision ID: d5f1a2b3c4e6
Revises: c4d2e8f1a6b7
Create Date: 2026-10-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5f1a2b3c4e6'
down_revision: Union[str, Sequence[str], None] = 'c4d2e8f1a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reel_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('niche', sa.String(length=200), nullable=False),
        sa.Column('platform', sa.String(length=40), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('topic', sa.JSON(), nullable=False),
        sa.Column('package', sa.JSON(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=60), nullable=True),
        sa.Column('live_research', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('idea_id', sa.Integer(), sa.ForeignKey('content_ideas.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_reel_plans_niche', 'reel_plans', ['niche'])
    op.create_index('ix_reel_plans_is_demo', 'reel_plans', ['is_demo'])
    op.create_index('ix_reel_plans_idea_id', 'reel_plans', ['idea_id'])


def downgrade() -> None:
    op.drop_table('reel_plans')
