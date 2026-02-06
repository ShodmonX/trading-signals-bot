from aiogram import Router

from .handlers import router as handlers_router
from .settings import router as settings_router
from .backtest import router as backtest_router
from .strategy_settings import router as strategy_settings_router

router = Router()
router.include_routers(handlers_router, settings_router, backtest_router, strategy_settings_router)

