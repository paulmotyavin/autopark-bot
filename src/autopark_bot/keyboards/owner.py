from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from autopark_bot.db.models import Vehicle
from autopark_bot.enums import VEHICLE_STATUS_TITLES, VehicleStatus
from autopark_bot.services.vehicles import FIELDS, VehiclePage

MENU_VEHICLES = "🚗 Машины"


def staff_menu() -> ReplyKeyboardMarkup:
    """Постоянное меню внизу экрана для владельца и администратора."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MENU_VEHICLES)]], resize_keyboard=True
    )


class VehicleCb(CallbackData, prefix="veh"):
    """Все кнопки раздела «Машины». Что делать — в `action`, остальное — параметры.

    Здесь только «что нажали». Права и актуальность данных проверяет сервис в момент действия.
    """

    action: str  # list | card | add | edit_menu | edit | to_repair | from_repair | archive | ...
    id: int = 0
    status: str = "all"  # активный фильтр списка (чтобы вернуться туда же)
    page: int = 0  # страница списка (то же)
    field: str = ""  # для action="edit": какое поле менять


def _btn(text: str, **params: object) -> InlineKeyboardButton:
    data = VehicleCb(**params)  # type: ignore[arg-type]
    return InlineKeyboardButton(text=text, callback_data=data.pack())


_FILTERS = (("all", "Все"), ("free", "🟢"), ("rented", "🔵"), ("repair", "🔧"))


def vehicles_list_kb(page: VehiclePage, *, status: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    rows.append(
        [
            _btn(f"• {title}" if code == status else title, action="list", status=code)
            for code, title in _FILTERS
        ]
    )
    for v in page.items:
        icon = VEHICLE_STATUS_TITLES[VehicleStatus(v.status)].split()[0]
        rows.append(
            [
                _btn(
                    f"{icon} {v.make} {v.model} · {v.plate}",
                    action="card",
                    id=v.id,
                    status=status,
                    page=page.page,
                )
            ]
        )
    if page.pages > 1:
        rows.append(
            [
                _btn("◀", action="list", status=status, page=max(page.page - 1, 0)),
                _btn(f"{page.page + 1}/{page.pages}", action="noop"),
                _btn("▶", action="list", status=status, page=min(page.page + 1, page.pages - 1)),
            ]
        )
    rows.append([_btn("➕ Добавить машину", action="add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vehicle_card_kb(vehicle: Vehicle, *, status: str, page: int) -> InlineKeyboardMarkup:
    ctx = {"id": vehicle.id, "status": status, "page": page}
    rows = [[_btn("✏️ Изменить", action="edit_menu", **ctx)]]
    if vehicle.status == VehicleStatus.FREE.value:
        rows.append(
            [
                _btn("🔧 На ремонт", action="to_repair", **ctx),
                _btn("🗄 В архив", action="archive", **ctx),
            ]
        )
    elif vehicle.status == VehicleStatus.REPAIR.value:
        rows.append([_btn("✅ Вернуть из ремонта", action="from_repair", **ctx)])
    rows.append([_btn("◀ К списку", action="list", status=status, page=page)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vehicle_edit_kb(vehicle_id: int, *, status: str, page: int) -> InlineKeyboardMarkup:
    ctx = {"id": vehicle_id, "status": status, "page": page}
    buttons = [_btn(spec.label, action="edit", field=key, **ctx) for key, spec in FIELDS.items()]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn("◀ Назад", action="card", **ctx)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def archive_confirm_kb(vehicle_id: int, *, status: str, page: int) -> InlineKeyboardMarkup:
    ctx = {"id": vehicle_id, "status": status, "page": page}
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("✅ Да, в архив", action="archive_ok", **ctx),
                _btn("Отмена", action="card", **ctx),
            ]
        ]
    )
