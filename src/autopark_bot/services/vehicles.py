import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from autopark_bot.db.models import User, Vehicle
from autopark_bot.enums import VehicleStatus
from autopark_bot.services.audit import audit
from autopark_bot.services.users import require_staff
from autopark_bot.utils.text import (
    parse_km,
    parse_money,
    parse_plate,
    parse_title,
    parse_vin,
    parse_year,
)

PAGE_SIZE = 8
FILTERABLE_STATUSES = (VehicleStatus.FREE, VehicleStatus.RENTED, VehicleStatus.REPAIR)


class VehicleError(Exception):
    """Ошибка с текстом, который можно показать пользователю."""


class VehicleNotFound(VehicleError):
    pass


class VehicleConflict(VehicleError):
    pass


# ---------- какие поля есть у машины и как их вводить ----------


@dataclass(frozen=True)
class Field:
    label: str
    hint: str
    parse: Callable[[str], object]
    optional: bool = False  # необязательное поле можно пропустить или очистить вводом «-»


FIELDS: dict[str, Field] = {
    "plate": Field("Госномер", "например А123ВС77", parse_plate),
    "make": Field("Марка", "например Kia", parse_title),
    "model": Field("Модель", "например Rio", parse_title),
    "year": Field("Год выпуска", "например 2020", parse_year, optional=True),
    "odometer_km": Field("Пробег, км", "например 120000", parse_km),
    "purchase_price": Field("Цена покупки, ₽", "например 1500000", parse_money, optional=True),
    "vin": Field("VIN", "17 символов", parse_vin, optional=True),
}

# Порядок вопросов при добавлении машины (VIN можно добавить позже через «Изменить»).
ADD_STEPS = ("plate", "make", "model", "year", "odometer_km", "purchase_price")


def parse_field(key: str, raw: str) -> object:
    """Разбирает ввод пользователя для поля. ValueError — текст ошибки для пользователя."""
    spec = FIELDS[key]
    if spec.optional and raw.strip() in {"-", "—"}:
        return None
    return spec.parse(raw)


# ---------- чтение ----------


@dataclass(frozen=True)
class VehiclePage:
    items: list[Vehicle]
    total: int
    page: int
    pages: int


async def get_vehicle(session: AsyncSession, vehicle_id: int) -> Vehicle:
    vehicle = await session.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.status == VehicleStatus.ARCHIVED.value:
        raise VehicleNotFound("Машина не найдена")
    return vehicle


async def plate_taken(session: AsyncSession, plate: str) -> bool:
    return await session.scalar(select(Vehicle.id).where(Vehicle.plate == plate)) is not None


async def status_counts(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        select(Vehicle.status, func.count())
        .where(Vehicle.status != VehicleStatus.ARCHIVED.value)
        .group_by(Vehicle.status)
    )
    return {status: count for status, count in rows.all()}


async def list_vehicles(
    session: AsyncSession, *, status: str | None, page: int, page_size: int = PAGE_SIZE
) -> VehiclePage:
    conditions = [Vehicle.status != VehicleStatus.ARCHIVED.value]
    if status in {s.value for s in FILTERABLE_STATUSES}:
        conditions.append(Vehicle.status == status)

    total = await session.scalar(select(func.count()).select_from(Vehicle).where(*conditions)) or 0
    pages = max(1, math.ceil(total / page_size))
    page = min(max(page, 0), pages - 1)
    items = (
        await session.scalars(
            select(Vehicle)
            .where(*conditions)
            .order_by(Vehicle.plate)
            .limit(page_size)
            .offset(page * page_size)
        )
    ).all()
    return VehiclePage(items=list(items), total=total, page=page, pages=pages)


# ---------- запись (только персонал) ----------


def _conflict(exc: IntegrityError) -> VehicleConflict:
    # Уникальность гарантирует БД; здесь только переводим её ошибку в понятный текст.
    details = str(exc.orig)
    if "uq_vehicles_plate" in details:
        return VehicleConflict("Машина с таким госномером уже есть.")
    if "uq_vehicles_vin" in details:
        return VehicleConflict("Машина с таким VIN уже есть.")
    return VehicleConflict("Не удалось сохранить: данные нарушают ограничения.")


async def create_vehicle(
    session: AsyncSession, *, actor: User, values: dict[str, Any]
) -> Vehicle:
    require_staff(actor)
    vehicle = Vehicle(**values)
    try:
        async with session.begin_nested():  # SAVEPOINT: при конфликте откатится только он
            session.add(vehicle)
            await session.flush()
    except IntegrityError as exc:
        raise _conflict(exc) from exc
    await audit(
        session,
        actor_user_id=actor.id,
        action="vehicle.create",
        entity="vehicle",
        entity_id=vehicle.id,
    )
    return vehicle


async def update_vehicle_field(
    session: AsyncSession, *, actor: User, vehicle_id: int, field: str, value: object
) -> Vehicle:
    require_staff(actor)
    if field not in FIELDS:  # белый список: другие колонки (status и т.д.) так не меняются
        raise ValueError(f"Поле {field!r} нельзя менять")
    vehicle = await get_vehicle(session, vehicle_id)
    old = getattr(vehicle, field)
    try:
        async with session.begin_nested():
            setattr(vehicle, field, value)
            await session.flush()
    except IntegrityError as exc:
        raise _conflict(exc) from exc
    await audit(
        session,
        actor_user_id=actor.id,
        action="vehicle.update",
        entity="vehicle",
        entity_id=vehicle_id,
        details={"field": field, "old": str(old), "new": str(value)},
    )
    return vehicle


async def _transition(
    session: AsyncSession,
    *,
    actor: User,
    vehicle_id: int,
    from_status: VehicleStatus,
    to_status: VehicleStatus,
    action: str,
) -> None:
    """Меняет статус атомарно: сработает, только если машина всё ещё в ожидаемом статусе.

    Кнопки в чате живут долго, а статус мог измениться (другой админ, начало аренды).
    Условие `status = from_status` в самом UPDATE делает проверку надёжной.
    """
    require_staff(actor)
    moved = await session.scalar(
        update(Vehicle)
        .where(Vehicle.id == vehicle_id, Vehicle.status == from_status.value)
        .values(status=to_status.value)
        .returning(Vehicle.id)
    )
    if moved is None:
        raise VehicleConflict("Статус машины уже изменился. Откройте карточку заново.")
    await audit(
        session, actor_user_id=actor.id, action=action, entity="vehicle", entity_id=vehicle_id
    )


async def send_to_repair(session: AsyncSession, *, actor: User, vehicle_id: int) -> None:
    await _transition(
        session,
        actor=actor,
        vehicle_id=vehicle_id,
        from_status=VehicleStatus.FREE,
        to_status=VehicleStatus.REPAIR,
        action="vehicle.to_repair",
    )


async def return_from_repair(session: AsyncSession, *, actor: User, vehicle_id: int) -> None:
    await _transition(
        session,
        actor=actor,
        vehicle_id=vehicle_id,
        from_status=VehicleStatus.REPAIR,
        to_status=VehicleStatus.FREE,
        action="vehicle.from_repair",
    )


async def archive_vehicle(session: AsyncSession, *, actor: User, vehicle_id: int) -> None:
    await _transition(
        session,
        actor=actor,
        vehicle_id=vehicle_id,
        from_status=VehicleStatus.FREE,
        to_status=VehicleStatus.ARCHIVED,
        action="vehicle.archive",
    )
