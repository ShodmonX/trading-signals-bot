from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, or_f

import logging

from app.services.api import get_klines
from app.config import SYMBOLS
from app.keyboards.db import get_add_db_buttons
from .utils import analyze_symbol


router = Router()


@router.callback_query(F.data.startswith("strategy"))
async def strategy_check(callback: CallbackQuery):
    strategy = callback.data.split(":")[1]
    await callback.answer()
    for symbol in SYMBOLS:
        try:
            klines, error = await get_klines(symbol, limit=999)
            if error:
                logging.error(f"{symbol} - olishda xatolik")
                continue
            text, data, save_db = await analyze_symbol(symbol, klines, strategy)
            await callback.message.answer(text, parse_mode="HTML")
        except Exception as e:
            logging.error(e)
  
@router.message(Command(commands=['check']))
async def checking_coins(message: Message):
    for symbol in SYMBOLS:
        try:
            klines, error = await get_klines(symbol, limit=999)
            if error:
                logging.error(f"{symbol} - olishda xatolik")
                await message.answer(f"{symbol} - olishda xatolik")
                continue

            text, data, save_db = await analyze_symbol(symbol, klines)
            await message.answer(text, parse_mode="HTML", reply_markup=get_add_db_buttons(save_db, symbol))

        except Exception as e:
            logging.error(e)

