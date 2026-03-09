"""
ResidentScoringProfile — per-resident per-task feedback signals.

Updated by the history agent after each completion/skip.
Read by the suggestion agent to personalise scoring.

One row per (resident_id, task_template_id) pair — upserted on each update.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import Base


class ResidentScoringProfile(Base):
    __tablename__ = "resident_scoring_profiles"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    resident_id: Mapped[int] = Column(
        Integer, ForeignKey("residents.id"), nullable=False, index=True
    )
    task_template_id: Mapped[int] = Column(
        Integer, ForeignKey("task_templates.id"), nullable=False, index=True
    )

    # Rejection tracking
    rejection_count: Mapped[int] = Column(Integer, nullable=False, default=0)
    last_rejected_at: Mapped[datetime] = Column(DateTime, nullable=True)

    # Time-of-day preference (detected from completion history)
    # Values: morning, afternoon, evening, none
    preferred_time_of_day: Mapped[str] = Column(
        String(20), nullable=False, default="none"
    )

    # Imbalance flag: True when this resident should do this task more (others did it all)
    imbalance_flag: Mapped[bool] = Column(Boolean, nullable=False, default=False)

    last_updated: Mapped[datetime] = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("resident_id", "task_template_id", name="uq_profile_resident_task"),
    )
