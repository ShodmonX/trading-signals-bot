from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, or_f

import logging

from app.services.api import get_klines
from app.config import get_settings
from app.keyboards.db import get_add_db_buttons
from .utils import analyze_symbol


settings = get_settings()
router = Router()


@router.callback_query(F.data.startswith("strategy"))
async def strategy_check(callback: CallbackQuery):
    if callback.data:
        strategy = callback.data.split(":")[1]
    else:
        strategy = list(settings.strategies.keys())[0]
    await callback.answer()
    for symbol in settings.symbols:
        try:
            klines, error = await get_klines(symbol, limit=999)
            if error:
                logging.error(f"{symbol} - olishda xatolik")
                continue
            if not klines:
                logging.error("Klines didn't get by API")
                return
            text, data, save_db = await analyze_symbol(symbol, klines, strategy)
            if callback.message:
                await callback.message.answer(text, parse_mode="HTML")
        except Exception as e:
            logging.error(e)
  
@router.message(Command(commands=['check']))
async def checking_coins(message: Message):
    await message.answer("1h timeframe bo'yicha kripto valyutalarni tekshirish")
    for symbol in settings.symbols:
        try:
            klines, error = await get_klines(symbol, limit=999)
            if error:
                logging.error(f"{symbol} - olishda xatolik")
                await message.answer(f"{symbol} - olishda xatolik")
                continue
            if not klines:
                logging.error("Klines didn't get by API")
                return
            text, data, save_db = await analyze_symbol(symbol, klines)
            await message.answer(text, parse_mode="HTML", reply_markup=get_add_db_buttons(save_db, symbol))

        except Exception as e:
            logging.error(e)

@router.message(Command(commands=['check_5m']))
async def checking_coins_5m(message: Message):
    await message.answer("5m timeframe bo'yicha kripto valyutalarni tekshirish")
    for symbol in settings.symbols:
        try:
            klines, error = await get_klines(symbol, limit=999, interval='5m')
            if error:
                logging.error(f"{symbol} - olishda xatolik")
                await message.answer(f"{symbol} - olishda xatolik")
                continue
            if not klines:
                logging.error("Klines didn't get by API")
                return
            text, data, save_db = await analyze_symbol(symbol, klines)
            await message.answer(text, parse_mode="HTML", reply_markup=get_add_db_buttons(save_db, symbol))

        except Exception as e:
            logging.error(e)

