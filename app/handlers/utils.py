import logging
from typing import Any

from app.db import SignalCRUD, LocalAsyncSession, UserCRUD, StrategyCRUD, CryptoCRUD
from app.config import (
    get_settings, 
    SIGNAL_THRESHOLD, 
    STOP_LOSS_MULTIPLIER, 
    TAKE_PROFIT_MULTIPLIERS
)
from app.strategies import SignalAggregator, AggregatedSignal
from app.services.strategy_registry import (
    get_strategy_class, 
    get_active_strategy_classes,
    get_all_strategy_classes
)


settings = get_settings()


async def analyze_symbol_ensemble(
    symbol: str, 
    klines: list[Any], 
    telegram_id: int = settings.ADMIN_ID, 
    add_to_db: bool = False,
    timeframe: str = '1h',
    threshold: float = SIGNAL_THRESHOLD
) -> tuple[str, AggregatedSignal]:
    """
    Ensemble tizimi - barcha faol strategiyalarni birlashtiradi va 
    weighted confidence asosida signal qaytaradi.
    """
    # DB dan faol strategiyalarni olish
    strategy_classes = await get_active_strategy_classes()
    
    if not strategy_classes:
        # Fallback - agar DB da strategiyalar bo'lmasa, barcha klasslarni ishlatish
        strategy_classes = get_all_strategy_classes()
    
    # SignalAggregator yaratish
    aggregator = SignalAggregator(
        data=klines,
        symbol=symbol,
        strategies=strategy_classes,
        threshold=threshold,
        stop_multiplier=STOP_LOSS_MULTIPLIER,
        tp_multipliers=TAKE_PROFIT_MULTIPLIERS
    )
    
    # Signalni olish
    signal = aggregator.run()
    total_strategies = len(signal.strategy_results)
    
    # Xabar matnini yaratish
    emoji_map = {"LONG": "🟢", "SHORT": "🔴", "NEUTRAL": "⚪"}
    result_text = f"📊 <b>{symbol}</b> | <code>{timeframe}</code>\n\n"
    result_text += f"<b>Signal:</b> <code>{signal.direction}</code> {emoji_map[signal.direction]}\n"
    result_text += f"<b>Consensus Score:</b> <code>{signal.confidence:.1f}%</code>\n"
    result_text += f"<b>Threshold:</b> <code>{threshold}%</code>\n\n"
    
    if signal.direction != "NEUTRAL":
        result_text += f"<b>Entry:</b> <code>{signal.entry_price:.8g}</code>\n"
        if signal.stop_loss:
            result_text += f"<b>Stop Loss:</b> <code>{signal.stop_loss:.8g}</code>\n"
        if signal.take_profit_1:
            result_text += f"<b>TP1:</b> <code>{signal.take_profit_1:.8g}</code>\n"
        if signal.take_profit_2:
            result_text += f"<b>TP2:</b> <code>{signal.take_profit_2:.8g}</code>\n"
        if signal.take_profit_3:
            result_text += f"<b>TP3:</b> <code>{signal.take_profit_3:.8g}</code>\n"
        result_text += "\n"
    
    # Strategiya ovozlari (consensus score bilan)
    result_text += f"📈 Long: <code>{signal.long_votes}/{total_strategies}</code> (score: {signal.weighted_long_confidence:.1f}%)\n"
    result_text += f"📉 Short: <code>{signal.short_votes}/{total_strategies}</code> (score: {signal.weighted_short_confidence:.1f}%)\n"
    result_text += f"➖ Neutral: <code>{signal.neutral_votes}</code>\n\n"
    
    # Strategiya detallari
    result_text += "🔹 <b>Strategy Details:</b>\n"
    for result in signal.strategy_results:
        dir_emoji = emoji_map.get(result.direction, "⚪")
        result_text += f"• {result.name}: <code>{result.direction}</code> {dir_emoji} ({result.confidence:.1f}%)\n"
    
    # Bazaga saqlash
    if add_to_db and signal.direction != "NEUTRAL":
        try:
            async with LocalAsyncSession() as session:
                signal_crud = SignalCRUD(session)
                user_crud = UserCRUD(session)
                crypto_crud = CryptoCRUD(session)
                strategy_crud = StrategyCRUD(session)
                
                user_db = await user_crud.get(telegram_id)
                crypto_db = await crypto_crud.get_by_symbol(symbol)
                # Ensemble uchun birinchi strategiyani olaylik yoki maxsus 'ensemble' strategy
                strategy_db = await strategy_crud.get_by_code("ensemble")
                if strategy_db is None:
                    # Fallback to first matching strategy
                    for sr in signal.strategy_results:
                        if sr.direction == signal.direction:
                            strategy_db = await strategy_crud.get_by_code(sr.name.lower())
                            if strategy_db:
                                break
                
                if user_db is None:
                    logging.error(f"User not found: telegram_id={telegram_id}")
                elif crypto_db is None:
                    logging.error(f"Crypto not found: symbol={symbol}")
                elif strategy_db is None:
                    logging.error(f"No suitable strategy found for signal")
                else:
                    signal_data = {
                        "user_id": user_db.id,
                        "strategy_id": strategy_db.id,
                        "crypto_id": crypto_db.id,
                        "signal": signal.direction,
                        "timeframe": timeframe,
                        "stop_loss": signal.stop_loss,
                        "take_profit_1": signal.take_profit_1,
                        "take_profit_2": signal.take_profit_2,
                        "take_profit_3": signal.take_profit_3,
                        "entry_price": signal.entry_price,
                        "position_size": None,
                        "in_position": False,
                    }
                    await signal_crud.create(signal_data)
                    logging.info(f"Signal saved: {symbol} - {signal.direction}")
        except Exception as e:
            logging.error(f"Signal saqlashda xatolik: {e}")
    
    return result_text, signal


async def analyze_symbol(
    symbol: str, 
    klines: list[Any], 
    strategy_code: str | None = None, 
    telegram_id: int = settings.ADMIN_ID, 
    add_to_db: bool = False,
    timeframe: str = '1h'
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """
    Legacy funksiya - bitta yoki bir nechta strategiyalarni tekshiradi.
    Yangi loyihalar uchun analyze_symbol_ensemble() ni ishlating.
    """
    result_text = f"📊 <b>{symbol}</b>\n\n"
    last_data: dict[str, Any] = {}

    # --- DB dan strategiyalarni olish
    if strategy_code:
        strategy_class = get_strategy_class(strategy_code)
        if strategy_class is None:
            return f"❌ Strategiya topilmadi: {strategy_code}", {}, {}
        strategies = [strategy_class]
    else:
        strategies = get_all_strategy_classes()
    
    result_text += "🔹 <b>Strategies</b>\n" if len(strategies) > 1 else "🔹 <b>Strategy</b>\n"
    save_db: dict[str, Any] = {}
    
    for strategy_cls in strategies:
        try:
            strategy_instance = strategy_cls(klines, symbol)
            result = strategy_instance.run()
            # Yangi StrategyResult formatini dict ga aylantirish
            data = {
                'signal': result.direction,
                'other_data': result.indicators,
                'close': result.indicators.get('close'),
                'stop_loss': None,
                'take_profit_1': None,
                'take_profit_2': None,
                'take_profit_3': None,
            }
        except Exception as e:
            logging.error(f"{symbol} - {strategy_cls.__name__} - Xatolik: {e}")
            result_text += f"• {strategy_cls.__name__}: <code><b>ERROR</b> ⚠️</code>\n"
            continue
            
        for key, value in data['other_data'].items():
            last_data[key] = value

        logging.info(
            f"{symbol} - {strategy_instance.get_name()} - Tekshiruvdan o'tdi - {data['signal']}"
        )

        signal = data['signal']
        if signal != 'NEUTRAL':
            emoji = "🔴" if signal == "SHORT" else "🔵"
            result_text += f"• {strategy_instance.get_name()}: <code><b>{signal}</b> {emoji}</code>\n"
            result_text += f"\t\t• Confidence: <code>{result.confidence:.1f}%</code>\n\n"
            
            if add_to_db:
                save_db[strategy_instance.get_name()] = data
        else:
            result_text += f"• {strategy_instance.get_name()}: <code><b>{signal}</b> 📊</code>\n"

    # --- Indicators
    result_text += "\n🔹 <b>INDICATORS</b>\n"
    last_data.pop('stop_loss', None)
    last_data.pop('take_profit_1', None)
    last_data.pop('take_profit_2', None)
    last_data.pop('take_profit_3', None)

    for key, value in last_data.items():
        value = value if value is not None else "❌"
        if isinstance(value, (int, float)):
            display_value = round(value, 4)
        else:
            display_value = value
        result_text += f"• {key.upper()}: <code>{display_value}</code>\n"

    return result_text, last_data, save_db
