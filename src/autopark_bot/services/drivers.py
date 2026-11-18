from sqlalchemy.ext.asyncio import AsyncSession

from autopark_bot.db.models import Driver, User
from autopark_bot.services.audit import audit


async def create_driver(
    session: AsyncSession, *, actor: User, full_name: str, phone: str | None
) -> Driver:
    """Создаёт карточку водителя (без входа в бот: user_id заполнится по приглашению)."""
    driver = Driver(full_name=full_name, phone=phone)
    session.add(driver)
    await session.flush()  # получаем driver.id
    # Персональные данные (ФИО, телефон) в журнал не пишем: достаточно id.
    await audit(
        session,
        actor_user_id=actor.id,
        action="driver.create",
        entity="driver",
        entity_id=driver.id,
    )
    return driver
