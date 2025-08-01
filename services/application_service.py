from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from database.models import (
    Application, User, ApplicationStatus, StatusHistory, Document
)
from database.database import get_db_session
from services.user_service import UserService
# GPT диагностика будет импортироваться динамически для избежания циклических импортов
import logging
import json

logger = logging.getLogger(__name__)

class ApplicationService:
    """Сервис для работы с заявками"""
    
    def __init__(self):
        self.user_service = UserService()
    
    async def create_application(
        self,
        user: User,
        target_bank: Optional[str] = None,
        loan_purpose: Optional[str] = None,
        loan_amount: Optional[float] = None
    ) -> Application:
        """Создать новую заявку"""
        
        async with get_db_session() as session:
            application = Application(
                user_id=user.id,
                status=ApplicationStatus.CREATED,
                current_step="document_upload",
                target_bank=target_bank,
                loan_purpose=loan_purpose,
                loan_amount=loan_amount
            )
            
            session.add(application)
            await session.commit()
            await session.refresh(application)
            
            # Создаем запись в истории статусов
            await self.add_status_history(
                application.id,
                None,
                ApplicationStatus.CREATED,
                "Заявка создана",
                "system"
            )
            
            # Логируем действие
            await self.user_service.log_user_action(
                user.id,
                "application_created",
                {
                    "application_id": application.id,
                    "target_bank": target_bank,
                    "loan_amount": loan_amount
                }
            )
            
            logger.info(f"Создана заявка {application.id} для пользователя {user.id}")
            return application
    
    async def get_user_application(self, user_id: int) -> Optional[Application]:
        """Получить активную заявку пользователя"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Application)
                .options(
                    selectinload(Application.documents),
                    selectinload(Application.status_history)
                )
                .where(Application.user_id == user_id)
                .where(Application.status != ApplicationStatus.COMPLETED)
                .where(Application.status != ApplicationStatus.REJECTED)
                .order_by(Application.created_at.desc())
            )
            return result.scalars().first()
    
    async def get_application_by_id(self, application_id: int) -> Optional[Application]:
        """Получить заявку по ID"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Application)
                .options(
                    selectinload(Application.user),
                    selectinload(Application.documents),
                    selectinload(Application.status_history)
                )
                .where(Application.id == application_id)
            )
            return result.scalars().first()
    
    async def update_application_status(
        self,
        application_id: int,
        new_status: ApplicationStatus,
        comment: Optional[str] = None,
        created_by: str = "system"
    ) -> bool:
        """Обновить статус заявки"""
        
        async with get_db_session() as session:
            # Получаем текущую заявку
            result = await session.execute(
                select(Application).where(Application.id == application_id)
            )
            application = result.scalars().first()
            
            if not application:
                return False
            
            old_status = application.status
            
            # Обновляем статус
            await session.execute(
                update(Application)
                .where(Application.id == application_id)
                .values(
                    status=new_status,
                    updated_at=datetime.utcnow(),
                    completed_at=datetime.utcnow() if new_status in [
                        ApplicationStatus.COMPLETED, 
                        ApplicationStatus.REJECTED
                    ] else None
                )
            )
            
            await session.commit()
            
            # Добавляем запись в историю
            await self.add_status_history(
                application_id,
                old_status,
                new_status,
                comment,
                created_by
            )
            
            # Логируем изменение
            await self.user_service.log_user_action(
                application.user_id,
                "application_status_changed",
                {
                    "application_id": application_id,
                    "old_status": old_status.value if old_status else None,
                    "new_status": new_status.value,
                    "comment": comment
                }
            )
            
            logger.info(f"Статус заявки {application_id} изменен: {old_status} -> {new_status}")
            return True
    
    async def add_status_history(
        self,
        application_id: int,
        old_status: Optional[ApplicationStatus],
        new_status: ApplicationStatus,
        comment: Optional[str] = None,
        created_by: str = "system"
    ):
        """Добавить запись в историю статусов"""
        
        async with get_db_session() as session:
            history = StatusHistory(
                application_id=application_id,
                old_status=old_status,
                new_status=new_status,
                comment=comment,
                created_by=created_by
            )
            
            session.add(history)
            await session.commit()
    
    async def set_diagnosis_result(
        self,
        application_id: int,
        diagnosis_data: Dict[str, Any],
        recommendations: List[str]
    ) -> bool:
        """Установить результаты диагностики"""
        
        async with get_db_session() as session:
            await session.execute(
                update(Application)
                .where(Application.id == application_id)
                .values(
                    diagnosis_result=json.dumps(diagnosis_data, ensure_ascii=False),
                    recommendations="\n".join(recommendations),
                    updated_at=datetime.utcnow()
                )
            )
            await session.commit()
            
            # Обновляем статус
            await self.update_application_status(
                application_id,
                ApplicationStatus.DIAGNOSIS_COMPLETED,
                "Диагностика завершена"
            )
            
            return True
    
    async def get_application_stats(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику заявок пользователя"""
        
        async with get_db_session() as session:
            result = await session.execute(
                select(Application).where(Application.user_id == user_id)
            )
            applications = result.scalars().all()
            
            stats = {
                "total": len(applications),
                "by_status": {},
                "completed": 0,
                "in_progress": 0
            }
            
            for app in applications:
                status_key = app.status.value
                stats["by_status"][status_key] = stats["by_status"].get(status_key, 0) + 1
                
                if app.status == ApplicationStatus.COMPLETED:
                    stats["completed"] += 1
                elif app.status not in [ApplicationStatus.COMPLETED, ApplicationStatus.REJECTED]:
                    stats["in_progress"] += 1
            
            return stats
    
    async def get_documents_for_application(self, application_id: int) -> List[Document]:
        """Получить документы заявки"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Document)
                .where(Document.application_id == application_id)
                .order_by(Document.uploaded_at.desc())
            )
            return result.scalars().all()
    
    async def check_documents_ready_for_diagnosis(self, application_id: int) -> bool:
        """Проверить готовность документов для диагностики"""
        documents = await self.get_documents_for_application(application_id)
        
        # Проверяем наличие хотя бы одного кредитного отчета
        credit_reports = [
            d for d in documents 
            if d.file_type.value.startswith('credit_report_')
        ]
        
        return len(credit_reports) > 0
    
    async def start_diagnosis(self, application_id: int) -> bool:
        """Запустить диагностику КИ через GPT"""
        
        # Проверяем готовность документов
        if not await self.check_documents_ready_for_diagnosis(application_id):
            return False
        
        # Получаем заявку
        application = await self.get_application_by_id(application_id)
        if not application:
            return False
        
        # Обновляем статус
        await self.update_application_status(
            application_id,
            ApplicationStatus.DIAGNOSIS_IN_PROGRESS,
            "Диагностика КИ запущена через GPT"
        )
        
        try:
            # Динамический импорт для избежания циклических зависимостей
            from services.gpt_diagnosis_service import GPTDiagnosisService
            
            gpt_service = GPTDiagnosisService()
            
            # Запускаем анализ
            logger.info(f"Запуск GPT диагностики для заявки {application_id}")
            
            result = await gpt_service.analyze_credit_history(
                user_id=application.user_id,
                application_id=application_id
            )
            
            if result["success"]:
                # Обновляем статус на завершенный
                await self.update_application_status(
                    application_id,
                    ApplicationStatus.DIAGNOSIS_COMPLETED,
                    f"GPT диагностика завершена. Проанализировано документов: {result.get('documents_analyzed', 0)}"
                )
                
                logger.info(f"GPT диагностика завершена для заявки {application_id}")
                return True
            else:
                # Ошибка анализа
                await self.update_application_status(
                    application_id,
                    ApplicationStatus.CREATED,  # Возвращаем к исходному статусу
                    f"Ошибка GPT диагностики: {result.get('error', 'Неизвестная ошибка')}"
                )
                
                logger.error(f"Ошибка GPT диагностики для заявки {application_id}: {result.get('error')}")
                return False
                
        except Exception as e:
            # Критическая ошибка
            logger.error(f"Критическая ошибка GPT диагностики для заявки {application_id}: {e}")
            
            await self.update_application_status(
                application_id,
                ApplicationStatus.CREATED,
                f"Техническая ошибка диагностики: {str(e)}"
            )
            
            return False
    
    async def get_application_timeline(self, application_id: int) -> List[Dict[str, Any]]:
        """Получить временную линию заявки"""
        
        async with get_db_session() as session:
            result = await session.execute(
                select(StatusHistory)
                .where(StatusHistory.application_id == application_id)
                .order_by(StatusHistory.created_at.desc())
            )
            history = result.scalars().all()
            
            timeline = []
            for item in history:
                timeline.append({
                    "date": item.created_at,
                    "status": item.new_status.value,
                    "comment": item.comment,
                    "created_by": item.created_by
                })
            
            return timeline
    
    def get_status_description(self, status: ApplicationStatus) -> str:
        """Получить описание статуса для пользователя"""
        descriptions = {
            ApplicationStatus.CREATED: "📝 Заявка создана",
            ApplicationStatus.DOCUMENTS_UPLOADED: "📄 Документы загружены",
            ApplicationStatus.DIAGNOSIS_IN_PROGRESS: "🔍 Идет диагностика КИ",
            ApplicationStatus.DIAGNOSIS_COMPLETED: "✅ Диагностика завершена",
            ApplicationStatus.APPLICATIONS_PENDING: "⏳ Заявления подготовлены",
            ApplicationStatus.APPLICATIONS_SENT: "📤 Заявления отправлены в БКИ",
            ApplicationStatus.COMPLETED: "🎉 Работа завершена",
            ApplicationStatus.REJECTED: "❌ Заявка отклонена"
        }
        return descriptions.get(status, status.value)
    
    def get_next_step_description(self, status: ApplicationStatus) -> str:
        """Получить описание следующего шага"""
        next_steps = {
            ApplicationStatus.CREATED: "Загрузите кредитные отчеты из БКИ",
            ApplicationStatus.DOCUMENTS_UPLOADED: "Ожидайте начала диагностики",
            ApplicationStatus.DIAGNOSIS_IN_PROGRESS: "Ожидайте результаты диагностики",
            ApplicationStatus.DIAGNOSIS_COMPLETED: "Ознакомьтесь с результатами и рекомендациями",
            ApplicationStatus.APPLICATIONS_PENDING: "Подтвердите отправку заявлений в БКИ",
            ApplicationStatus.APPLICATIONS_SENT: "Ожидайте ответа от БКИ (до 30 дней)",
            ApplicationStatus.COMPLETED: "Работа завершена",
            ApplicationStatus.REJECTED: "Обратитесь в поддержку"
        }
        return next_steps.get(status, "Свяжитесь с поддержкой") 