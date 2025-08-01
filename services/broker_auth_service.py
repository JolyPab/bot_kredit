import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from database.models import BrokerApplication, InviteCode, User, UserRole, Broker
from database.database import get_db_session
from services.user_service import UserService
import logging

logger = logging.getLogger(__name__)

class BrokerAuthService:
    """Сервис для авторизации брокеров"""
    
    def __init__(self):
        self.user_service = UserService()
    
    async def create_broker_application(
        self,
        telegram_id: int,
        username: str,
        full_name: str,
        company: str = None,
        phone: str = None,
        email: str = None,
        experience: str = None
    ) -> BrokerApplication:
        """Создать заявку на становление брокером"""
        
        async with get_db_session() as session:
            # Проверяем нет ли уже активной заявки
            existing = await session.execute(
                select(BrokerApplication)
                .where(BrokerApplication.telegram_id == telegram_id)
                .where(BrokerApplication.status == "pending")
            )
            
            if existing.scalars().first():
                raise ValueError("У вас уже есть активная заявка на рассмотрении")
            
            application = BrokerApplication(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                company=company,
                phone=phone,
                email=email,
                experience=experience,
                status="pending"
            )
            
            session.add(application)
            await session.commit()
            await session.refresh(application)
            
            logger.info(f"Создана заявка брокера #{application.id} от пользователя {telegram_id}")
            return application
    
    async def get_pending_applications(self) -> List[BrokerApplication]:
        """Получить заявки на рассмотрении"""
        async with get_db_session() as session:
            result = await session.execute(
                select(BrokerApplication)
                .where(BrokerApplication.status == "pending")
                .order_by(BrokerApplication.created_at.asc())
            )
            return result.scalars().all()
    
    async def get_application_by_id(self, app_id: int) -> Optional[BrokerApplication]:
        """Получить заявку по ID"""
        async with get_db_session() as session:
            result = await session.execute(
                select(BrokerApplication).where(BrokerApplication.id == app_id)
            )
            return result.scalars().first()
    
    async def approve_application(
        self,
        app_id: int,
        admin_user_id: int,
        admin_comment: str = None
    ) -> InviteCode:
        """Одобрить заявку и создать инвайт-код"""
        
        async with get_db_session() as session:
            # Обновляем заявку
            await session.execute(
                update(BrokerApplication)
                .where(BrokerApplication.id == app_id)
                .values(
                    status="approved",
                    admin_comment=admin_comment,
                    processed_by=admin_user_id,
                    processed_at=datetime.utcnow()
                )
            )
            
            # Создаем инвайт-код
            code = self._generate_broker_code()
            invite_code = InviteCode(
                code=code,
                code_type="broker",
                application_id=app_id,
                created_by=admin_user_id,
                expires_at=datetime.utcnow() + timedelta(days=7)  # Действует неделю
            )
            
            session.add(invite_code)
            await session.commit()
            await session.refresh(invite_code)
            
            logger.info(f"Заявка #{app_id} одобрена, создан код {code}")
            return invite_code
    
    async def reject_application(
        self,
        app_id: int,
        admin_user_id: int,
        admin_comment: str = None
    ) -> bool:
        """Отклонить заявку"""
        
        async with get_db_session() as session:
            await session.execute(
                update(BrokerApplication)
                .where(BrokerApplication.id == app_id)
                .values(
                    status="rejected",
                    admin_comment=admin_comment,
                    processed_by=admin_user_id,
                    processed_at=datetime.utcnow()
                )
            )
            await session.commit()
            
            logger.info(f"Заявка #{app_id} отклонена")
            return True
    
    async def activate_invite_code(self, code: str, user_id: int) -> bool:
        """Активировать инвайт-код"""
        
        async with get_db_session() as session:
            # Найти код
            result = await session.execute(
                select(InviteCode)
                .where(InviteCode.code == code)
                .where(InviteCode.is_used == False)
                .where(InviteCode.expires_at > datetime.utcnow())
            )
            invite_code = result.scalars().first()
            
            if not invite_code:
                return False
            
            # Получить пользователя
            user = await self.user_service.get_user_by_id(user_id)
            if not user:
                return False
            
            # Обновить код как использованный
            await session.execute(
                update(InviteCode)
                .where(InviteCode.id == invite_code.id)
                .values(
                    is_used=True,
                    used_by=user_id,
                    used_at=datetime.utcnow(),
                    current_uses=invite_code.current_uses + 1
                )
            )
            
            # Изменить роль пользователя на брокера
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(role=UserRole.BROKER)
            )
            
            # Создать запись брокера если нужно
            await self._create_broker_profile(session, user, invite_code.application_id)
            
            await session.commit()
            
            # Логируем активацию
            await self.user_service.log_user_action(
                user_id,
                "invite_code_activated",
                {
                    "code": code,
                    "application_id": invite_code.application_id,
                    "new_role": "broker"
                }
            )
            
            logger.info(f"Код {code} активирован пользователем {user_id}")
            return True
    
    async def _create_broker_profile(self, session, user: User, application_id: int):
        """Создать профиль брокера"""
        
        # Проверяем есть ли уже профиль
        existing_broker = await session.execute(
            select(Broker).where(Broker.telegram_id == user.telegram_id)
        )
        
        if existing_broker.scalars().first():
            return  # Уже есть
        
        # Получаем данные из заявки
        application = None
        if application_id:
            app_result = await session.execute(
                select(BrokerApplication).where(BrokerApplication.id == application_id)
            )
            application = app_result.scalars().first()
        
        # Создаем профиль брокера
        broker = Broker(
            telegram_id=user.telegram_id,
            name=application.full_name if application else user.first_name,
            company=application.company if application else None,
            phone=application.phone if application else None,
            email=application.email if application else None,
            ref_code=self._generate_ref_code(),
            commission_rate=0.15  # 15% по умолчанию
        )
        
        session.add(broker)
    
    def _generate_broker_code(self) -> str:
        """Генерировать инвайт-код для брокера"""
        # Формат: BR_YYYY_XXX (например BR_2024_A7K)
        year = datetime.now().year
        random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(3))
        return f"BR_{year}_{random_part}"
    
    def _generate_ref_code(self) -> str:
        """Генерировать реферальный код"""
        # Формат: REF_XXXXX (например REF_A7K2M)
        return 'REF_' + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5))
    
    async def get_user_application_status(self, telegram_id: int) -> Optional[BrokerApplication]:
        """Получить статус заявки пользователя"""
        async with get_db_session() as session:
            result = await session.execute(
                select(BrokerApplication)
                .where(BrokerApplication.telegram_id == telegram_id)
                .order_by(BrokerApplication.created_at.desc())
            )
            return result.scalars().first()
    
    async def create_manual_invite_code(
        self,
        admin_user_id: int,
        code_type: str = "broker",
        expires_days: int = 7
    ) -> InviteCode:
        """Создать инвайт-код вручную (для админа)"""
        
        async with get_db_session() as session:
            code = self._generate_broker_code()
            invite_code = InviteCode(
                code=code,
                code_type=code_type,
                created_by=admin_user_id,
                expires_at=datetime.utcnow() + timedelta(days=expires_days)
            )
            
            session.add(invite_code)
            await session.commit()
            await session.refresh(invite_code)
            
            logger.info(f"Создан ручной инвайт-код {code}")
            return invite_code 