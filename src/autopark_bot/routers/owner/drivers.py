import html
from datetime import timedelta

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from autopark_bot.config import Settings
from autopark_bot.db.models import Driver, User
from autopark_bot.enums import Role
from autopark_bot.keyboards.owner import (
    MENU_DRIVERS,
    DriverCb,
    driver_archive_confirm_kb,
    driver_card_kb,
    driver_edit_kb,
    drivers_list_kb,
)
from autopark_bot.routers.owner.common import TEXT_INPUT, format_rate, show
from autopark_bot.routers.owner.invites import build_invite_link
from autopark_bot.services.common import NotFound, ServiceError
from autopark_bot.services.drivers import (
    ADD_DRIVER_STEPS,
    DRIVER_FIELDS,
    archive_driver,
    create_driver,
    get_driver,
    list_drivers,
    parse_driver_field,
    update_driver_field,
)
from autopark_bot.services.invites import create_invitation
from autopark_bot.services.rentals import get_active_rental_of_driver
from autopark_bot.utils.text import format_date

router = Router(name="owner-drivers")


class AddDriver(StatesGroup):
    waiting = State()  # номер вопроса лежит в данных FSM


class EditDriver(StatesGroup):
    waiting = State()


# ---------- отображение ----------


async def _card_view(
    session: AsyncSession, driver: Driver, *, page: int
) -> tuple[str, InlineKeyboardMarkup]:
    active = await get_active_rental_of_driver(session, driver.id)
    lines = [
        f"👤 <b>{html.escape(driver.full_name)}</b>",
        f"Телефон: {html.escape(driver.phone) if driver.phone else '—'}",
        "Вход в бот: " + ("✅ выполнен" if driver.user_id is not None else "⏳ ещё не входил"),
    ]
    if active is None:
        lines.append("Машина: нет")
    else:
        rental, vehicle = active
        lines.append(
            f"Машина: <b>{html.escape(vehicle.make)} {html.escape(vehicle.model)}"
            f" · {html.escape(vehicle.plate)}</b>"
            f"\nС {format_date(rental.starts_on)}, "
            f"{format_rate(rental.rate_amount, rental.rate_period)}"
        )
    kb = driver_card_kb(driver, page=page, on_rental=active is not None)
    return "\n".join(lines), kb


async def _list_view(session: AsyncSession, *, page: int) -> tuple[str, InlineKeyboardMarkup]:
    result = await list_drivers(session, page=page)
    text = f"<b>Водители</b>: {result.total}\n🔵 на машине · 🟢 свободен"
    if not result.items:
        text += "\n\nЗдесь пока пусто."
    return text, drivers_list_kb(result)


def _prompt(field_key: str) -> str:
    spec = DRIVER_FIELDS[field_key]
    tail = " «-» — оставить пустым." if spec.optional else ""
    return f"{spec.label} ({spec.hint}).{tail}\n/cancel — отмена"


# ---------- меню, списки, карточка ----------


@router.message(F.text == MENU_DRIVERS)
async def on_menu(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    text, kb = await _list_view(session, page=0)
    await message.answer(text, reply_markup=kb)


@router.callback_query(DriverCb.filter(F.action == "noop"))
async def on_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(DriverCb.filter(F.action == "list"))
async def on_list(callback: CallbackQuery, callback_data: DriverCb, session: AsyncSession) -> None:
    text, kb = await _list_view(session, page=callback_data.page)
    await show(callback, text, kb)


async def _show_card(
    callback: CallbackQuery, session: AsyncSession, *, driver_id: int, page: int
) -> None:
    try:
        driver = await get_driver(session, driver_id)
    except NotFound as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    text, kb = await _card_view(session, driver, page=page)
    await show(callback, text, kb)


@router.callback_query(DriverCb.filter(F.action == "card"))
async def on_card(callback: CallbackQuery, callback_data: DriverCb, session: AsyncSession) -> None:
    await _show_card(callback, session, driver_id=callback_data.id, page=callback_data.page)


# ---------- новая ссылка для входа ----------


@router.callback_query(DriverCb.filter(F.action == "invite"))
async def on_invite(
    callback: CallbackQuery,
    callback_data: DriverCb,
    session: AsyncSession,
    user: User,
    settings: Settings,
    bot: Bot,
) -> None:
    try:
        driver = await get_driver(session, callback_data.id)
        raw_token = await create_invitation(
            session,
            role=Role.DRIVER,
            created_by=user.id,
            ttl=timedelta(hours=settings.invite_ttl_hours),
            driver_id=driver.id,
        )
    except ServiceError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await session.commit()

    link = await build_invite_link(bot, raw_token)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"Ссылка для «{html.escape(driver.full_name)}», действует "
            f"{settings.invite_ttl_hours} ч, одноразовая:\n{link}"
        )


# ---------- архивация ----------


@router.callback_query(DriverCb.filter(F.action == "archive"))
async def on_archive_ask(callback: CallbackQuery, callback_data: DriverCb) -> None:
    await show(
        callback,
        "Убрать водителя в архив? Вход в бот для него будет закрыт, история сохранится.",
        driver_archive_confirm_kb(callback_data.id, page=callback_data.page),
    )


@router.callback_query(DriverCb.filter(F.action == "archive_ok"))
async def on_archive(
    callback: CallbackQuery, callback_data: DriverCb, session: AsyncSession, user: User
) -> None:
    try:
        await archive_driver(session, actor=user, driver_id=callback_data.id)
    except ServiceError as exc:
        await callback.answer(str(exc), show_alert=True)
        await _show_card(callback, session, driver_id=callback_data.id, page=callback_data.page)
        return
    await session.commit()
    text, kb = await _list_view(session, page=callback_data.page)
    await show(callback, text, kb)


# ---------- редактирование поля ----------


@router.callback_query(DriverCb.filter(F.action == "edit_menu"))
async def on_edit_menu(callback: CallbackQuery, callback_data: DriverCb) -> None:
    await show(
        callback, "Что изменить?", driver_edit_kb(callback_data.id, page=callback_data.page)
    )


@router.callback_query(DriverCb.filter(F.action == "edit"))
async def on_edit(
    callback: CallbackQuery, callback_data: DriverCb, state: FSMContext, session: AsyncSession
) -> None:
    if callback_data.field not in DRIVER_FIELDS:
        await callback.answer()
        return
    try:
        await get_driver(session, callback_data.id)
    except NotFound as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await state.set_state(EditDriver.waiting)
    await state.update_data(
        driver_id=callback_data.id, field=callback_data.field, page=callback_data.page
    )
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(f"Новое значение.\n{_prompt(callback_data.field)}")


@router.message(EditDriver.waiting, TEXT_INPUT)
async def on_edit_value(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    data = await state.get_data()
    try:
        value = parse_driver_field(data["field"], message.text or "")
    except ValueError as exc:
        await message.answer(f"{exc}\nПопробуйте ещё раз или /cancel.")
        return

    try:
        driver = await update_driver_field(
            session, actor=user, driver_id=data["driver_id"], field=data["field"], value=value
        )
    except ServiceError as exc:
        await state.clear()
        await message.answer(str(exc))
        return

    await session.commit()
    await state.clear()
    text, kb = await _card_view(session, driver, page=data["page"])
    await message.answer("Сохранено ✅\n\n" + text, reply_markup=kb)


# ---------- добавление водителя (пошаговый ввод) ----------


@router.callback_query(DriverCb.filter(F.action == "add"))
async def on_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddDriver.waiting)
    await state.update_data(step=0, values={})
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(f"Добавляем водителя.\n\n{_prompt(ADD_DRIVER_STEPS[0])}")


@router.message(AddDriver.waiting, TEXT_INPUT)
async def on_add_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    settings: Settings,
    bot: Bot,
) -> None:
    raw = (message.text or "").strip()
    data = await state.get_data()
    step: int = data["step"]
    values: dict[str, str] = data["values"]
    key = ADD_DRIVER_STEPS[step]

    try:
        parse_driver_field(key, raw)
    except ValueError as exc:
        await message.answer(f"{exc}\nПопробуйте ещё раз или /cancel.")
        return

    values[key] = raw
    step += 1
    if step < len(ADD_DRIVER_STEPS):
        await state.update_data(step=step, values=values)
        await message.answer(_prompt(ADD_DRIVER_STEPS[step]))
        return

    # Карточка и приглашение создаются в одной транзакции: либо оба, либо ничего.
    try:
        driver = await create_driver(
            session,
            actor=user,
            values={k: parse_driver_field(k, v) for k, v in values.items()},
        )
        raw_token = await create_invitation(
            session,
            role=Role.DRIVER,
            created_by=user.id,
            ttl=timedelta(hours=settings.invite_ttl_hours),
            driver_id=driver.id,
        )
    except ServiceError as exc:
        await state.clear()
        await message.answer(str(exc))
        return

    await session.commit()
    await state.clear()
    text, kb = await _card_view(session, driver, page=0)
    await message.answer("Водитель добавлен ✅\n\n" + text, reply_markup=kb)
    link = await build_invite_link(bot, raw_token)
    await message.answer(
        f"Одноразовая ссылка для входа, действует {settings.invite_ttl_hours} ч.\n"
        f"Отправьте её водителю:\n{link}"
    )


@router.message(StateFilter(AddDriver, EditDriver))
async def on_unexpected(message: Message) -> None:
    await message.answer("Жду текстовый ответ. /cancel — отмена.")
