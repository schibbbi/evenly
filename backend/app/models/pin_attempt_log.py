from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PINAttemptLog(Base):
    __tablename__ = "pin_attempt_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)  # IPv4 or IPv6
