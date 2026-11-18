from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .vehicle import Vehicle


class MaintenanceRecord(Base):
    """Плановое или выполненное обслуживание автомобиля."""

    __tablename__ = "maintenance_records"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'cancelled')",
            name="ck_maintenance_records_status",
        ),
        CheckConstraint(
            "planned_mileage IS NULL OR planned_mileage >= 0",
            name="ck_maintenance_records_planned_mileage",
        ),
        CheckConstraint(
            "completed_mileage IS NULL OR completed_mileage >= 0",
            name="ck_maintenance_records_completed_mileage",
        ),
        CheckConstraint("cost IS NULL OR cost >= 0", name="ck_maintenance_records_cost"),
        Index("ix_maintenance_records_status_date", "status", "planned_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="planned",
        server_default=text("'planned'"),
    )
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    vehicle: Mapped[Vehicle] = relationship(back_populates="maintenance_records")
