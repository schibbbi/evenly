"""
HouseholdContext — Single-row table per household storing the current calendar alert state.

Upserted by the Calendar Agent after each sync.
Read by the Suggestion Agent to apply scoring boosts.

One row per household (unique constraint on household_id).
If no row exists: no active alert, scoring proceeds normally.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AlertLevelEnum


class HouseholdContext(Base):
    __tablename__ = "household_contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    household_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("households.id"), nullable=False, unique=True, index=True
    )

    # Current highest-urgency alert level (None if no active guest event)
    current_alert_level: Mapped[AlertLevelEnum] = mapped_column(
        SAEnum(AlertLevelEnum), nullable=True
    )

    # Date of the soonest triggering event (ISO date string, e.g. "2026-03-15")
    event_date: Mapped[str] = mapped_column(String(10), nullable=True)

    # Title of the soonest triggering event (for display in prompts)
    event_title: Mapped[str] = mapped_column(String(500), nullable=True)

    # Whether a panic prompt should be surfaced in the next session response
    panic_prompt_active: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    household: Mapped["Household"] = relationship("Household")  # noqa: F821
