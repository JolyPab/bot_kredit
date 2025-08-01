import os
import json
import asyncio
import aiofiles
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, update

from database.models import Document, User, Application, DocumentType
from database.database import get_db_session
from services.document_service import DocumentService
from config.settings import get_settings
import logging

# Для работы с PDF и извлечения текста
try:
    import PyMuPDF as fitz  # pip install PyMuPDF
except ImportError:
    fitz = None

try:
    import openai  # pip install openai
except ImportError:
    openai = None

logger = logging.getLogger(__name__)

class GPTDiagnosisService:
    """Сервис для анализа кредитной истории через GPT"""
    
    def __init__(self):
        self.settings = get_settings()
        self.document_service = DocumentService()
        
        # Настраиваем OpenAI
        if openai:
            openai.api_key = getattr(self.settings, 'OPENAI_API_KEY', None)
    
    async def analyze_credit_history(
        self, 
        user_id: int, 
        application_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Главный метод анализа кредитной истории"""
        
        try:
            logger.info(f"Начинаем анализ КИ для пользователя {user_id}")
            
            # 1. Получаем документы пользователя
            documents = await self._get_bki_documents(user_id, application_id)
            
            if not documents:
                return {
                    "success": False,
                    "error": "Не найдены документы БКИ для анализа",
                    "required_documents": ["НБКИ", "ОКБ", "Эквифакс"]
                }
            
            # 2. Извлекаем текст из PDF файлов
            extracted_texts = await self._extract_texts_from_documents(documents)
            
            if not extracted_texts:
                return {
                    "success": False,
                    "error": "Не удалось извлечь текст из документов"
                }
            
            # 3. Объединяем тексты БКИ
            combined_text = await self._combine_bki_texts(extracted_texts)
            
            # 4. Проверяем лимит символов (120,000)
            if len(combined_text) > 120000:
                logger.warning(f"Текст превышает лимит: {len(combined_text)} символов")
                combined_text = combined_text[:120000] + "\n[ТЕКСТ ОБРЕЗАН]"
            
            # 5. Отправляем в GPT на анализ
            gpt_result = await self._send_to_gpt(combined_text)
            
            if not gpt_result["success"]:
                return gpt_result
            
            # 6. Парсим результат GPT
            analysis_result = await self._parse_gpt_response(gpt_result["response"])
            
            # 7. Сохраняем результат
            await self._save_analysis_result(user_id, application_id, analysis_result)
            
            logger.info(f"Анализ КИ завершен для пользователя {user_id}")
            
            return {
                "success": True,
                "analysis": analysis_result,
                "documents_analyzed": len(documents),
                "text_length": len(combined_text)
            }
            
        except Exception as e:
            logger.error(f"Ошибка анализа КИ: {e}")
            return {
                "success": False,
                "error": f"Ошибка анализа: {str(e)}"
            }
    
    async def _get_bki_documents(
        self, 
        user_id: int, 
        application_id: Optional[int] = None
    ) -> List[Document]:
        """Получить документы БКИ пользователя"""
        
        async with get_db_session() as session:
            query = select(Document).where(
                Document.user_id == user_id,
                Document.file_type.in_([
                    DocumentType.CREDIT_REPORT_NBKI,
                    DocumentType.CREDIT_REPORT_OKB,
                    DocumentType.CREDIT_REPORT_EQUIFAX
                ])
            )
            
            if application_id:
                query = query.where(Document.application_id == application_id)
            
            query = query.order_by(Document.uploaded_at.desc())
            result = await session.execute(query)
            
            documents = result.scalars().all()
            
            logger.info(f"Найдено {len(documents)} документов БКИ для пользователя {user_id}")
            return documents
    
    async def _extract_texts_from_documents(
        self, 
        documents: List[Document]
    ) -> Dict[str, str]:
        """Извлечь текст из PDF документов"""
        
        extracted_texts = {}
        
        for document in documents:
            try:
                # Читаем файл
                file_data = await self.document_service.get_file_data(document)
                
                if not file_data:
                    logger.warning(f"Не удалось прочитать файл {document.file_name}")
                    continue
                
                # Извлекаем текст
                text = await self._extract_text_from_pdf(file_data, document.file_name)
                
                if text:
                    # Определяем тип БКИ
                    bki_type = self._determine_bki_type(document.file_type, text)
                    extracted_texts[bki_type] = text
                    
                    logger.info(f"Извлечен текст из {document.file_name}: {len(text)} символов")
                
            except Exception as e:
                logger.error(f"Ошибка извлечения текста из {document.file_name}: {e}")
                continue
        
        return extracted_texts
    
    async def _extract_text_from_pdf(
        self, 
        file_data: bytes, 
        file_name: str
    ) -> Optional[str]:
        """Извлечь текст из PDF файла"""
        
        if not fitz:
            logger.error("PyMuPDF не установлен. Используйте: pip install PyMuPDF")
            return None
        
        try:
            # Открываем PDF из байтов
            pdf_document = fitz.open(stream=file_data, filetype="pdf")
            
            text_parts = []
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document.load_page(page_num)
                text = page.get_text()
                text_parts.append(text)
            
            pdf_document.close()
            
            full_text = "\n".join(text_parts)
            
            # Базовая очистка текста
            full_text = self._clean_extracted_text(full_text)
            
            return full_text
            
        except Exception as e:
            logger.error(f"Ошибка извлечения текста из PDF {file_name}: {e}")
            return None
    
    def _clean_extracted_text(self, text: str) -> str:
        """Очистка извлеченного текста"""
        
        # Убираем лишние пробелы и переносы
        text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
        
        # Убираем повторяющиеся символы
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        return text
    
    def _determine_bki_type(
        self, 
        document_type: DocumentType, 
        text: str
    ) -> str:
        """Определить тип БКИ по типу документа и содержимому"""
        
        # Сначала по типу документа
        type_mapping = {
            DocumentType.CREDIT_REPORT_NBKI: "НБКИ",
            DocumentType.CREDIT_REPORT_OKB: "ОКБ", 
            DocumentType.CREDIT_REPORT_EQUIFAX: "Эквифакс"
        }
        
        if document_type in type_mapping:
            return type_mapping[document_type]
        
        # Если не определилось - по содержимому
        text_lower = text.lower()
        
        if "нбки" in text_lower or "национальн" in text_lower:
            return "НБКИ"
        elif "окб" in text_lower or "объединенн" in text_lower:
            return "ОКБ"
        elif "эквифакс" in text_lower or "equifax" in text_lower:
            return "Эквифакс"
        else:
            return "БКИ_Неизвестный"
    
    async def _combine_bki_texts(self, extracted_texts: Dict[str, str]) -> str:
        """Объединить тексты БКИ в один файл"""
        
        combined_parts = []
        
        # Заголовок
        combined_parts.append("=== ОБЪЕДИНЕННЫЙ ОТЧЕТ КРЕДИТНОЙ ИСТОРИИ ===\n")
        
        # Порядок БКИ как в протоколе: НБКИ, ОКБ, Эквифакс
        bki_order = ["НБКИ", "ОКБ", "Эквифакс"]
        
        for bki_name in bki_order:
            if bki_name in extracted_texts:
                combined_parts.append(f"\n{'='*50}")
                combined_parts.append(f"БЛОК: ОТЧЕТ {bki_name}")
                combined_parts.append(f"{'='*50}\n")
                combined_parts.append(extracted_texts[bki_name])
                combined_parts.append(f"\n{'='*50}")
                combined_parts.append(f"КОНЕЦ БЛОКА {bki_name}")
                combined_parts.append(f"{'='*50}\n")
        
        # Добавляем остальные БКИ если есть
        for bki_name, text in extracted_texts.items():
            if bki_name not in bki_order:
                combined_parts.append(f"\n{'='*50}")
                combined_parts.append(f"БЛОК: ОТЧЕТ {bki_name}")
                combined_parts.append(f"{'='*50}\n")
                combined_parts.append(text)
                combined_parts.append(f"\n{'='*50}")
                combined_parts.append(f"КОНЕЦ БЛОКА {bki_name}")
                combined_parts.append(f"{'='*50}\n")
        
        combined_text = "\n".join(combined_parts)
        
        logger.info(f"Объединенный текст: {len(combined_text)} символов")
        
        return combined_text
    
    async def _send_to_gpt(self, combined_text: str) -> Dict[str, Any]:
        """Отправить текст в GPT на анализ"""
        
        if not openai or not openai.api_key:
            return {
                "success": False,
                "error": "OpenAI API не настроен"
            }
        
        # Читаем промпт
        prompt = await self._get_analysis_prompt()
        
        try:
            logger.info("Отправляем запрос в GPT...")
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",  # или gpt-3.5-turbo для экономии
                messages=[
                    {
                        "role": "system", 
                        "content": prompt
                    },
                    {
                        "role": "user", 
                        "content": f"Проанализируй кредитную историю:\n\n{combined_text}"
                    }
                ],
                max_tokens=4000,
                temperature=0.1  # Минимальная креативность
            )
            
            gpt_response = response.choices[0].message.content
            
            logger.info(f"Получен ответ от GPT: {len(gpt_response)} символов")
            
            return {
                "success": True,
                "response": gpt_response,
                "tokens_used": response.usage.total_tokens
            }
            
        except Exception as e:
            logger.error(f"Ошибка запроса к GPT: {e}")
            return {
                "success": False,
                "error": f"Ошибка GPT API: {str(e)}"
            }
    
    async def _get_analysis_prompt(self) -> str:
        """Получить промпт для анализа"""
        
        # Возвращаем промпт из нашего файла
        # TODO: Можно вынести в отдельный файл или настройки
        
        return """🧠 ПОДРОБНЫЙ ПРОМТ: КИ-Аналитик (1-й этап — поиск ошибок и расчёты)
Ты — технический аналитик кредитной истории. Работаешь по трём отчётам БКИ (НБКИ, ОКБ, Эквифакс) и анкете клиента. На выходе ты должен:
Найти все ошибки, дубли, противоречия;
Выявить стоп-факторы и технические слабые места;
Рассчитать текущую кредитную нагрузку (ПДН, платежи, просрочки);
Выдать по каждому блоку чёткий отчёт: что найдено, где, почему это критично.

📋 ОБЩИЕ ПРАВИЛА ДЛЯ GPT:
Анализируй все отчёты и анкету клиента блочно.
Результат будет передан другому GPT (Консультанту).
Не делай выводов и не давай рекомендаций.
Пиши максимально подробно. Никаких сокращений.
Если нет информации — пиши нет данных.
Если нет ошибок — пиши ошибок не выявлено.
Указывай источник: из какого БКИ, по какому договору, с каким номером и датой.

АНАЛИЗИРУЙ ПО СЛЕДУЮЩИМ 12 БЛОКАМ:

Блок 1. Ошибки в титуле
Блок 2. Ошибки в реквизитах  
Блок 3. Контактные данные
Блок 4. Незакрытые счета
Блок 5. Плохие счета (МФО, ЖКХ, коллекторы)
Блок 6. Разночтения между БКИ
Блок 7. Ошибки в платёжной дисциплине
Блок 8. Задвоение счетов
Блок 9. Необнулённые счета
Блок 10. Стоп-комментарии
Блок 11. Неверные параметры договоров
Блок 12. Незаконные запросы

ФОРМАТ КАЖДОГО БЛОКА:
Блок X. Название
Критичность: 🟥/🟨/🟩
[Описание найденных ошибок с указанием источника]

В КОНЦЕ ОБЯЗАТЕЛЬНО:
Статус анализа:
Всего блоков обработано: 12
Блоков с ошибками: N
Блоков без ошибок: M  
Блоков с отсутствием данных: K"""
    
    async def _parse_gpt_response(self, gpt_response: str) -> Dict[str, Any]:
        """Парсинг ответа GPT"""
        
        # Базовый парсинг - можно улучшить
        analysis_result = {
            "raw_response": gpt_response,
            "blocks": {},
            "summary": {},
            "parsed_at": datetime.utcnow().isoformat()
        }
        
        # Простой парсинг блоков
        lines = gpt_response.split('\n')
        current_block = None
        current_content = []
        
        for line in lines:
            if line.startswith('Блок') and '.' in line:
                # Сохраняем предыдущий блок
                if current_block and current_content:
                    analysis_result["blocks"][current_block] = '\n'.join(current_content)
                
                # Начинаем новый блок
                current_block = line.strip()
                current_content = [line]
                
            elif current_block:
                current_content.append(line)
        
        # Сохраняем последний блок
        if current_block and current_content:
            analysis_result["blocks"][current_block] = '\n'.join(current_content)
        
        # Ищем статистику
        if "Статус анализа" in gpt_response:
            status_section = gpt_response.split("Статус анализа")[-1]
            analysis_result["summary"]["status_section"] = status_section.strip()
        
        return analysis_result
    
    async def _save_analysis_result(
        self, 
        user_id: int, 
        application_id: Optional[int], 
        analysis_result: Dict[str, Any]
    ):
        """Сохранить результат анализа"""
        
        try:
            # Сохраняем в базу данных
            if application_id:
                async with get_db_session() as session:
                    await session.execute(
                        update(Application)
                        .where(Application.id == application_id)
                        .values(
                            diagnosis_result=json.dumps(analysis_result, ensure_ascii=False),
                            updated_at=datetime.utcnow()
                        )
                    )
                    await session.commit()
            
            # Сохраняем в файл для логирования
            log_dir = "gpt_analysis_logs"
            os.makedirs(log_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(log_dir, f"analysis_{user_id}_{timestamp}.json")
            
            async with aiofiles.open(log_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(analysis_result, ensure_ascii=False, indent=2))
            
            logger.info(f"Результат анализа сохранен: {log_file}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения результата анализа: {e}")