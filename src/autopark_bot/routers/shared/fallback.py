from aiogram import Router
from aiogram.types import CallbackQuery, Message

from autopark_bot.filters.role import Anonymous
from autopark_bot.routers.shared.start import NO_ACCESS_TEXT

router = Router(name="fallback")


@router.message(Anonymous())
async def anonymous_message(message: Message) -> None:
    await message.answer(NO_ACCESS_TEXT)


@router.callback_query(Anonymous())
async def anonymous_callback(callback: CallbackQuery) -> None:
    await callback.answer("Нет доступа", show_alert=True)
