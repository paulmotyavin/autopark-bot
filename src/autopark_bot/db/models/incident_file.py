from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .file import StoredFile
    from .incident import Incident


class IncidentFile(Base):
    """Связь происшествия с фотографиями и другими вложениями."""

    __tablename__ = "incident_files"
    __table_args__ = (Index("ix_incident_files_file_id", "file_id"),)

    incident_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    file_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("files.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    order_index: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )

    incident: Mapped[Incident] = relationship(back_populates="files")
    file: Mapped[StoredFile] = relationship(back_populates="incident_links")
