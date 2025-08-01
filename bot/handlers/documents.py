from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
import logging

from database.models import User, DocumentType
from services.document_service import DocumentService
from services.user_service import UserService
from services.application_service import ApplicationService
from bot.keyboards.inline import (
    get_document_upload_keyboard, 
    get_back_button,
    get_main_menu_keyboard
)
from bot.utils.messages import MESSAGES

logger = logging.getLogger(__name__)
router = Router()

class DocumentStates(StatesGroup):
    waiting_for_document = State()
    selecting_bank = State()

document_service = DocumentService()
user_service = UserService()
application_service = ApplicationService()

@router.callback_query(F.data == "start_diagnosis")
async def start_diagnosis(callback: CallbackQuery, user: User):
    """Начать диагностику КИ"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    # Проверяем права пользователя
    permissions = await user_service.check_user_permissions(user)
    if not permissions['can_upload_documents']:
        await callback.message.edit_text(
            MESSAGES["error_no_permission"],
            reply_markup=get_back_button()
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        MESSAGES["start_diagnosis_info"],
        reply_markup=get_document_upload_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "my_documents")
async def show_my_documents(callback: CallbackQuery, user: User):
    """Показать документы пользователя"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    # Получаем статистику документов
    stats = await document_service.get_documents_stats(user.id)
    documents = await document_service.get_user_documents(user.id)
    
    if not documents:
        text = """📄 У вас пока нет загруженных документов.
        
Для начала диагностики кредитной истории загрузите отчеты из БКИ."""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📋 Загрузить документы",
                callback_data="start_diagnosis"
            )],
            [InlineKeyboardButton(
                text="🔙 Назад в меню",
                callback_data="back_to_menu"
            )]
        ])
    else:
        text = f"""📄 ВАШИ ДОКУМЕНТЫ
        
📊 Всего загружено: {stats['total']}
✅ Обработано: {stats['processed']}
⏳ В обработке: {stats['total'] - stats['processed']}

📋 По типам:
• НБКИ: {stats['by_type'].get('credit_report_nbki', 0)}
• ОКБ: {stats['by_type'].get('credit_report_okb', 0)}
• Эквифакс: {stats['by_type'].get('credit_report_equifax', 0)}"""
        
        # Создаем клавиатуру с документами
        inline_kb = []
        for i, doc in enumerate(documents[:5]):  # Показываем только последние 5
            status_emoji = "✅" if doc.is_processed else "⏳"
            doc_type_name = {
                'credit_report_nbki': 'НБКИ',
                'credit_report_okb': 'ОКБ', 
                'credit_report_equifax': 'Эквифакс',
                'passport': 'Паспорт',
                'other': 'Другое'
            }.get(doc.file_type.value, doc.file_type.value)
            
            inline_kb.append([InlineKeyboardButton(
                text=f"{status_emoji} {doc_type_name} - {doc.file_name[:20]}...",
                callback_data=f"view_doc_{doc.id}"
            )])
        
        inline_kb.extend([
            [InlineKeyboardButton(
                text="📋 Загрузить еще",
                callback_data="start_diagnosis"
            )],
            [InlineKeyboardButton(
                text="🔙 Назад в меню",
                callback_data="back_to_menu"
            )]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("upload_"))
async def handle_upload_type(callback: CallbackQuery, state: FSMContext, user: User):
    """Обработка выбора типа документа"""
    
    upload_type = callback.data.split("_")[1]
    
    # Определяем тип документа
    document_type_map = {
        "nbki": DocumentType.CREDIT_REPORT_NBKI,
        "okb": DocumentType.CREDIT_REPORT_OKB,
        "equifax": DocumentType.CREDIT_REPORT_EQUIFAX,
        "other": DocumentType.OTHER
    }
    
    document_type = document_type_map.get(upload_type, DocumentType.OTHER)
    
    # Определяем название типа для пользователя
    type_names = {
        "nbki": "НБКИ",
        "okb": "ОКБ",
        "equifax": "Эквифакс",
        "other": "другой документ"
    }
    
    type_name = type_names.get(upload_type, "документ")
    
    await state.update_data(document_type=document_type)
    await state.set_state(DocumentStates.waiting_for_document)
    
    text = f"""📤 Загрузка отчета {type_name}

📋 Инструкция:
1. Отправьте PDF файл отчета из БКИ
2. Размер файла не более 20 МБ
3. Принимаются форматы: PDF, JPG, PNG

⚠️ Важно: загружайте только официальные отчеты из БКИ!"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="back_to_menu"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.message(F.document, StateFilter(DocumentStates.waiting_for_document))
async def handle_document_upload(message: Message, state: FSMContext, user: User, bot: Bot):
    """Обработка загруженного документа"""
    
    if not user:
        await message.answer("❌ Необходимо зарегистрироваться")
        return
    
    document = message.document
    state_data = await state.get_data()
    document_type = state_data.get('document_type', DocumentType.OTHER)
    
    # Проверяем формат файла
    if not await document_service.validate_file_format(document.file_name):
        await message.answer(
            MESSAGES["error_wrong_file_format"],
            reply_markup=get_back_button()
        )
        return
    
    # Проверяем размер файла
    if not await document_service.check_file_size(document.file_size):
        size_mb = round(document.file_size / (1024 * 1024), 2)
        await message.answer(
            MESSAGES["error_file_too_large"].format(size=size_mb),
            reply_markup=get_back_button()
        )
        return
    
    try:
        # Уведомляем о начале загрузки
        progress_msg = await message.answer("📤 Загружаю документ...")
        
        # Скачиваем файл
        file_info = await bot.get_file(document.file_id)
        file_data = await bot.download_file(file_info.file_path)
        
        # Сохраняем документ
        saved_document = await document_service.save_document(
            user=user,
            file_data=file_data.read(),
            file_name=document.file_name,
            file_type=document_type
        )
        
        # Логируем действие
        await user_service.log_user_action(
            user.id,
            "document_uploaded",
            {
                "document_id": saved_document.id,
                "file_name": document.file_name,
                "file_type": document_type.value,
                "file_size": document.file_size
            }
        )
        
        # Проверяем возможность автозапуска диагностики
        diagnosis_started = False
        diagnosis_status = ""
        
        try:
            # Получаем или создаем заявку
            application = await application_service.get_user_application(user.id)
            if not application:
                # Создаем новую заявку
                application = await application_service.create_application(user)
            
            # Проверяем готовность для диагностики
            if await application_service.check_documents_ready_for_diagnosis(application.id):
                logger.info(f"Автозапуск диагностики для пользователя {user.id}")
                
                # Запускаем диагностику
                diagnosis_started = await application_service.start_diagnosis(application.id)
                
                if diagnosis_started:
                    diagnosis_status = "\n\n🤖 GPT диагностика запущена автоматически!"
                else:
                    diagnosis_status = "\n\n⚠️ Документы готовы, но диагностика не запустилась. Попробуйте позже."
            else:
                diagnosis_status = "\n\n📋 Загрузите остальные отчеты БКИ для запуска диагностики."
                
        except Exception as e:
            logger.error(f"Ошибка автозапуска диагностики: {e}")
            diagnosis_status = "\n\n⚠️ Документ загружен, но возникла ошибка при запуске диагностики."
        
        await progress_msg.delete()
        
        # Формируем сообщение в зависимости от результата
        if diagnosis_started:
            message_text = f"""✅ Документ загружен! 🤖 Диагностика запущена!

📄 Файл: {document.file_name}
📊 Размер: {round(document.file_size / (1024 * 1024), 2)} МБ
📋 Тип: {document_type.value}

🔍 GPT анализирует вашу кредитную историю...
⏱️ Результаты будут готовы через 2-5 минут!"""
        else:
            message_text = f"""✅ Документ успешно загружен!
            
📄 Файл: {document.file_name}
📊 Размер: {round(document.file_size / (1024 * 1024), 2)} МБ
📋 Тип: {document_type.value}{diagnosis_status}"""
        
        await message.answer(
            message_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📋 Загрузить еще документы",
                    callback_data="start_diagnosis"
                )],
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
        
    except Exception as e:
        logger.error(f"Ошибка загрузки документа: {e}")
        await message.answer(
            "❌ Произошла ошибка при загрузке документа. Попробуйте еще раз или обратитесь в поддержку.",
            reply_markup=get_back_button()
        )

@router.message(StateFilter(DocumentStates.waiting_for_document))
async def handle_wrong_document_type(message: Message):
    """Обработка неправильного типа сообщения при ожидании документа"""
    
    await message.answer(
        "❌ Пожалуйста, отправьте документ в виде файла (PDF, JPG или PNG).\n\n"
        "Если хотите отменить загрузку, нажмите кнопку \"Отмена\" выше."
    )

@router.callback_query(F.data.startswith("view_doc_"))
async def view_document_details(callback: CallbackQuery, user: User):
    """Просмотр деталей документа"""
    
    document_id = int(callback.data.split("_")[2])
    document = await document_service.get_document_by_id(document_id)
    
    if not document or document.user_id != user.id:
        await callback.answer("❌ Документ не найден", show_alert=True)
        return
    
    status_text = "✅ Обработан" if document.is_processed else "⏳ В обработке"
    
    doc_type_name = {
        'credit_report_nbki': 'НБКИ',
        'credit_report_okb': 'ОКБ',
        'credit_report_equifax': 'Эквифакс',
        'passport': 'Паспорт',
        'other': 'Другое'
    }.get(document.file_type.value, document.file_type.value)
    
    text = f"""📄 ДЕТАЛИ ДОКУМЕНТА

📋 Название: {document.file_name}
📊 Тип: {doc_type_name}
💾 Размер: {round(document.file_size / (1024 * 1024), 2)} МБ
📅 Загружен: {document.uploaded_at.strftime('%d.%m.%Y %H:%M')}
⚡ Статус: {status_text}"""

    if document.is_processed and document.processed_at:
        text += f"\n🕐 Обработан: {document.processed_at.strftime('%d.%m.%Y %H:%M')}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 Удалить документ",
            callback_data=f"delete_doc_{document.id}"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад к документам",
            callback_data="my_documents"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("delete_doc_"))
async def confirm_delete_document(callback: CallbackQuery):
    """Подтверждение удаления документа"""
    
    document_id = callback.data.split("_")[2]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, удалить",
                callback_data=f"confirm_delete_{document_id}"
            ),
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=f"view_doc_{document_id}"
            )
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить этот документ?\n\n"
        "Восстановить документ будет невозможно!",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_"))
async def delete_document(callback: CallbackQuery, user: User):
    """Удаление документа"""
    
    document_id = int(callback.data.split("_")[2])
    document = await document_service.get_document_by_id(document_id)
    
    if not document or document.user_id != user.id:
        await callback.answer("❌ Документ не найден", show_alert=True)
        return
    
    # Удаляем документ
    success = await document_service.delete_document(document)
    
    if success:
        # Логируем действие
        await user_service.log_user_action(
            user.id,
            "document_deleted",
            {
                "document_id": document_id,
                "file_name": document.file_name
            }
        )
        
        await callback.message.edit_text(
            "✅ Документ успешно удален.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📄 Мои документы",
                    callback_data="my_documents"
                )],
                [InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="back_to_menu"
                )]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при удалении документа. Попробуйте еще раз или обратитесь в поддержку.",
            reply_markup=get_back_button()
        )
    
    await callback.answer()

@router.callback_query(F.data == "back_to_menu")
async def back_to_main_menu(callback: CallbackQuery, user: User):
    """Возврат в главное меню"""
    
    if user:
        name = user.first_name or callback.from_user.first_name
        text = f"🏠 Главное меню\n\nПривет, {name}! Выберите действие:"
    else:
        text = MESSAGES["main_menu"]
    
    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu_keyboard(user.role if user else None)
    )
    await callback.answer() 