from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Household composition flags — control which catalog tasks are visible
    has_children: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_cats: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_dogs: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_garden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Appliance / device capability flags — influence task scoring and variants
    # Each True flag changes which tasks are suggested and at what frequency
    has_robot_vacuum: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_robot_mop: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_dishwasher: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_washer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_dryer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_window_cleaner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_steam_cleaner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_robot_mower: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_irrigation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    residents: Mapped[list["Resident"]] = relationship(  # noqa: F821
        "Resident", back_populates="household"
    )
    rooms: Mapped[list["Room"]] = relationship(  # noqa: F821
        "Room", back_populates="household"
    )
    devices: Mapped[list["Device"]] = relationship(  # noqa: F821
        "Device", back_populates="household"
    )
