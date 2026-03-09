"""
CalendarConfig — Per-household Google Calendar OAuth2 configuration.

One row per household. Stores the refresh token (never exposed in API responses)
and the list of calendar IDs to monitor.

Security note:
  google_refresh_token is stored in plain text in SQLite.
  For a self-hosted, LAN-only deployment this is acceptable.
  The token is excluded from all API response schemas.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CalendarConfig(Base):
    __tablename__ = "calendar_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    household_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("households.id"), nullable=False, unique=True, index=True
    )

    # OAuth2 refresh token — never returned in API responses
    google_refresh_token: Mapped[str] = mapped_column(Text, nullable=True)

    # JSON array of Google Calendar IDs to monitor, e.g. ["primary", "abc@group.calendar.google.com"]
    calendar_ids: Mapped[str] = mapped_column(
        Text, nullable=False, default='["primary"]'
    )

    last_synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # is_active becomes True once OAuth2 flow completes and refresh token is stored

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    household: Mapped["Household"] = relationship("Household")  # noqa: F821
    events: Mapped[list["CalendarEvent"]] = relationship(  # noqa: F821
        "CalendarEvent", back_populates="calendar_config", cascade="all, delete-orphan"
    )

    # Helpers
    def get_calendar_ids(self) -> list[str]:
        return json.loads(self.calendar_ids)

    def set_calendar_ids(self, ids: list[str]) -> None:
        self.calendar_ids = json.dumps(ids)
