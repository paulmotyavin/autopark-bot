import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from autopark_bot.db.models import User, Vehicle
from autopark_bot.enums import VEHICLE_STATUS_TITLES, VehicleStatus
from autopark_bot.keyboards.owner import (
    MENU_VEHICLES,
    VehicleCb,
    archive_confirm_kb,
    vehicle_card_kb,
    vehicle_edit_kb,
    vehicles_list_kb,
)
from autopark_bot.services.vehicles import (
    ADD_STEPS,
    FIELDS,
    VehicleError,
    VehicleNotFound,
    archive_vehicle,
    create_vehicle,
    get_vehicle,
    list_vehicles,
    parse_field,
    plate_taken,
    return_from_repair,
    send_to_repair,
    status_counts,
    update_vehicle_field,
)
from autopark_bot.utils.text import format_km, format_money

router = Router(name="owner-vehicles")


class AddVehicle(StatesGroup):
    waiting = State()  # ждём ответ на текущий вопрос; номер вопроса лежит в данных FSM


class EditVehicle(StatesGroup):
    waiting = State()  # ждём новое значение поля


# ---------- отображение ----------


def _card_text(v: Vehicle) -> str:
    # make/model/plate/vin вводит человек, а parse_mode=HTML: экранируем.
    price = format_money(v.purchase_price) if v.purchase_price is not None else "—"
    lines = [
        f"🚗 <b>{html.escape(v.make)} {html.escape(v.model)}</b>",
        f"Госномер: <b>{html.escape(v.plate)}</b>",
        f"Статус: {VEHICLE_STATUS_TITLES[VehicleStatus(v.status)]}",
        f"Год: {v.year or '—'} · Пробег: {format_km(v.odometer_km)}",
        f"VIN: {html.escape(v.vin) if v.vin else '—'}",
        f"Цена покупки: {price}",
    ]
    if v.status == VehicleStatus.RENTED.value:
        lines.append("\nЧтобы сменить статус, сначала завершите аренду.")
    return "\n".join(lines)


async def _list_view(
    session: AsyncSession, *, status: str, page: int
) -> tuple[str, InlineKeyboardMarkup]:
    counts = await status_counts(session)
    result = await list_vehicles(session, status=None if status == "all" else status, page=page)
    text = (
        f"<b>Машины</b>: всего {sum(counts.values())}"
        f" · 🟢 {counts.get('free', 0)} · 🔵 {counts.get('rented', 0)}"
        f" · 🔧 {counts.get('repair', 0)}"
    )
    if not result.items:
        text += "\n\nЗдесь пока пусто."
    return text, vehicles_list_kb(result, status=status)


def _prompt(field_key: str) -> str:
    spec = FIELDS[field_key]
    tail = " «-» — оставить пустым." if spec.optional else ""
    return f"{spec.label} ({spec.hint}).{tail}\n/cancel — отмена"


async def _show(callback: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    """Меняет текст сообщения с кнопками (а не шлёт новое) и закрывает «часики» на кнопке."""
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc):
                raise
    await callback.answer()


async def _show_card(
    callback: CallbackQuery, session: AsyncSession, *, vehicle_id: int, status: str, page: int
) -> None:
    try:
        vehicle = await get_vehicle(session, vehicle_id)
    except VehicleNotFound as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await _show(callback, _card_text(vehicle), vehicle_card_kb(vehicle, status=status, page=page))


# ---------- меню, отмена, списки, карточка ----------


@router.message(F.text == MENU_VEHICLES)
async def on_menu(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()  # нажатие меню прерывает любой незаконченный ввод
    text, kb = await _list_view(session, status="all", page=0)
    await message.answer(text, reply_markup=kb)


@router.message(Command("cancel"), StateFilter("*"))
async def on_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("Нечего отменять.")
        return
    await state.clear()
    await message.answer("Отменено.")


@router.callback_query(VehicleCb.filter(F.action == "noop"))
async def on_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(VehicleCb.filter(F.action == "list"))
async def on_list(callback: CallbackQuery, callback_data: VehicleCb, session: AsyncSession) -> None:
    text, kb = await _list_view(session, status=callback_data.status, page=callback_data.page)
    await _show(callback, text, kb)


@router.callback_query(VehicleCb.filter(F.action == "card"))
async def on_card(callback: CallbackQuery, callback_data: VehicleCb, session: AsyncSession) -> None:
    await _show_card(
        callback,
        session,
        vehicle_id=callback_data.id,
        status=callback_data.status,
        page=callback_data.page,
    )


# ---------- смена статуса ----------

_TRANSITIONS = {
    "to_repair": send_to_repair,
    "from_repair": return_from_repair,
    "archive_ok": archive_vehicle,
}


@router.callback_query(VehicleCb.filter(F.action == "archive"))
async def on_archive_ask(callback: CallbackQuery, callback_data: VehicleCb) -> None:
    await _show(
        callback,
        "Убрать машину в архив? Из списков она исчезнет, история сохранится.",
        archive_confirm_kb(callback_data.id, status=callback_data.status, page=callback_data.page),
    )


@router.callback_query(VehicleCb.filter(F.action.in_(_TRANSITIONS)))
async def on_transition(
    callback: CallbackQuery, callback_data: VehicleCb, session: AsyncSession, user: User
) -> None:
    try:
        await _TRANSITIONS[callback_data.action](session, actor=user, vehicle_id=callback_data.id)
    except VehicleError as exc:
        # Статус уже изменился (например, другой админ): сообщаем и показываем актуальную карточку.
        await callback.answer(str(exc), show_alert=True)
        await _show_card(
            callback,
            session,
            vehicle_id=callback_data.id,
            status=callback_data.status,
            page=callback_data.page,
        )
        return
    await session.commit()

    if callback_data.action == "archive_ok":
        text, kb = await _list_view(session, status=callback_data.status, page=callback_data.page)
        await _show(callback, text, kb)
    else:
        await _show_card(
            callback,
            session,
            vehicle_id=callback_data.id,
            status=callback_data.status,
            page=callback_data.page,
        )


# ---------- редактирование поля ----------


@router.callback_query(VehicleCb.filter(F.action == "edit_menu"))
async def on_edit_menu(callback: CallbackQuery, callback_data: VehicleCb) -> None:
    await _show(
        callback,
        "Что изменить?",
        vehicle_edit_kb(callback_data.id, status=callback_data.status, page=callback_data.page),
    )


@router.callback_query(VehicleCb.filter(F.action == "edit"))
async def on_edit(
    callback: CallbackQuery, callback_data: VehicleCb, state: FSMContext, session: AsyncSession
) -> None:
    if callback_data.field not in FIELDS:
        await callback.answer()
        return
    try:
        await get_vehicle(session, callback_data.id)
    except VehicleNotFound as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await state.set_state(EditVehicle.waiting)
    await state.update_data(
        vehicle_id=callback_data.id,
        field=callback_data.field,
        status=callback_data.status,
        page=callback_data.page,
    )
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(f"Новое значение.\n{_prompt(callback_data.field)}")


@router.message(EditVehicle.waiting, F.text)
async def on_edit_value(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    data = await state.get_data()
    try:
        value = parse_field(data["field"], message.text or "")
    except ValueError as exc:
        await message.answer(f"{exc}\nПопробуйте ещё раз или /cancel.")
        return

    try:
        vehicle = await update_vehicle_field(
            session,
            actor=user,
            vehicle_id=data["vehicle_id"],
            field=data["field"],
            value=value,
        )
    except VehicleNotFound as exc:
        await state.clear()
        await message.answer(str(exc))
        return
    except VehicleError as exc:  # например, такой госномер уже есть: даём ввести другой
        await message.answer(f"{exc}\nВведите другое значение или /cancel.")
        return

    await session.commit()
    await state.clear()
    await message.answer(
        "Сохранено ✅\n\n" + _card_text(vehicle),
        reply_markup=vehicle_card_kb(vehicle, status=data["status"], page=data["page"]),
    )


# ---------- добавление машины (пошаговый ввод) ----------


@router.callback_query(VehicleCb.filter(F.action == "add"))
async def on_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddVehicle.waiting)
    # В FSM кладём только то, что умеет JSON: номер шага и введённые строки.
    await state.update_data(step=0, values={})
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(f"Добавляем машину.\n\n{_prompt(ADD_STEPS[0])}")


@router.message(AddVehicle.waiting, F.text)
async def on_add_value(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    raw = (message.text or "").strip()
    data = await state.get_data()
    step: int = data["step"]
    values: dict[str, str] = data["values"]
    key = ADD_STEPS[step]

    try:
        parsed = parse_field(key, raw)
    except ValueError as exc:
        await message.answer(f"{exc}\nПопробуйте ещё раз или /cancel.")
        return
    # Ранняя проверка, чтобы не заставлять вводить всё до конца. Финальный страж — БД (UNIQUE).
    if key == "plate" and isinstance(parsed, str) and await plate_taken(session, parsed):
        await message.answer("Машина с таким госномером уже есть. Введите другой или /cancel.")
        return

    values[key] = raw
    step += 1
    if step < len(ADD_STEPS):
        await state.update_data(step=step, values=values)
        await message.answer(_prompt(ADD_STEPS[step]))
        return

    try:
        vehicle = await create_vehicle(
            session,
            actor=user,
            values={k: parse_field(k, v) for k, v in values.items()},
        )
    except VehicleError as exc:
        await state.clear()
        await message.answer(str(exc))
        return

    await session.commit()
    await state.clear()
    await message.answer(
        "Машина добавлена ✅\n\n" + _card_text(vehicle),
        reply_markup=vehicle_card_kb(vehicle, status="all", page=0),
    )


@router.message(StateFilter(AddVehicle, EditVehicle))
async def on_unexpected(message: Message) -> None:
    await message.answer("Жду текстовый ответ. /cancel — отмена.")
