from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from autopark_bot.db.models import AuditLog


async def audit(
    session: AsyncSession,
    *,
    actor_user_id: int | None,
    action: str,
    entity: str | None = None,
    entity_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Пишет запись в audit_log в рамках текущей транзакции (коммитит DbSession)."""
    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            details=details,
        )
    )
