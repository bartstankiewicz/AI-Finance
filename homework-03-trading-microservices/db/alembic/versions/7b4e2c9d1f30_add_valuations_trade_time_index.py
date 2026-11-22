"""add index on valuations (trade_id, valuation_time)

Revision ID: 7b4e2c9d1f30
Revises: 3c1d5e7a9b20
Create Date: 2026-11-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7b4e2c9d1f30'
down_revision: Union[str, Sequence[str], None] = '3c1d5e7a9b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_valuations_trade_id_valuation_time', 'Valuations', ['trade_id', 'valuation_time'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_valuations_trade_id_valuation_time', table_name='Valuations')
