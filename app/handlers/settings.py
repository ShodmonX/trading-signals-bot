from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from app.keyboards.settings import settings_btns
from app.schedulers.utils import pause_job, resume_job
from app.config import check_types

router = Router()

@router.message(Command(commands=['settings']))
async def settings_check(message: Message):
    await message.answer("Settings", reply_markup=settings_btns(check_types))

@router.callback_query(F.data.startswith("check_"))
async def settings_check(callback: CallbackQuery):
    if check_types[callback.data]:
        pause_job(callback.data)
        check_types[callback.data] = False
    else:
        resume_job(callback.data)
        check_types[callback.data] = True
    await callback.message.edit_reply_markup(reply_markup=settings_btns(check_types))
    await callback.answer()