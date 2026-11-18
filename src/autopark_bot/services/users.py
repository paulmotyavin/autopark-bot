from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from autopark_bot.db.models import User
from autopark_bot.enums import STAFF_ROLES, Role


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def ensure_owner(
    session: AsyncSession, telegram_id: int, full_name: str = "Владелец"
) -> None:
    """Гарантирует, что OWNER_TG_ID из окружения — активный владелец.

    Переменная окружения — корень доверия: если запись есть, роль и активность
    принудительно восстанавливаются.
    """
    stmt = pg_insert(User).values(
        telegram_id=telegram_id,
        role=Role.OWNER.value,
        full_name=full_name,
        is_active=True,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[User.telegram_id],
        set_={"role": Role.OWNER.value, "is_active": True},
    )
    await session.execute(stmt)


def require_staff(actor: User) -> None:
    """Страховка внутри сервиса: изменять данные парка может только персонал.

    Роутер уже фильтрует по роли, но сервис не должен полагаться на то, что его вызвали
    из «правильного» места: ошибка в роутинге не должна открывать запись водителю.
    """
    if not actor.is_active or Role(actor.role) not in STAFF_ROLES:
        raise PermissionError("Недостаточно прав")
