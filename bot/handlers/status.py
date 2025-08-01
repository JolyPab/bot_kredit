from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import logging
import json
from datetime import datetime

from database.models import User, ApplicationStatus
from services.application_service import ApplicationService
from services.user_service import UserService
from bot.keyboards.inline import get_status_keyboard, get_back_button
from bot.utils.messages import MESSAGES

logger = logging.getLogger(__name__)
router = Router()

application_service = ApplicationService()
user_service = UserService()

@router.callback_query(F.data == "check_status")
async def check_application_status(callback: CallbackQuery, user: User):
    """Проверить статус заявки"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    # Получаем активную заявку пользователя
    application = await application_service.get_user_application(user.id)
    
    if not application:
        # Если нет активной заявки - предлагаем создать
        text = """📊 У вас пока нет активных заявок.
        
Чтобы начать диагностику кредитной истории, загрузите документы из БКИ."""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📋 Начать диагностику",
                callback_data="start_diagnosis"
            )],
            [InlineKeyboardButton(
                text="🔙 Назад в меню",
                callback_data="back_to_menu"
            )]
        ])
    else:
        # Формируем информацию о статусе
        status_description = application_service.get_status_description(application.status)
        next_step = application_service.get_next_step_description(application.status)
        
        # Подсчитываем документы
        documents_count = len(application.documents) if application.documents else 0
        
        # Время с момента создания
        time_diff = datetime.utcnow() - application.created_at
        if time_diff.days > 0:
            time_text = f"{time_diff.days} дн."
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            time_text = f"{hours} ч."
        else:
            minutes = time_diff.seconds // 60
            time_text = f"{minutes} мин."
        
        text = f"""📊 СТАТУС ВАШЕЙ ЗАЯВКИ #{application.id}

⚡ Текущий статус: {status_description}
📅 Создана: {application.created_at.strftime('%d.%m.%Y %H:%M')} ({time_text} назад)
📄 Документов загружено: {documents_count}

🎯 Следующий шаг:
{next_step}"""

        # Добавляем информацию о банке если указан
        if application.target_bank:
            text += f"\n🏦 Целевой банк: {application.target_bank}"
        
        # Добавляем информацию о результатах диагностики
        if application.status == ApplicationStatus.DIAGNOSIS_COMPLETED and application.diagnosis_result:
            text += "\n\n✅ GPT диагностика завершена! Результаты готовы к просмотру."
        
        # Передаем информацию о наличии результатов диагностики
        has_diagnosis_results = (
            application.status == ApplicationStatus.DIAGNOSIS_COMPLETED and 
            application.diagnosis_result is not None
        )
        keyboard = get_status_keyboard(has_diagnosis_results)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "refresh_status")
async def refresh_application_status(callback: CallbackQuery, user: User):
    """Обновить статус заявки"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    # Получаем заявку заново из БД
    application = await application_service.get_user_application(user.id)
    
    if not application:
        await callback.answer("❌ Активная заявка не найдена", show_alert=True)
        return
    
    # Логируем действие
    await user_service.log_user_action(
        user.id,
        "status_refresh",
        {"application_id": application.id}
    )
    
    # Повторно вызываем обработчик статуса
    await check_application_status(callback, user)
    await callback.answer("🔄 Статус обновлен")

@router.callback_query(F.data == "detailed_status")
async def show_detailed_status(callback: CallbackQuery, user: User):
    """Показать подробную информацию о заявке"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    application = await application_service.get_user_application(user.id)
    
    if not application:
        await callback.answer("❌ Активная заявка не найдена", show_alert=True)
        return
    
    # Получаем временную линию заявки
    timeline = await application_service.get_application_timeline(application.id)
    
    text = f"""📋 ПОДРОБНАЯ ИНФОРМАЦИЯ О ЗАЯВКЕ #{application.id}

📅 Создана: {application.created_at.strftime('%d.%m.%Y в %H:%M')}
📄 Документов: {len(application.documents) if application.documents else 0}
⚡ Статус: {application_service.get_status_description(application.status)}

📊 История изменений:"""

    # Добавляем историю статусов
    for i, event in enumerate(timeline[:5]):  # Показываем последние 5 событий
        date_str = event['date'].strftime('%d.%m %H:%M')
        status_desc = application_service.get_status_description(
            ApplicationStatus(event['status'])
        )
        text += f"\n• {date_str} - {status_desc}"
        if event['comment']:
            text += f" ({event['comment']})"
    
    # Показываем результаты диагностики если есть
    if (application.status == ApplicationStatus.DIAGNOSIS_COMPLETED and 
        application.diagnosis_result):
        text += "\n\n✅ Результаты диагностики готовы!"
        
        if application.recommendations:
            recommendations_lines = application.recommendations.split('\n')[:3]
            text += f"\n\n💡 Рекомендации:\n"
            for rec in recommendations_lines:
                text += f"• {rec}\n"
            
            if len(application.recommendations.split('\n')) > 3:
                text += "• ..."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📄 Мои документы",
            callback_data="my_documents"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад к статусу",
            callback_data="check_status"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="back_to_menu"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "view_diagnosis_results")
async def view_diagnosis_results(callback: CallbackQuery, user: User):
    """Просмотр результатов диагностики"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    application = await application_service.get_user_application(user.id)
    
    if not application or application.status != ApplicationStatus.DIAGNOSIS_COMPLETED:
        await callback.answer("❌ Результаты диагностики не готовы", show_alert=True)
        return
    
    # Логируем просмотр результатов
    await user_service.log_user_action(
        user.id,
        "diagnosis_results_viewed",
        {"application_id": application.id}
    )
    
    text = f"""📊 РЕЗУЛЬТАТЫ ДИАГНОСТИКИ КИ

📋 Заявка #{application.id}
✅ Анализ завершен: {application.updated_at.strftime('%d.%m.%Y в %H:%M')}

"""

    # Показываем рекомендации
    if application.recommendations:
        text += "💡 Рекомендации по улучшению:\n"
        recommendations = application.recommendations.split('\n')
        for i, rec in enumerate(recommendations[:5], 1):
            if rec.strip():
                text += f"{i}. {rec.strip()}\n"
        
        if len(recommendations) > 5:
            text += f"...и еще {len(recommendations) - 5} рекомендаций"
    else:
        text += "📝 Подробные результаты будут доступны в ближайшее время."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📤 Подать заявления в БКИ",
            callback_data="submit_applications"
        )],
        [InlineKeyboardButton(
            text="💬 Консультация",
            callback_data="contact_support"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад к статусу",
            callback_data="check_status"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "submit_applications")
async def submit_applications_confirmation(callback: CallbackQuery, user: User):
    """Подтверждение подачи заявлений в БКИ"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    application = await application_service.get_user_application(user.id)
    
    if not application or application.status != ApplicationStatus.DIAGNOSIS_COMPLETED:
        await callback.answer("❌ Диагностика не завершена", show_alert=True)
        return
    
    # Проверяем согласие на подачу заявлений
    permissions = await user_service.check_user_permissions(user)
    if not permissions['can_submit_applications']:
        await callback.message.edit_text(
            "❌ Для подачи заявлений необходимо согласие на представительство.\n\n"
            "Обратитесь в поддержку для оформления дополнительных согласий.",
            reply_markup=get_back_button()
        )
        await callback.answer()
        return
    
    text = """📤 ПОДАЧА ЗАЯВЛЕНИЙ В БКИ

⚠️ Внимание! Вы собираетесь подать заявления на исправление ошибок в кредитной истории.

📋 Что будет сделано:
• Сформированы заявления на основе найденных ошибок
• Заявления отправлены в соответствующие БКИ
• Начнется процесс рассмотрения (до 30 дней)

💰 Стоимость услуги будет списана после подтверждения.

Подтверждаете подачу заявлений?"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Да, подать заявления",
            callback_data="confirm_submit_applications"
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="view_diagnosis_results"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "confirm_submit_applications")
async def confirm_submit_applications(callback: CallbackQuery, user: User):
    """Подтверждение и подача заявлений"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    application = await application_service.get_user_application(user.id)
    
    if not application:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    # Обновляем статус на "заявления отправлены"
    success = await application_service.update_application_status(
        application.id,
        ApplicationStatus.APPLICATIONS_SENT,
        "Заявления поданы в БКИ пользователем",
        "user"
    )
    
    if success:
        # Логируем действие
        await user_service.log_user_action(
            user.id,
            "applications_submitted",
            {"application_id": application.id}
        )
        
        text = """✅ ЗАЯВЛЕНИЯ УСПЕШНО ПОДАНЫ!

📤 Ваши заявления отправлены в БКИ.

⏰ Сроки рассмотрения:
• НБКИ: до 30 дней
• ОКБ: до 30 дней  
• Эквифакс: до 30 дней

📱 Уведомления:
Мы будем информировать вас о статусе рассмотрения и результатах.

💡 Рекомендация:
Следите за обновлениями статуса в боте."""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📊 Проверить статус",
                callback_data="check_status"
            )],
            [InlineKeyboardButton(
                text="💬 Поддержка",
                callback_data="contact_support"
            )],
            [InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="back_to_menu"
            )]
        ])
    else:
        text = "❌ Произошла ошибка при подаче заявлений. Попробуйте еще раз или обратитесь в поддержку."
        keyboard = get_back_button()
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "view_gpt_results")
async def view_gpt_diagnosis_results(callback: CallbackQuery, user: User):
    """Показать результаты GPT диагностики"""
    
    if not user:
        await callback.answer("❌ Необходимо зарегистрироваться", show_alert=True)
        return
    
    application = await application_service.get_user_application(user.id)
    
    if not application or not application.diagnosis_result:
        await callback.answer("❌ Результаты диагностики не найдены", show_alert=True)
        return
    
    try:
        # Парсим результаты диагностики
        diagnosis_data = json.loads(application.diagnosis_result)
        
        # Формируем красивое сообщение
        text = "🤖 **РЕЗУЛЬТАТЫ GPT ДИАГНОСТИКИ**\n\n"
        
        # Добавляем информацию о блоках
        blocks = diagnosis_data.get("blocks", {})
        
        if blocks:
            text += "📋 **НАЙДЕННЫЕ ОШИБКИ:**\n\n"
            
            for block_name, block_content in blocks.items():
                if "ошибок не выявлено" not in block_content.lower():
                    # Определяем критичность
                    if "🟥" in block_content:
                        criticality = "🟥 КРИТИЧНО"
                    elif "🟨" in block_content:
                        criticality = "🟨 ВАЖНО"
                    else:
                        criticality = "🟩 НЕЗНАЧИТЕЛЬНО"
                    
                    text += f"▫️ {block_name}\n"
                    text += f"   {criticality}\n\n"
        
        # Добавляем дату анализа
        parsed_at = diagnosis_data.get("parsed_at", "")
        if parsed_at:
            try:
                date_obj = datetime.fromisoformat(parsed_at.replace('Z', '+00:00'))
                formatted_date = date_obj.strftime("%d.%m.%Y %H:%M")
                text += f"🕐 Анализ: {formatted_date}\n\n"
            except:
                pass
        
        # Добавляем призыв к действию
        text += "💼 **Нужна помощь в исправлении ошибок?**\n"
        text += "Обратитесь к специалистам!"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📄 Подробный отчет",
                callback_data="detailed_gpt_report"
            )],
            [InlineKeyboardButton(
                text="💬 Связаться",
                callback_data="contact_support"
            )],
            [InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="check_status"
            )]
        ])
        
        # Логируем просмотр результатов
        await user_service.log_user_action(
            user.id,
            "gpt_results_viewed",
            {"application_id": application.id}
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка отображения результатов GPT: {e}")
        await callback.answer("❌ Ошибка при загрузке результатов", show_alert=True) 