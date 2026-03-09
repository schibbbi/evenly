"""
PanicSession — A time-boxed emergency cleaning plan activated by any resident.

Panic Mode generates a prioritized task distribution across selected residents,
covering visible/shared areas first. All task completions feed into history and
gamification as normal (normal points, normal streaks).

status: active → completed
"""

import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PanicSession(Base):
    __tablename__ = "panic_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    activated_by_resident_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("residents.id"), nullable=False, index=True
    )

    # Total minutes budgeted for the panic session (120, 180, or 240)
    available_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # JSON array of resident IDs who are available to help
    # e.g. "[1, 2]" — stored as text, parsed in application layer
    available_resident_ids: Mapped[str] = mapped_column(Text, nullable=False)

    # status: "active" | "completed"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    activated_by: Mapped["Resident"] = relationship(  # noqa: F821
        "Resident", foreign_keys=[activated_by_resident_id]
    )
    assignments: Mapped[list["TaskAssignment"]] = relationship(  # noqa: F821
        "TaskAssignment",
        primaryjoin="TaskAssignment.panic_session_id == PanicSession.id",
        back_populates="panic_session",
    )

    # Helpers
    def get_resident_ids(self) -> list[int]:
        return json.loads(self.available_resident_ids)

    def set_resident_ids(self, ids: list[int]) -> None:
        self.available_resident_ids = json.dumps(ids)
