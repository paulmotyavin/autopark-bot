import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import ErrorEvent
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from autopark_bot.config import Settings
from autopark_bot.middlewares.auth import AuthMiddleware
from autopark_bot.middlewares.db_session import DbSessionMiddleware
from autopark_bot.middlewares.throttling import ThrottlingMiddleware
from autopark_bot.routers import router as main_router
from autopark_bot.storage.s3 import S3Storage

logger = structlog.get_logger(__name__)


def create_bot(settings: Settings) -> Bot:
    """Бот с исходящим прокси к Telegram (если задан TELEGRAM_PROXY).

    Прокси действует только на запросы к api.telegram.org: БД, Redis и S3 используют
    собственные соединения и через него не ходят.
    """
    proxy = settings.telegram_proxy.get_secret_value() if settings.telegram_proxy else None
    session = AiohttpSession(proxy=proxy) if proxy else AiohttpSession()
    logger.info("bot.session", proxy_enabled=proxy is not None)  # учётные данные не логируем
    return Bot(
        token=settings.bot_token.get_secret_value(),
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def on_error(event: ErrorEvent) -> None:
    update = event.update
    logger.error(
        "handler.failed",
        update_type=update.event_type,
        update_id=update.update_id,
        exc_info=event.exception,
    )
    try:
        if update.callback_query:
            await update.callback_query.answer("Произошла ошибка", show_alert=True)
        elif update.message:
            await update.message.answer("Произошла ошибка. Попробуйте ещё раз позже.")
    except Exception:
        logger.debug("handler.failed_notify_skipped")


def create_dispatcher(
    *,
    settings: Settings,
    storage: RedisStorage,
    sessionmaker: async_sessionmaker[AsyncSession],
    s3: S3Storage,
) -> Dispatcher:
    # settings и s3 попадают в workflow_data: хендлеры просят их по имени аргумента.
    dp = Dispatcher(storage=storage, settings=settings, s3=s3)

    throttling = ThrottlingMiddleware(rate=0.5)
    db_session = DbSessionMiddleware(sessionmaker)
    auth = AuthMiddleware()

    # Порядок = порядок регистрации: троттлинг -> сессия БД -> авторизация.
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(throttling)
        observer.outer_middleware(db_session)
        observer.outer_middleware(auth)

    dp.include_router(main_router)
    dp.errors.register(on_error)
    return dp
