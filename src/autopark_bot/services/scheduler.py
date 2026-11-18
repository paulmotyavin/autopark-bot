import structlog
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from autopark_bot.config import Settings
from autopark_bot.services.heartbeat import send_heartbeat

logger = structlog.get_logger(__name__)


def create_scheduler(
    settings: Settings, bot: Bot, sessionmaker: async_sessionmaker[AsyncSession]
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(
        timezone=settings.timezone,
        job_defaults={
            "coalesce": True,  # пропущенные запуски схлопываются в один
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
    )

    if settings.healthcheck_url:
        scheduler.add_job(
            send_heartbeat,
            IntervalTrigger(minutes=settings.healthcheck_interval_minutes),
            kwargs={"bot": bot, "sessionmaker": sessionmaker, "url": settings.healthcheck_url},
            id="heartbeat",
            replace_existing=True,
        )
    else:
        logger.warning("scheduler.heartbeat_disabled", hint="HEALTHCHECK_URL не задан")

    # Доменные джобы (ежедневно ~10:00 MSK): начисления, напоминания об оплате, дайджест
    # просрочек, ТО, документы; еженедельно — запрос пробега. Каждая джоба пишет в
    # notification_log с dedup_key, чтобы рестарт не приводил к повторной рассылке.
    return scheduler
