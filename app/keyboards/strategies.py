from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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