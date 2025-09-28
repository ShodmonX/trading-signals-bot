from aiogram import Router

from .strategies import router as strategies_router
from .start import router as start_router

router = Router()
router.include_routers(strategies_router, start_router)

