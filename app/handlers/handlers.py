from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, or_f

import logging

from app.services.api import get_klines
from app.config import get_settings
from app.keyboards.strategies import strategies
from .utils import analyze_symbol


settings = get_settings()
router = Router()

@router.message(Command(commands=['menu', 'start']))
async def start_command(message: Message):
    await message.answer("Quyidagi Strategiyalar orqali Kripto valyutalarni tekshirishingiz mumkin!", reply_markup=strategies)

@router.callback_query(F.data.startswith("strategy"))
async def strategy_check(callback: CallbackQuery):
    if callback.data is None:
        await callback.answer()
        return
    strategy = callback.data.split(":")[1]
    await callback.answer()
    for symbol in settings.symbols:
        try:
            klines, error = await get_klines(symbol, limit=999)
            if error:
                logging.error(f"{symbol} - olishda xatolik")
                continue
            if klines is None:
                logging.error("Klines didn't get by API")
                return 
            text, data, save_db = await analyze_symbol(symbol, klines, strategy)
            if callback.message is not None:
                await callback.message.answer(text, parse_mode="HTML")
        except Exception as e:
            logging.error(e)

@router.message(Command(commands=['check']))
async def checking_coins(message: Message):
    for symbol in settings.symbols:
        try:
            klines, error = await get_klines(symbol, limit=999)
            if error:
                logging.error(f"{symbol} - olishda xatolik")
                await message.answer(f"{symbol} - olishda xatolik")
                continue
            if klines is None:
                logging.error("Klines didn't get by API")
                return 

            text, data, save_db = await analyze_symbol(symbol, klines)
            await message.answer(text, parse_mode="HTML")

        except Exception as e:
            logging.error(e)

