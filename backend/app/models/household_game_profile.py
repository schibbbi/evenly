"""
HouseholdGameProfile — Team-level gamification state.

Tracks combined team points and the team streak
(days on which ALL active residents completed at least one task).
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HouseholdGameProfile(Base):
    __tablename__ = "household_game_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    household_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("households.id"), nullable=False, unique=True, index=True
    )

    # Cumulative points earned via team multiplier
    team_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Consecutive days where all residents completed ≥1 task
    team_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ISO date of last day the team streak incremented
    last_team_activity_date: Mapped[str] = mapped_column(String(10), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    household: Mapped["Household"] = relationship("Household")  # noqa: F821
