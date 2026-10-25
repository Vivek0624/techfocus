"""growth features: audience tags, feed attribution metrics

Revision ID: a3c1f0d2e9b4
Revises: 951c656cabaf
Create Date: 2026-10-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c1f0d2e9b4'
down_revision: Union[str, Sequence[str], None] = '951c656cabaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('media', schema=None) as b:
        b.add_column(sa.Column('audience', sa.String(length=30), nullable=True))
    with op.batch_alter_table('content_ideas', schema=None) as b:
        b.add_column(sa.Column('audience', sa.String(length=30), nullable=True))
    with op.batch_alter_table('media_snapshots', schema=None) as b:
        for col in ('follows', 'profile_visits', 'profile_activity', 'reposts'):
            b.add_column(sa.Column(col, sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('media_snapshots', schema=None) as b:
        for col in ('reposts', 'profile_activity', 'profile_visits', 'follows'):
            b.drop_column(col)
    with op.batch_alter_table('content_ideas', schema=None) as b:
        b.drop_column('audience')
    with op.batch_alter_table('media', schema=None) as b:
        b.drop_column('audience')
