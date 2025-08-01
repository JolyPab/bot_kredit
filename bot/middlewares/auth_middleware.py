from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
import logging

from services.user_service import UserService

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseMiddleware):
    """Middleware для аутентификации пользователей"""
    
    def __init__(self):
        super().__init__()
        self.user_service = UserService()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        # Получаем user_id из события
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
        
        if user_id:
            # Получаем пользователя из БД
            user = await self.user_service.get_user_by_telegram_id(user_id)
            
            # Добавляем пользователя в контекст
            data["user"] = user
            
            # Если пользователь существует, обновляем время последней активности
            if user:
                await self.user_service.update_last_activity(user.id)
                
                # Проверяем, активен ли пользователь
                if not user.is_active:
                    if isinstance(event, Message):
                        await event.answer(
                            "❌ Ваш аккаунт заблокирован. Обратитесь в поддержку."
                        )
                    elif isinstance(event, CallbackQuery):
                        await event.answer(
                            "❌ Ваш аккаунт заблокирован. Обратитесь в поддержку.",
                            show_alert=True
                        )
                    return
            
        return await handler(event, data) 