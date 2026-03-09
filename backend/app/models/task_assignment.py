"""
TaskAssignment — a concrete suggestion of a task to a resident in a session.

Lifecycle: suggested → accepted → in_progress → completed
                                              → skipped
                                              → delegated (R6)

points_awarded is set by the Gamification Agent (R6) on completion.

session_id is nullable to support Panic Mode assignments (R7) which are not tied
to a DailySession. Exactly one of session_id or panic_session_id is set.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, relationship

from app.database import Base


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    # Nullable — Panic Mode assignments have no daily session
    session_id: Mapped[int] = Column(
        Integer, ForeignKey("daily_sessions.id"), nullable=True, index=True
    )
    # R7: Panic Mode session FK (NULL for normal assignments)
    panic_session_id: Mapped[int] = Column(
        Integer, ForeignKey("panic_sessions.id"), nullable=True, index=True
    )
    resident_id: Mapped[int] = Column(
        Integer, ForeignKey("residents.id"), nullable=False, index=True
    )
    task_template_id: Mapped[int] = Column(
        Integer, ForeignKey("task_templates.id"), nullable=False, index=True
    )

    # Status lifecycle
    status: Mapped[str] = Column(String(20), nullable=False, default="suggested")
    # AssignmentStatusEnum: suggested/accepted/in_progress/completed/skipped/delegated

    # Score snapshot (stored for debugging and feedback loop in R5)
    score: Mapped[float] = Column(Float, nullable=True)

    # Timestamps
    suggested_at: Mapped[datetime] = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    accepted_at: Mapped[datetime] = Column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = Column(DateTime, nullable=True)

    # Reroll + delegation tracking
    reroll_count: Mapped[int] = Column(Integer, nullable=False, default=0)
    is_forced: Mapped[bool] = Column(Boolean, nullable=False, default=False)
    # is_forced=True: unpopular overdue task — cannot be replaced by reroll

    # Points — set by Gamification Agent in R6
    points_awarded: Mapped[int] = Column(Integer, nullable=True)

    # Relationships
    session: Mapped["DailySession"] = relationship(  # noqa: F821
        "DailySession", back_populates="assignments"
    )
    panic_session: Mapped["PanicSession"] = relationship(  # noqa: F821
        "PanicSession",
        foreign_keys=[panic_session_id],
        back_populates="assignments",
    )
    task_template: Mapped["TaskTemplate"] = relationship("TaskTemplate")  # noqa: F821
