import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config.settings import get_settings
from bot.handlers import register_all_handlers
from bot.middlewares.logging_middleware import LoggingMiddleware
from bot.middlewares.auth_middleware import AuthMiddleware
from database.database import init_db, close_db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Главная функция запуска бота"""
    
    settings = get_settings()
    
    # Инициализация бота и диспетчера
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    
    # Регистрация middleware
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    
    # Инициализация базы данных
    await init_db()
    
    # Регистрация хэндлеров
    register_all_handlers(dp)
    
    logger.info("Бот запущен")
    
    try:
        # Запуск бота
        await dp.start_polling(bot)
    finally:
        # Закрытие соединений
        await close_db()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main()) 