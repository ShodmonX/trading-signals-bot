import logging
from app.db import SignalCRUD, LocalAsyncSession, UserCRUD, StrategyCRUD, CryptoCRUD

from app.config import get_settings


settings = get_settings()

async def analyze_symbol(symbol: str, klines: list, strategy: str | None = None, telegram_id: int = settings.ADMIN_ID, add_to_db: bool = False) -> tuple[str, dict, dict]:
    """
    Bitta coin uchun strategiyalarni tekshiradi va xabar formatini qaytaradi
    """
    result_text = f"📊 <b>{symbol}</b>\n\n"
    last_data = {}

    # --- Strategies
    strategies = [settings.strategies[strategy], ] if strategy else settings.strategies.values()
    result_text += "🔹 <b>Strategies</b>\n" if len(strategies) > 1 else "🔹 <b>Strategy</b>\n"
    save_db = {}
    for strategy_ in strategies:
        strategy_instance = strategy_(klines, symbol)
        data = strategy_instance.run()
        for key, value in data['other_data'].items():
            last_data[key] = value  # oxirgi strategy'dan indikatorlar olinadi

        logging.info(
            f"{symbol} - {strategy_instance.get_name()} - Tekshiruvdan o'tdi - {data['signal']}"
        )

        signal = data['signal']
        if signal != 'NEUTRAL':
            emoji = "🔴" if signal == "SHORT" else "🔵"
            result_text += f"• {strategy_instance.get_name()}: <code><b>{signal}</b> {emoji}</code>\n"
            result_text += f"\t\t• SL: <code>{round(data['stop_loss'], 4)}</code>\n"
            result_text += f"\t\t• TP 1: <code>{round(data['take_profit_1'], 4)}</code>\n"
            result_text += f"\t\t• TP 2: <code>{round(data['take_profit_2'], 4)}</code>\n"
            result_text += f"\t\t• TP 3: <code>{round(data['take_profit_3'], 4)}</code>\n\n"
            if add_to_db:
                save_db[strategy_instance.get_name()] = data
                async with LocalAsyncSession() as session:
                    signal_crud = SignalCRUD(session)
                    user_crud = UserCRUD(session)
                    strategy_crud = StrategyCRUD(session)
                    crypto_crud = CryptoCRUD(session)
                    user_db = await user_crud.get(telegram_id)
                    strategy_db = await strategy_crud.get_by_code(strategy_instance.get_name().lower())
                    crypto_db = await crypto_crud.get_by_symbol(symbol)
                    signal_data = {
                        "user_id": user_db.id,
                        "strategy_id": strategy_db.id,
                        "crypto_id": crypto_db.id,
                        "signal": signal,
                        "stop_loss": data['stop_loss'],
                        "take_profit_1": data['take_profit_1'],
                        "take_profit_2": data['take_profit_2'],
                        "take_profit_3": data['take_profit_3'],
                        "entry_price": data['close'],
                        "position_size": None,
                        "in_position": False,
                    }
                    await signal_crud.create(signal_data)
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
