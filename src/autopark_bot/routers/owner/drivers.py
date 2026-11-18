import html
from datetime import timedelta

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from autopark_bot.config import Settings
from autopark_bot.db.models import User
from autopark_bot.enums import Role
from autopark_bot.routers.owner.invites import build_invite_link
from autopark_bot.services.drivers import create_driver
from autopark_bot.services.invites import create_invitation
from autopark_bot.utils.text import parse_name_and_phone

router = Router(name="owner-drivers")

USAGE = (
    "Использование: /adddriver Фамилия Имя | телефон\n"
    "Пример: /adddriver Иван Петров | +7 900 123-45-67\n"
    "Телефон необязателен."
)


# Временная команда: пока нет меню с кнопками и пошагового ввода (FSM), водитель
# добавляется одной строкой. Логика (сервисы) от этого не изменится.
@router.message(Command("adddriver"))
async def cmd_add_driver(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    user: User,
    settings: Settings,
    bot: Bot,
) -> None:
    parsed = parse_name_and_phone(command.args)
    if parsed is None:
        await message.answer(USAGE)
        return
    full_name, phone = parsed

    driver = await create_driver(session, actor=user, full_name=full_name, phone=phone)
    raw_token = await create_invitation(
        session,
        role=Role.DRIVER,
        created_by=user.id,
        ttl=timedelta(hours=settings.invite_ttl_hours),
        driver_id=driver.id,
    )
    await session.commit()

    link = await build_invite_link(bot, raw_token)
    await message.answer(
        f"Водитель «{html.escape(full_name)}» добавлен.\n"
        f"Одноразовая ссылка для входа, действует {settings.invite_ttl_hours} ч:\n{link}"
    )
