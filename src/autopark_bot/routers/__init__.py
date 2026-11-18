from aiogram import Router

from autopark_bot.routers.driver import router as driver_router
from autopark_bot.routers.owner import router as owner_router
from autopark_bot.routers.shared.fallback import router as fallback_router
from autopark_bot.routers.shared.start import router as start_router

router = Router(name="main")
# Порядок важен: /start для всех -> роли -> заглушка для незнакомцев (последней).
router.include_routers(start_router, owner_router, driver_router, fallback_router)
