from aiogram import Bot, Dispatcher

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import BOT_TOKEN, ADMIN_ID
from .schedulers.schedulers import check_signals
from .schedulers.starter import start_scheduler
from .handlers import router


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

async def on_startup():
    start_scheduler(bot, check_signals)
    await bot.send_message(ADMIN_ID, "Bot muvaffaqiyatli ishga tushurildi.")

async def on_shutdown():
    await bot.send_message(ADMIN_ID, "Bot ishdan to'xtadi.")

async def main():
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()