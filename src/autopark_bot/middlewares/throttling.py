import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from cachetools import TTLCache

logger = structlog.get_logger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """Не чаще одного нажатия/текстового сообщения в `rate` секунд на пользователя.

    Фото, документы и альбомы НЕ троттлятся: пользователь легально присылает
    несколько фото подряд (чек, одометр, повреждения), и их нельзя терять.
    """

    def __init__(self, rate: float = 0.5) -> None:
        self._rate = rate
        self._last: TTLCache = TTLCache(maxsize=10_000, ttl=60)

    @staticmethod
    def _is_throttled_kind(event: TelegramObject) -> bool:
        if isinstance(event, CallbackQuery):
            return True
        if isinstance(event, Message):
            return event.media_group_id is None and event.text is not None
        return False

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None or not self._is_throttled_kind(event):
            return await handler(event, data)

        now = time.monotonic()
        last = self._last.get(user.id)
        if last is not None and now - last < self._rate:
            logger.info("throttling.dropped", user_id=user.id)
            if isinstance(event, CallbackQuery):
                await event.answer("Не так быстро")
            return None

        self._last[user.id] = now
        return await handler(event, data)
