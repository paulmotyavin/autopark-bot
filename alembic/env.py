import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from autopark_bot.config import get_settings
from autopark_bot.db import models  # noqa: F401  (регистрирует таблицы в metadata)
from autopark_bot.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Один пользователь advisory-lock: две одновременные миграции не пересекутся.
ADVISORY_LOCK_KEY = 0x4155544F50524B  # "AUTOPRK"


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    settings = get_settings()
    connectable = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
        connect_args=settings.db_connect_args,
    )

    async with connectable.connect() as connection:
        await connection.execute(text("SELECT pg_advisory_lock(:k)"), {"k": ADVISORY_LOCK_KEY})
        try:
            await connection.run_sync(do_run_migrations)
            # pg_advisory_lock автоначал внешнюю транзакцию, а Alembic её не коммитит.
            await connection.commit()
        except Exception:
            await connection.rollback()
            raise
        finally:
            try:
                await connection.execute(
                    text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK_KEY}
                )
                await connection.commit()
            except Exception:
                # сессионный лок снимется при закрытии соединения
                pass

    await connectable.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline-режим не поддерживается: используйте онлайн-миграции")
else:
    asyncio.run(run_migrations_online())
