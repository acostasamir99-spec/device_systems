"""Modelo SQLAlchemy de préstamos."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'returned', 'overdue')",
            name="ck_loans_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id"), nullable=False
    )
    # SQLite guarda esta fecha UTC sin información de zona horaria.
    loan_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=func.current_timestamp(),
    )
    return_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="loans")
    device: Mapped["Device"] = relationship("Device", back_populates="loans")
