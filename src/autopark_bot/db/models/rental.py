from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from autopark_bot.db.base import Base, utcnow
from autopark_bot.enums import RentalStatus


class Rental(Base):
    """Аренда: «водитель X ездит на машине Y с даты Z по ставке S».

    Это центр всей модели: к аренде привязываются начисления и платежи (следующий этап).
    Отдельная таблица (а не vehicle.driver_id) нужна ради истории и честных цифр:
    ставка фиксируется в аренде, и её смена завтра не меняет прошлые долги.
    """

    __tablename__ = "rentals"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'closed')", name="status_valid"),
        CheckConstraint("rate_period IN ('daily', 'weekly', 'monthly')", name="rate_period_valid"),
        CheckConstraint("rate_amount > 0", name="rate_amount_positive"),
        CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="dates_valid"),
        # База сама не даст нарушить правило: у машины не больше одной активной аренды
        # и у водителя тоже. Даже если в коде появится ошибка или два админа нажмут разом.
        Index(
            "uq_rentals_active_vehicle",
            "vehicle_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_rentals_active_driver",
            "driver_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("vehicles.id"), index=True)
    driver_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("drivers.id"), index=True)

    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)  # NULL = аренда продолжается

    rate_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # сумма за период
    rate_period: Mapped[str] = mapped_column(String(8))  # daily | weekly | monthly

    status: Mapped[str] = mapped_column(
        String(8), default=RentalStatus.ACTIVE.value, server_default=RentalStatus.ACTIVE.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
