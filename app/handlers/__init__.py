from aiogram import Router

from .strategies import router as strategies_router
from .start import router as start_router
from .settings import router as settings_router

router = Router()
router.include_routers(strategies_router, start_router, settings_router)

