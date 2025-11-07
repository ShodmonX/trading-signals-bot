import logging

from ..config import SYMBOLS, ADMIN_ID
from ..services.api import get_klines
from ..strategies import TrendFollowStrategy, MACDCrossoverStrategy, BollingerBandSqueezeStrategy, StochasticOscillatorStrategy, SMACrossoverStrategy
from ..handlers.utils import analyze_symbol

STRATEGIES = [TrendFollowStrategy, MACDCrossoverStrategy, BollingerBandSqueezeStrategy, StochasticOscillatorStrategy, SMACrossoverStrategy]

async def check_signals(bot, interval='5m'):
    is_sended = False
    for symbol in SYMBOLS:
        try:
            klines, error = await get_klines(symbol, limit=999, interval=interval)
            if error:
                logging.error(f"{symbol} - olishda xatolik")
                continue

            text, data, save_db = await analyze_symbol(symbol, klines, add_to_db=True)
            if "SHORT" in text or "LONG" in text:
                if not is_sended:
                    await bot.send_message(ADMIN_ID, f"{interval} timeframe bo'yicha kripto valyutalarni tekshirish")
                    is_sended = True
                await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
                
        except Exception as e:
            logging.error(e)

    if is_sended:
        await bot.send_message(ADMIN_ID, "Kripto valyutalarni tekshirish tugadi.")