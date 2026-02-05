"""
DEPRECATED: Bu fayl endi ishlatilmaydi.
Dinamik keyboard uchun app.services.strategy_registry.build_strategies_keyboard() dan foydalaning.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Legacy static keyboard - faqat fallback uchun
strategies = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='Trend Follow Strategy', callback_data='strategy:trendfollowstrategy')
    ],
    [
        InlineKeyboardButton(text='MACD Crossover Strategy', callback_data='strategy:macdcrossoverstrategy')
    ],
    [
        InlineKeyboardButton(text='Bollinger Band Squeeze Strategy', callback_data='strategy:bollingerbandsqueezestrategy')
    ],
    [
        InlineKeyboardButton(text='Stochastic Oscillator Strategy', callback_data='strategy:stochasticoscillatorstrategy')
    ],
    [
        InlineKeyboardButton(text='SMA Crossover Strategy', callback_data='strategy:smacrossoverstrategy')
    ],
    [
        InlineKeyboardButton(text='Williams Fractals Strategy', callback_data='strategy:williamsfractalsstrategy')
    ]
])