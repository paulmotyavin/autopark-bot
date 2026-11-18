from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from autopark_bot.db.base import utcnow
from autopark_bot.services.users import get_by_telegram_id

logger = structlog.get_logger(__name__)

_SEEN_REFRESH = timedelta(seconds=60)


def _chat_type(event: TelegramObject) -> str | None:
    if isinstance(event, Message):
        return event.chat.type
    if isinstance(event, CallbackQuery) and event.message is not None:
        return event.message.chat.type
    return None


class AuthMiddleware(BaseMiddleware):
    """Определяет пользователя и кладёт в `data["user"]` (None — незнакомец).

    Роль и активность читаются из БД на КАЖДЫЙ апдейт (один SELECT по уникальному
    индексу), без кеша: отозванный доступ перестаёт работать мгновенно.
    Должен стоять после DbSessionMiddleware.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = getattr(event, "from_user", None)
        if tg_user is None or tg_user.is_bot:
            return None

        # Бот работает только в личных чатах: группы и каналы игнорируем.
        chat_type = _chat_type(event)
        if chat_type is not None and chat_type != "private":
            return None

        session: AsyncSession = data["session"]
        user = await get_by_telegram_id(session, tg_user.id)

        if user is not None and not user.is_active:
            logger.info("auth.inactive_dropped", telegram_id=tg_user.id)
            if isinstance(event, CallbackQuery):
                await event.answer()
            return None

        if user is not None:
            now = utcnow()
            if now - user.last_seen_at > _SEEN_REFRESH:
                user.last_seen_at = now
            if user.username != tg_user.username:
                user.username = tg_user.username
            structlog.contextvars.bind_contextvars(user_id=user.id, role=user.role)
        else:
            structlog.contextvars.bind_contextvars(telegram_id=tg_user.id)

        data["user"] = user
        return await handler(event, data)
