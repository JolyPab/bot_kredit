import os
from dataclasses import dataclass
from typing import Optional

# Загружаем переменные из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Если dotenv не установлен

@dataclass
class Settings:
    """Настройки приложения"""
    
    # Telegram Bot
    BOT_TOKEN: str = ""
    
    # База данных
    DATABASE_URL: str = "sqlite+aiosqlite:///bot.db"
    
    # AmoCRM
    AMOCRM_SUBDOMAIN: str = ""
    AMOCRM_CLIENT_ID: str = ""
    AMOCRM_CLIENT_SECRET: str = ""
    AMOCRM_REDIRECT_URI: str = ""
    AMOCRM_ACCESS_TOKEN: Optional[str] = None
    
    # Google Drive
    GOOGLE_CREDENTIALS_FILE: str = "credentials.json"
    GOOGLE_FOLDER_ID: str = ""
    
    # Сервер диагностики КИ
    KI_SERVER_URL: str = ""
    KI_SERVER_TOKEN: Optional[str] = None
    
    # OpenAI GPT
    OPENAI_API_KEY: Optional[str] = None
    
    # Безопасность
    ENCRYPTION_KEY: str = "your-secret-key-here"
    
    # Логирование
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "bot.log"
    
    # Настройки бота
    MAX_FILE_SIZE_MB: int = 20
    SESSION_TIMEOUT_HOURS: int = 24
    
    @classmethod
    def from_env(cls) -> 'Settings':
        """Загрузка настроек из переменных окружения"""
        return cls(
            # Telegram
            BOT_TOKEN=os.getenv("BOT_TOKEN", ""),
            
            # База данных
            DATABASE_URL=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db"),
            
            # AmoCRM
            AMOCRM_SUBDOMAIN=os.getenv("AMOCRM_SUBDOMAIN", ""),
            AMOCRM_CLIENT_ID=os.getenv("AMOCRM_CLIENT_ID", ""),
            AMOCRM_CLIENT_SECRET=os.getenv("AMOCRM_CLIENT_SECRET", ""),
            AMOCRM_REDIRECT_URI=os.getenv("AMOCRM_REDIRECT_URI", ""),
            AMOCRM_ACCESS_TOKEN=os.getenv("AMOCRM_ACCESS_TOKEN"),
            
            # Google Drive
            GOOGLE_CREDENTIALS_FILE=os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
            GOOGLE_FOLDER_ID=os.getenv("GOOGLE_FOLDER_ID", ""),
            
            # Сервер КИ
            KI_SERVER_URL=os.getenv("KI_SERVER_URL", ""),
            KI_SERVER_TOKEN=os.getenv("KI_SERVER_TOKEN"),
            
            # OpenAI
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
            
            # Безопасность
            ENCRYPTION_KEY=os.getenv("ENCRYPTION_KEY", "your-secret-key-here"),
            
            # Настройки
            LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
            LOG_FILE=os.getenv("LOG_FILE", "bot.log"),
            MAX_FILE_SIZE_MB=int(os.getenv("MAX_FILE_SIZE_MB", "20")),
            SESSION_TIMEOUT_HOURS=int(os.getenv("SESSION_TIMEOUT_HOURS", "24")),
        )

def get_settings() -> Settings:
    """Получить настройки приложения"""
    return Settings.from_env() 