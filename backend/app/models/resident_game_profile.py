"""
ResidentGameProfile — Personal gamification state per resident.

Tracks total points, current streak, longest streak, streak-safes,
last activity date, and voucher threshold watermark.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ResidentGameProfile(Base):
    __tablename__ = "resident_game_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    resident_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("residents.id"), nullable=False, unique=True, index=True
    )

    # Points
    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Watermark: how many full 100-point thresholds have already yielded vouchers
    voucher_threshold_watermark: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Streak
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Streak-safes — no cap on total held; max 3 earned per day
    streak_safes_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak_safes_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Date of last task completion (ISO date string, e.g. "2026-03-08")
    last_activity_date: Mapped[str] = mapped_column(String(10), nullable=True)

    # Delegation lock: when True, only delegated tasks appear in suggestions
    delegation_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    resident: Mapped["Resident"] = relationship("Resident")  # noqa: F821
    transactions: Mapped[list["PointTransaction"]] = relationship(  # noqa: F821
        "PointTransaction", back_populates="game_profile", cascade="all, delete-orphan"
    )
    vouchers: Mapped[list["Voucher"]] = relationship(  # noqa: F821
        "Voucher", back_populates="game_profile", cascade="all, delete-orphan"
    )
