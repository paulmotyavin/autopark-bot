import asyncio
from collections.abc import Awaitable, Callable

import structlog
from sqlalchemy import text

from autopark_bot.app import create_bot, create_dispatcher
from autopark_bot.config import get_settings
from autopark_bot.db.session import build_engine, build_sessionmaker
from autopark_bot.logging_config import configure_logging
from autopark_bot.services.scheduler import create_scheduler
from autopark_bot.services.users import ensure_owner
from autopark_bot.storage.fsm import create_fsm_storage
from autopark_bot.storage.s3 import S3Storage


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    logger = structlog.get_logger("autopark_bot.main")

    engine = build_engine(settings)
    sessionmaker = build_sessionmaker(engine)
    storage = create_fsm_storage(settings)
    s3 = S3Storage(settings)
    bot = create_bot(settings)
    dp = create_dispatcher(settings=settings, storage=storage, sessionmaker=sessionmaker, s3=s3)
    scheduler = create_scheduler(settings, bot, sessionmaker)

    cleanups: list[tuple[str, Callable[[], Awaitable[object]]]] = []
    try:
        # --- preflight: падаем сразу, если БД или Redis недоступны ---
        async with sessionmaker() as session, session.begin():
            await session.execute(text("SELECT 1"))
            await ensure_owner(session, settings.owner_tg_id)
        await storage.redis.ping()
        logger.info("preflight.ok", owner_tg_id=settings.owner_tg_id)

        # S3 не критичен для старта: бот должен подняться, даже если хранилище моргнуло.
        await s3.check()

        scheduler.start()

        async def stop_scheduler() -> None:
            scheduler.shutdown(wait=False)

        cleanups.append(("scheduler.shutdown", stop_scheduler))

        logger.info("bot.starting")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception:
        logger.exception("bot.fatal_error")
        raise
    finally:
        cleanups.extend(
            [
                ("storage.close", storage.close),
                ("bot.session.close", bot.session.close),
                ("engine.dispose", engine.dispose),
            ]
        )
        for name, cleanup in cleanups:
            try:
                await cleanup()
            except Exception:
                logger.exception("main.cleanup_failed", cleanup=name)


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
