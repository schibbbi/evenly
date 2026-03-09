from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Enum as SAEnum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.enums import RoleEnum


class Resident(Base):
    __tablename__ = "residents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6366f1")  # hex color
    role: Mapped[RoleEnum] = mapped_column(
        SAEnum(RoleEnum), nullable=False, default=RoleEnum.view
    )
    pin_hash: Mapped[str] = mapped_column(String(60), nullable=False)  # bcrypt hash
    setup_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    household: Mapped["Household"] = relationship(  # noqa: F821
        "Household", back_populates="residents"
    )
    preferences: Mapped[list["ResidentPreference"]] = relationship(  # noqa: F821
        "ResidentPreference", back_populates="resident", cascade="all, delete-orphan"
    )
