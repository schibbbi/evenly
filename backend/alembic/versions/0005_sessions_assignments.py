"""Add daily_sessions and task_assignments tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-08

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # daily_sessions
    op.create_table(
        "daily_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.String(length=10), nullable=False),
        sa.Column("energy_level", sa.String(length=20), nullable=False),
        sa.Column("available_minutes", sa.Integer(), nullable=False),
        sa.Column("reroll_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reroll_malus", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_daily_sessions_id"), "daily_sessions", ["id"], unique=False)
    op.create_index("ix_daily_sessions_resident_id", "daily_sessions", ["resident_id"], unique=False)
    op.create_index("ix_daily_sessions_date", "daily_sessions", ["date"], unique=False)

    # task_assignments
    op.create_table(
        "task_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("task_template_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="suggested"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("suggested_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("reroll_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_forced", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("points_awarded", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["daily_sessions.id"]),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.id"]),
        sa.ForeignKeyConstraint(["task_template_id"], ["task_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_assignments_id"), "task_assignments", ["id"], unique=False)
    op.create_index("ix_task_assignments_session_id", "task_assignments", ["session_id"], unique=False)
    op.create_index("ix_task_assignments_resident_id", "task_assignments", ["resident_id"], unique=False)
    op.create_index("ix_task_assignments_task_template_id", "task_assignments", ["task_template_id"], unique=False)
    op.create_index("ix_task_assignments_status", "task_assignments", ["status"], unique=False)
    op.create_index(
        "ix_task_assignments_resident_completed",
        "task_assignments",
        ["resident_id", "completed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_task_assignments_resident_completed", table_name="task_assignments")
    op.drop_index("ix_task_assignments_status", table_name="task_assignments")
    op.drop_index("ix_task_assignments_task_template_id", table_name="task_assignments")
    op.drop_index("ix_task_assignments_resident_id", table_name="task_assignments")
    op.drop_index("ix_task_assignments_session_id", table_name="task_assignments")
    op.drop_index(op.f("ix_task_assignments_id"), table_name="task_assignments")
    op.drop_table("task_assignments")

    op.drop_index("ix_daily_sessions_date", table_name="daily_sessions")
    op.drop_index("ix_daily_sessions_resident_id", table_name="daily_sessions")
    op.drop_index(op.f("ix_daily_sessions_id"), table_name="daily_sessions")
    op.drop_table("daily_sessions")
