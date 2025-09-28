from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable

from app.db import LocalAsyncSession, UserCRUD

class StartMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        
        async with LocalAsyncSession() as session:
            crud = UserCRUD(session)
            data = {
                'telegram_id': event.from_user.id,
                'username': event.from_user.username,
                'first_name': event.from_user.first_name,
                'last_name': event.from_user.last_name,
            }
            await crud.create_and_update(data)

        return await handler(event, data)