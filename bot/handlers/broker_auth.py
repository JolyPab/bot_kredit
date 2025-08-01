from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from database.models import User, UserRole
from services.broker_auth_service import BrokerAuthService
from services.user_service import UserService

logger = logging.getLogger(__name__)
router = Router()

broker_auth_service = BrokerAuthService()
user_service = UserService()

class BrokerApplicationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_company = State()
    waiting_for_phone = State()
    waiting_for_email = State()
    waiting_for_experience = State()

# Заменяем старую демо-кнопку на реальную заявочную систему
@router.callback_query(F.data == "become_broker_demo")
async def start_broker_application(callback: CallbackQuery, state: FSMContext, user: User):
    """Начать подачу заявки на становление брокером"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    # Проверяем не брокер ли уже
    if user.role == UserRole.BROKER:
        await callback.message.edit_text(
            "✅ Вы уже являетесь брокером!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="👨‍💼 Открыть кабинет",
                    callback_data="broker_mode"
                )],
                [InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="settings"
                )]
            ])
        )
        await callback.answer()
        return
    
    # Проверяем статус существующих заявок
    existing_app = await broker_auth_service.get_user_application_status(user.telegram_id)
    
    if existing_app:
        if existing_app.status == "pending":
            await callback.message.edit_text(
                f"""⏳ У вас уже есть заявка на рассмотрении
                
📋 Заявка #{existing_app.id}
📅 Подана: {existing_app.created_at.strftime('%d.%m.%Y %H:%M')}
⚡ Статус: На рассмотрении

Ожидайте ответа администратора.""",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="settings"
                    )]
                ])
            )
            await callback.answer()
            return
        elif existing_app.status == "approved":
            await callback.message.edit_text(
                f"""✅ Ваша заявка одобрена!
                
📋 Заявка #{existing_app.id}
📅 Одобрена: {existing_app.processed_at.strftime('%d.%m.%Y %H:%M')}

Вам должен был прийти инвайт-код для активации. Если не получили - обратитесь в поддержку.""",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="💬 Поддержка",
                        callback_data="contact_support"
                    )],
                    [InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="settings"
                    )]
                ])
            )
            await callback.answer()
            return
        elif existing_app.status == "rejected":
            reason = existing_app.admin_comment or "Не указана"
            await callback.message.edit_text(
                f"""❌ Ваша заявка отклонена
                
📋 Заявка #{existing_app.id}
📅 Отклонена: {existing_app.processed_at.strftime('%d.%m.%Y %H:%M')}
💬 Причина: {reason}

Можете подать новую заявку.""",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📝 Подать новую заявку",
                        callback_data="new_broker_application"
                    )],
                    [InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="settings"
                    )]
                ])
            )
            await callback.answer()
            return
    
    # Начинаем новую заявку
    await start_new_application(callback, state)

@router.callback_query(F.data == "new_broker_application")
async def start_new_application(callback: CallbackQuery, state: FSMContext):
    """Начать новую заявку"""
    
    await state.set_state(BrokerApplicationStates.waiting_for_name)
    
    text = """📝 ЗАЯВКА НА СТАНОВЛЕНИЕ БРОКЕРОМ

Для подачи заявки нужно заполнить несколько полей.

👤 Шаг 1 из 5: Как вас зовут?
Напишите ваше полное имя (Фамилия Имя Отчество)"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="settings"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.message(StateFilter(BrokerApplicationStates.waiting_for_name))
async def process_broker_name(message: Message, state: FSMContext):
    """Обработка имени брокера"""
    
    full_name = message.text.strip()
    
    if len(full_name) < 3:
        await message.answer("❌ Имя слишком короткое. Введите полное имя (минимум 3 символа).")
        return
    
    await state.update_data(full_name=full_name)
    await state.set_state(BrokerApplicationStates.waiting_for_company)
    
    await message.answer(
        f"""✅ Имя сохранено: {full_name}

🏢 Шаг 2 из 5: В какой компании работаете?
Укажите название компании или напишите "Самозанятый"/"ИП" """,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🏠 Самозанятый",
                callback_data="company_self_employed"
            )],
            [InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="settings"
            )]
        ])
    )

@router.callback_query(F.data == "company_self_employed", StateFilter(BrokerApplicationStates.waiting_for_company))
async def set_self_employed(callback: CallbackQuery, state: FSMContext):
    """Установить самозанятость"""
    await state.update_data(company="Самозанятый")
    await process_company_next_step(callback, state, "Самозанятый")

@router.message(StateFilter(BrokerApplicationStates.waiting_for_company))
async def process_broker_company(message: Message, state: FSMContext):
    """Обработка компании брокера"""
    
    company = message.text.strip()
    await state.update_data(company=company)
    await process_company_next_step(message, state, company)

async def process_company_next_step(event, state: FSMContext, company: str):
    """Переход к следующему шагу после компании"""
    
    await state.set_state(BrokerApplicationStates.waiting_for_phone)
    
    text = f"""✅ Компания сохранена: {company}

📞 Шаг 3 из 5: Контактный телефон
Укажите ваш рабочий номер телефона в формате +7XXXXXXXXXX"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📱 Поделиться номером",
            callback_data="share_phone_broker"
        )],
        [InlineKeyboardButton(
            text="⏭ Пропустить",
            callback_data="skip_phone_broker"
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="settings"
        )]
    ])
    
    if hasattr(event, 'message'):
        # Это CallbackQuery
        await event.message.edit_text(text, reply_markup=keyboard)
        await event.answer()
    else:
        # Это Message
        await event.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "skip_phone_broker", StateFilter(BrokerApplicationStates.waiting_for_phone))
async def skip_phone_broker(callback: CallbackQuery, state: FSMContext):
    """Пропустить телефон"""
    await state.update_data(phone=None)
    await process_phone_next_step(callback, state)

@router.message(StateFilter(BrokerApplicationStates.waiting_for_phone))
async def process_broker_phone(message: Message, state: FSMContext):
    """Обработка телефона брокера"""
    
    phone = message.text.strip()
    await state.update_data(phone=phone)
    await process_phone_next_step(message, state)

async def process_phone_next_step(event, state: FSMContext):
    """Переход к email"""
    
    await state.set_state(BrokerApplicationStates.waiting_for_email)
    
    text = """📧 Шаг 4 из 5: Email для связи
Укажите ваш рабочий email адрес"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⏭ Пропустить",
            callback_data="skip_email_broker"
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="settings"
        )]
    ])
    
    if hasattr(event, 'message'):
        # Это CallbackQuery
        await event.message.edit_text(text, reply_markup=keyboard)
        await event.answer()
    else:
        # Это Message
        await event.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "skip_email_broker", StateFilter(BrokerApplicationStates.waiting_for_email))
async def skip_email_broker(callback: CallbackQuery, state: FSMContext):
    """Пропустить email"""
    await state.update_data(email=None)
    await process_email_next_step(callback, state)

@router.message(StateFilter(BrokerApplicationStates.waiting_for_email))
async def process_broker_email(message: Message, state: FSMContext):
    """Обработка email брокера"""
    
    email = message.text.strip()
    await state.update_data(email=email)
    await process_email_next_step(message, state)

async def process_email_next_step(event, state: FSMContext):
    """Переход к опыту"""
    
    await state.set_state(BrokerApplicationStates.waiting_for_experience)
    
    text = """💼 Шаг 5 из 5: Опыт работы
Расскажите кратко о вашем опыте:
• Сколько работаете в сфере кредитования/финансов?
• Есть ли опыт работы с кредитными историями?
• Откуда о нас узнали?

Можете написать в свободной форме или пропустить."""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⏭ Пропустить",
            callback_data="skip_experience_broker"
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="settings"
        )]
    ])
    
    if hasattr(event, 'message'):
        # Это CallbackQuery
        await event.message.edit_text(text, reply_markup=keyboard)
        await event.answer()
    else:
        # Это Message
        await event.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "skip_experience_broker", StateFilter(BrokerApplicationStates.waiting_for_experience))
async def skip_experience_broker(callback: CallbackQuery, state: FSMContext):
    """Пропустить опыт"""
    await state.update_data(experience=None)
    await submit_broker_application(callback, state)

@router.message(StateFilter(BrokerApplicationStates.waiting_for_experience))
async def process_broker_experience(message: Message, state: FSMContext):
    """Обработка опыта брокера"""
    
    experience = message.text.strip()
    await state.update_data(experience=experience)
    await submit_broker_application(message, state)

async def submit_broker_application(event, state: FSMContext):
    """Отправить заявку на рассмотрение"""
    
    data = await state.get_data()
    user_id = event.from_user.id
    username = event.from_user.username
    
    try:
        # Создаем заявку
        application = await broker_auth_service.create_broker_application(
            telegram_id=user_id,
            username=username,
            full_name=data['full_name'],
            company=data.get('company'),
            phone=data.get('phone'),
            email=data.get('email'),
            experience=data.get('experience')
        )
        
        # TODO: Отправить уведомление админу
        # await notify_admin_about_application(application)
        
        text = f"""✅ ЗАЯВКА ПОДАНА!

📋 №{application.id} от {application.created_at.strftime('%d.%m.%Y %H:%M')}

👤 {data['full_name']}
🏢 {data.get('company', 'Не указано')}

⏳ Заявка на рассмотрении (1-2 дня)
При одобрении получите инвайт-код."""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🏠 В главное меню",
                callback_data="back_to_menu"
            )]
        ])
        
        if hasattr(event, 'message'):
            # Это CallbackQuery
            await event.message.edit_text(text, reply_markup=keyboard)
            await event.answer("✅ Заявка подана!")
        else:
            # Это Message
            await event.answer(text, reply_markup=keyboard)
        
        await state.clear()
        
    except ValueError as e:
        error_text = f"❌ Ошибка: {str(e)}"
        
        if hasattr(event, 'message'):
            # Это CallbackQuery
            await event.message.edit_text(error_text)
            await event.answer()
        else:
            # Это Message
            await event.answer(error_text)

# Активация инвайт-кодов
@router.message(Command("activate"))
async def activate_invite_code(message: Message, user: User):
    """Активировать инвайт-код"""
    
    if not user:
        await message.answer("❌ Необходимо зарегистрироваться в боте через /start")
        return
    
    # Извлекаем код из команды
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer(
            """❌ Неверный формат команды.

Используйте: `/activate BR_2024_ABC`

Пример: `/activate BR_2024_K7M`"""
        )
        return
    
    code = parts[1].upper()
    
    # Проверяем не брокер ли уже
    if user.role == UserRole.BROKER:
        await message.answer("✅ Вы уже являетесь брокером!")
        return
    
    # Активируем код
    success = await broker_auth_service.activate_invite_code(code, user.id)
    
    if success:
        await message.answer(
            f"""🎉 ПОЗДРАВЛЯЕМ! 

✅ Инвайт-код `{code}` успешно активирован!
👨‍💼 Вы теперь брокер нашей платформы!

Вам доступны:
• Реферальная система для привлечения клиентов
• Статистика и аналитика по клиентам  
• Комиссионные с каждого клиента
• Брокерский кабинет с отчетами

💡 Перейдите в главное меню чтобы увидеть "Брокерский кабинет" """,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="👨‍💼 Открыть кабинет",
                    callback_data="broker_mode"
                )],
                [InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="back_to_menu"
                )]
            ])
        )
    else:
        await message.answer(
            f"""❌ Не удалось активировать код `{code}`

Возможные причины:
• Код недействителен или не существует
• Код уже использован
• Срок действия кода истек
• Технические неполадки

💬 Обратитесь в поддержку если считаете что произошла ошибка.""",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="💬 Поддержка",
                    callback_data="contact_support"
                )]
            ])
        ) 