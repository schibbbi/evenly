"""Add calendar_configs, calendar_events, household_contexts tables (R8)

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-08

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # calendar_configs
    # ------------------------------------------------------------------ #
    op.create_table(
        "calendar_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("google_refresh_token", sa.Text(), nullable=True),
        sa.Column("calendar_ids", sa.Text(), nullable=False, server_default='["primary"]'),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", name="uq_calendar_config_household"),
    )
    op.create_index(op.f("ix_calendar_configs_id"), "calendar_configs", ["id"], unique=False)
    op.create_index(
        "ix_calendar_configs_household_id", "calendar_configs", ["household_id"], unique=True
    )

    # ------------------------------------------------------------------ #
    # calendar_events
    # ------------------------------------------------------------------ #
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("calendar_config_id", sa.Integer(), nullable=False),
        sa.Column("google_event_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("start_datetime", sa.DateTime(), nullable=False),
        sa.Column("end_datetime", sa.DateTime(), nullable=True),
        sa.Column(
            "guest_probability",
            sa.Enum("low", "medium", "high", name="guestprobabilityenum"),
            nullable=False,
        ),
        sa.Column(
            "alert_level",
            sa.Enum("early", "medium", "urgent", "panic", name="alertlevelenum"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["calendar_config_id"], ["calendar_configs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_calendar_events_id"), "calendar_events", ["id"], unique=False)
    op.create_index(
        "ix_calendar_events_calendar_config_id",
        "calendar_events",
        ["calendar_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_calendar_events_google_event_id",
        "calendar_events",
        ["google_event_id"],
        unique=False,
    )
    op.create_index(
        "ix_calendar_events_start_datetime",
        "calendar_events",
        ["start_datetime"],
        unique=False,
    )

    # ------------------------------------------------------------------ #
    # household_contexts
    # ------------------------------------------------------------------ #
    op.create_table(
        "household_contexts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column(
            "current_alert_level",
            sa.Enum("early", "medium", "urgent", "panic", name="alertlevelenum"),
            nullable=True,
        ),
        sa.Column("event_date", sa.String(length=10), nullable=True),
        sa.Column("event_title", sa.String(length=500), nullable=True),
        sa.Column("panic_prompt_active", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", name="uq_household_context"),
    )
    op.create_index(
        op.f("ix_household_contexts_id"), "household_contexts", ["id"], unique=False
    )
    op.create_index(
        "ix_household_contexts_household_id",
        "household_contexts",
        ["household_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_household_contexts_household_id", table_name="household_contexts")
    op.drop_index(op.f("ix_household_contexts_id"), table_name="household_contexts")
    op.drop_table("household_contexts")

    op.drop_index("ix_calendar_events_start_datetime", table_name="calendar_events")
    op.drop_index("ix_calendar_events_google_event_id", table_name="calendar_events")
    op.drop_index("ix_calendar_events_calendar_config_id", table_name="calendar_events")
    op.drop_index(op.f("ix_calendar_events_id"), table_name="calendar_events")
    op.drop_table("calendar_events")

    op.drop_index("ix_calendar_configs_household_id", table_name="calendar_configs")
    op.drop_index(op.f("ix_calendar_configs_id"), table_name="calendar_configs")
    op.drop_table("calendar_configs")

    # SQLite ignores enum drops; for PostgreSQL:
    # op.execute("DROP TYPE IF EXISTS alertlevelenum")
    # op.execute("DROP TYPE IF EXISTS guestprobabilityenum")
