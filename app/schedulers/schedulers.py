import logging

from app.config import get_settings, SIGNAL_THRESHOLD
from app.services.api import get_klines
from app.handlers.utils import analyze_symbol_ensemble


async def check_signals(bot, interval='5m'):
    """
    Ensemble tizimi bilan signallarni tekshirish.
    Barcha strategiyalar birlashtiriladi va threshold dan yuqori bo'lsa signal yuboriladi.
    """
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
            
            # Yangi ensemble tizimidan foydalanish
            text, signal = await analyze_symbol_ensemble(
                symbol=symbol, 
                klines=klines, 
                add_to_db=True, 
                timeframe=interval,
                threshold=SIGNAL_THRESHOLD
            )
            
            # Faqat LONG yoki SHORT signal bo'lganda xabar yuborish
            if signal.direction != "NEUTRAL":
                if not is_sended:
                    await bot.send_message(
                        settings.ADMIN_ID, 
                        f"🔔 <b>{interval}</b> timeframe signallari:\n"
                        f"Threshold: {SIGNAL_THRESHOLD}%",
                        parse_mode="HTML"
                    )
                    is_sended = True
                await bot.send_message(settings.ADMIN_ID, text, parse_mode="HTML")
                
        except Exception as e:
            logging.error(f"{symbol} - {interval}: {e}")

    if is_sended:
        await bot.send_message(settings.ADMIN_ID, "✅ Tekshirish tugadi.")