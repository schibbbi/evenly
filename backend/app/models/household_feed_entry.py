"""
HouseholdFeedEntry — shared activity feed for all residents.

Human-readable entries generated server-side.
Only completed and delegated actions create feed entries — skips are private.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped

from app.database import Base


class HouseholdFeedEntry(Base):
    __tablename__ = "household_feed_entries"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    resident_id: Mapped[int] = Column(
        Integer, ForeignKey("residents.id"), nullable=False, index=True
    )

    # Human-readable text (e.g. "Alex completed: Wipe kitchen counters")
    text: Mapped[str] = Column(String(300), nullable=False)

    # Action type for frontend filtering/icon display
    action_type: Mapped[str] = Column(String(30), nullable=False)
    # Values: completed, delegated, delegation_received

    # Denormalized for display speed (no join needed)
    task_name: Mapped[str] = Column(String(200), nullable=False)

    timestamp: Mapped[datetime] = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
