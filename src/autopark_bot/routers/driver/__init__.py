from aiogram import Router

from autopark_bot.enums import Role
from autopark_bot.filters.role import RoleFilter

router = Router(name="driver")

# Роутер водителя: хендлеры внутри доступны только активным водителям.
router.message.filter(RoleFilter(Role.DRIVER))
router.callback_query.filter(RoleFilter(Role.DRIVER))

# Сюда: payments.py (чек), odometer.py (пробег + фото), incidents.py (поломка).
# Водитель видит только свою аренду: фильтруйте по user.id в SQL, а не по callback_data.
