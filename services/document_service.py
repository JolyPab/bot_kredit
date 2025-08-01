import os
import aiofiles
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from database.models import Document, User, Application, DocumentType
from database.database import get_db_session
from config.settings import get_settings
import logging

logger = logging.getLogger(__name__)

class DocumentService:
    """Сервис для работы с документами"""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def save_document(
        self,
        user: User,
        file_data: bytes,
        file_name: str,
        file_type: DocumentType,
        application_id: Optional[int] = None
    ) -> Document:
        """Сохранить документ пользователя"""
        
        # Создаем папку для документов если не существует
        docs_dir = "documents"
        user_dir = os.path.join(docs_dir, str(user.id))
        os.makedirs(user_dir, exist_ok=True)
        
        # Генерируем уникальное имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = os.path.splitext(file_name)[1]
        unique_filename = f"{timestamp}_{file_type.value}{file_extension}"
        file_path = os.path.join(user_dir, unique_filename)
        
        # Сохраняем файл
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_data)
        
        # Записываем в БД
        async with get_db_session() as session:
            document = Document(
                user_id=user.id,
                application_id=application_id,
                file_name=file_name,
                file_type=file_type,
                file_size=len(file_data),
                file_path=file_path,
                is_processed=False
            )
            
            session.add(document)
            await session.commit()
            await session.refresh(document)
            
            logger.info(f"Документ {file_name} сохранен для пользователя {user.id}")
            return document
    
    async def get_user_documents(
        self,
        user_id: int,
        document_type: Optional[DocumentType] = None
    ) -> List[Document]:
        """Получить документы пользователя"""
        async with get_db_session() as session:
            query = select(Document).where(Document.user_id == user_id)
            
            if document_type:
                query = query.where(Document.file_type == document_type)
            
            query = query.order_by(Document.uploaded_at.desc())
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_document_by_id(self, document_id: int) -> Optional[Document]:
        """Получить документ по ID"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Document)
                .options(selectinload(Document.user))
                .where(Document.id == document_id)
            )
            return result.scalars().first()
    
    async def mark_document_processed(
        self,
        document_id: int,
        processing_result: dict
    ) -> bool:
        """Отметить документ как обработанный"""
        async with get_db_session() as session:
            await session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(
                    is_processed=True,
                    processed_at=datetime.utcnow(),
                    processing_result=str(processing_result)
                )
            )
            await session.commit()
            return True
    
    async def validate_file_format(self, file_name: str) -> bool:
        """Проверить формат файла"""
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
        file_extension = os.path.splitext(file_name)[1].lower()
        return file_extension in allowed_extensions
    
    async def check_file_size(self, file_size: int) -> bool:
        """Проверить размер файла"""
        max_size = self.settings.MAX_FILE_SIZE_MB * 1024 * 1024  # В байтах
        return file_size <= max_size
    
    async def get_file_data(self, document: Document) -> Optional[bytes]:
        """Получить данные файла"""
        try:
            if os.path.exists(document.file_path):
                async with aiofiles.open(document.file_path, 'rb') as f:
                    return await f.read()
        except Exception as e:
            logger.error(f"Ошибка чтения файла {document.file_path}: {e}")
        return None
    
    async def delete_document(self, document: Document) -> bool:
        """Удалить документ"""
        try:
            # Удаляем файл с диска
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
            
            # Удаляем из БД
            async with get_db_session() as session:
                await session.delete(document)
                await session.commit()
            
            logger.info(f"Документ {document.id} удален")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления документа {document.id}: {e}")
            return False
    
    async def get_documents_stats(self, user_id: int) -> dict:
        """Получить статистику документов пользователя"""
        documents = await self.get_user_documents(user_id)
        
        stats = {
            'total': len(documents),
            'processed': len([d for d in documents if d.is_processed]),
            'by_type': {}
        }
        
        for doc_type in DocumentType:
            type_docs = [d for d in documents if d.file_type == doc_type]
            stats['by_type'][doc_type.value] = len(type_docs)
        
        return stats 