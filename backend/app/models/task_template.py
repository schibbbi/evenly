"""
TaskTemplate — the catalog of all household tasks.

Each row represents one task that the suggestion engine can schedule.
Tasks are either AI-generated (is_custom=False) or user-created (is_custom=True).

Visibility logic:
- household_flag=None  → always visible
- household_flag=cats  → visible only when household.has_cats=True
- device_flag=None     → always visible
- device_flag=robot_vacuum → visible only when household.has_robot_vacuum=True

Robot scoring logic:
- Manual floor tasks have a paired robot variant (is_robot_variant=True)
- robot_frequency_multiplier reduces manual task frequency when robot is present
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped

from app.database import Base
from app.models.enums import (
    CategoryEnum,
    DeviceFlagEnum,
    EnergyLevelEnum,
    HouseholdFlagEnum,
    RoomTypeEnum,
)


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = Column(String(200), nullable=False)
    description: Mapped[str] = Column(String(500), nullable=True)

    # Location + classification
    room_type: Mapped[str] = Column(String(50), nullable=False)   # RoomTypeEnum value
    category: Mapped[str] = Column(String(50), nullable=False)    # CategoryEnum value

    # Scheduling defaults (editable by resident)
    default_duration_minutes: Mapped[int] = Column(Integer, nullable=False, default=15)
    default_frequency_days: Mapped[int] = Column(Integer, nullable=False, default=7)
    energy_level: Mapped[str] = Column(String(20), nullable=False, default="medium")  # EnergyLevelEnum value

    # Visibility gates
    household_flag: Mapped[str] = Column(String(50), nullable=True)  # HouseholdFlagEnum | None
    device_flag: Mapped[str] = Column(String(50), nullable=True)      # DeviceFlagEnum | None

    # Robot scoring fields
    is_robot_variant: Mapped[bool] = Column(Boolean, nullable=False, default=False)
    robot_frequency_multiplier: Mapped[float] = Column(Float, nullable=True)

    # State
    is_active: Mapped[bool] = Column(Boolean, nullable=False, default=True)
    is_custom: Mapped[bool] = Column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
