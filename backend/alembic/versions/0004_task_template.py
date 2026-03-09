"""Add task_templates table

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-08

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("room_type", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("default_duration_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("default_frequency_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("energy_level", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("household_flag", sa.String(length=50), nullable=True),
        sa.Column("device_flag", sa.String(length=50), nullable=True),
        sa.Column("is_robot_variant", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("robot_frequency_multiplier", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_templates_id"), "task_templates", ["id"], unique=False)
    op.create_index("ix_task_templates_room_type", "task_templates", ["room_type"], unique=False)
    op.create_index("ix_task_templates_category", "task_templates", ["category"], unique=False)
    op.create_index("ix_task_templates_is_active", "task_templates", ["is_active"], unique=False)
    op.create_index("ix_task_templates_household_flag", "task_templates", ["household_flag"], unique=False)
    op.create_index("ix_task_templates_device_flag", "task_templates", ["device_flag"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_templates_device_flag", table_name="task_templates")
    op.drop_index("ix_task_templates_household_flag", table_name="task_templates")
    op.drop_index("ix_task_templates_is_active", table_name="task_templates")
    op.drop_index("ix_task_templates_category", table_name="task_templates")
    op.drop_index("ix_task_templates_room_type", table_name="task_templates")
    op.drop_index(op.f("ix_task_templates_id"), table_name="task_templates")
    op.drop_table("task_templates")
