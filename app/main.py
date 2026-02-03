from aiogram import Bot, Dispatcher

import asyncio
import logging

from .config import get_settings
from .schedulers.schedulers import check_signals
from .schedulers.starter import start_scheduler, scheduler
from .handlers import router
from .services.api import BinanceAPI
from app.logger import configure_logs


settings = get_settings()
bot = Bot(token=settings.BOT_TOKEN)

async def on_startup():
    start_scheduler(bot, check_signals)
    logging.info("Scheduler ishga tushdi")
    await bot.send_message(settings.ADMIN_ID, "Bot muvaffaqiyatli ishga tushurildi.")

async def on_shutdown():
    await BinanceAPI.close_session()
    scheduler.shutdown()
    logging.info("Scheduler va API sessiyasi yopildi")
    await bot.send_message(settings.ADMIN_ID, "Bot ishdan to'xtadi.")

async def main():
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    configure_logs()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot ishdan to'xtadi!")
    except Exception as e:
        logging.exception(e)