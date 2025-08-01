from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import logging
from datetime import datetime, timedelta
from typing import Optional

from database.models import User, UserRole, Broker
from services.user_service import UserService
from services.referral_service import ReferralService
from bot.keyboards.inline import get_broker_menu_keyboard
from bot.utils.messages import MESSAGES

logger = logging.getLogger(__name__)
router = Router()

user_service = UserService()
referral_service = ReferralService()



# Заглушка для BrokerService
class BrokerService:
    """Временный сервис для брокеров"""
    
    async def get_broker_by_telegram_id(self, telegram_id: int) -> Optional[Broker]:
        # TODO: Реализовать получение брокера
        return None
    
    async def get_broker_clients_count(self, broker_id: int) -> int:
        # TODO: Реализовать подсчет клиентов
        return 0
    
    async def get_broker_earnings(self, broker_id: int) -> float:
        # TODO: Реализовать подсчет заработка
        return 0.0
    
    async def generate_referral_link(self, broker: Broker) -> str:
        # TODO: Реализовать генерацию ссылки
        return f"https://t.me/your_bot?start={broker.ref_code if broker else 'DEMO'}"

broker_service = BrokerService()

@router.callback_query(F.data == "broker_mode")
async def enter_broker_mode(callback: CallbackQuery, user: User):
    """Вход в режим брокера"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    # Проверяем роль пользователя
    if user.role != UserRole.BROKER and user.role != UserRole.ADMIN:
        await callback.message.edit_text(
            """❌ У вас нет доступа к брокерскому кабинету.
            
Для получения доступа обратитесь к администратору или в службу поддержки.""",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="💬 Обратиться в поддержку",
                    callback_data="contact_support"
                )],
                [InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data="back_to_menu"
                )]
            ])
        )
        await callback.answer()
        return
    
    # Получаем данные брокера
    broker = await broker_service.get_broker_by_telegram_id(user.telegram_id)
    
    if not broker:
        # Создаем временную заглушку для демонстрации
        class MockBroker:
            id = user.id
            name = user.first_name or "Брокер"
            ref_code = f"BR{user.id}"
            commission_rate = 0.15
        
        broker = MockBroker()
    
    # Получаем статистику
    clients_count = await broker_service.get_broker_clients_count(broker.id)
    earnings = await broker_service.get_broker_earnings(broker.id)
    
    # Вычисляем статистику за месяц (заглушка)
    month_clients = max(0, clients_count - 5)  # Демо данные
    active_applications = max(0, clients_count - 2)  # Демо данные
    
    text = MESSAGES["broker_welcome"].format(
        total_clients=clients_count,
        active_applications=active_applications,
        month_clients=month_clients,
        earnings=earnings
    )
    
    await callback.message.edit_text(text, reply_markup=get_broker_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "broker_clients")
async def show_broker_clients(callback: CallbackQuery, user: User):
    """Показать клиентов брокера"""
    
    if not user or user.role not in [UserRole.BROKER, UserRole.ADMIN]:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # TODO: Получить реальных клиентов из БД
    # Пока показываем демо данные
    
    text = """👥 ВАШИ КЛИЕНТЫ

📊 Общая статистика:
• Всего клиентов: 12
• Активных заявок: 7
• Завершенных дел: 5

📋 Последние клиенты:
• Иван И. - Диагностика завершена (вчера)
• Мария П. - Документы загружены (2 дня назад)
• Алексей С. - Заявления отправлены (3 дня назад)
• Ольга К. - Работа завершена (неделю назад)

💰 Заработок:
• За месяц: 15,750 руб.
• За все время: 47,250 руб."""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Подробная статистика",
            callback_data="broker_detailed_stats"
        )],
        [InlineKeyboardButton(
            text="📈 Экспорт отчета",
            callback_data="broker_export_report"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад в кабинет",
            callback_data="broker_mode"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "broker_stats")
async def show_broker_statistics(callback: CallbackQuery, user: User):
    """Показать статистику брокера"""
    
    if not user or user.role not in [UserRole.BROKER, UserRole.ADMIN]:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Демо статистика
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    text = f"""📊 ДЕТАЛЬНАЯ СТАТИСТИКА

📅 За сегодня:
• Новых клиентов: 2
• Завершенных дел: 1
• Заработок: 1,500 руб.

📅 За неделю:
• Новых клиентов: 8
• Завершенных дел: 3
• Заработок: 4,750 руб.

📅 За месяц:
• Новых клиентов: 23
• Завершенных дел: 12
• Заработок: 15,750 руб.

📈 Конверсия:
• Регистрация → Загрузка документов: 85%
• Диагностика → Подача заявлений: 92%
• Общая конверсия: 78%

🏆 Рейтинг: 3 место среди брокеров"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 График по дням",
            callback_data="broker_daily_chart"
        )],
        [InlineKeyboardButton(
            text="💰 Детализация заработка",
            callback_data="broker_earnings_detail"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад в кабинет",
            callback_data="broker_mode"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "broker_ref_link")
async def show_referral_link(callback: CallbackQuery, user: User):
    """Показать реферальную ссылку"""
    
    if not user or user.role not in [UserRole.BROKER, UserRole.ADMIN]:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Получаем брокера
    broker = await broker_service.get_broker_by_telegram_id(user.telegram_id)
    
    if not broker:
        # Создаем временную заглушку
        class MockBroker:
            ref_code = f"BR{user.id}"
        broker = MockBroker()
    
    # Генерируем ссылку
    ref_link = await broker_service.generate_referral_link(broker)
    
    text = MESSAGES["broker_ref_link"].format(link=ref_link)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📱 Поделиться ссылкой",
            url=f"https://t.me/share/url?url={ref_link}&text=Проверь свою кредитную историю бесплатно!"
        )],
        [InlineKeyboardButton(
            text="📋 Скопировать",
            callback_data=f"copy_ref_link_{broker.ref_code}"
        )],
        [InlineKeyboardButton(
            text="🔄 Новая ссылка",
            callback_data="regenerate_ref_code"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад в кабинет",
            callback_data="broker_mode"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("copy_ref_link_"))
async def copy_referral_link(callback: CallbackQuery):
    """Копирование реферальной ссылки"""
    
    ref_code = callback.data.split("_")[-1]
    
    # Показываем ссылку для копирования
    ref_link = f"https://t.me/your_bot?start={ref_code}"
    
    await callback.answer(
        f"Ссылка скопирована:\n{ref_link}",
        show_alert=True
    )

@router.callback_query(F.data == "broker_reports")
async def broker_reports(callback: CallbackQuery, user: User):
    """Отчеты брокера"""
    
    if not user or user.role not in [UserRole.BROKER, UserRole.ADMIN]:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    text = """📈 ОТЧЕТЫ И АНАЛИТИКА

Выберите тип отчета для формирования:"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Отчет по клиентам",
            callback_data="report_clients"
        )],
        [InlineKeyboardButton(
            text="💰 Отчет по заработку",
            callback_data="report_earnings"
        )],
        [InlineKeyboardButton(
            text="📅 Отчет за период",
            callback_data="report_period"
        )],
        [InlineKeyboardButton(
            text="📋 Сводный отчет",
            callback_data="report_summary"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад в кабинет",
            callback_data="broker_mode"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "report_summary")
async def generate_summary_report(callback: CallbackQuery, user: User):
    """Сводный отчет"""
    
    if not user or user.role not in [UserRole.BROKER, UserRole.ADMIN]:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Логируем генерацию отчета
    await user_service.log_user_action(
        user.id,
        "broker_report_generated",
        {"report_type": "summary"}
    )
    
    # Генерируем отчет (демо данные)
    report_text = f"""📋 СВОДНЫЙ ОТЧЕТ БРОКЕРА

👤 Брокер: {user.first_name}
📅 Период: {datetime.now().strftime('%d.%m.%Y')}

📊 ОСНОВНЫЕ ПОКАЗАТЕЛИ:
• Всего клиентов: 23
• Активных дел: 7
• Завершенных дел: 12
• Конверсия: 78%

💰 ФИНАНСЫ:
• Заработок за месяц: 15,750 руб.
• Средний чек: 1,312 руб.
• Комиссия: 15%

📈 ДИНАМИКА:
• Рост клиентов: +15% к прошлому месяцу
• Рост заработка: +23% к прошлому месяцу

🏆 РЕЙТИНГ: 3 место в общем зачете

Отчет сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📧 Отправить на email",
            callback_data="send_report_email"
        )],
        [InlineKeyboardButton(
            text="📊 Другие отчеты",
            callback_data="broker_reports"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад в кабинет",
            callback_data="broker_mode"
        )]
    ])
    
    await callback.message.edit_text(report_text, reply_markup=keyboard)
    await callback.answer("📋 Отчет сформирован!")

@router.callback_query(F.data == "broker_settings")
async def broker_settings(callback: CallbackQuery, user: User):
    """Настройки брокера"""
    
    if not user or user.role not in [UserRole.BROKER, UserRole.ADMIN]:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Получаем данные брокера
    broker = await broker_service.get_broker_by_telegram_id(user.telegram_id)
    
    if not broker:
        # Создаем заглушку
        class MockBroker:
            name = user.first_name or "Брокер"
            company = "Не указано"
            commission_rate = 0.15
            is_active = True
        broker = MockBroker()
    
    text = f"""⚙️ НАСТРОЙКИ БРОКЕРА

👤 Персональные данные:
• Имя: {broker.name}
• Компания: {broker.company}
• Ставка комиссии: {broker.commission_rate * 100}%
• Статус: {'✅ Активен' if broker.is_active else '❌ Неактивен'}

📱 Уведомления:
• О новых клиентах: ✅ Включены
• О завершенных делах: ✅ Включены
• Ежедневная сводка: ✅ Включена

💼 Для изменения настроек обратитесь к администратору."""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔔 Настроить уведомления",
            callback_data="broker_notifications"
        )],
        [InlineKeyboardButton(
            text="💬 Связаться с админом",
            callback_data="contact_admin"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад в кабинет",
            callback_data="broker_mode"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "broker_ref_link")
async def show_broker_referral_link(callback: CallbackQuery, user: User):
    """Показать реферальную ссылку брокера"""
    
    if not user or user.role not in [UserRole.BROKER, UserRole.ADMIN]:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Получаем брокера
    broker = await user_service.get_broker_by_telegram_id(user.telegram_id)
    if not broker:
        await callback.answer("❌ Профиль брокера не найден", show_alert=True)
        return
    
    # Получаем реферальную ссылку
    referral_link = await referral_service.get_broker_referral_link(broker.id)
    
    if not referral_link:
        await callback.answer("❌ Ошибка получения ссылки", show_alert=True)
        return
    
    # Получаем статистику
    stats = await referral_service.get_broker_stats(broker.id)
    
    conversion_display = f"{stats['conversion_rate']}%" if stats['clicks'] > 0 else "Нет данных"
    
    text = f"""🔗 РЕФЕРАЛЬНАЯ СИСТЕМА

📊 Ваша статистика:
• 👆 Клики: {stats['clicks']}
• 👥 Регистрации: {stats['registrations']} 
• 📈 Конверсия: {conversion_display}
• 💰 Заработано: {stats['total_commission']:.2f} руб.

🎯 Ваша ссылка:
`{referral_link}`

💡 Поделитесь ссылкой с потенциальными клиентами. 
Каждый зарегистрировавшийся будет привязан к вам!"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Подробная статистика",
            callback_data="referral_detailed_stats"
        )],
        [InlineKeyboardButton(
            text="🔄 Обновить код",
            callback_data="regenerate_ref_code"
        )],
        [InlineKeyboardButton(
            text="📋 Скопировать ссылку",
            callback_data="copy_ref_link"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад в кабинет",
            callback_data="broker_mode"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "referral_detailed_stats")
async def show_detailed_referral_stats(callback: CallbackQuery, user: User):
    """Показать подробную статистику рефералов"""
    
    if not user or user.role not in [UserRole.BROKER, UserRole.ADMIN]:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    broker = await user_service.get_broker_by_telegram_id(user.telegram_id)
    if not broker:
        await callback.answer("❌ Профиль брокера не найден", show_alert=True)
        return
    
    stats = await referral_service.get_broker_stats(broker.id)
    
    # Форматируем данные
    first_click = "Нет" if not stats['first_click'] else stats['first_click'].strftime('%d.%m.%Y')
    last_click = "Нет" if not stats['last_click'] else stats['last_click'].strftime('%d.%m.%Y %H:%M')
    
    text = f"""📊 ПОДРОБНАЯ СТАТИСТИКА

🎯 Общие показатели:
• 👆 Всего кликов: {stats['clicks']}
• 👥 Регистрации: {stats['registrations']}
• ✅ Конверсии: {stats['conversions']} 
• 📈 Конверсия: {stats['conversion_rate']}%

👨‍💼 Ваши клиенты:
• 📋 Всего клиентов: {stats['total_clients']}
• 🔥 Активных заявок: {stats['active_applications']}

💰 Финансы:
• 💵 Общий заработок: {stats['total_commission']:.2f} руб.
• ✅ Выплачено: {stats['paid_commission']:.2f} руб.
• ⏳ К выплате: {stats['total_commission'] - stats['paid_commission']:.2f} руб.

📅 Временные рамки:
• 🎯 Первый клик: {first_click}
• ⏰ Последний клик: {last_click}"""

    # Добавляем последние клики если есть
    if stats['recent_clicks']:
        text += "\n\n🕐 Последние переходы (7 дней):"
        for i, click in enumerate(stats['recent_clicks'][:5]):
            status = "✅" if click['converted'] else "👆"
            date = click['clicked_at'].strftime('%d.%m %H:%M')
            text += f"\n• {status} {date}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔙 К реферальной ссылке",
            callback_data="broker_ref_link"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()



@router.callback_query(F.data == "regenerate_ref_code")
async def regenerate_referral_code(callback: CallbackQuery, user: User):
    """Сгенерировать новый реферальный код"""
    
    logger.info(f"Запрос на обновление реферального кода от пользователя {callback.from_user.id}")
    
    if not user or user.role not in [UserRole.BROKER, UserRole.ADMIN]:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    broker = await user_service.get_broker_by_telegram_id(user.telegram_id)
    if not broker:
        await callback.answer("❌ Профиль брокера не найден", show_alert=True)
        return
    
    # Генерируем новый код
    new_code = await referral_service.generate_new_ref_code(broker.id)
    
    if not new_code:
        await callback.answer("❌ Ошибка генерации кода", show_alert=True)
        return
    
    new_link = f"https://t.me/{referral_service.bot_username}?start={new_code}"
    
    text = f"""🔄 КОД ОБНОВЛЕН!

✅ Новый реферальный код: `{new_code}`
🔗 Новая ссылка: `{new_link}`

⚠️ Внимание: 
• Старая ссылка больше не работает
• Вся статистика сохранена
• Поделитесь новой ссылкой с клиентами"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔙 К реферальной ссылке",
            callback_data="broker_ref_link"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer("✅ Код обновлен!")

@router.callback_query(F.data == "copy_ref_link")
async def copy_referral_link(callback: CallbackQuery):
    """Подсказка как скопировать ссылку"""
    
    await callback.answer(
        "💡 Нажмите на ссылку выше и выберите 'Копировать' в контекстном меню",
        show_alert=True
    )

# Добавляем кнопку перехода в брокерский режим в главное меню
@router.callback_query(F.data == "back_to_menu")
async def back_to_main_menu_with_broker_check(callback: CallbackQuery, user: User):
    """Возврат в главное меню с проверкой роли брокера"""
    
    # Заново получаем пользователя из БД для актуальной роли
    fresh_user = await user_service.get_user_by_telegram_id(callback.from_user.id)
    
    if fresh_user and fresh_user.role in [UserRole.BROKER, UserRole.ADMIN]:
        # Показываем расширенное меню для брокеров
        name = fresh_user.first_name or callback.from_user.first_name
        text = f"🏠 Главное меню\n\nПривет, {name}! Выберите действие:"
        
        from bot.keyboards.inline import get_main_menu_keyboard
        keyboard = get_main_menu_keyboard(fresh_user.role)
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        # Обычное меню для клиентов
        from bot.handlers.documents import back_to_main_menu
        await back_to_main_menu(callback, fresh_user or user)
    
    await callback.answer() 