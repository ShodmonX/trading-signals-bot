from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from app.keyboards.strategies import strategies
from app.middlewares.start import StartMiddleware


router = Router()

router.message.middleware.register(StartMiddleware())

@router.message(Command(commands=['menu', 'start']))
async def start_command(message: Message):
    await message.answer("Quyidagi Strategiyalar orqali Kripto valyutalarni tekshirishingiz mumkin!", reply_markup=strategies)
