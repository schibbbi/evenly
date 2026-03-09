"""Add pin_attempt_logs table

Revision ID: 0003
Revises: 0002d
Create Date: 2026-03-09

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pin_attempt_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pin_attempt_logs_id"), "pin_attempt_logs", ["id"], unique=False)
    op.create_index(
        "ix_pin_attempt_logs_resident_time",
        "pin_attempt_logs",
        ["resident_id", "attempted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pin_attempt_logs_resident_time", table_name="pin_attempt_logs")
    op.drop_index(op.f("ix_pin_attempt_logs_id"), table_name="pin_attempt_logs")
    op.drop_table("pin_attempt_logs")
