from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import User, Broker, UserRole, UserLog
from database.database import get_db_session
from services.encryption_service import EncryptionService
import logging

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для работы с пользователями"""
    
    def __init__(self):
        self.encryption = EncryptionService()
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID"""
        async with get_db_session() as session:
            result = await session.execute(
                select(User)
                .options(selectinload(User.broker))
                .where(User.telegram_id == telegram_id)
            )
            return result.scalars().first()
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        async with get_db_session() as session:
            result = await session.execute(
                select(User)
                .options(selectinload(User.broker))
                .where(User.id == user_id)
            )
            return result.scalars().first()
    
    async def create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        broker_ref_code: Optional[str] = None
    ) -> User:
        """Создать нового пользователя"""
        
        async with get_db_session() as session:
            # Проверяем привязку к брокеру
            broker = None
            if broker_ref_code:
                broker_result = await session.execute(
                    select(Broker).where(Broker.ref_code == broker_ref_code)
                )
                broker = broker_result.scalars().first()
            
            # Создаем пользователя
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                broker_id=broker.id if broker else None,
                broker_ref_code=broker_ref_code,
                role=UserRole.CLIENT
            )
            
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
            # Логируем регистрацию
            await self.log_user_action(
                user.id, 
                "registration", 
                {"broker_ref_code": broker_ref_code}
            )
            
            logger.info(f"Создан новый пользователь: {telegram_id}")
            return user
    
    async def update_user_contact_info(
        self,
        user_id: int,
        phone: Optional[str] = None,
        email: Optional[str] = None
    ) -> bool:
        """Обновить контактную информацию пользователя"""
        
        async with get_db_session() as session:
            update_data = {}
            
            if phone:
                update_data["phone"] = self.encryption.encrypt(phone)
            if email:
                update_data["email"] = self.encryption.encrypt(email)
            
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(**update_data)
                )
                await session.commit()
                
                await self.log_user_action(
                    user_id, 
                    "contact_info_updated", 
                    {"phone_updated": bool(phone), "email_updated": bool(email)}
                )
                
                return True
            
            return False
    
    async def set_user_consent(
        self,
        user_id: int,
        pd_consent: Optional[bool] = None,
        application_consent: Optional[bool] = None
    ) -> bool:
        """Установить согласия пользователя"""
        
        async with get_db_session() as session:
            update_data = {"updated_at": datetime.utcnow()}
            
            if pd_consent is not None:
                update_data["pd_consent"] = pd_consent
                update_data["pd_consent_date"] = datetime.utcnow() if pd_consent else None
            
            if application_consent is not None:
                update_data["application_consent"] = application_consent
                update_data["application_consent_date"] = datetime.utcnow() if application_consent else None
            
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(**update_data)
            )
            await session.commit()
            
            await self.log_user_action(
                user_id, 
                "consent_updated", 
                {
                    "pd_consent": pd_consent,
                    "application_consent": application_consent
                }
            )
            
            return True
    
    async def update_last_activity(self, user_id: int):
        """Обновить время последней активности"""
        async with get_db_session() as session:
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(last_activity=datetime.utcnow())
            )
            await session.commit()
    
    async def get_user_phone(self, user: User) -> Optional[str]:
        """Получить расшифрованный телефон пользователя"""
        if user.phone:
            return self.encryption.decrypt(user.phone)
        return None
    
    async def get_user_email(self, user: User) -> Optional[str]:
        """Получить расшифрованный email пользователя"""
        if user.email:
            return self.encryption.decrypt(user.email)
        return None
    
    async def log_user_action(
        self,
        user_id: int,
        action: str,
        details: dict = None,
        ip_address: Optional[str] = None
    ):
        """Записать действие пользователя в лог"""
        async with get_db_session() as session:
            log_entry = UserLog(
                user_id=user_id,
                action=action,
                details=str(details) if details else None,
                ip_address=ip_address
            )
            session.add(log_entry)
            await session.commit()
    
    async def get_user_logs(self, user_id: int, limit: int = 50) -> List[UserLog]:
        """Получить логи действий пользователя"""
        async with get_db_session() as session:
            result = await session.execute(
                select(UserLog)
                .where(UserLog.user_id == user_id)
                .order_by(UserLog.created_at.desc())
                .limit(limit)
            )
            return result.scalars().all()
    
    async def check_user_permissions(self, user: User) -> dict:
        """Проверить права пользователя"""
        return {
            "can_upload_documents": user.pd_consent and user.is_active,
            "can_submit_applications": user.application_consent and user.is_active,
            "is_broker": user.role == UserRole.BROKER,
            "is_admin": user.role == UserRole.ADMIN,
            "has_broker": user.broker_id is not None
        }
    
    async def get_broker_by_telegram_id(self, telegram_id: int) -> Optional[Broker]:
        """Получить профиль брокера по Telegram ID"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Broker).where(Broker.telegram_id == telegram_id)
            )
            broker = result.scalars().first()
            if broker:
                logger.info(f"Брокер найден: ID={broker.id}, ref_code={broker.ref_code}")
            else:
                logger.warning(f"Брокер с telegram_id={telegram_id} не найден")
            return broker 