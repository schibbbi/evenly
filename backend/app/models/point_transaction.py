"""
PointTransaction — Immutable audit log of every point change.

reason:       why points changed (see PointReasonEnum)
reference_id: optional FK to the related entity (assignment_id, delegation_id, voucher_id)
amount:       signed integer (+10, -3, etc.)
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import PointReasonEnum


class PointTransaction(Base):
    __tablename__ = "point_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    resident_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("residents.id"), nullable=False, index=True
    )
    # FK to resident_game_profiles — every transaction is linked to the profile snapshot
    game_profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resident_game_profiles.id"), nullable=False, index=True
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # Positive = earn, Negative = spend

    reason: Mapped[PointReasonEnum] = mapped_column(
        SAEnum(PointReasonEnum), nullable=False
    )

    # Optional reference to the originating entity
    reference_id: Mapped[int] = mapped_column(Integer, nullable=True)
    # e.g. assignment.id, delegation_record.id, voucher.id

    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    resident: Mapped["Resident"] = relationship("Resident")  # noqa: F821
    game_profile: Mapped["ResidentGameProfile"] = relationship(  # noqa: F821
        "ResidentGameProfile", back_populates="transactions"
    )
