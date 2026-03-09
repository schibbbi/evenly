"""Add household device capability flags and has_garden

Revision ID: 0002c
Revises: 0002b
Create Date: 2026-03-09

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0002c"
down_revision: Union[str, None] = "0002b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for col in [
        "has_garden",
        "has_robot_vacuum",
        "has_robot_mop",
        "has_dishwasher",
        "has_washer",
        "has_dryer",
        "has_window_cleaner",
        "has_steam_cleaner",
        "has_robot_mower",
        "has_irrigation",
    ]:
        op.add_column(
            "households",
            sa.Column(col, sa.Boolean(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    for col in [
        "has_irrigation",
        "has_robot_mower",
        "has_steam_cleaner",
        "has_window_cleaner",
        "has_dryer",
        "has_washer",
        "has_dishwasher",
        "has_robot_mop",
        "has_robot_vacuum",
        "has_garden",
    ]:
        op.drop_column("households", col)
