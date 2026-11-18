from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .driver import Driver
    from .file import StoredFile
    from .vehicle import Vehicle


class MileageRecord(Base):
    """Историческое показание одометра автомобиля."""

    __tablename__ = "mileage_records"
    __table_args__ = (
        CheckConstraint("mileage >= 0", name="ck_mileage_records_nonnegative"),
        Index("ix_mileage_records_vehicle_recorded_at", "vehicle_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False
    )
    driver_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True
    )
    mileage: Mapped[int] = mapped_column(Integer, nullable=False)
    photo_file_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("files.id", ondelete="RESTRICT"), nullable=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    vehicle: Mapped[Vehicle] = relationship(back_populates="mileage_records")
    driver: Mapped[Driver | None] = relationship(back_populates="mileage_records")
    photo_file: Mapped[StoredFile | None] = relationship(back_populates="mileage_photos")
