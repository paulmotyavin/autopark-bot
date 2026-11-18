from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .driver import Driver
    from .file import StoredFile
    from .vehicle import Vehicle


class Document(Base):
    """Документ, принадлежащий ровно одному водителю или автомобилю."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "(vehicle_id IS NOT NULL AND driver_id IS NULL) "
            "OR (vehicle_id IS NULL AND driver_id IS NOT NULL)",
            name="ck_documents_single_owner",
        ),
        CheckConstraint(
            "expires_at IS NULL OR issued_at IS NULL OR expires_at >= issued_at",
            name="ck_documents_date_range",
        ),
        Index("ix_documents_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=True
    )
    driver_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=True
    )
    file_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("files.id", ondelete="RESTRICT"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issued_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    vehicle: Mapped[Vehicle | None] = relationship(back_populates="documents")
    driver: Mapped[Driver | None] = relationship(back_populates="documents")
    file: Mapped[StoredFile] = relationship(back_populates="documents")
