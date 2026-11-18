from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from autopark_bot.db.base import Base, utcnow


class AuditLog(Base):
    """Журнал чувствительных действий: кто, что, над какой сущностью."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), index=True
    )
