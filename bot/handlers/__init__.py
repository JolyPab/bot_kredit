from aiogram import Dispatcher

from .onboarding import router as onboarding_router
from .documents import router as documents_router
from .status import router as status_router
from .faq_support import router as faq_support_router
from .broker import router as broker_router
from .broker_auth import router as broker_auth_router
from .admin import router as admin_router

def register_all_handlers(dp: Dispatcher):
    """Регистрация всех хэндлеров"""
    
    # Регистрируем роутеры в порядке приоритета
    dp.include_router(onboarding_router)
    dp.include_router(documents_router)
    dp.include_router(status_router)
    dp.include_router(faq_support_router)
    dp.include_router(broker_router)
    dp.include_router(broker_auth_router)
    dp.include_router(admin_router)
    
    # Будущие роутеры:
    # dp.include_router(diagnosis_router) 