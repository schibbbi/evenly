"""
CalendarEvent — A detected guest-related event from Google Calendar.

Cleared automatically when start_datetime is in the past (run by calendar_agent).
guest_probability: how likely the event involves external guests.
alert_level: how urgently homeowners should respond.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import GuestProbabilityEnum, AlertLevelEnum


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # FK to the CalendarConfig that sourced this event
    calendar_config_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("calendar_configs.id"), nullable=False, index=True
    )

    # Google Calendar event ID (for deduplication / upsert)
    google_event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Event content (title only — no full description stored for privacy)
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    start_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    guest_probability: Mapped[GuestProbabilityEnum] = mapped_column(
        SAEnum(GuestProbabilityEnum), nullable=False
    )
    alert_level: Mapped[AlertLevelEnum] = mapped_column(
        SAEnum(AlertLevelEnum), nullable=False
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    calendar_config: Mapped["CalendarConfig"] = relationship(  # noqa: F821
        "CalendarConfig", back_populates="events"
    )
