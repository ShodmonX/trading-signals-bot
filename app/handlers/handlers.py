from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

import logging

from app.services.api import get_klines
from app.config import get_settings
from .utils import analyze_symbol_ensemble


settings = get_settings()
router = Router()

# Timeframe keyboard
TIMEFRAMES = ['5m', '15m', '30m', '1h', '4h']

def get_timeframe_keyboard() -> ReplyKeyboardMarkup:
    """Timeframe tanlash uchun reply keyboard"""
    buttons = [
        [KeyboardButton(text=tf) for tf in TIMEFRAMES],
        [KeyboardButton(text="📊 Backtest")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


@router.message(Command(commands=['menu', 'start']))
async def start_command(message: Message):
    """Timeframe tanlash menyusi"""
    await message.answer(
        "⏱ Qaysi timeframe bo'yicha kripto valyutalarni tekshirmoqchisiz?\n\n"
        "Tanlangan timeframe bo'yicha barcha strategiyalar birlashtiriladi va consensus signal ko'rsatiladi.",
        reply_markup=get_timeframe_keyboard()
    )


@router.message(F.text.in_(TIMEFRAMES))
async def timeframe_check(message: Message):
    """Tanlangan timeframe bo'yicha ensemble tekshiruv"""
    timeframe = message.text
    if not timeframe:
        return
    
    await message.answer(f"🔄 <b>{timeframe.upper()}</b> timeframe bo'yicha tekshirilmoqda...", parse_mode="HTML")
    
    signals_found = False
    
    for symbol in settings.symbols:
        try:
            klines, error = await get_klines(symbol, limit=999, interval=timeframe)
            if error:
                logging.error(f"{symbol} - olishda xatolik")
                continue
            if klines is None:
                logging.error("Klines didn't get by API")
                continue
            
            text, signal = await analyze_symbol_ensemble(symbol, klines, timeframe=timeframe)
            await message.answer(text, parse_mode="HTML")
            signals_found = True
                
        except Exception as e:
            logging.error(f"Timeframe check error: {e}")
    
    if signals_found:
        await message.answer(f"✅ <b>{timeframe.upper()}</b> tekshiruv tugadi.", parse_mode="HTML")


@router.message(Command(commands=['check']))
async def checking_coins(message: Message):
    """1h timeframe bo'yicha tezkor tekshirish"""
    await message.answer("🔄 <b>1H</b> timeframe bo'yicha tekshirilmoqda...", parse_mode="HTML")
    
    for symbol in settings.symbols:
        try:
            klines, error = await get_klines(symbol, limit=999, interval='1h')
            if error:
                logging.error(f"{symbol} - olishda xatolik")
                await message.answer(f"{symbol} - olishda xatolik")
                continue
            if klines is None:
                logging.error("Klines didn't get by API")
                return 

            text, signal = await analyze_symbol_ensemble(symbol, klines, timeframe='1h')
            await message.answer(text, parse_mode="HTML")

        except Exception as e:
            logging.error(e)
    
    await message.answer("✅ Tekshiruv tugadi.")


@router.message(Command(commands=['signals']))
async def signals_only(message: Message):
    """Faqat signal bo'lgan coinlarni ko'rsatish (1h)"""
    await message.answer("🔄 Faqat signallar tekshirilmoqda...", parse_mode="HTML")
    
    found = False
    for symbol in settings.symbols:
        try:
            klines, error = await get_klines(symbol, limit=999, interval='1h')
            if error or klines is None:
                continue

            text, signal = await analyze_symbol_ensemble(symbol, klines, timeframe='1h')
            
            # Faqat LONG yoki SHORT signallarni ko'rsatish
            if signal.direction != "NEUTRAL":
                await message.answer(text, parse_mode="HTML")
                found = True

        except Exception as e:
            logging.error(f"Signals check error: {e}")
    
    if not found:
        await message.answer("📊 Hozircha signal yo'q.")
    else:
        await message.answer("✅ Signal tekshiruvi tugadi.")

