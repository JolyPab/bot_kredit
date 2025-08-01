from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
from typing import Union

from config.settings import get_settings

class EncryptionService:
    """Сервис для шифрования персональных данных"""
    
    def __init__(self):
        self._fernet = None
        self._init_cipher()
    
    def _init_cipher(self):
        """Инициализация cipher для шифрования"""
        settings = get_settings()
        
        # Генерируем ключ из пароля
        password = settings.ENCRYPTION_KEY.encode()
        salt = b'stable_salt_for_credit_history_bot'  # В продакшене должен быть случайным
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password))
        self._fernet = Fernet(key)
    
    def encrypt(self, data: str) -> bytes:
        """Зашифровать строку"""
        if not data:
            return b''
        
        return self._fernet.encrypt(data.encode('utf-8'))
    
    def decrypt(self, encrypted_data: bytes) -> str:
        """Расшифровать данные"""
        if not encrypted_data:
            return ''
        
        try:
            decrypted = self._fernet.decrypt(encrypted_data)
            return decrypted.decode('utf-8')
        except Exception:
            # Если не удалось расшифровать, возвращаем пустую строку
            return ''
    
    def encrypt_dict(self, data: dict) -> dict:
        """Зашифровать значения в словаре"""
        encrypted = {}
        for key, value in data.items():
            if isinstance(value, str) and value:
                encrypted[key] = self.encrypt(value)
            else:
                encrypted[key] = value
        return encrypted
    
    def decrypt_dict(self, encrypted_data: dict) -> dict:
        """Расшифровать значения в словаре"""
        decrypted = {}
        for key, value in encrypted_data.items():
            if isinstance(value, bytes):
                decrypted[key] = self.decrypt(value)
            else:
                decrypted[key] = value
        return decrypted 