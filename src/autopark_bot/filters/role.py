from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from autopark_bot.db.models import User
from autopark_bot.enums import Role


class RoleFilter(BaseFilter):
    """Пропускает только активных пользователей с одной из перечисленных ролей.

    Пользователя кладёт в `data["user"]` AuthMiddleware. Вешается на весь роутер роли:
    `router.message.filter(RoleFilter(...))` — вложенные роутеры тоже защищены.
    """

    def __init__(self, *roles: Role) -> None:
        self._roles = frozenset(role.value for role in roles)

    async def __call__(self, event: TelegramObject, user: User | None = None) -> bool:
        return user is not None and user.is_active and user.role in self._roles


class Anonymous(BaseFilter):
    """Пользователя нет в БД (пришёл без приглашения)."""

    async def __call__(self, event: TelegramObject, user: User | None = None) -> bool:
        return user is None
