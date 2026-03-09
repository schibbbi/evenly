"""
Voucher — Personal reward earned at point thresholds.

Types:
    free_day  — Grants +1 streak-safe immediately on redemption.
    custom    — Household-defined reward (display only, label from household).

Vouchers are personal: cannot be shared or transferred.
Auto-redemption is NOT supported — always resident's explicit choice.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import VoucherTypeEnum


class Voucher(Base):
    __tablename__ = "vouchers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    resident_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("residents.id"), nullable=False, index=True
    )
    game_profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resident_game_profiles.id"), nullable=False, index=True
    )

    type: Mapped[VoucherTypeEnum] = mapped_column(SAEnum(VoucherTypeEnum), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # For free_day: auto-label "Free Day Voucher".
    # For custom: household fills in the label.

    earned_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    redeemed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_redeemed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    resident: Mapped["Resident"] = relationship("Resident")  # noqa: F821
    game_profile: Mapped["ResidentGameProfile"] = relationship(  # noqa: F821
        "ResidentGameProfile", back_populates="vouchers"
    )
