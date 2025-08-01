from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import logging

from database.models import User, UserRole
from services.broker_auth_service import BrokerAuthService
from services.user_service import UserService

logger = logging.getLogger(__name__)
router = Router()

broker_auth_service = BrokerAuthService()
user_service = UserService()

# Список админов (можно вынести в конфиг)
ADMIN_TELEGRAM_IDS = [762169219]  # Добавляем для тестирования

def is_admin(user: User) -> bool:
    """Проверить является ли пользователь админом"""
    if not user:
        return False
    
    # Проверяем роль админа в БД
    if user.role == UserRole.ADMIN:
        return True
    
    # Или проверяем по списку ID (резервный способ)
    return user.telegram_id in ADMIN_TELEGRAM_IDS

@router.message(Command("admin"))
async def admin_menu(message: Message, user: User):
    """Админское меню"""
    
    if not is_admin(user):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    pending_count = len(await broker_auth_service.get_pending_applications())
    
    text = f"""👑 АДМИНСКАЯ ПАНЕЛЬ

📋 Заявок на рассмотрении: {pending_count}

Доступные команды:
• `/applications` - Список заявок брокеров
• `/codes` - Создать инвайт-код вручную
• `/make_admin @username` - Сделать пользователя админом
• `/stats` - Общая статистика"""

    await message.answer(text)

@router.message(Command("applications"))
async def show_applications(message: Message, user: User):
    """Показать заявки брокеров"""
    
    if not is_admin(user):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    applications = await broker_auth_service.get_pending_applications()
    
    if not applications:
        await message.answer("📋 Нет заявок на рассмотрении")
        return
    
    text = "📋 ЗАЯВКИ БРОКЕРОВ НА РАССМОТРЕНИИ:\n\n"
    
    for app in applications[:10]:  # Показываем первые 10
        text += f"""#{app.id} | {app.full_name}
🏢 {app.company or 'Не указано'}
📅 {app.created_at.strftime('%d.%m.%Y %H:%M')}
👤 @{app.username or 'no_username'}

"""
    
    text += f"\n💡 Для детального просмотра: `/app [номер]`\nПример: `/app {applications[0].id}`"
    
    await message.answer(text)

@router.message(Command("app"))
async def show_application_details(message: Message, user: User):
    """Показать детали заявки"""
    
    if not is_admin(user):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    # Извлекаем ID заявки
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❌ Использование: `/app [номер_заявки]`\nПример: `/app 1`")
        return
    
    try:
        app_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Номер заявки должен быть числом")
        return
    
    application = await broker_auth_service.get_application_by_id(app_id)
    
    if not application:
        await message.answer(f"❌ Заявка #{app_id} не найдена")
        return
    
    text = f"""📋 ЗАЯВКА БРОКЕРА #{application.id}

👤 Данные заявителя:
• Имя: {application.full_name}
• Компания: {application.company or 'Не указано'}
• Телефон: {application.phone or 'Не указан'}
• Email: {application.email or 'Не указан'}
• Telegram: @{application.username or 'no_username'} (ID: {application.telegram_id})

💼 Опыт работы:
{application.experience or 'Не указан'}

📅 Подана: {application.created_at.strftime('%d.%m.%Y в %H:%M')}
⚡ Статус: {application.status}

Команды для управления:
• `/approve {app_id}` - Одобрить заявку
• `/reject {app_id} [причина]` - Отклонить заявку"""

    await message.answer(text)

@router.message(Command("approve"))
async def approve_application(message: Message, user: User):
    """Одобрить заявку брокера"""
    
    if not is_admin(user):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    # Извлекаем ID заявки
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Использование: `/approve [номер_заявки] [комментарий]`")
        return
    
    try:
        app_id = int(parts[1])
        comment = " ".join(parts[2:]) if len(parts) > 2 else "Заявка одобрена"
    except ValueError:
        await message.answer("❌ Номер заявки должен быть числом")
        return
    
    application = await broker_auth_service.get_application_by_id(app_id)
    if not application:
        await message.answer(f"❌ Заявка #{app_id} не найдена")
        return
    
    if application.status != "pending":
        await message.answer(f"❌ Заявка #{app_id} уже обработана (статус: {application.status})")
        return
    
    try:
        # Одобряем заявку и создаем инвайт-код
        invite_code = await broker_auth_service.approve_application(
            app_id=app_id,
            admin_user_id=user.id,
            admin_comment=comment
        )
        
        # Отправляем код заявителю
        await send_invite_code_to_user(message.bot, application.telegram_id, invite_code.code)
        
        await message.answer(
            f"""✅ Заявка #{app_id} одобрена!

👤 Заявитель: {application.full_name}
🎫 Код: `{invite_code.code}`
⏰ Действует до: {invite_code.expires_at.strftime('%d.%m.%Y %H:%M')}

Инвайт-код отправлен заявителю в личные сообщения."""
        )
        
    except Exception as e:
        logger.error(f"Ошибка одобрения заявки {app_id}: {e}")
        await message.answer(f"❌ Ошибка при одобрении заявки: {str(e)}")

@router.message(Command("reject"))
async def reject_application(message: Message, user: User):
    """Отклонить заявку брокера"""
    
    if not is_admin(user):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    # Извлекаем ID заявки и причину
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Использование: `/reject [номер_заявки] [причина]`")
        return
    
    try:
        app_id = int(parts[1])
        reason = " ".join(parts[2:]) if len(parts) > 2 else "Заявка отклонена"
    except ValueError:
        await message.answer("❌ Номер заявки должен быть числом")
        return
    
    application = await broker_auth_service.get_application_by_id(app_id)
    if not application:
        await message.answer(f"❌ Заявка #{app_id} не найдена")
        return
    
    if application.status != "pending":
        await message.answer(f"❌ Заявка #{app_id} уже обработана (статус: {application.status})")
        return
    
    try:
        # Отклоняем заявку
        await broker_auth_service.reject_application(
            app_id=app_id,
            admin_user_id=user.id,
            admin_comment=reason
        )
        
        # Уведомляем заявителя
        await notify_user_about_rejection(message.bot, application.telegram_id, reason)
        
        await message.answer(
            f"""❌ Заявка #{app_id} отклонена

👤 Заявитель: {application.full_name}
💬 Причина: {reason}

Заявитель уведомлен об отклонении."""
        )
        
    except Exception as e:
        logger.error(f"Ошибка отклонения заявки {app_id}: {e}")
        await message.answer(f"❌ Ошибка при отклонении заявки: {str(e)}")

@router.message(Command("codes"))
async def create_manual_invite_code(message: Message, user: User):
    """Создать инвайт-код вручную"""
    
    if not is_admin(user):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    try:
        invite_code = await broker_auth_service.create_manual_invite_code(
            admin_user_id=user.id,
            expires_days=7
        )
        
        await message.answer(
            f"""🎫 ИНВАЙТ-КОД СОЗДАН

🔑 Код: `{invite_code.code}`
⏰ Действует до: {invite_code.expires_at.strftime('%d.%m.%Y %H:%M')}
👤 Создал: {user.first_name or user.username}

Отправьте этот код брокеру для активации.
Активация: `/activate {invite_code.code}`"""
        )
        
    except Exception as e:
        logger.error(f"Ошибка создания кода: {e}")
        await message.answer(f"❌ Ошибка создания кода: {str(e)}")

@router.message(Command("make_admin"))
async def make_user_admin(message: Message, user: User):
    """Сделать пользователя админом"""
    
    if not is_admin(user):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    # Пока простая заглушка
    await message.answer(
        """👑 НАЗНАЧЕНИЕ АДМИНА

Функция в разработке. Пока можно:
1. Вручную изменить роль в БД: `UPDATE users SET role = 'admin' WHERE telegram_id = ID`
2. Добавить ID в список ADMIN_TELEGRAM_IDS в коде"""
    )

@router.message(Command("reset_role"))
async def reset_user_role(message: Message, user: User):
    """Сбросить роль пользователя для тестирования"""
    
    if not is_admin(user):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    # Извлекаем ID пользователя
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❌ Использование: `/reset_role [telegram_id]`\nПример: `/reset_role 762169219`")
        return
    
    try:
        target_telegram_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом")
        return
    
    # Получаем пользователя
    target_user = await user_service.get_user_by_telegram_id(target_telegram_id)
    if not target_user:
        await message.answer(f"❌ Пользователь с ID {target_telegram_id} не найден")
        return
    
    # Сбрасываем роль на CLIENT
    try:
        from sqlalchemy import update
        from database.database import get_db_session
        from database.models import User as UserModel
        
        async with get_db_session() as session:
            await session.execute(
                update(UserModel)
                .where(UserModel.telegram_id == target_telegram_id)
                .values(role=UserRole.CLIENT)
            )
            await session.commit()
        
        await message.answer(
            f"""✅ Роль сброшена!
            
👤 Пользователь: {target_user.first_name or 'Неизвестно'}
🆔 Telegram ID: {target_telegram_id}
🔄 Новая роль: CLIENT

Теперь он может подать заявку на становление брокером."""
        )
        
    except Exception as e:
        logger.error(f"Ошибка сброса роли: {e}")
        await message.answer(f"❌ Ошибка сброса роли: {str(e)}")

@router.message(Command("reset_me"))
async def reset_my_role(message: Message, user: User):
    """Сбросить свою роль (для тестирования)"""
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    if user.role == UserRole.CLIENT:
        await message.answer("✅ У вас уже роль клиента")
        return
    
    try:
        from sqlalchemy import update
        from database.database import get_db_session
        from database.models import User as UserModel
        
        async with get_db_session() as session:
            await session.execute(
                update(UserModel)
                .where(UserModel.telegram_id == user.telegram_id)
                .values(role=UserRole.CLIENT)
            )
            await session.commit()
        
        await message.answer(
            """✅ Ваша роль сброшена на "клиент"!
            
🔄 Теперь вы можете:
• Подать заявку на становление брокером
• Протестировать новую систему авторизации

⚙️ Настройки → 👨‍💼 Стать брокером"""
        )
        
    except Exception as e:
        logger.error(f"Ошибка сброса роли: {e}")
        await message.answer(f"❌ Ошибка сброса роли: {str(e)}")

async def send_invite_code_to_user(bot, telegram_id: int, code: str):
    """Отправить инвайт-код пользователю"""
    try:
        await bot.send_message(
            telegram_id,
            f"""🎉 ПОЗДРАВЛЯЕМ!

✅ Ваша заявка на становление брокером одобрена!

🎫 Ваш инвайт-код: `{code}`

Для активации отправьте команду:
`/activate {code}`

⏰ Код действует 7 дней.

Добро пожаловать в команду! 👨‍💼"""
        )
    except Exception as e:
        logger.error(f"Не удалось отправить код пользователю {telegram_id}: {e}")

async def notify_user_about_rejection(bot, telegram_id: int, reason: str):
    """Уведомить пользователя об отклонении"""
    try:
        await bot.send_message(
            telegram_id,
            f"""😔 К сожалению, ваша заявка на становление брокером отклонена.

💬 Причина: {reason}

Вы можете подать новую заявку через бота, исправив указанные замечания.

💬 Если у вас есть вопросы - обратитесь в поддержку."""
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {telegram_id}: {e}") 