"""add alpha and beta to valuations

Revision ID: 5d8a2f6c4b17
Revises: 7b4e2c9d1f30
Create Date: 2026-11-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d8a2f6c4b17'
down_revision: Union[str, Sequence[str], None] = '7b4e2c9d1f30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable: NULL until the book's rolling window is full, and for rows written before this migration
    op.add_column('Valuations', sa.Column('alpha', sa.Numeric(), nullable=True))
    op.add_column('Valuations', sa.Column('beta', sa.Numeric(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('Valuations', 'beta')
    op.drop_column('Valuations', 'alpha')
