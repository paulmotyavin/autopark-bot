from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from autopark_bot.db.base import Base, utcnow
from autopark_bot.enums import DriverStatus


class Driver(Base):
    """Карточка водителя как бизнес-сущность («кто ездит на машинах парка»).

    Отличается от users: карточку создаёт владелец ДО того, как человек зашёл в бот.
    Когда водитель переходит по ссылке-приглашению, user_id заполняется — и с этого момента
    его Telegram-аккаунт связан с карточкой.
    """

    __tablename__ = "drivers"
    __table_args__ = (CheckConstraint("status IN ('active', 'archived')", name="status_valid"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # NULL, пока водитель не зашёл в бот. UNIQUE: один аккаунт = одна карточка.
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True)

    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(16), default=DriverStatus.ACTIVE.value, server_default=DriverStatus.ACTIVE.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
