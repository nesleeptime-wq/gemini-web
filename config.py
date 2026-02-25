import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class ProxyConfig:
    """Конфигурация прокси"""
    
    # HTTP прокси (из вашей конфигурации V2Ray)
    HTTP_PROXY = os.getenv('HTTP_PROXY', 'http://127.0.0.1:10809')
    
    # SOCKS прокси (из вашей конфигурации V2Ray)
    SOCKS_PROXY = os.getenv('SOCKS_PROXY', 'socks5://127.0.0.1:10808')
    
    # Тип прокси для использования (http/socks5/none)
    PROXY_TYPE = os.getenv('PROXY_TYPE', 'none')  # или 'socks5' или 'http'
    
    @classmethod
    def get_proxy_url(cls) -> str:
        """Получить URL прокси для использования"""
        if cls.PROXY_TYPE == 'socks5':
            return cls.SOCKS_PROXY
        return cls.HTTP_PROXY

class GeminiConfig:
    """Конфигурация Google Gemini API"""
    
    # API ключ для Google Gemini
    API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyAgqMSeDlfRAjULMwWAFLwa4PqB9BoWZMM')
    
    # URL эндпоинта Gemini API - исправляем на рабочую модель
    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    
    # Модель для использования
    MODEL_NAME = "gemini-1.5-flash"
    
    # Параметры генерации
    TEMPERATURE = float(os.getenv('GEMINI_TEMPERATURE', '0.7'))
    MAX_TOKENS = int(os.getenv('GEMINI_MAX_TOKENS', '2048'))
    TOP_P = float(os.getenv('GEMINI_TOP_P', '0.8'))
    TOP_K = int(os.getenv('GEMINI_TOP_K', '40'))
    
    # Системный промпт для бота
    SYSTEM_PROMPT = os.getenv('SYSTEM_PROMPT', 
        """Ты — дружелюбный и полезный ИИ-ассистент. 
        Отвечай на русском языке просто и понятно. 
        Будь вежливым и терпеливым. Помогай решать любые вопросы.""")
    
    @classmethod
    def validate(cls) -> bool:
        """Проверить конфигурацию"""
        if not cls.API_KEY or cls.API_KEY == 'YOUR_GEMINI_API_KEY':
            raise ValueError("GEMINI_API_KEY не установлен")
        return True

class BotConfig:
    """Конфигурация Telegram бота"""
    
    # Токен бота
    TOKEN = os.getenv('BOT_TOKEN', '8571176408:AAHA3oBsDMFRkotdijJ742mPddRFk9gGa-Q')
    
    # Путь к базе данных
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'bot.db')
     
    # ID администратора
    ADMIN_ID = int(os.getenv('ADMIN_ID', '6465758675'))
    
    # Настройки логирования
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Ограничения
    MAX_MESSAGE_LENGTH = 4096
    RATE_LIMIT = int(os.getenv('RATE_LIMIT', '3'))  # сообщений в секунду
    
    # Настройки кэширования
    CACHE_TTL = int(os.getenv('CACHE_TTL', '3600'))  # 1 час
    MAX_CACHE_SIZE = int(os.getenv('MAX_CACHE_SIZE', '1000'))
    
    # Настройки сессий
    SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '1800'))  # 30 минут
    
    @classmethod
    def validate(cls) -> bool:
        """Проверить конфигурацию"""
        if not cls.TOKEN or cls.TOKEN == 'YOUR_BOT_TOKEN_HERE':
            raise ValueError("BOT_TOKEN не установлен")
        if cls.TOKEN and len(cls.TOKEN) < 10:
            raise ValueError("Неверный формат BOT_TOKEN")
        return True

class AppConfig:
    """Общая конфигурация приложения"""
    
    # Режим отладки
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # Настройки производительности
    MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', '10'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
    
    # Настройки безопасности
    ALLOWED_USERS = os.getenv('ALLOWED_USERS', '').split(',') if os.getenv('ALLOWED_USERS') else []
    BLOCKED_USERS = os.getenv('BLOCKED_USERS', '').split(',') if os.getenv('BLOCKED_USERS') else []
    
    @classmethod
    def validate_all(cls) -> bool:
        """Проверить всю конфигурацию"""
        BotConfig.validate()
        GeminiConfig.validate()
        return True
