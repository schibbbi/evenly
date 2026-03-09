from sqlalchemy import ForeignKey, String, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.enums import PreferenceEnum


class ResidentPreference(Base):
    __tablename__ = "resident_preferences"
    __table_args__ = (
        UniqueConstraint("resident_id", "task_category", name="uq_resident_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), nullable=False)
    task_category: Mapped[str] = mapped_column(String(50), nullable=False)
    preference: Mapped[PreferenceEnum] = mapped_column(
        SAEnum(PreferenceEnum), nullable=False, default=PreferenceEnum.neutral
    )

    # Relationships
    resident: Mapped["Resident"] = relationship(  # noqa: F821
        "Resident", back_populates="preferences"
    )
