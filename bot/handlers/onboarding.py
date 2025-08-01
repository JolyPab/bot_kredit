from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import re
import logging

from services.user_service import UserService
from services.referral_service import ReferralService
from bot.keyboards.inline import get_consent_keyboard, get_main_menu_keyboard
from bot.utils.messages import MESSAGES
from database.models import UserRole

logger = logging.getLogger(__name__)
router = Router()

class OnboardingStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_email = State()
    waiting_for_consent = State()

user_service = UserService()
referral_service = ReferralService()



@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    
    # Извлекаем реферальный код брокера из ссылки
    broker_ref_code = None
    if message.text and len(message.text.split()) > 1:
        broker_ref_code = message.text.split()[1]
        
        # Трекаем клик по реферальной ссылке
        await referral_service.track_referral_click(
            ref_code=broker_ref_code,
            telegram_id=message.from_user.id
        )
    
    # Проверяем, существует ли пользователь
    user = await user_service.get_user_by_telegram_id(message.from_user.id)
    
    if user:
        # Пользователь уже зарегистрирован
        await message.answer(
            MESSAGES["welcome_back"].format(
                name=user.first_name or message.from_user.first_name
            ),
            reply_markup=get_main_menu_keyboard(user.role)
        )
        await state.clear()
    else:
        # Новый пользователь - запускаем онбординг
        await state.update_data(broker_ref_code=broker_ref_code)
        
        # Создаем пользователя
        user = await user_service.create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            broker_ref_code=broker_ref_code
        )
        
        # Трекаем регистрацию по реферальной ссылке
        if broker_ref_code:
            await referral_service.track_referral_registration(
                user_id=user.id,
                ref_code=broker_ref_code
            )
        
        welcome_text = MESSAGES["welcome_new_user"].format(
            name=message.from_user.first_name
        )
        
        if broker_ref_code:
            welcome_text += MESSAGES["broker_referral_info"]
        
        await message.answer(welcome_text)
        
        # Запрашиваем телефон
        await message.answer(
            MESSAGES["request_phone"],
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📱 Поделиться номером", 
                    callback_data="share_contact"
                )]
            ])
        )
        await state.set_state(OnboardingStates.waiting_for_phone)

@router.callback_query(F.data == "share_contact")
async def request_contact(callback: CallbackQuery, state: FSMContext):
    """Запрос контакта пользователя"""
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback.message.edit_text(
        "Нажмите кнопку ниже, чтобы поделиться номером телефона:"
    )
    await callback.message.answer(
        "👇 Нажмите кнопку для отправки номера:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.message(F.contact, StateFilter(OnboardingStates.waiting_for_phone))
async def process_contact(message: Message, state: FSMContext):
    """Обработка полученного контакта"""
    from aiogram.types import ReplyKeyboardRemove
    
    if message.contact.user_id != message.from_user.id:
        await message.answer(
            "❌ Пожалуйста, отправьте свой номер телефона, а не чужой.",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    
    # Сохраняем телефон
    user = await user_service.get_user_by_telegram_id(message.from_user.id)
    await user_service.update_user_contact_info(user.id, phone=phone)
    
    await message.answer(
        "✅ Номер телефона сохранен!\n\n" + MESSAGES["request_email"],
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(OnboardingStates.waiting_for_email)

@router.message(F.text, StateFilter(OnboardingStates.waiting_for_phone))
async def process_phone_text(message: Message, state: FSMContext):
    """Обработка телефона введенного текстом"""
    phone = message.text.strip()
    
    # Валидация телефона
    phone_pattern = r'^(\+7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
    if not re.match(phone_pattern, phone):
        await message.answer(
            "❌ Неверный формат номера телефона.\n"
            "Пример правильного формата: +79123456789"
        )
        return
    
    # Нормализуем номер
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    if phone.startswith('8'):
        phone = '+7' + phone[1:]
    elif phone.startswith('7'):
        phone = '+7' + phone[1:]
    elif not phone.startswith('+7'):
        phone = '+7' + phone
    
    await state.update_data(phone=phone)
    
    # Сохраняем телефон
    user = await user_service.get_user_by_telegram_id(message.from_user.id)
    await user_service.update_user_contact_info(user.id, phone=phone)
    
    await message.answer(
        "✅ Номер телефона сохранен!\n\n" + MESSAGES["request_email"]
    )
    await state.set_state(OnboardingStates.waiting_for_email)

@router.message(F.text, StateFilter(OnboardingStates.waiting_for_email))
async def process_email(message: Message, state: FSMContext):
    """Обработка email адреса"""
    email = message.text.strip()
    
    # Валидация email
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        await message.answer(
            "❌ Неверный формат email адреса.\n"
            "Пример правильного формата: example@mail.com"
        )
        return
    
    await state.update_data(email=email)
    
    # Сохраняем email
    user = await user_service.get_user_by_telegram_id(message.from_user.id)
    await user_service.update_user_contact_info(user.id, email=email)
    
    await message.answer(
        "✅ Email адрес сохранен!\n\n" + MESSAGES["request_consent"],
        reply_markup=get_consent_keyboard()
    )
    await state.set_state(OnboardingStates.waiting_for_consent)

@router.callback_query(F.data == "consent_agree", StateFilter(OnboardingStates.waiting_for_consent))
async def process_consent_agree(callback: CallbackQuery, state: FSMContext):
    """Обработка согласия на обработку ПД"""
    
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)
    await user_service.set_user_consent(
        user.id,
        pd_consent=True,
        application_consent=True
    )
    
    await callback.message.edit_text(
        "✅ " + MESSAGES["consent_accepted"],
        reply_markup=None
    )
    
    await callback.message.answer(
        MESSAGES["onboarding_complete"],
        reply_markup=get_main_menu_keyboard(UserRole.CLIENT)
    )
    
    await state.clear()
    await callback.answer("✅ Регистрация завершена!")

@router.callback_query(F.data == "consent_decline", StateFilter(OnboardingStates.waiting_for_consent))
async def process_consent_decline(callback: CallbackQuery, state: FSMContext):
    """Обработка отказа от согласия"""
    
    await callback.message.edit_text(
        MESSAGES["consent_declined"],
        reply_markup=None
    )
    
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "show_consent_details")
async def show_consent_details(callback: CallbackQuery):
    """Показать детали согласия на обработку ПД"""
    
    await callback.message.answer(
        MESSAGES["consent_details"],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Назад к согласию", callback_data="back_to_consent")]
        ])
    )
    await callback.answer() 