from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .document import Document
    from .incident_file import IncidentFile
    from .mileage_record import MileageRecord
    from .payment import Payment
    from .user import User


class StoredFile(Base):
    """Метаданные объекта, физически сохранённого в S3."""

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("bucket", "object_key", name="uq_files_bucket_object_key"),
        CheckConstraint("size_bytes >= 0", name="ck_files_size_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    uploaded_by_user: Mapped[User | None] = relationship(
        back_populates="uploaded_files",
        foreign_keys=[uploaded_by_id],
    )
    documents: Mapped[list[Document]] = relationship(back_populates="file")
    payment_proofs: Mapped[list[Payment]] = relationship(back_populates="proof_file")
    mileage_photos: Mapped[list[MileageRecord]] = relationship(back_populates="photo_file")
    incident_links: Mapped[list[IncidentFile]] = relationship(back_populates="file")
