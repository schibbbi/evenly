"""Add history_entries, resident_scoring_profiles, household_feed_entries tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-08

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # history_entries
    op.create_table(
        "history_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("task_template_id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("room_type", sa.String(length=50), nullable=False),
        sa.Column("points_awarded", sa.Integer(), nullable=True),
        sa.Column("was_unpopular", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("was_forced", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.id"]),
        sa.ForeignKeyConstraint(["task_template_id"], ["task_templates.id"]),
        sa.ForeignKeyConstraint(["assignment_id"], ["task_assignments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_history_entries_id"), "history_entries", ["id"], unique=False)
    op.create_index("ix_history_entries_resident_id", "history_entries", ["resident_id"], unique=False)
    op.create_index("ix_history_entries_task_template_id", "history_entries", ["task_template_id"], unique=False)
    op.create_index("ix_history_entries_timestamp", "history_entries", ["timestamp"], unique=False)
    op.create_index(
        "ix_history_entries_resident_timestamp",
        "history_entries",
        ["resident_id", "timestamp"],
        unique=False,
    )

    # resident_scoring_profiles
    op.create_table(
        "resident_scoring_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("task_template_id", sa.Integer(), nullable=False),
        sa.Column("rejection_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_rejected_at", sa.DateTime(), nullable=True),
        sa.Column("preferred_time_of_day", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("imbalance_flag", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.id"]),
        sa.ForeignKeyConstraint(["task_template_id"], ["task_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resident_id", "task_template_id", name="uq_profile_resident_task"),
    )
    op.create_index(op.f("ix_resident_scoring_profiles_id"), "resident_scoring_profiles", ["id"], unique=False)
    op.create_index("ix_resident_scoring_profiles_resident_id", "resident_scoring_profiles", ["resident_id"], unique=False)
    op.create_index("ix_resident_scoring_profiles_task_template_id", "resident_scoring_profiles", ["task_template_id"], unique=False)

    # household_feed_entries
    op.create_table(
        "household_feed_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("action_type", sa.String(length=30), nullable=False),
        sa.Column("task_name", sa.String(length=200), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_household_feed_entries_id"), "household_feed_entries", ["id"], unique=False)
    op.create_index("ix_household_feed_entries_resident_id", "household_feed_entries", ["resident_id"], unique=False)
    op.create_index("ix_household_feed_entries_timestamp", "household_feed_entries", ["timestamp"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_household_feed_entries_timestamp", table_name="household_feed_entries")
    op.drop_index("ix_household_feed_entries_resident_id", table_name="household_feed_entries")
    op.drop_index(op.f("ix_household_feed_entries_id"), table_name="household_feed_entries")
    op.drop_table("household_feed_entries")

    op.drop_index("ix_resident_scoring_profiles_task_template_id", table_name="resident_scoring_profiles")
    op.drop_index("ix_resident_scoring_profiles_resident_id", table_name="resident_scoring_profiles")
    op.drop_index(op.f("ix_resident_scoring_profiles_id"), table_name="resident_scoring_profiles")
    op.drop_table("resident_scoring_profiles")

    op.drop_index("ix_history_entries_resident_timestamp", table_name="history_entries")
    op.drop_index("ix_history_entries_timestamp", table_name="history_entries")
    op.drop_index("ix_history_entries_task_template_id", table_name="history_entries")
    op.drop_index("ix_history_entries_resident_id", table_name="history_entries")
    op.drop_index(op.f("ix_history_entries_id"), table_name="history_entries")
    op.drop_table("history_entries")
