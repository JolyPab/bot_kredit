from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from contextlib import asynccontextmanager
import logging

from config.settings import get_settings
from .models import Base

logger = logging.getLogger(__name__)

# Глобальные переменные для движка и сессии
engine = None
async_session_maker = None

async def init_db():
    """Инициализация базы данных"""
    global engine, async_session_maker
    
    settings = get_settings()
    
    # Создание движка
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # Логирование SQL запросов
        pool_pre_ping=True,
        pool_recycle=300,
    )
    
    # Создание фабрики сессий
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Создание таблиц
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("База данных инициализирована")

async def close_db():
    """Закрытие соединения с базой данных"""
    global engine
    if engine:
        await engine.dispose()
        logger.info("Соединение с БД закрыто")

@asynccontextmanager
async def get_db_session():
    """Контекстный менеджер для получения сессии БД"""
    if not async_session_maker:
        raise RuntimeError("База данных не инициализирована")
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_session() -> AsyncSession:
    """Получить сессию БД (для dependency injection)"""
    if not async_session_maker:
        raise RuntimeError("База данных не инициализирована")
    
    return async_session_maker() 