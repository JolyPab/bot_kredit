from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
import logging
import time

from services.user_service import UserService

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования действий пользователей"""
    
    def __init__(self):
        super().__init__()
        self.user_service = UserService()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        start_time = time.time()
        
        # Получаем информацию о событии
        user_id = None
        action = None
        details = {}
        
        if isinstance(event, Message):
            user_id = event.from_user.id
            action = f"message_{event.content_type}"
            details = {
                "text": event.text[:100] if event.text else None,
                "chat_type": event.chat.type,
                "message_id": event.message_id
            }
            
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            action = f"callback_{event.data}"
            details = {
                "callback_data": event.data,
                "message_id": event.message.message_id if event.message else None
            }
        
        # Логируем начало обработки
        logger.info(
            f"Processing {action} from user {user_id} "
            f"({event.from_user.username if hasattr(event, 'from_user') else 'unknown'})"
        )
        
        try:
            # Выполняем основной обработчик
            result = await handler(event, data)
            
            # Время выполнения
            execution_time = time.time() - start_time
            
            # Логируем успешное выполнение
            logger.info(f"Completed {action} for user {user_id} in {execution_time:.2f}s")
            
            # Записываем в БД только для зарегистрированных пользователей
            user = data.get("user")
            if user and action:
                details["execution_time"] = execution_time
                await self.user_service.log_user_action(
                    user.id,
                    action,
                    details
                )
            
            return result
            
        except Exception as e:
            # Время выполнения при ошибке
            execution_time = time.time() - start_time
            
            # Логируем ошибку
            logger.error(
                f"Error processing {action} for user {user_id} "
                f"in {execution_time:.2f}s: {str(e)}"
            )
            
            # Записываем ошибку в БД
            user = data.get("user")
            if user and action:
                details.update({
                    "execution_time": execution_time,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                await self.user_service.log_user_action(
                    user.id,
                    f"error_{action}",
                    details
                )
            
            # Пробрасываем ошибку дальше
            raise 