from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def settings_btns(check_types: dict) -> InlineKeyboardMarkup:
    settings_btns = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text='5 Minute Check ' + ("🟢" if check_types['check_5m'] else "🔴"), callback_data='check_5m')
        ],
        [
            InlineKeyboardButton(text='15 Minute Check ' + ("🟢" if check_types['check_15m'] else "🔴"), callback_data='check_15m')
        ],
        [
            InlineKeyboardButton(text='30 Minute Check ' + ("🟢" if check_types['check_30m'] else "🔴"), callback_data='check_30m')
        ],
        [
            InlineKeyboardButton(text='1 Hour Check ' + ("🟢" if check_types['check_1h'] else "🔴"), callback_data='check_1h')
        ],
        [
            InlineKeyboardButton(text='4 Hour Check ' + ("🟢" if check_types['check_4h'] else "🔴"), callback_data='check_4h')
        ]
    ])
    return settings_btns