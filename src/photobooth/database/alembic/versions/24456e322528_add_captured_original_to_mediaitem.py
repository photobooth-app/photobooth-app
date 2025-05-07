"""add captured_original to mediaitem

Revision ID: 24456e322528
Revises: 7e0d6dfb1b1d
Create Date: 2025-05-07 11:32:05.378511

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import photobooth.database.types

# revision identifiers, used by Alembic.
revision: str = "24456e322528"
down_revision: str | None = "7e0d6dfb1b1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("mediaitems", sa.Column("captured_original", photobooth.database.types.PathType(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("mediaitems", "captured_original")
