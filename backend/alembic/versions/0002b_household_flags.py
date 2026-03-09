"""Add household composition flags: has_children, has_cats, has_dogs

Revision ID: 0002b
Revises: 0002
Create Date: 2026-03-09

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0002b"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("households", sa.Column("has_children", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("households", sa.Column("has_cats", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("households", sa.Column("has_dogs", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("households", "has_dogs")
    op.drop_column("households", "has_cats")
    op.drop_column("households", "has_children")
