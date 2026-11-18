from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .file import StoredFile
    from .rental_charge import RentalCharge
    from .user import User


class Payment(Base):
    """Платёж водителя, привязанный к конкретному начислению аренды."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')",
            name="ck_payments_status",
        ),
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        Index("ix_payments_charge_status", "charge_id", "status"),
        Index("ix_payments_submitted_at", "submitted_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    charge_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("rental_charges.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    proof_file_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("files.id", ondelete="RESTRICT"),
        nullable=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    charge: Mapped[RentalCharge] = relationship(back_populates="payments")
    proof_file: Mapped[StoredFile | None] = relationship(
        back_populates="payment_proofs",
        foreign_keys=[proof_file_id],
    )
    reviewed_by_user: Mapped[User | None] = relationship(
        back_populates="reviewed_payments",
        foreign_keys=[reviewed_by_id],
    )
