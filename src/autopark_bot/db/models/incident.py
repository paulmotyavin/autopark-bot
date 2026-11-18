from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .driver import Driver
    from .incident_file import IncidentFile
    from .user import User
    from .vehicle import Vehicle


class Incident(Base):
    """Сообщение о ДТП, повреждении или другом происшествии."""

    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved')",
            name="ck_incidents_status",
        ),
        Index("ix_incidents_vehicle_occurred_at", "vehicle_id", "occurred_at"),
        Index("ix_incidents_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False
    )
    driver_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="open",
        server_default=text("'open'"),
    )
    reported_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    vehicle: Mapped[Vehicle] = relationship(back_populates="incidents")
    driver: Mapped[Driver | None] = relationship(back_populates="incidents")
    reported_by_user: Mapped[User | None] = relationship(foreign_keys=[reported_by_id])
    files: Mapped[list[IncidentFile]] = relationship(back_populates="incident")
