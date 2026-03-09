"""Add setup_complete flag to residents

Revision ID: 0002d
Revises: 0002c
Create Date: 2026-03-09

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0002d"
down_revision: Union[str, None] = "0002c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "residents",
        sa.Column("setup_complete", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("residents", "setup_complete")
