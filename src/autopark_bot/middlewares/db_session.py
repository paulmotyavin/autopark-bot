from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    """Одна сессия и одна транзакция на апдейт.

    Хендлер получает `session`. Коммит — после успешного хендлера, откат — при любой
    ошибке. Благодаря этому «подтвердить платёж + запись в аудит + смена статуса»
    либо применяются целиком, либо не применяются вовсе.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            async with self._sessionmaker() as session:
                data["session"] = session
                try:
                    result = await handler(event, data)
                    await session.commit()
                    return result
                except Exception:
                    await session.rollback()
                    raise
        finally:
            structlog.contextvars.clear_contextvars()
