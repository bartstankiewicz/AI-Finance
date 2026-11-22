"""add option and irs fields to trades

Revision ID: 3c1d5e7a9b20
Revises: 952f21b33873
Create Date: 2026-09-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c1d5e7a9b20'
down_revision: Union[str, Sequence[str], None] = '952f21b33873'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('Trades', sa.Column('underlying_symbol', sa.Text(), nullable=True))
    op.add_column('Trades', sa.Column('option_type', sa.Text(), nullable=True))
    op.add_column('Trades', sa.Column('strike', sa.Numeric(), nullable=True))
    op.add_column('Trades', sa.Column('maturity_years', sa.Numeric(), nullable=True))
    op.add_column('Trades', sa.Column('volatility', sa.Numeric(), nullable=True))
    op.add_column('Trades', sa.Column('notional', sa.Numeric(), nullable=True))
    op.add_column('Trades', sa.Column('fixed_rate', sa.Numeric(), nullable=True))
    op.add_column('Trades', sa.Column('payments_per_year', sa.Numeric(), nullable=True))
    op.add_column('Trades', sa.Column('direction', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('Trades', 'direction')
    op.drop_column('Trades', 'payments_per_year')
    op.drop_column('Trades', 'fixed_rate')
    op.drop_column('Trades', 'notional')
    op.drop_column('Trades', 'volatility')
    op.drop_column('Trades', 'maturity_years')
    op.drop_column('Trades', 'strike')
    op.drop_column('Trades', 'option_type')
    op.drop_column('Trades', 'underlying_symbol')
