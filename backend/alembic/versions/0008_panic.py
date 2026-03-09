"""Add panic_sessions table and extend task_assignments with panic_session_id;
make session_id nullable to support panic assignments.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-08

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # panic_sessions — must be created before altering task_assignments FK
    # ------------------------------------------------------------------ #
    op.create_table(
        "panic_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activated_by_resident_id", sa.Integer(), nullable=False),
        sa.Column("available_minutes", sa.Integer(), nullable=False),
        sa.Column("available_resident_ids", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["activated_by_resident_id"], ["residents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_panic_sessions_id"), "panic_sessions", ["id"], unique=False)
    op.create_index(
        "ix_panic_sessions_activated_by_resident_id",
        "panic_sessions",
        ["activated_by_resident_id"],
        unique=False,
    )
    op.create_index("ix_panic_sessions_created_at", "panic_sessions", ["created_at"], unique=False)

    # ------------------------------------------------------------------ #
    # Extend task_assignments:
    #   - Add panic_session_id (nullable FK)
    #   - Make session_id nullable (SQLite requires table recreation)
    # ------------------------------------------------------------------ #
    # SQLite does not support ALTER COLUMN, so we recreate the table.
    # Steps: rename → create new → copy data → drop old.

    # 1. Drop indexes on existing table before renaming
    #    (SQLite rename_table carries indexes along — names would clash on recreate)
    op.drop_index("ix_task_assignments_resident_completed", table_name="task_assignments")
    op.drop_index("ix_task_assignments_status", table_name="task_assignments")
    op.drop_index("ix_task_assignments_task_template_id", table_name="task_assignments")
    op.drop_index("ix_task_assignments_resident_id", table_name="task_assignments")
    op.drop_index("ix_task_assignments_session_id", table_name="task_assignments")
    op.drop_index(op.f("ix_task_assignments_id"), table_name="task_assignments")

    # 2. Rename existing table
    op.rename_table("task_assignments", "task_assignments_old")

    # 3. Create new table with updated constraints
    op.create_table(
        "task_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),          # NOW NULLABLE
        sa.Column("panic_session_id", sa.Integer(), nullable=True),    # NEW R7
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("task_template_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("suggested_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("reroll_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_forced", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("points_awarded", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["daily_sessions.id"]),
        sa.ForeignKeyConstraint(["panic_session_id"], ["panic_sessions.id"]),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.id"]),
        sa.ForeignKeyConstraint(["task_template_id"], ["task_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. Copy existing data (panic_session_id defaults to NULL)
    op.execute(
        """
        INSERT INTO task_assignments
            (id, session_id, panic_session_id, resident_id, task_template_id,
             status, score, suggested_at, accepted_at, completed_at,
             reroll_count, is_forced, points_awarded)
        SELECT
            id, session_id, NULL, resident_id, task_template_id,
            status, score, suggested_at, accepted_at, completed_at,
            reroll_count, is_forced, points_awarded
        FROM task_assignments_old
        """
    )

    # 4. Recreate indexes on new table
    op.create_index(op.f("ix_task_assignments_id"), "task_assignments", ["id"], unique=False)
    op.create_index("ix_task_assignments_session_id", "task_assignments", ["session_id"], unique=False)
    op.create_index("ix_task_assignments_panic_session_id", "task_assignments", ["panic_session_id"], unique=False)
    op.create_index("ix_task_assignments_resident_id", "task_assignments", ["resident_id"], unique=False)
    op.create_index("ix_task_assignments_task_template_id", "task_assignments", ["task_template_id"], unique=False)

    # 5. Drop old table
    op.drop_table("task_assignments_old")


def downgrade() -> None:
    # Reverse: recreate old table without panic_session_id, session_id NOT NULL
    op.rename_table("task_assignments", "task_assignments_new")

    op.create_table(
        "task_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("task_template_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
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

    op.execute(
        """
        INSERT INTO task_assignments
            (id, session_id, resident_id, task_template_id,
             status, score, suggested_at, accepted_at, completed_at,
             reroll_count, is_forced, points_awarded)
        SELECT
            id, session_id, resident_id, task_template_id,
            status, score, suggested_at, accepted_at, completed_at,
            reroll_count, is_forced, points_awarded
        FROM task_assignments_new
        WHERE session_id IS NOT NULL
        """
    )

    op.create_index(op.f("ix_task_assignments_id"), "task_assignments", ["id"], unique=False)
    op.create_index("ix_task_assignments_session_id", "task_assignments", ["session_id"], unique=False)
    op.create_index("ix_task_assignments_resident_id", "task_assignments", ["resident_id"], unique=False)
    op.create_index("ix_task_assignments_task_template_id", "task_assignments", ["task_template_id"], unique=False)

    op.drop_table("task_assignments_new")

    op.drop_index("ix_panic_sessions_created_at", table_name="panic_sessions")
    op.drop_index("ix_panic_sessions_activated_by_resident_id", table_name="panic_sessions")
    op.drop_index(op.f("ix_panic_sessions_id"), table_name="panic_sessions")
    op.drop_table("panic_sessions")
