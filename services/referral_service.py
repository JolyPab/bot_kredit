import hashlib
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from database.models import (
    Broker, User, ReferralStats, ReferralClick, 
    Application, ApplicationStatus
)
from database.database import get_db_session
import logging

logger = logging.getLogger(__name__)

class ReferralService:
    """Сервис для работы с реферальной системой"""
    
    def __init__(self):
        self.bot_username = "clear_credit_history_bot"  # Имя бота для ссылок
    
    async def get_broker_referral_link(self, broker_id: int) -> Optional[str]:
        """Получить реферальную ссылку брокера"""
        
        async with get_db_session() as session:
            result = await session.execute(
                select(Broker).where(Broker.id == broker_id)
            )
            broker = result.scalars().first()
            
            if not broker:
                return None
            
            # Генерируем ссылку
            referral_link = f"https://t.me/{self.bot_username}?start={broker.ref_code}"
            
            # Создаем или обновляем статистику
            await self._ensure_referral_stats(session, broker_id, broker.ref_code)
            await session.commit()
            
            return referral_link
    
    async def track_referral_click(
        self, 
        ref_code: str, 
        telegram_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Отследить переход по реферальной ссылке"""
        
        async with get_db_session() as session:
            # Находим брокера по коду
            broker_result = await session.execute(
                select(Broker).where(Broker.ref_code == ref_code)
            )
            broker = broker_result.scalars().first()
            
            if not broker:
                logger.warning(f"Брокер с кодом {ref_code} не найден")
                return False
            
            # Хешируем IP и User-Agent для дедупликации
            ip_hash = None
            user_agent_hash = None
            
            if ip_address:
                ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()
            if user_agent:
                user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest()
            
            # Проверяем дублирование клика
            existing_click = await session.execute(
                select(ReferralClick)
                .where(ReferralClick.ref_code == ref_code)
                .where(ReferralClick.telegram_id == telegram_id)
                .where(ReferralClick.clicked_at > datetime.utcnow() - timedelta(hours=24))
            )
            
            if existing_click.scalars().first():
                logger.info(f"Дублирующий клик от {telegram_id} по коду {ref_code}")
                return False
            
            # Записываем клик
            click = ReferralClick(
                ref_code=ref_code,
                broker_id=broker.id,
                telegram_id=telegram_id,
                ip_hash=ip_hash,
                user_agent_hash=user_agent_hash
            )
            session.add(click)
            
            # Обновляем статистику
            await self._update_click_stats(session, broker.id, ref_code)
            await session.commit()
            
            logger.info(f"Клик отслежен: код {ref_code}, брокер {broker.id}")
            return True
    
    async def track_referral_registration(self, user_id: int, ref_code: str) -> bool:
        """Отследить регистрацию по реферальной ссылке"""
        
        async with get_db_session() as session:
            # Находим брокера
            broker_result = await session.execute(
                select(Broker).where(Broker.ref_code == ref_code)
            )
            broker = broker_result.scalars().first()
            
            if not broker:
                return False
            
            # Обновляем последний клик как конвертированный
            await session.execute(
                update(ReferralClick)
                .where(ReferralClick.ref_code == ref_code)
                .where(ReferralClick.user_id.is_(None))
                .values(
                    converted_to_registration=True,
                    user_id=user_id
                )
            )
            
            # Обновляем статистику регистраций
            await self._update_registration_stats(session, broker.id, ref_code)
            await session.commit()
            
            logger.info(f"Регистрация отслежена: пользователь {user_id}, код {ref_code}")
            return True
    
    async def get_broker_stats(self, broker_id: int) -> Dict[str, Any]:
        """Получить статистику брокера"""
        
        async with get_db_session() as session:
            # Основная статистика
            stats_result = await session.execute(
                select(ReferralStats).where(ReferralStats.broker_id == broker_id)
            )
            stats = stats_result.scalars().first()
            
            if not stats:
                return {
                    "clicks": 0,
                    "registrations": 0,
                    "conversions": 0,
                    "conversion_rate": 0.0,
                    "total_commission": 0.0,
                    "recent_clicks": []
                }
            
            # Последние клики (за 7 дней)
            recent_clicks_result = await session.execute(
                select(ReferralClick)
                .where(ReferralClick.broker_id == broker_id)
                .where(ReferralClick.clicked_at > datetime.utcnow() - timedelta(days=7))
                .order_by(ReferralClick.clicked_at.desc())
                .limit(10)
            )
            recent_clicks = recent_clicks_result.scalars().all()
            
            # Подсчет клиентов
            clients_result = await session.execute(
                select(func.count(User.id))
                .where(User.broker_id == broker_id)
            )
            total_clients = clients_result.scalar() or 0
            
            # Активные заявки
            active_apps_result = await session.execute(
                select(func.count(Application.id))
                .join(User)
                .where(User.broker_id == broker_id)
                .where(Application.status.in_([
                    ApplicationStatus.CREATED,
                    ApplicationStatus.DOCUMENTS_UPLOADED,
                    ApplicationStatus.DIAGNOSIS_IN_PROGRESS
                ]))
            )
            active_applications = active_apps_result.scalar() or 0
            
            conversion_rate = 0.0
            if stats.clicks > 0:
                conversion_rate = (stats.registrations / stats.clicks) * 100
            
            return {
                "clicks": stats.clicks,
                "registrations": stats.registrations,
                "conversions": stats.conversions,
                "conversion_rate": round(conversion_rate, 1),
                "total_commission": stats.total_commission,
                "paid_commission": stats.paid_commission,
                "total_clients": total_clients,
                "active_applications": active_applications,
                "first_click": stats.first_click,
                "last_click": stats.last_click,
                "recent_clicks": [
                    {
                        "clicked_at": click.clicked_at,
                        "converted": click.converted_to_registration,
                        "telegram_id": click.telegram_id
                    }
                    for click in recent_clicks
                ]
            }
    
    async def calculate_commission(self, user_id: int, amount: float) -> bool:
        """Рассчитать и начислить комиссию брокеру"""
        
        async with get_db_session() as session:
            # Находим пользователя и его брокера
            user_result = await session.execute(
                select(User)
                .options(selectinload(User.broker))
                .where(User.id == user_id)
            )
            user = user_result.scalars().first()
            
            if not user or not user.broker:
                return False
            
            commission_amount = amount * user.broker.commission_rate
            
            # Обновляем статистику
            await session.execute(
                update(ReferralStats)
                .where(ReferralStats.broker_id == user.broker.id)
                .values(
                    total_commission=ReferralStats.total_commission + commission_amount,
                    conversions=ReferralStats.conversions + 1
                )
            )
            await session.commit()
            
            logger.info(f"Начислена комиссия {commission_amount} брокеру {user.broker.id}")
            return True
    
    async def generate_new_ref_code(self, broker_id: int) -> Optional[str]:
        """Сгенерировать новый реферальный код для брокера"""
        
        logger.info(f"Генерация нового реферального кода для брокера {broker_id}")
        
        async with get_db_session() as session:
            # Проверяем существует ли брокер
            broker_check = await session.execute(
                select(Broker).where(Broker.id == broker_id)
            )
            if not broker_check.scalars().first():
                logger.error(f"Брокер с ID {broker_id} не найден")
                return None
            
            # Генерируем уникальный код
            attempts = 0
            while attempts < 10:
                new_code = self._generate_ref_code()
                
                # Проверяем уникальность
                existing = await session.execute(
                    select(Broker).where(Broker.ref_code == new_code)
                )
                
                if not existing.scalars().first():
                    # Обновляем код брокера
                    await session.execute(
                        update(Broker)
                        .where(Broker.id == broker_id)
                        .values(ref_code=new_code)
                    )
                    
                    # Создаем новую статистику
                    await self._ensure_referral_stats(session, broker_id, new_code)
                    await session.commit()
                    
                    logger.info(f"Новый реферальный код {new_code} создан для брокера {broker_id}")
                    return new_code
                
                attempts += 1
            
            logger.error(f"Не удалось сгенерировать уникальный код для брокера {broker_id} за 10 попыток")
            return None
    
    async def _ensure_referral_stats(self, session, broker_id: int, ref_code: str):
        """Создать статистику рефералов если не существует"""
        
        existing = await session.execute(
            select(ReferralStats)
            .where(ReferralStats.broker_id == broker_id)
            .where(ReferralStats.ref_code == ref_code)
        )
        
        if not existing.scalars().first():
            stats = ReferralStats(
                broker_id=broker_id,
                ref_code=ref_code
            )
            session.add(stats)
    
    async def _update_click_stats(self, session, broker_id: int, ref_code: str):
        """Обновить статистику кликов"""
        
        now = datetime.utcnow()
        
        await session.execute(
            update(ReferralStats)
            .where(ReferralStats.broker_id == broker_id)
            .where(ReferralStats.ref_code == ref_code)
            .values(
                clicks=ReferralStats.clicks + 1,
                last_click=now,
                first_click=func.coalesce(ReferralStats.first_click, now)
            )
        )
    
    async def _update_registration_stats(self, session, broker_id: int, ref_code: str):
        """Обновить статистику регистраций"""
        
        await session.execute(
            update(ReferralStats)
            .where(ReferralStats.broker_id == broker_id)
            .where(ReferralStats.ref_code == ref_code)
            .values(registrations=ReferralStats.registrations + 1)
        )
    
    def _generate_ref_code(self) -> str:
        """Сгенерировать реферальный код"""
        # Формат: REF_XXXXX (например REF_A7K2M)
        return 'REF_' + ''.join(
            secrets.choice(string.ascii_uppercase + string.digits) 
            for _ in range(5)
        ) 