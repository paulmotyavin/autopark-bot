from aiogram import Router

from autopark_bot.enums import STAFF_ROLES
from autopark_bot.filters.role import RoleFilter
from autopark_bot.routers.owner import drivers, invites, vehicles

router = Router(name="owner")

# Роутер владельца и администратора. Фильтр на весь роутер: ни один хендлер внутри
# (и во вложенных роутерах) не сработает для водителя или незнакомца.
router.message.filter(RoleFilter(*STAFF_ROLES))
router.callback_query.filter(RoleFilter(*STAFF_ROLES))

router.include_routers(invites.router, drivers.router, vehicles.router)

# Сюда добавляются фичи по мере роста: rentals.py, payments.py, ...
# Принадлежность данных проверяйте в сервисах запросом (WHERE ... = :user_id),
# а не по значениям из callback_data.
