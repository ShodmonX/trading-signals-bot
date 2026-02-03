from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from typing import Callable, Dict, Any, Awaitable

from app.db import LocalAsyncSession, UserCRUD

class StartMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        if isinstance(event, Message):
            if event.from_user:
                async with LocalAsyncSession() as session:
                    crud = UserCRUD(session)
                    db_data = {
                        'telegram_id': event.from_user.id,
                        'username': event.from_user.username,
                        'first_name': event.from_user.first_name,
                        'last_name': event.from_user.last_name,
                    }
                    await crud.create_and_update(db_data)

        return await handler(event, data)