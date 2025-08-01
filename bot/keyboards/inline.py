from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import UserRole

def get_consent_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для согласия на обработку ПД"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Согласен", 
                callback_data="consent_agree"
            ),
            InlineKeyboardButton(
                text="❌ Не согласен", 
                callback_data="consent_decline"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Подробнее о согласии", 
                callback_data="show_consent_details"
            )
        ]
    ])

def get_main_menu_keyboard(user_role=None) -> InlineKeyboardMarkup:
    """Главное меню бота с учетом роли пользователя"""
    
    # Базовое меню для всех
    keyboard_buttons = [
        [
            InlineKeyboardButton(
                text="📋 Диагностика КИ", 
                callback_data="start_diagnosis"
            )
        ],
        [
            InlineKeyboardButton(
                text="📄 Мои документы", 
                callback_data="my_documents"
            ),
            InlineKeyboardButton(
                text="📊 Статус заявки", 
                callback_data="check_status"
            )
        ]
    ]
    
    # Для брокеров добавляем кнопку кабинета
    if user_role in [UserRole.BROKER, UserRole.ADMIN]:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="👨‍💼 Брокерский кабинет",
                callback_data="broker_mode"
            )
        ])
    
    # Общие кнопки внизу
    keyboard_buttons.extend([
        [
            InlineKeyboardButton(
                text="❓ FAQ", 
                callback_data="show_faq"
            ),
            InlineKeyboardButton(
                text="💬 Поддержка", 
                callback_data="contact_support"
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ Настройки", 
                callback_data="settings"
            )
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

def get_document_upload_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для загрузки документов"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📋 НБКИ", 
                callback_data="upload_nbki"
            ),
            InlineKeyboardButton(
                text="📋 ОКБ", 
                callback_data="upload_okb"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Эквифакс", 
                callback_data="upload_equifax"
            ),
            InlineKeyboardButton(
                text="📄 Другое", 
                callback_data="upload_other"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="back_to_menu"
            )
        ]
    ])

def get_status_keyboard(has_diagnosis_results: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для проверки статуса"""
    
    keyboard_buttons = [
        [
            InlineKeyboardButton(
                text="🔄 Обновить статус", 
                callback_data="refresh_status"
            )
        ]
    ]
    
    # Добавляем кнопку просмотра результатов диагностики если они есть
    if has_diagnosis_results:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="🤖 Результаты GPT диагностики", 
                callback_data="view_gpt_results"
            )
        ])
    
    keyboard_buttons.extend([
        [
            InlineKeyboardButton(
                text="📋 Подробная информация", 
                callback_data="detailed_status"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="back_to_menu"
            )
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

def get_broker_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню для брокеров"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="👥 Мои клиенты", 
                callback_data="broker_clients"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Статистика", 
                callback_data="broker_stats"
            ),
            InlineKeyboardButton(
                text="📈 Отчеты", 
                callback_data="broker_reports"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔗 Реферальная ссылка", 
                callback_data="broker_ref_link"
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ Настройки", 
                callback_data="broker_settings"
            )
        ]
    ])

def get_faq_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура FAQ"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⏱️ Сроки обработки", 
                callback_data="faq_timing"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Какие документы нужны", 
                callback_data="faq_documents"
            )
        ],
        [
            InlineKeyboardButton(
                text="💰 Стоимость услуг", 
                callback_data="faq_pricing"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔒 Безопасность данных", 
                callback_data="faq_security"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="back_to_menu"
            )
        ]
    ])

def get_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить", 
                callback_data=f"confirm_{action}"
            ),
            InlineKeyboardButton(
                text="❌ Отмена", 
                callback_data=f"cancel_{action}"
            )
        ]
    ])

def get_back_button() -> InlineKeyboardMarkup:
    """Простая кнопка "Назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔙 Назад", 
                callback_data="back_to_menu"
            )
        ]
    ]) 