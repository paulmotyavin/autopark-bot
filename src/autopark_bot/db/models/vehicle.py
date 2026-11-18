from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from autopark_bot.db.base import Base, utcnow
from autopark_bot.enums import VehicleStatus


class Vehicle(Base):
    """Автомобиль парка. Одна строка = одна машина."""

    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("status IN ('free', 'rented', 'repair', 'archived')", name="status_valid"),
        CheckConstraint("odometer_km >= 0", name="odometer_non_negative"),
        CheckConstraint(
            "purchase_price IS NULL OR purchase_price >= 0", name="purchase_price_non_negative"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Госномер: хранить в одном виде (верхний регистр, без пробелов) — это делает сервис.
    plate: Mapped[str] = mapped_column(String(16), unique=True)
    # VIN необязателен; UNIQUE допускает много NULL, но два одинаковых VIN не пропустит.
    vin: Mapped[str | None] = mapped_column(String(17), unique=True)
    make: Mapped[str] = mapped_column(String(64))  # марка: Kia
    model: Mapped[str] = mapped_column(String(64))  # модель: Rio
    year: Mapped[int | None] = mapped_column(SmallInteger)

    # Статус меняется ТОЛЬКО через сервис (начало/конец аренды, ремонт), не вручную в хендлерах.
    status: Mapped[str] = mapped_column(
        String(16), default=VehicleStatus.FREE.value, server_default=VehicleStatus.FREE.value
    )

    # Текущий пробег: обновляется, когда админ принимает показание от водителя.
    odometer_km: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    # Нужны для «окупаемости»: доход по машине / цена покупки.
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    purchase_date: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
