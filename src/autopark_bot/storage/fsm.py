from datetime import timedelta

from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage

from autopark_bot.config import Settings


def create_fsm_storage(settings: Settings) -> RedisStorage:
    ttl = timedelta(hours=settings.fsm_ttl_hours)
    return RedisStorage.from_url(
        settings.redis_url,
        key_builder=DefaultKeyBuilder(prefix="autopark:fsm", with_bot_id=True),
        # Брошенный сценарий (например, отправка чека) не должен держать пользователя
        # в состоянии бесконечно.
        state_ttl=ttl,
        data_ttl=ttl,
        connection_kwargs={
            "max_connections": 20,
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
            "health_check_interval": 30,
        },
    )
