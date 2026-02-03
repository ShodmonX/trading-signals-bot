from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_add_db_buttons(data, symbol) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, value in data.items():
        builder.add(InlineKeyboardButton(text=key, callback_data=f"db:{symbol}"))
    return builder.as_markup(resize_keyboard=True)