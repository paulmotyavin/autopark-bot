from datetime import timedelta

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from autopark_bot.config import Settings
from autopark_bot.db.models import User
from autopark_bot.enums import Role
from autopark_bot.services.invites import create_invitation

router = Router(name="owner-invites")

USAGE = (
    "Использование: /invite admin\n"
    "Для водителя используйте /adddriver Фамилия Имя | телефон"
)


async def build_invite_link(bot: Bot, raw_token: str) -> str:
    me = await bot.me()  # aiogram кеширует результат
    return f"https://t.me/{me.username}?start={raw_token}"


@router.message(Command("invite"))
async def cmd_invite(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    user: User,
    settings: Settings,
    bot: Bot,
) -> None:
    arg = (command.args or "").strip().lower()
    if arg != Role.ADMIN.value:
        await message.answer(USAGE)
        return
    if user.role != Role.OWNER.value:
        await message.answer("Приглашать администраторов может только владелец.")
        return

    ttl = timedelta(hours=settings.invite_ttl_hours)
    raw_token = await create_invitation(session, role=Role.ADMIN, created_by=user.id, ttl=ttl)
    # Ссылка должна работать к моменту, когда её увидит человек: коммитим до ответа.
    await session.commit()

    link = await build_invite_link(bot, raw_token)
    await message.answer(
        f"Одноразовая ссылка для администратора, действует {settings.invite_ttl_hours} ч:\n{link}"
    )
