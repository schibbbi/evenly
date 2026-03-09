"""Add gamification tables: resident_game_profiles, household_game_profiles,
point_transactions, vouchers, delegation_records

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-08

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # resident_game_profiles
    # ------------------------------------------------------------------ #
    op.create_table(
        "resident_game_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("total_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("voucher_threshold_watermark", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("streak_safes_available", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("streak_safes_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_activity_date", sa.String(length=10), nullable=True),
        sa.Column("delegation_locked", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resident_id", name="uq_game_profile_resident"),
    )
    op.create_index(op.f("ix_resident_game_profiles_id"), "resident_game_profiles", ["id"], unique=False)
    op.create_index("ix_resident_game_profiles_resident_id", "resident_game_profiles", ["resident_id"], unique=True)

    # ------------------------------------------------------------------ #
    # household_game_profiles
    # ------------------------------------------------------------------ #
    op.create_table(
        "household_game_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("team_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("team_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_team_activity_date", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", name="uq_household_game_profile"),
    )
    op.create_index(op.f("ix_household_game_profiles_id"), "household_game_profiles", ["id"], unique=False)
    op.create_index("ix_household_game_profiles_household_id", "household_game_profiles", ["household_id"], unique=True)

    # ------------------------------------------------------------------ #
    # point_transactions
    # ------------------------------------------------------------------ #
    op.create_table(
        "point_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("game_profile_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "task_completed", "unpopular_bonus", "team_bonus",
                "delegation_cost", "reroll_malus", "voucher_redeemed",
                name="pointreasonenum",
            ),
            nullable=False,
        ),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.id"]),
        sa.ForeignKeyConstraint(["game_profile_id"], ["resident_game_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_point_transactions_id"), "point_transactions", ["id"], unique=False)
    op.create_index("ix_point_transactions_resident_id", "point_transactions", ["resident_id"], unique=False)
    op.create_index("ix_point_transactions_game_profile_id", "point_transactions", ["game_profile_id"], unique=False)
    op.create_index("ix_point_transactions_timestamp", "point_transactions", ["timestamp"], unique=False)

    # ------------------------------------------------------------------ #
    # vouchers
    # ------------------------------------------------------------------ #
    op.create_table(
        "vouchers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("game_profile_id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("free_day", "custom", name="vouchertypeenum"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("earned_at", sa.DateTime(), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(), nullable=True),
        sa.Column("is_redeemed", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.id"]),
        sa.ForeignKeyConstraint(["game_profile_id"], ["resident_game_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vouchers_id"), "vouchers", ["id"], unique=False)
    op.create_index("ix_vouchers_resident_id", "vouchers", ["resident_id"], unique=False)
    op.create_index("ix_vouchers_game_profile_id", "vouchers", ["game_profile_id"], unique=False)
    op.create_index("ix_vouchers_earned_at", "vouchers", ["earned_at"], unique=False)

    # ------------------------------------------------------------------ #
    # delegation_records
    # ------------------------------------------------------------------ #
    op.create_table(
        "delegation_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_resident_id", sa.Integer(), nullable=False),
        sa.Column("to_resident_id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("receiver_assignment_id", sa.Integer(), nullable=True),
        sa.Column("delegated_at", sa.DateTime(), nullable=False),
        sa.Column("deadline_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("no_points_on_completion", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["from_resident_id"], ["residents.id"]),
        sa.ForeignKeyConstraint(["to_resident_id"], ["residents.id"]),
        sa.ForeignKeyConstraint(["assignment_id"], ["task_assignments.id"]),
        sa.ForeignKeyConstraint(["receiver_assignment_id"], ["task_assignments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_delegation_records_id"), "delegation_records", ["id"], unique=False)
    op.create_index("ix_delegation_records_from_resident_id", "delegation_records", ["from_resident_id"], unique=False)
    op.create_index("ix_delegation_records_to_resident_id", "delegation_records", ["to_resident_id"], unique=False)
    op.create_index("ix_delegation_records_assignment_id", "delegation_records", ["assignment_id"], unique=False)
    op.create_index("ix_delegation_records_deadline_at", "delegation_records", ["deadline_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_delegation_records_deadline_at", table_name="delegation_records")
    op.drop_index("ix_delegation_records_assignment_id", table_name="delegation_records")
    op.drop_index("ix_delegation_records_to_resident_id", table_name="delegation_records")
    op.drop_index("ix_delegation_records_from_resident_id", table_name="delegation_records")
    op.drop_index(op.f("ix_delegation_records_id"), table_name="delegation_records")
    op.drop_table("delegation_records")

    op.drop_index("ix_vouchers_earned_at", table_name="vouchers")
    op.drop_index("ix_vouchers_game_profile_id", table_name="vouchers")
    op.drop_index("ix_vouchers_resident_id", table_name="vouchers")
    op.drop_index(op.f("ix_vouchers_id"), table_name="vouchers")
    op.drop_table("vouchers")

    op.drop_index("ix_point_transactions_timestamp", table_name="point_transactions")
    op.drop_index("ix_point_transactions_game_profile_id", table_name="point_transactions")
    op.drop_index("ix_point_transactions_resident_id", table_name="point_transactions")
    op.drop_index(op.f("ix_point_transactions_id"), table_name="point_transactions")
    op.drop_table("point_transactions")

    op.drop_index("ix_household_game_profiles_household_id", table_name="household_game_profiles")
    op.drop_index(op.f("ix_household_game_profiles_id"), table_name="household_game_profiles")
    op.drop_table("household_game_profiles")

    op.drop_index("ix_resident_game_profiles_resident_id", table_name="resident_game_profiles")
    op.drop_index(op.f("ix_resident_game_profiles_id"), table_name="resident_game_profiles")
    op.drop_table("resident_game_profiles")

    # Drop custom enums (SQLite ignores this; PostgreSQL would need it)
    # op.execute("DROP TYPE IF EXISTS pointreasonenum")
    # op.execute("DROP TYPE IF EXISTS vouchertypeenum")
