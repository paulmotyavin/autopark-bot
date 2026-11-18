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
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .payment import Payment
    from .rental import Rental


class RentalCharge(Base):
    """Начисление арендной платы за определённый период."""

    __tablename__ = "rental_charges"
    __table_args__ = (
        CheckConstraint("period_end >= period_start", name="ck_rental_charges_period"),
        CheckConstraint("amount > 0", name="ck_rental_charges_amount_positive"),
        UniqueConstraint(
            "rental_id",
            "period_start",
            "period_end",
            name="uq_rental_charges_rental_period",
        ),
        Index("ix_rental_charges_due_date", "due_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rental_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rentals.id", ondelete="RESTRICT"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    rental: Mapped[Rental] = relationship(back_populates="charges")
    payments: Mapped[list[Payment]] = relationship(back_populates="charge")
