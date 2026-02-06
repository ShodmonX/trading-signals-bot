"""Backtest handlers - FSM bilan backtest oqimi (Inline keyboard)"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

import logging
import json
from datetime import datetime

from app.config import get_settings
from app.services.backtester import Backtester, BacktestSummary
from app.services.pdf_report import generate_backtest_pdf, get_pdf_filename
from app.db.session import get_session
from app.db.crud import BacktestResultCRUD


settings = get_settings()
router = Router()


class BacktestStates(StatesGroup):
    """Backtest FSM states"""
    select_symbol = State()
    select_timeframe = State()
    enter_start_date = State()
    enter_end_date = State()
    enter_threshold = State()
    confirm = State()
    running = State()


# Inline Keyboards
def get_symbol_keyboard() -> InlineKeyboardMarkup:
    """Symbol tanlash uchun inline keyboard"""
    symbols = settings.symbols[:12]  # Max 12 ta
    buttons = []
    row = []
    for symbol in symbols:
        row.append(InlineKeyboardButton(text=symbol, callback_data=f"bt_symbol:{symbol}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bt_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_signal_timeframe_keyboard() -> InlineKeyboardMarkup:
    """Signal timeframe tanlash uchun inline keyboard"""
    buttons = [
        [
            InlineKeyboardButton(text="15m", callback_data="bt_tf:15m"),
            InlineKeyboardButton(text="30m", callback_data="bt_tf:30m"),
        ],
        [
            InlineKeyboardButton(text="1h", callback_data="bt_tf:1h"),
            InlineKeyboardButton(text="4h", callback_data="bt_tf:4h"),
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bt_cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Tasdiqlash uchun inline keyboard"""
    buttons = [
        [InlineKeyboardButton(text="✅ Boshlash", callback_data="bt_confirm:yes")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bt_cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Faqat bekor qilish tugmasi"""
    buttons = [
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bt_cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "📊 Backtest")
async def backtest_start(message: Message, state: FSMContext):
    """Backtest boshlash - symbol tanlash"""
    await state.clear()
    
    await message.answer(
        "🔬 <b>Backtesting</b>\n\n"
        "Qaysi kripto valyuta uchun backtest qilmoqchisiz?\n\n"
        "Backtest - bu tarixiy ma'lumotlar asosida strategiyalarni sinash.",
        parse_mode="HTML",
        reply_markup=get_symbol_keyboard()
    )
    await state.set_state(BacktestStates.select_symbol)


@router.callback_query(F.data == "bt_cancel")
async def backtest_cancel(callback: CallbackQuery, state: FSMContext):
    """Backtest bekor qilish"""
    await state.clear()
    await callback.message.edit_text("❌ Backtest bekor qilindi.")  # type: ignore
    await callback.answer()


@router.callback_query(F.data.startswith("bt_symbol:"))
async def backtest_select_symbol(callback: CallbackQuery, state: FSMContext):
    """Symbol tanlash"""
    symbol = callback.data.split(":")[1]  # type: ignore
    
    if symbol not in settings.symbols:
        await callback.answer("❌ Noto'g'ri symbol!", show_alert=True)
        return
    
    await state.update_data(symbol=symbol)
    
    await callback.message.edit_text(  # type: ignore
        f"✅ Symbol: <b>{symbol}</b>\n\n"
        "Endi signal timeframe ni tanlang:\n"
        "<i>(Execution timeframe avtomatik eng kichigi tanlanadi)</i>",
        parse_mode="HTML",
        reply_markup=get_signal_timeframe_keyboard()
    )
    await state.set_state(BacktestStates.select_timeframe)
    await callback.answer()


@router.callback_query(F.data.startswith("bt_tf:"))
async def backtest_select_timeframe(callback: CallbackQuery, state: FSMContext):
    """Timeframe tanlash"""
    timeframe = callback.data.split(":")[1]  # type: ignore
    
    valid_timeframes = ["15m", "30m", "1h", "4h"]
    if timeframe not in valid_timeframes:
        await callback.answer("❌ Noto'g'ri timeframe!", show_alert=True)
        return
    
    await state.update_data(timeframe=timeframe)
    
    await callback.message.edit_text(  # type: ignore
        f"✅ Signal TF: <b>{timeframe}</b>\n\n"
        "Endi boshlanish sanasini kiriting:\n"
        "Format: <code>DD.MM.YYYY</code>\n"
        "Masalan: <code>01.01.2026</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(BacktestStates.enter_start_date)
    await callback.answer()


@router.message(BacktestStates.enter_start_date)
async def backtest_enter_start_date(message: Message, state: FSMContext):
    """Boshlanish sanasini kiritish"""
    date_text = message.text
    if not date_text:
        await message.answer("❌ Sana kiriting.")
        return
    
    try:
        start_date = datetime.strptime(date_text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format. <code>DD.MM.YYYY</code> formatida kiriting.\n"
            "Masalan: <code>01.01.2026</code>",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Sanani tekshirish
    if start_date >= datetime.now():
        await message.answer(
            "❌ Boshlanish sanasi bugundan oldin bo'lishi kerak.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await state.update_data(start_date=start_date)
    
    await message.answer(
        f"✅ Boshlanish: <b>{start_date.strftime('%d.%m.%Y')}</b>\n\n"
        "Endi tugash sanasini kiriting:\n"
        "Format: <code>DD.MM.YYYY</code>\n"
        "Masalan: <code>01.02.2026</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(BacktestStates.enter_end_date)


@router.message(BacktestStates.enter_end_date)
async def backtest_enter_end_date(message: Message, state: FSMContext):
    """Tugash sanasini kiritish"""
    date_text = message.text
    if not date_text:
        await message.answer("❌ Sana kiriting.")
        return
    
    try:
        end_date = datetime.strptime(date_text.strip(), "%d.%m.%Y")
        # Kun oxirigacha olish uchun
        end_date = end_date.replace(hour=23, minute=59, second=59)
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format. <code>DD.MM.YYYY</code> formatida kiriting.\n"
            "Masalan: <code>01.02.2026</code>",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    data = await state.get_data()
    start_date: datetime = data.get("start_date")  # type: ignore
    
    if end_date <= start_date:
        await message.answer(
            "❌ Tugash sanasi boshlanish sanasidan keyin bo'lishi kerak.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Davr tekshirish - kamida 7 kun
    days_diff = (end_date - start_date).days
    if days_diff < 7:
        await message.answer(
            f"❌ Minimum davr 7 kun.\n"
            f"Siz {days_diff} kun tanladingiz.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await state.update_data(end_date=end_date)
    
    # Threshold so'rash
    await message.answer(
        f"✅ Tugash: <b>{end_date.strftime('%d.%m.%Y')}</b>\n\n"
        "Endi signal threshold ni kiriting (1-100):\n"
        "<i>Bu qiymat signal kuchini belgilaydi. Default: 60</i>\n\n"
        "Masalan: <code>60</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(BacktestStates.enter_threshold)


@router.message(BacktestStates.enter_threshold)
async def backtest_enter_threshold(message: Message, state: FSMContext):
    """Threshold qiymatini kiritish"""
    threshold_text = message.text
    if not threshold_text:
        await message.answer("❌ Threshold kiriting (1-100).")
        return
    
    try:
        threshold = int(threshold_text.strip())
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format. Faqat raqam kiriting (1-100).\n"
            "Masalan: <code>60</code>",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    if threshold < 1 or threshold > 100:
        await message.answer(
            "❌ Threshold 1 dan 100 gacha bo'lishi kerak.\n"
            "Masalan: <code>60</code>",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await state.update_data(threshold=float(threshold))
    
    data = await state.get_data()
    symbol = data.get("symbol")
    timeframe = data.get("timeframe", "1h")
    start_date: datetime = data.get("start_date")  # type: ignore
    end_date: datetime = data.get("end_date")  # type: ignore
    
    # Execution timeframe ni hisoblash
    if timeframe in ["1h", "4h"]:
        exec_tf = "5m"
    else:
        exec_tf = "1m"
    
    days_diff = (end_date - start_date).days
    
    # Mavjud natijani tekshirish
    user_id = message.from_user.id if hasattr(message, 'from_user') else message.from_user.id  # type: ignore
    
    async with get_session() as session:
        crud = BacktestResultCRUD(session)
        existing = await crud.find_existing(
            user_id=user_id,
            symbol=symbol,  # type: ignore
            timeframe=timeframe,  # type: ignore
            threshold=float(threshold),
            start_date=start_date.date(),
            end_date=end_date.date(),
        )
    
    if existing:
        # Mavjud natija topildi - uni ko'rsatish
        await state.update_data(existing_result_id=existing.id)
        
        # Win rate color
        if existing.win_rate >= 60:
            wr_emoji = "🟢"
        elif existing.win_rate >= 40:
            wr_emoji = "🟡"
        else:
            wr_emoji = "🔴"
        
        # Profit color
        if existing.total_profit > 0:
            profit_emoji = "📈"
            profit_sign = "+"
        else:
            profit_emoji = "📉"
            profit_sign = ""
        
        existing_text = (
            f"📦 <b>Mavjud natija topildi!</b>\n\n"
            f"📋 <b>Parametrlar:</b>\n"
            f"├ Symbol: <b>{symbol}</b>\n"
            f"├ Signal TF: <b>{timeframe}</b>\n"
            f"├ Threshold: <b>{threshold}%</b>\n"
            f"└ Davr: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
            f"📊 <b>Natijalar:</b>\n"
            f"├ Signallar: {existing.total_signals}\n"
            f"├ {wr_emoji} Win rate: <b>{existing.win_rate:.1f}%</b>\n"
            f"├ Wins/Losses: {existing.wins}/{existing.losses}\n"
            f"└ {profit_emoji} Profit: <b>{profit_sign}{existing.total_profit:.2f}%</b>\n\n"
            f"📅 Test vaqti: {existing.created_at.strftime('%d.%m.%Y %H:%M') if existing.created_at else '-'}\n\n"
            f"<i>Mavjud natijani ishlatishni yoki qayta test qilishni tanlang:</i>"
        )
        
        buttons = [
            [InlineKeyboardButton(text="📄 PDF yuklash", callback_data=f"bt_pdf:{existing.id}")],
            [InlineKeyboardButton(text="🔄 Qayta test qilish", callback_data="bt_rerun")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bt_cancel")],
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await message.answer(existing_text, parse_mode="HTML", reply_markup=keyboard)
        await state.set_state(BacktestStates.confirm)
        return
    
    # Yangi test uchun tasdiqlash
    summary_text = (
        f"📋 <b>Backtest parametrlari:</b>\n\n"
        f"📈 Symbol: <b>{symbol}</b>\n"
        f"⏱ Signal TF: <b>{timeframe}</b>\n"
        f"⚡ Execution TF: <b>{exec_tf}</b>\n"
        f"🎯 Threshold: <b>{threshold}%</b>\n"
        f"📅 Davr: <b>{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}</b>\n"
        f"📊 Kunlar: <b>{days_diff}</b>\n\n"
        f"Backtest ni boshlashni xohlaysizmi?"
    )
    
    await message.answer(
        summary_text,
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard()
    )
    await state.set_state(BacktestStates.confirm)


@router.callback_query(F.data.startswith("bt_pdf:"))
async def backtest_send_existing_pdf(callback: CallbackQuery, state: FSMContext):
    """Mavjud natija uchun PDF yuborish"""
    result_id = int(callback.data.split(":")[1])  # type: ignore
    
    async with get_session() as session:
        crud = BacktestResultCRUD(session)
        result = await crud.get_by_id(result_id)
    
    if not result:
        await callback.answer("❌ Natija topilmadi!", show_alert=True)
        return
    
    await callback.answer("📄 PDF tayyorlanmoqda...")
    
    # Trades JSON dan BacktestSummary yaratish
    summary = BacktestSummary(
        session_id=str(result.id),
        symbol=result.symbol,
        signal_timeframe=result.timeframe,
        execution_timeframe="1m",
        period_start=datetime.combine(result.start_date, datetime.min.time()),
        period_end=datetime.combine(result.end_date, datetime.min.time()),
        total_signals=result.total_signals,
        long_signals=result.long_signals,
        short_signals=result.short_signals,
        wins=result.wins,
        losses=result.losses,
        partial_wins=result.partial_wins,
        timeouts=result.timeouts,
        tp1_hits=result.tp1_hits,
        tp2_hits=result.tp2_hits,
        tp3_hits=result.tp3_hits,
        total_profit_percent=result.total_profit,
        average_profit=result.average_profit,
        average_loss=result.average_loss,
        max_profit=result.max_profit,
        max_loss=result.max_loss,
        profit_factor=result.profit_factor,
        win_rate=result.win_rate,
    )
    
    # Trades ni yuklash
    if result.trades_json:
        try:
            from app.services.backtester import TradeResult
            trades_data = json.loads(result.trades_json)
            for t in trades_data:
                trade = TradeResult(
                    signal_time=datetime.fromisoformat(t["signal_time"]),
                    direction=t["direction"],
                    confidence=t["confidence"],
                    entry_price=t["entry_price"],
                    stop_loss=t["stop_loss"],
                    take_profit_1=t["take_profit_1"],
                    take_profit_2=t["take_profit_2"],
                    take_profit_3=t["take_profit_3"],
                    result=t["result"],
                    exit_time=datetime.fromisoformat(t["exit_time"]) if t.get("exit_time") else None,
                    exit_price=t.get("exit_price"),
                    tp1_hit=t.get("tp1_hit", False),
                    tp2_hit=t.get("tp2_hit", False),
                    tp3_hit=t.get("tp3_hit", False),
                    sl_hit=t.get("sl_hit", False),
                    sl_hit_at=t.get("sl_hit_at"),
                    total_profit_percent=t.get("total_profit_percent", 0.0),
                )
                summary.trades.append(trade)
        except Exception as e:
            logging.error(f"Trades JSON parse error: {e}")

    # Strategiya performance ni yuklash
    if result.strategy_performance_json:
        try:
            from app.services.backtester import StrategyPerformance
            perf_data = json.loads(result.strategy_performance_json)
            for p in perf_data:
                summary.strategy_performance.append(StrategyPerformance(
                    code=p.get("code", ""),
                    name=p.get("name", ""),
                    total_signals=p.get("total_signals", 0),
                    wins=p.get("wins", 0),
                    losses=p.get("losses", 0),
                    partial_wins=p.get("partial_wins", 0),
                    timeouts=p.get("timeouts", 0),
                    total_profit_percent=p.get("total_profit_percent", 0.0),
                    average_profit=p.get("average_profit", 0.0),
                    average_loss=p.get("average_loss", 0.0),
                    profit_factor=p.get("profit_factor", 0.0),
                    win_rate=p.get("win_rate", 0.0),
                    current_weight=p.get("current_weight", 1.0),
                    suggested_weight=p.get("suggested_weight", 1.0),
                    base_weight=p.get("base_weight", 1.0),
                    perf_weight=p.get("perf_weight", 1.0),
                    regime_mult=p.get("regime_mult", 1.0),
                    stability_weight=p.get("stability_weight", 1.0),
                    corr_penalty=p.get("corr_penalty", 1.0),
                    actual_weight=p.get("actual_weight", 1.0),
                ))
        except Exception as e:
            logging.error(f"Strategy performance JSON parse error: {e}")
    
    try:
        pdf_buffer = generate_backtest_pdf(summary)
        pdf_filename = get_pdf_filename(summary)
        
        pdf_file = BufferedInputFile(
            file=pdf_buffer.read(),
            filename=pdf_filename
        )
        
        await callback.message.answer_document(  # type: ignore
            document=pdf_file,
            caption="📄 <b>Batafsil PDF hisobot</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"PDF generation error: {e}")
        await callback.message.answer(  # type: ignore
            "⚠️ PDF hisobot yaratishda xatolik yuz berdi.",
            parse_mode="HTML"
        )
    
    await state.clear()


@router.callback_query(F.data == "bt_rerun")
async def backtest_rerun(callback: CallbackQuery, state: FSMContext):
    """Qayta test qilish"""
    await callback.answer("🔄 Qayta test boshlanmoqda...")
    
    # bt_confirm:yes ga o'tkazish
    await backtest_confirm(callback, state)


@router.callback_query(F.data == "bt_confirm:yes")
async def backtest_confirm(callback: CallbackQuery, state: FSMContext):
    """Backtest ni tasdiqlash va boshlash"""
    data = await state.get_data()
    symbol = data.get("symbol")
    timeframe = data.get("timeframe")
    start_date: datetime = data.get("start_date")  # type: ignore
    end_date: datetime = data.get("end_date")  # type: ignore
    threshold: float = data.get("threshold", 60.0)  # type: ignore
    user_id = callback.from_user.id
    
    # Agar mavjud natija bo'lsa - avval o'chiramiz (qayta test uchun)
    existing_result_id = data.get("existing_result_id")
    if existing_result_id:
        async with get_session() as session:
            crud = BacktestResultCRUD(session)
            await crud.delete(existing_result_id)
    
    await state.set_state(BacktestStates.running)
    
    # Progress message
    await callback.message.edit_text(  # type: ignore
        "🚀 <b>Backtest boshlanmoqda...</b>\n\n"
        "📥 1m candle ma'lumotlari yuklanmoqda...\n"
        "⏳ Bu bir necha daqiqa vaqt olishi mumkin.",
        parse_mode="HTML"
    )
    await callback.answer()
    
    progress_msg = callback.message
    last_progress = -1
    
    # Progress callback
    async def update_progress(current: int, total: int, msg: str):
        nonlocal last_progress
        # Faqat progress o'zgarganda yangilash (spam oldini olish)
        if current == last_progress:
            return
        last_progress = current
        
        try:
            bar_length = 20
            filled = int(bar_length * current / total)
            bar = "▓" * filled + "░" * (bar_length - filled)
            
            await progress_msg.edit_text(  # type: ignore
                f"🔬 <b>Backtest: {symbol}</b>\n"
                f"📊 TF: {timeframe} | 🎯 Threshold: {threshold}%\n\n"
                f"<code>{bar}</code> {current}%\n\n"
                f"{msg}",
                parse_mode="HTML"
            )
        except Exception:
            pass
    
    try:
        # Backtester yaratish va ishga tushirish
        backtester = Backtester(
            symbol=symbol,  # type: ignore
            signal_timeframe=timeframe,  # type: ignore
            start_date=start_date,
            end_date=end_date,
            threshold=threshold,
        )
        
        summary = await backtester.run(progress_callback=update_progress)
        
        # Natijani bazaga saqlash
        result_id = await save_backtest_result(
            user_id=user_id,
            symbol=symbol,  # type: ignore
            timeframe=timeframe,  # type: ignore
            threshold=threshold,
            start_date=start_date,
            end_date=end_date,
            summary=summary,
        )
        
        # Natijani ko'rsatish
        await send_backtest_summary(callback.message, summary, result_id)  # type: ignore
        
    except Exception as e:
        logging.error(f"Backtest error: {e}")
        await callback.message.answer(  # type: ignore
            f"❌ Backtest da xatolik yuz berdi:\n<code>{str(e)}</code>",
            parse_mode="HTML"
        )
    
    finally:
        await state.clear()


async def save_backtest_result(
    user_id: int,
    symbol: str,
    timeframe: str,
    threshold: float,
    start_date: datetime,
    end_date: datetime,
    summary: BacktestSummary,
) -> int | None:
    """Backtest natijasini bazaga saqlash"""
    
    # Trades ni JSON ga aylantirish
    trades_data = []
    for trade in summary.trades:
        trades_data.append({
            "signal_time": trade.signal_time.isoformat(),
            "direction": trade.direction,
            "confidence": trade.confidence,
            "entry_price": trade.entry_price,
            "stop_loss": trade.stop_loss,
            "take_profit_1": trade.take_profit_1,
            "take_profit_2": trade.take_profit_2,
            "take_profit_3": trade.take_profit_3,
            "result": trade.result,
            "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
            "exit_price": trade.exit_price,
            "tp1_hit": trade.tp1_hit,
            "tp2_hit": trade.tp2_hit,
            "tp3_hit": trade.tp3_hit,
            "sl_hit": trade.sl_hit,
            "sl_hit_at": trade.sl_hit_at,
            "total_profit_percent": trade.total_profit_percent,
        })

    # Strategiya performance ni JSON ga aylantirish
    strategy_perf_data = [sp.to_dict() for sp in summary.strategy_performance]
    
    try:
        async with get_session() as session:
            crud = BacktestResultCRUD(session)
            result = await crud.create({
                "user_id": user_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "threshold": threshold,
                "start_date": start_date.date(),
                "end_date": end_date.date(),
                "total_signals": summary.total_signals,
                "long_signals": summary.long_signals,
                "short_signals": summary.short_signals,
                "wins": summary.wins,
                "losses": summary.losses,
                "partial_wins": summary.partial_wins,
                "timeouts": summary.timeouts,
                "tp1_hits": summary.tp1_hits,
                "tp2_hits": summary.tp2_hits,
                "tp3_hits": summary.tp3_hits,
                "total_profit": summary.total_profit_percent,
                "average_profit": summary.average_profit,
                "average_loss": summary.average_loss,
                "max_profit": summary.max_profit,
                "max_loss": summary.max_loss,
                "profit_factor": summary.profit_factor,
                "win_rate": summary.win_rate,
                "trades_json": json.dumps(trades_data),
                "strategy_performance_json": json.dumps(strategy_perf_data),
            })
            return result.id
    except Exception as e:
        logging.error(f"Failed to save backtest result: {e}")
        return None


async def send_backtest_summary(message: Message, summary: BacktestSummary, result_id: int | None = None):
    """Backtest natijasini chiroyli formatda ko'rsatish"""
    
    if summary.total_signals == 0:
        await message.answer(
            "📊 <b>Backtest natijasi</b>\n\n"
            "❌ Berilgan davrda signal topilmadi.\n"
            "Boshqa parametrlar bilan sinab ko'ring.",
            parse_mode="HTML"
        )
        return
    
    # Win rate color
    if summary.win_rate >= 60:
        wr_emoji = "🟢"
    elif summary.win_rate >= 40:
        wr_emoji = "🟡"
    else:
        wr_emoji = "🔴"
    
    # Profit color
    if summary.total_profit_percent > 0:
        profit_emoji = "📈"
        profit_sign = "+"
    else:
        profit_emoji = "📉"
        profit_sign = ""
    
    text = f"""
📊 <b>BACKTEST NATIJASI</b>

<b>📋 Parametrlar:</b>
├ Symbol: <b>{summary.symbol}</b>
├ Signal TF: <b>{summary.signal_timeframe}</b>
├ Execution TF: <b>{summary.execution_timeframe}</b>
├ Davr: {summary.period_start.strftime('%d.%m.%Y')} - {summary.period_end.strftime('%d.%m.%Y')}
└ Kunlar: {(summary.period_end - summary.period_start).days}

<b>📉 Signallar:</b>
├ Jami: <b>{summary.total_signals}</b>
├ 🟢 LONG: {summary.long_signals} ({summary.long_signals/summary.total_signals*100:.1f}%)
└ 🔴 SHORT: {summary.short_signals} ({summary.short_signals/summary.total_signals*100:.1f}%)

<b>✅ Natijalar:</b>
├ {wr_emoji} Win rate: <b>{summary.win_rate:.1f}%</b>
├ Wins: {summary.wins}
├ Losses: {summary.losses}
├ Partial: {summary.partial_wins}
└ Timeout: {summary.timeouts}

<b>🎯 Take Profit taqsimoti:</b>
├ TP1 hit: {summary.tp1_hits} ({summary.tp1_hits/summary.total_signals*100:.1f}%)
├ TP2 hit: {summary.tp2_hits} ({summary.tp2_hits/summary.total_signals*100:.1f}%)
└ TP3 hit: {summary.tp3_hits} ({summary.tp3_hits/summary.total_signals*100:.1f}%)

<b>{profit_emoji} Profit/Loss (partial close 40/30/30):</b>
├ Jami: <b>{profit_sign}{summary.total_profit_percent:.2f}%</b>
├ O'rtacha profit: +{summary.average_profit:.2f}%
├ O'rtacha loss: -{summary.average_loss:.2f}%
├ Max profit: +{summary.max_profit:.2f}%
├ Max loss: -{summary.max_loss:.2f}%
└ Profit factor: <b>{summary.profit_factor:.2f}</b>

<i>💡 Partial close: TP1=40%, TP2=30%, TP3=30%
SL hit bo'lganda qolgan pozitsiya yopiladi.</i>
"""

    if summary.strategy_performance:
        text += "\n\n<b>🧩 Strategiyalar performance:</b>\n"
        for perf in summary.strategy_performance:
            text += (
                f"• {perf.name}: "
                f"WR {perf.win_rate:.1f}% | "
                f"PF {perf.profit_factor:.2f} | "
                f"P&L {perf.total_profit_percent:.2f}% | "
                f"W {perf.current_weight:.2f} → {perf.suggested_weight:.2f}\n"
            )
        text += "\n<b>⚙️ Weight breakdown (debug):</b>\n"
        for perf in summary.strategy_performance:
            text += (
                f"• {perf.name}: "
                f"base {perf.base_weight:.2f} | "
                f"perf {perf.perf_weight:.2f} | "
                f"reg {perf.regime_mult:.2f} | "
                f"stab {perf.stability_weight:.2f} | "
                f"corr {perf.corr_penalty:.2f} | "
                f"actual {perf.actual_weight:.2f}\n"
            )
    
    # Saqlangan bo'lsa xabar qo'shish
    if result_id:
        text += f"\n\n✅ <i>Natija saqlandi (ID: {result_id})</i>"
    
    await message.answer(text.strip(), parse_mode="HTML")
    
    # Oxirgi 5 ta trade ni ko'rsatish
    if summary.trades:
        recent_trades = summary.trades[-5:]
        trades_text = "\n<b>📝 Oxirgi 5 ta trade:</b>\n\n"
        
        for i, trade in enumerate(recent_trades, 1):
            dir_emoji = "🟢" if trade.direction == "LONG" else "🔴"
            
            if trade.result == "TP3":
                result_emoji = "🏆"
            elif trade.result == "PARTIAL":
                result_emoji = "⚡"
            elif trade.result == "SL":
                result_emoji = "❌"
            else:
                result_emoji = "⏳"
            
            profit_str = f"+{trade.total_profit_percent:.2f}%" if trade.total_profit_percent > 0 else f"{trade.total_profit_percent:.2f}%"
            
            trades_text += (
                f"{i}. {dir_emoji} {trade.direction} | "
                f"{result_emoji} {trade.result} | "
                f"{profit_str}\n"
            )
        
        await message.answer(trades_text.strip(), parse_mode="HTML")

    # PDF report yuborish
    try:
        pdf_buffer = generate_backtest_pdf(summary)
        pdf_filename = get_pdf_filename(summary)
        
        pdf_file = BufferedInputFile(
            file=pdf_buffer.read(),
            filename=pdf_filename
        )
        
        await message.answer_document(
            document=pdf_file,
            caption="📄 <b>Batafsil PDF hisobot</b>\n\nBarcha signallar va natijalar yuqoridagi faylda.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"PDF generation error: {e}")
        await message.answer(
            "⚠️ PDF hisobot yaratishda xatolik yuz berdi.",
            parse_mode="HTML"
        )
