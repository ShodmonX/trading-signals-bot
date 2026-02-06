from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import logging

from app.db.session import get_session
from app.db.crud import StrategyCRUD


router = Router()


class StrategySettingsStates(StatesGroup):
    edit_weight = State()


async def build_strategy_settings_keyboard() -> InlineKeyboardMarkup:
    async with get_session() as session:
        crud = StrategyCRUD(session)
        strategies = await crud.get_all(only_active=False)

    buttons: list[list[InlineKeyboardButton]] = []

    for strategy in strategies:
        if strategy.code == "ensemble":
            continue
        status_emoji = "🟢" if strategy.is_active else "🔴"
        weight = strategy.performance_weight or 1.0
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_emoji} {strategy.name}",
                callback_data=f"stg_toggle:{strategy.code}"
            ),
            InlineKeyboardButton(
                text=f"⚖️ {weight:.2f}",
                callback_data=f"stg_weight:{strategy.code}"
            ),
        ])

    buttons.append([InlineKeyboardButton(text="🔄 Refresh", callback_data="stg_refresh")])
    buttons.append([InlineKeyboardButton(text="❌ Close", callback_data="stg_close")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command(commands=["strategies"]))
@router.message(F.text == "🧩 Strategies")
async def show_strategy_settings(message: Message, state: FSMContext):
    await state.clear()
    keyboard = await build_strategy_settings_keyboard()
    await message.answer(
        "🧩 <b>Strategiyalar sozlamalari</b>\n\n"
        "• Tugma bosib yoqish/o'chirish\n"
        "• ⚖️ tugmasi orqali performance weight ni tahrirlash",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "stg_refresh")
async def refresh_strategy_settings(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        keyboard = await build_strategy_settings_keyboard()
        await callback.message.edit_reply_markup(reply_markup=keyboard)


@router.callback_query(F.data == "stg_close")
async def close_strategy_settings(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.edit_text("❌ Yopildi.")


@router.callback_query(F.data.startswith("stg_toggle:"))
async def toggle_strategy(callback: CallbackQuery):
    code = callback.data.split(":")[1] if callback.data else ""
    if not code:
        await callback.answer("❌ Noto'g'ri strategiya kodi", show_alert=True)
        return

    try:
        async with get_session() as session:
            crud = StrategyCRUD(session)
            strategy = await crud.get_by_code(code)
            if not strategy:
                await callback.answer("❌ Strategiya topilmadi", show_alert=True)
                return
            await crud.update_status(code, not strategy.is_active)
    except Exception as e:
        logging.error(f"Strategy toggle error: {e}")
        await callback.answer("⚠️ Xatolik yuz berdi", show_alert=True)
        return

    await callback.answer("✅ Yangilandi")
    if callback.message:
        keyboard = await build_strategy_settings_keyboard()
        await callback.message.edit_reply_markup(reply_markup=keyboard)


@router.callback_query(F.data.startswith("stg_weight:"))
async def edit_strategy_weight(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1] if callback.data else ""
    if not code:
        await callback.answer("❌ Noto'g'ri strategiya kodi", show_alert=True)
        return

    await state.set_state(StrategySettingsStates.edit_weight)
    await state.update_data(strategy_code=code)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "⚖️ Yangi performance weight qiymatini kiriting.\n"
            "Masalan: <code>1.0</code> (range: 0.1 - 5.0)\n"
            "Bekor qilish uchun /cancel yuboring.",
            parse_mode="HTML"
        )


@router.message(StrategySettingsStates.edit_weight, Command(commands=["cancel"]))
async def cancel_edit_weight(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor qilindi.")


@router.message(StrategySettingsStates.edit_weight)
async def save_strategy_weight(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    try:
        weight = float(text)
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Raqam kiriting. Masalan: 1.0")
        return

    if weight < 0.1 or weight > 5.0:
        await message.answer("❌ Weight 0.1 dan 5.0 gacha bo'lishi kerak.")
        return

    data = await state.get_data()
    code = data.get("strategy_code")
    if not code:
        await state.clear()
        await message.answer("❌ Strategiya topilmadi.")
        return

    try:
        async with get_session() as session:
            crud = StrategyCRUD(session)
            strategy = await crud.update_performance_weight(code, weight)
            if not strategy:
                await message.answer("❌ Strategiya topilmadi.")
                await state.clear()
                return
    except Exception as e:
        logging.error(f"Strategy weight update error: {e}")
        await message.answer("⚠️ Xatolik yuz berdi. Qayta urinib ko'ring.")
        return

    await state.clear()
    keyboard = await build_strategy_settings_keyboard()
    await message.answer(
        f"✅ <b>{strategy.name}</b> weight yangilandi: <code>{weight:.2f}</code>",
        parse_mode="HTML",
        reply_markup=keyboard
    )
