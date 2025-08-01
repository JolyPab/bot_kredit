from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from database.models import User, UserRole
from services.user_service import UserService
from bot.keyboards.inline import get_faq_keyboard, get_back_button
from bot.utils.messages import MESSAGES

logger = logging.getLogger(__name__)
router = Router()

user_service = UserService()

class SupportStates(StatesGroup):
    waiting_for_message = State()

@router.callback_query(F.data == "show_faq")
async def show_faq_menu(callback: CallbackQuery):
    """Показать меню FAQ"""
    
    text = """❓ ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ

Выберите интересующую вас тему:"""

    await callback.message.edit_text(text, reply_markup=get_faq_keyboard())
    await callback.answer()

@router.callback_query(F.data == "faq_timing")
async def faq_timing(callback: CallbackQuery):
    """FAQ по срокам обработки"""
    
    await callback.message.edit_text(
        MESSAGES["faq_timing"],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔙 Назад к FAQ",
                callback_data="show_faq"
            )],
            [InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="back_to_menu"
            )]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "faq_documents")
async def faq_documents(callback: CallbackQuery):
    """FAQ по документам"""
    
    await callback.message.edit_text(
        MESSAGES["faq_documents"],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📋 Загрузить документы",
                callback_data="start_diagnosis"
            )],
            [InlineKeyboardButton(
                text="🔙 Назад к FAQ",
                callback_data="show_faq"
            )]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "faq_pricing")
async def faq_pricing(callback: CallbackQuery):
    """FAQ по стоимости"""
    
    await callback.message.edit_text(
        MESSAGES["faq_pricing"],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💬 Уточнить стоимость",
                callback_data="contact_support"
            )],
            [InlineKeyboardButton(
                text="🔙 Назад к FAQ",
                callback_data="show_faq"
            )]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "faq_security")
async def faq_security(callback: CallbackQuery):
    """FAQ по безопасности"""
    
    await callback.message.edit_text(
        MESSAGES["faq_security"],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📋 Политика конфиденциальности",
                callback_data="privacy_policy"
            )],
            [InlineKeyboardButton(
                text="🔙 Назад к FAQ",
                callback_data="show_faq"
            )]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "privacy_policy")
async def privacy_policy(callback: CallbackQuery):
    """Политика конфиденциальности"""
    
    text = """📋 ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ

🔐 Мы гарантируем:

1️⃣ Шифрование данных
• Все персональные данные шифруются алгоритмом AES-256
• Ключи шифрования хранятся отдельно от данных
• Доступ к данным имеют только уполномоченные сотрудники

2️⃣ Минимизация данных
• Собираем только необходимые для услуги данные
• Храним данные минимально необходимое время
• Удаляем данные по первому требованию

3️⃣ Соблюдение законов
• Работаем в соответствии с 152-ФЗ "О персональных данных"
• Соблюдаем требования ЦБ РФ
• Следуем международным стандартам безопасности

4️⃣ Ваши права
• Право на доступ к своим данным
• Право на исправление данных
• Право на удаление данных
• Право на ограничение обработки

📞 По вопросам обработки данных: support@example.com"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 Удалить мои данные",
            callback_data="request_data_deletion"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="faq_security"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "request_data_deletion")
async def request_data_deletion(callback: CallbackQuery, user: User):
    """Запрос на удаление данных"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    text = """🗑 ЗАПРОС НА УДАЛЕНИЕ ДАННЫХ

⚠️ Внимание! При удалении данных:
• Будут удалены все ваши документы
• История заявок будет недоступна
• Аккаунт будет деактивирован
• Восстановление будет невозможно

📋 Для подтверждения удаления данных обратитесь в службу поддержки.

Мы обработаем ваш запрос в течение 3 рабочих дней в соответствии с требованиями закона."""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💬 Обратиться в поддержку",
            callback_data="contact_support"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="privacy_policy"
        )]
    ])
    
    # Логируем запрос на удаление
    await user_service.log_user_action(
        user.id,
        "data_deletion_requested",
        {"source": "bot_interface"}
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "contact_support")
async def contact_support(callback: CallbackQuery, user: User, state: FSMContext):
    """Обращение в поддержку"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    text = """💬 СЛУЖБА ПОДДЕРЖКИ

Опишите вашу проблему или вопрос в следующем сообщении, и мы обязательно вам поможем!

🕐 Время ответа: обычно в течение 1-2 часов в рабочее время (Пн-Пт 9:00-18:00)

💡 Для более быстрого решения укажите:
• Суть проблемы
• Номер заявки (если есть)
• Желаемый способ связи

📧 Email: support@example.com
📞 Телефон: +7 (XXX) XXX-XX-XX"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✍️ Написать сообщение",
            callback_data="write_support_message"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад в меню",
            callback_data="back_to_menu"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "write_support_message")
async def write_support_message(callback: CallbackQuery, state: FSMContext):
    """Написать сообщение в поддержку"""
    
    await state.set_state(SupportStates.waiting_for_message)
    
    text = """✍️ НАПИСАТЬ В ПОДДЕРЖКУ

Напишите ваше сообщение в следующем тексте. Мы получим его и обязательно ответим!

Для отмены нажмите кнопку ниже."""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="contact_support"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.message(StateFilter(SupportStates.waiting_for_message))
async def process_support_message(message: Message, state: FSMContext, user: User):
    """Обработка сообщения в поддержку"""
    
    if not user:
        await message.answer("❌ Необходимо зарегистрироваться")
        return
    
    # Логируем обращение в поддержку
    await user_service.log_user_action(
        user.id,
        "support_message_sent",
        {
            "message": message.text[:200],  # Сохраняем первые 200 символов
            "message_length": len(message.text)
        }
    )
    
    # TODO: Здесь можно добавить отправку в CRM или на email
    logger.info(f"Сообщение в поддержку от пользователя {user.id}: {message.text[:100]}...")
    
    await message.answer(
        """✅ СООБЩЕНИЕ ОТПРАВЛЕНО!

Ваше обращение получено и передано в службу поддержки.

📱 Номер обращения: #{support_id}
⏰ Ожидаемое время ответа: 1-2 часа

Мы свяжемся с вами через этот бот или по указанным контактам.

Спасибо за обращение!""".format(
            support_id=f"SUP{user.id}{message.message_id}"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📊 Проверить статус",
                callback_data="check_status"
            )],
            [InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="back_to_menu"
            )]
        ])
    )
    
    await state.clear()

# Дополнительные обработчики для полезных команд

@router.callback_query(F.data == "settings")
async def user_settings(callback: CallbackQuery, user: User):
    """Настройки пользователя"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    # Получаем контактные данные
    phone = await user_service.get_user_phone(user)
    email = await user_service.get_user_email(user)
    
    text = f"""⚙️ НАСТРОЙКИ АККАУНТА

👤 Информация:
• Имя: {user.first_name or 'Не указано'}
• Username: @{user.username or 'Не указан'}
• Телефон: {phone or 'Не указан'}
• Email: {email or 'Не указан'}

📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}
🔐 Согласие на ПД: {'✅ Дано' if user.pd_consent else '❌ Не дано'}
📋 Согласие на заявления: {'✅ Дано' if user.application_consent else '❌ Не дано'}

💡 Для изменения данных обратитесь в поддержку."""

    # Базовые кнопки для всех
    keyboard_buttons = [
        [InlineKeyboardButton(
            text="📊 Статистика",
            callback_data="user_stats"
        )]
    ]
    
    # Кнопка "Стать брокером" только для клиентов
    if user.role == UserRole.CLIENT:
        keyboard_buttons.append([InlineKeyboardButton(
            text="👨‍💼 Стать брокером",
            callback_data="become_broker_demo"
        )])
    
    # Остальные кнопки
    keyboard_buttons.extend([
        [InlineKeyboardButton(
            text="🔐 Управление согласиями",
            callback_data="manage_consents"
        )],
        [InlineKeyboardButton(
            text="💬 Изменить данные",
            callback_data="contact_support"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад в меню",
            callback_data="back_to_menu"
        )]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "user_stats")
async def user_statistics(callback: CallbackQuery, user: User):
    """Статистика пользователя"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    from services.application_service import ApplicationService
    from services.document_service import DocumentService
    
    app_service = ApplicationService()
    doc_service = DocumentService()
    
    # Получаем статистику
    app_stats = await app_service.get_application_stats(user.id)
    doc_stats = await doc_service.get_documents_stats(user.id)
    
    text = f"""📊 ВАША СТАТИСТИКА

📋 Заявки:
• Всего: {app_stats['total']}
• Завершенных: {app_stats['completed']}
• В работе: {app_stats['in_progress']}

📄 Документы:
• Всего загружено: {doc_stats['total']}
• Обработано: {doc_stats['processed']}
• В обработке: {doc_stats['total'] - doc_stats['processed']}

🕐 В системе с: {user.created_at.strftime('%d.%m.%Y')}
📱 Последняя активность: {user.last_activity.strftime('%d.%m.%Y %H:%M') if user.last_activity else 'Неизвестно'}"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 История действий",
            callback_data="user_history"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад к настройкам",
            callback_data="settings"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "user_history")
async def user_action_history(callback: CallbackQuery, user: User):
    """История действий пользователя"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    # Получаем последние действия
    logs = await user_service.get_user_logs(user.id, limit=10)
    
    text = "📋 ИСТОРИЯ ДЕЙСТВИЙ (последние 10)\n\n"
    
    if logs:
        for log in logs:
            date_str = log.created_at.strftime('%d.%m %H:%M')
            action_name = {
                'registration': '📝 Регистрация',
                'document_uploaded': '📤 Загрузка документа',
                'status_refresh': '🔄 Проверка статуса',
                'support_message_sent': '💬 Сообщение в поддержку',
                'contact_info_updated': '📞 Обновление контактов'
            }.get(log.action, log.action)
            
            text += f"• {date_str} - {action_name}\n"
    else:
        text += "Пока нет записей действий."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👨‍💼 Стать брокером (тест)",
            callback_data="become_broker_demo"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад к статистике",
            callback_data="user_stats"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

 