from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .user import User


class NotificationLog(Base):
    """Журнал отправки уведомлений с защитой от повторов."""

    __tablename__ = "notification_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="ck_notification_logs_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_notification_logs_attempts"),
        UniqueConstraint("deduplication_key", name="uq_notification_logs_deduplication_key"),
        Index("ix_notification_logs_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User | None] = relationship(back_populates="notifications")
