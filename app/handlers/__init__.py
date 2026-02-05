from aiogram import Router

from .handlers import router as handlers_router
from .settings import router as settings_router

router = Router()
router.include_routers(handlers_router, settings_router)

