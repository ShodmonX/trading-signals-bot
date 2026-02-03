from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InaccessibleMessage
from aiogram.filters import Command

from app.keyboards.settings import settings_btns
from app.schedulers.utils import pause_job, resume_job
from app.config import get_settings


settings = get_settings()
router = Router()

@router.message(Command(commands=['settings']))
async def settings_check(message: Message):
    await message.answer("Settings", reply_markup=settings_btns(settings.check_types))

@router.callback_query(F.data.startswith("check_"))
async def settings_check_(callback: CallbackQuery):
    if callback.data is None:
        await callback.answer()
        return
    if settings.check_types[callback.data]:
        pause_job(callback.data)
        settings.check_types[callback.data] = False
    else:
        resume_job(callback.data)
        settings.check_types[callback.data] = True
    if not isinstance(callback.message, InaccessibleMessage) and callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=settings_btns(settings.check_types))
    await callback.answer()