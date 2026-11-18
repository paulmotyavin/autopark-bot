from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from autopark_bot.db.base import Base, utcnow


class User(Base):
    """Учётная запись: кто может войти в бот и с какой ролью.

    Роль хранится строкой + CHECK (без PG ENUM — проще миграции).
    """

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('owner', 'admin', 'driver')", name="role_valid"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    role: Mapped[str] = mapped_column(String(16))
    full_name: Mapped[str] = mapped_column(String(200))
    username: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class Invitation(Base):
    """Одноразовая ссылка-приглашение. В БД лежит только sha256 токена."""

    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'driver')", name="role_valid"),
        # Приглашение водителя ОБЯЗАНО указывать карточку водителя, приглашение админа — нет.
        CheckConstraint("(role = 'driver') = (driver_id IS NOT NULL)", name="driver_link"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(16))
    # Для role='driver': какую карточку водителя привяжет это приглашение.
    driver_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("drivers.id"))
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
