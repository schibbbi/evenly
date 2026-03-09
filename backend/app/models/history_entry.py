"""
HistoryEntry — append-only log of every task action.

Entries are never modified or deleted after creation.
Actions: completed, skipped, delegated, delegation_received
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped

from app.database import Base


class HistoryEntry(Base):
    __tablename__ = "history_entries"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    resident_id: Mapped[int] = Column(
        Integer, ForeignKey("residents.id"), nullable=False, index=True
    )
    task_template_id: Mapped[int] = Column(
        Integer, ForeignKey("task_templates.id"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = Column(
        Integer, ForeignKey("task_assignments.id"), nullable=True
    )

    # Action type
    action: Mapped[str] = Column(String(30), nullable=False)
    # Values: completed, skipped, delegated, delegation_received

    timestamp: Mapped[datetime] = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Denormalized for query performance
    room_type: Mapped[str] = Column(String(50), nullable=False)

    # Gamification context (points filled by R6)
    points_awarded: Mapped[int] = Column(Integer, nullable=True)

    # Task context flags (snapshot at time of action)
    was_unpopular: Mapped[bool] = Column(Boolean, nullable=False, default=False)
    was_forced: Mapped[bool] = Column(Boolean, nullable=False, default=False)
