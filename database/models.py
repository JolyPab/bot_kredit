from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, 
    ForeignKey, Enum, LargeBinary, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    CLIENT = "client"
    BROKER = "broker"
    ADMIN = "admin"

class ApplicationStatus(enum.Enum):
    CREATED = "created"
    DOCUMENTS_UPLOADED = "documents_uploaded"
    DIAGNOSIS_IN_PROGRESS = "diagnosis_in_progress"
    DIAGNOSIS_COMPLETED = "diagnosis_completed"
    APPLICATIONS_PENDING = "applications_pending"
    APPLICATIONS_SENT = "applications_sent"
    COMPLETED = "completed"
    REJECTED = "rejected"

class DocumentType(enum.Enum):
    CREDIT_REPORT_NBKI = "credit_report_nbki"
    CREDIT_REPORT_OKB = "credit_report_okb"
    CREDIT_REPORT_EQUIFAX = "credit_report_equifax"
    PASSPORT = "passport"
    OTHER = "other"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Контактные данные (зашифрованы)
    phone = Column(LargeBinary, nullable=True)  # Зашифрованный телефон
    email = Column(LargeBinary, nullable=True)  # Зашифрованный email
    
    # Роль и статус
    role = Column(Enum(UserRole), default=UserRole.CLIENT)
    is_active = Column(Boolean, default=True)
    
    # Согласия на обработку ПД
    pd_consent = Column(Boolean, default=False)
    pd_consent_date = Column(DateTime, nullable=True)
    application_consent = Column(Boolean, default=False)
    application_consent_date = Column(DateTime, nullable=True)
    
    # Привязка к брокеру
    broker_id = Column(Integer, ForeignKey("brokers.id"), nullable=True)
    broker_ref_code = Column(String(50), nullable=True)
    
    # Системные поля
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    broker = relationship("Broker", back_populates="clients")
    applications = relationship("Application", back_populates="user")
    documents = relationship("Document", back_populates="user")
    logs = relationship("UserLog", back_populates="user")

class Broker(Base):
    __tablename__ = "brokers"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    company = Column(String(255), nullable=True)
    
    # Контактные данные
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    
    # Настройки
    ref_code = Column(String(50), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    commission_rate = Column(Float, default=0.0)
    
    # Системные поля
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    clients = relationship("User", back_populates="broker")

class Application(Base):
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Статус и этапы
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.CREATED)
    current_step = Column(String(100), nullable=True)
    
    # Данные для анализа
    target_bank = Column(String(255), nullable=True)
    loan_purpose = Column(String(500), nullable=True)
    loan_amount = Column(Float, nullable=True)
    
    # Результаты диагностики
    diagnosis_result = Column(Text, nullable=True)  # JSON с результатами
    recommendations = Column(Text, nullable=True)
    
    # AmoCRM интеграция
    amocrm_lead_id = Column(Integer, nullable=True)
    
    # Системные поля
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="applications")
    documents = relationship("Document", back_populates="application")
    status_history = relationship("StatusHistory", back_populates="application")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)
    
    # Информация о файле
    file_name = Column(String(255), nullable=False)
    file_type = Column(Enum(DocumentType), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=False)  # Путь в Google Drive
    
    # Обработка
    is_processed = Column(Boolean, default=False)
    processing_result = Column(Text, nullable=True)  # JSON с результатами парсинга
    
    # Системные поля
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="documents")
    application = relationship("Application", back_populates="documents")

class StatusHistory(Base):
    __tablename__ = "status_history"
    
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    
    # Изменение статуса
    old_status = Column(Enum(ApplicationStatus), nullable=True)
    new_status = Column(Enum(ApplicationStatus), nullable=False)
    comment = Column(Text, nullable=True)
    
    # Уведомления
    user_notified = Column(Boolean, default=False)
    broker_notified = Column(Boolean, default=False)
    
    # Системные поля
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)  # system/user/admin
    
    # Связи
    application = relationship("Application", back_populates="status_history")

class UserLog(Base):
    __tablename__ = "user_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Событие
    action = Column(String(100), nullable=False)  # login, upload_document, etc.
    details = Column(Text, nullable=True)  # JSON с деталями
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Системные поля
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    user = relationship("User", back_populates="logs")

class BrokerApplication(Base):
    __tablename__ = "broker_applications"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, nullable=False)
    username = Column(String(255), nullable=True)
    
    # Данные заявки
    full_name = Column(String(255), nullable=False)
    company = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    experience = Column(Text, nullable=True)
    
    # Статус заявки
    status = Column(String(50), default="pending")  # pending, approved, rejected
    admin_comment = Column(Text, nullable=True)
    processed_by = Column(Integer, nullable=True)  # admin user_id
    processed_at = Column(DateTime, nullable=True)
    
    # Системные поля
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class InviteCode(Base):
    __tablename__ = "invite_codes"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    code_type = Column(String(20), default="broker")  # broker, admin, etc.
    
    # Использование
    is_used = Column(Boolean, default=False)
    used_by = Column(Integer, nullable=True)  # user_id кто активировал
    used_at = Column(DateTime, nullable=True)
    
    # Ограничения
    expires_at = Column(DateTime, nullable=True)
    max_uses = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    
    # Связь с заявкой
    application_id = Column(Integer, ForeignKey("broker_applications.id"), nullable=True)
    
    # Создание
    created_by = Column(Integer, nullable=True)  # admin user_id
    created_at = Column(DateTime, default=datetime.utcnow)

class ReferralStats(Base):
    __tablename__ = "referral_stats"
    
    id = Column(Integer, primary_key=True)
    broker_id = Column(Integer, ForeignKey("brokers.id"), nullable=False)
    ref_code = Column(String(50), nullable=False)
    
    # Статистика переходов
    clicks = Column(Integer, default=0)
    registrations = Column(Integer, default=0)
    conversions = Column(Integer, default=0)  # завершенные заявки
    
    # Финансовая статистика
    total_commission = Column(Float, default=0.0)
    paid_commission = Column(Float, default=0.0)
    
    # Даты
    first_click = Column(DateTime, nullable=True)
    last_click = Column(DateTime, nullable=True)
    
    # Системные поля
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    broker = relationship("Broker", backref="referral_stats")

class ReferralClick(Base):
    __tablename__ = "referral_clicks"
    
    id = Column(Integer, primary_key=True)
    ref_code = Column(String(50), nullable=False)
    broker_id = Column(Integer, ForeignKey("brokers.id"), nullable=False)
    
    # Данные о клике
    telegram_id = Column(Integer, nullable=True)  # если пользователь уже зарегистрирован
    ip_hash = Column(String(64), nullable=True)  # хешированный IP для дедупликации
    user_agent_hash = Column(String(64), nullable=True)
    
    # Результат
    converted_to_registration = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Системные поля
    clicked_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    broker = relationship("Broker")
    user = relationship("User")

class BotSettings(Base):
    __tablename__ = "bot_settings"
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(String(500), nullable=True)
    
    # Системные поля
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 