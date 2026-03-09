"""
DelegationRecord — Tracks a task delegation from one resident to another.

Lifecycle:
    delegated_at          — when sender delegated
    deadline_at           — 3 days after delegated_at; background job checks this
    completed_at          — when the receiver completes (or NULL if expired/pending)
    no_points_on_completion — True when deadline expired; receiver gets no points

When deadline expires (background job):
    - delegation_locked = True is set on receiver's ResidentGameProfile
    - Receiver's suggestion queue shows ONLY this delegated task
    - no_points_on_completion = True
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DelegationRecord(Base):
    __tablename__ = "delegation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    from_resident_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("residents.id"), nullable=False, index=True
    )
    to_resident_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("residents.id"), nullable=False, index=True
    )

    # The original assignment (from the sender's session)
    assignment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("task_assignments.id"), nullable=False, index=True
    )
    # The new assignment created for the receiver
    receiver_assignment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("task_assignments.id"), nullable=True
    )

    delegated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    deadline_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # True once background job detects deadline passed without completion
    no_points_on_completion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Relationships
    from_resident: Mapped["Resident"] = relationship(  # noqa: F821
        "Resident", foreign_keys=[from_resident_id]
    )
    to_resident: Mapped["Resident"] = relationship(  # noqa: F821
        "Resident", foreign_keys=[to_resident_id]
    )
    assignment: Mapped["TaskAssignment"] = relationship(  # noqa: F821
        "TaskAssignment", foreign_keys=[assignment_id]
    )
    receiver_assignment: Mapped["TaskAssignment"] = relationship(  # noqa: F821
        "TaskAssignment", foreign_keys=[receiver_assignment_id]
    )
