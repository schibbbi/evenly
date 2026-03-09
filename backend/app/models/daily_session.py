"""
DailySession — records one suggestion session for a resident.

A session is created when a resident requests tasks. It captures their energy level
and available time, and tracks reroll count (for gamification malus in R6).
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, relationship

from app.database import Base


class DailySession(Base):
    __tablename__ = "daily_sessions"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    resident_id: Mapped[int] = Column(
        Integer, ForeignKey("residents.id"), nullable=False, index=True
    )
    date: Mapped[str] = Column(String(10), nullable=False)          # ISO date: YYYY-MM-DD
    energy_level: Mapped[str] = Column(String(20), nullable=False)  # EnergyLevelEnum value
    available_minutes: Mapped[int] = Column(Integer, nullable=False)
    reroll_count: Mapped[int] = Column(Integer, nullable=False, default=0)
    reroll_malus: Mapped[bool] = Column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    assignments: Mapped[list["TaskAssignment"]] = relationship(  # noqa: F821
        "TaskAssignment", back_populates="session", cascade="all, delete-orphan"
    )
