import hashlib
import re
import secrets
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from autopark_bot.db.base import utcnow
from autopark_bot.db.models import Driver, Invitation, User
from autopark_bot.enums import DriverStatus, Role
from autopark_bot.services.audit import audit

# payload deep-link в Telegram: до 64 символов [A-Za-z0-9_-]
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{20,64}")


class _InviteRejected(Exception):
    """Внутренний сигнал: откатить погашение приглашения (карточка недоступна)."""


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def create_invitation(
    session: AsyncSession,
    *,
    role: Role,
    created_by: int,
    ttl: timedelta,
    driver_id: int | None = None,
) -> str:
    """Создаёт приглашение и возвращает сырой токен (в БД остаётся только хеш).

    Для водителя обязателен driver_id (карточка, которую приглашение привяжет к аккаунту).
    """
    if role not in (Role.ADMIN, Role.DRIVER):
        raise ValueError("Приглашать можно только администратора или водителя")
    if (role is Role.DRIVER) != (driver_id is not None):
        raise ValueError("driver_id обязателен для водителя и запрещён для администратора")

    if driver_id is not None:
        free_card = await session.scalar(
            select(Driver.id).where(
                Driver.id == driver_id,
                Driver.status == DriverStatus.ACTIVE.value,
                Driver.user_id.is_(None),
            )
        )
        if free_card is None:
            raise ValueError("Карточка водителя не найдена, архивна или уже привязана")

    raw = secrets.token_urlsafe(24)  # 32 символа
    session.add(
        Invitation(
            token_hash=_hash(raw),
            role=role.value,
            driver_id=driver_id,
            created_by=created_by,
            expires_at=utcnow() + ttl,
        )
    )
    await audit(
        session,
        actor_user_id=created_by,
        action="invitation.create",
        entity="invitation",
        details={"role": role.value, "driver_id": driver_id},
    )
    return raw


async def redeem_invitation(
    session: AsyncSession,
    *,
    raw_token: str,
    telegram_id: int,
    full_name: str,
    username: str | None,
) -> User | None:
    """Атомарно «сжигает» приглашение, создаёт пользователя и (для водителя) привязывает карточку.

    None — токен не подошёл. Всё происходит в SAVEPOINT: если карточку привязать нельзя,
    погашение приглашения откатывается вместе со всем остальным.

    Условие `used_at IS NULL AND expires_at > now()` в одном UPDATE исключает гонку:
    две параллельные попытки не смогут использовать одну ссылку дважды.
    """
    if not _TOKEN_RE.fullmatch(raw_token):
        return None

    try:
        async with session.begin_nested():
            row = (
                await session.execute(
                    update(Invitation)
                    .where(
                        Invitation.token_hash == _hash(raw_token),
                        Invitation.used_at.is_(None),
                        Invitation.expires_at > func.now(),
                    )
                    .values(used_at=func.now())
                    .returning(Invitation.id, Invitation.role, Invitation.driver_id)
                )
            ).one_or_none()
            if row is None:
                return None

            driver: Driver | None = None
            if row.driver_id is not None:
                # FOR UPDATE: карточку не привяжут одновременно двумя разными аккаунтами.
                driver = await session.scalar(
                    select(Driver)
                    .where(
                        Driver.id == row.driver_id,
                        Driver.status == DriverStatus.ACTIVE.value,
                        Driver.user_id.is_(None),
                    )
                    .with_for_update()
                )
                if driver is None:
                    raise _InviteRejected

            user = User(
                telegram_id=telegram_id,
                role=row.role,
                # Для водителя берём имя из карточки (его ввёл владелец), а не из профиля Telegram.
                full_name=driver.full_name if driver is not None else full_name,
                username=username,
            )
            session.add(user)
            await session.flush()

            if driver is not None:
                driver.user_id = user.id

            await session.execute(
                update(Invitation).where(Invitation.id == row.id).values(used_by=user.id)
            )
            await audit(
                session,
                actor_user_id=user.id,
                action="invitation.redeem",
                entity="invitation",
                entity_id=row.id,
                details={"role": row.role, "driver_id": row.driver_id},
            )
    except _InviteRejected:
        return None
    return user
