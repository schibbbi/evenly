"""Initial empty migration — structure ready for R2 models

Revision ID: 0001
Revises:
Create Date: 2026-03-09

"""
from typing import Sequence, Union

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No tables yet — models are added from R2 onwards
    pass


def downgrade() -> None:
    pass
