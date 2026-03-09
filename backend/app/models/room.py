from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.enums import RoomTypeEnum


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[RoomTypeEnum] = mapped_column(SAEnum(RoomTypeEnum), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    household: Mapped["Household"] = relationship(  # noqa: F821
        "Household", back_populates="rooms"
    )
    devices: Mapped[list["Device"]] = relationship(  # noqa: F821
        "Device", back_populates="room"
    )
