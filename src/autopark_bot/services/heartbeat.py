import aiohttp
import structlog
from aiogram import Bot
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger(__name__)


async def send_heartbeat(
    bot: Bot, sessionmaker: async_sessionmaker[AsyncSession], url: str
) -> None:
    """Пингует внешний монитор (healthchecks.io и т.п.), только если всё живо.

    Проверки: bot.get_me() идёт через прокси к Telegram, SELECT 1 — до БД. Если упадёт
    прокси или БД, пинг не уйдёт, и монитор пришлёт алерт на почту. Сам бот в этот момент
    в Telegram написать не сможет — поэтому нужен внешний канал.
    """
    try:
        await bot.get_me()
        async with sessionmaker() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        logger.warning("heartbeat.check_failed", exc_info=True)
        return

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.get(url) as response:
                response.raise_for_status()
    except Exception:
        logger.warning("heartbeat.ping_failed", exc_info=True)
