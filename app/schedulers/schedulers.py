import logging

from app.config import get_settings
from app.services.api import get_klines
from app.strategies import TrendFollowStrategy, MACDCrossoverStrategy, BollingerBandSqueezeStrategy, StochasticOscillatorStrategy, SMACrossoverStrategy
from app.handlers.utils import analyze_symbol

STRATEGIES = [TrendFollowStrategy, MACDCrossoverStrategy, BollingerBandSqueezeStrategy, StochasticOscillatorStrategy, SMACrossoverStrategy]

async def check_signals(bot, interval='5m'):
    settings = get_settings()
    is_sended = False
    for symbol in settings.symbols:
        try:
            klines, error = await get_klines(symbol, limit=999, interval=interval)
            if error:
                logging.error(f"{symbol} - olishda xatolik")
                continue
            if not klines:
                logging.error("Klines didn't get by API")
                return
            text, data, save_db = await analyze_symbol(symbol, klines, add_to_db=True)
            if "SHORT" in text or "LONG" in text:
                if not is_sended:
                    await bot.send_message(settings.ADMIN_ID, f"{interval} timeframe bo'yicha kripto valyutalarni tekshirish")
                    is_sended = True
                await bot.send_message(settings.ADMIN_ID, text, parse_mode="HTML")
                
        except Exception as e:
            logging.error(e)

    if is_sended:
        await bot.send_message(settings.ADMIN_ID, "Kripto valyutalarni tekshirish tugadi.")