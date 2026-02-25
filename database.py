import asyncio
import aiosqlite
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from config import BotConfig

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Асинхронный менеджер базы данных SQLite"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or BotConfig.DATABASE_PATH
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def initialize(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            self._connection = await aiosqlite.connect(self.db_path)
            await self._create_tables()
            logger.info(f"База данных инициализирована: {self.db_path}")
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise
    
    async def close(self):
        """Закрытие соединения с базой данных"""
        if self._connection:
            await self._connection.close()
            logger.info("Соединение с БД закрыто")
    
    async def _create_tables(self):
        """Создание таблиц базы данных"""
        
        # Таблица пользователей
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_premium BOOLEAN DEFAULT FALSE,
                is_blocked BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица сообщений
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_type TEXT NOT NULL,  -- 'user' или 'bot'
                message_text TEXT NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                response_time REAL,  -- время ответа в секундах
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Таблица сессий диалога
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,  -- 'user' или 'model'
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Таблица кэша ответов
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS response_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_hash TEXT UNIQUE NOT NULL,
                response_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        ''')
        
        # Таблица статистики
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                total_messages INTEGER DEFAULT 0,
                total_users INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                avg_response_time REAL DEFAULT 0
            )
        ''')
        
        # Создание индексов для оптимизации
        await self._connection.execute('CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)')
        await self._connection.execute('CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)')
        await self._connection.execute('CREATE INDEX IF NOT EXISTS idx_conversations_user_session ON conversations(user_id, session_id)')
        await self._connection.execute('CREATE INDEX IF NOT EXISTS idx_cache_prompt_hash ON response_cache(prompt_hash)')
        await self._connection.execute('CREATE INDEX IF NOT EXISTS idx_cache_expires_at ON response_cache(expires_at)')
        
        await self._connection.commit()
        logger.info("Таблицы базы данных созданы")
    
    # Пользователи
    async def add_user(self, user_id: int, username: str, first_name: str, last_name: str = None) -> bool:
        """Добавление нового пользователя"""
        try:
            await self._connection.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_active)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, username, first_name, last_name))
            await self._connection.commit()
            logger.info(f"Пользователь добавлен/обновлен: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return False
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        try:
            cursor = await self._connection.execute(
                'SELECT * FROM users WHERE user_id = ?', (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
    
    async def update_user_activity(self, user_id: int):
        """Обновление времени последней активности пользователя"""
        try:
            await self._connection.execute('''
                UPDATE users 
                SET last_active = CURRENT_TIMESTAMP, message_count = message_count + 1
                WHERE user_id = ?
            ''', (user_id,))
            await self._connection.commit()
        except Exception as e:
            logger.error(f"Ошибка обновления активности: {e}")
    
    # Сообщения
    async def save_message(self, user_id: int, message_type: str, message_text: str, 
                          tokens_used: int = 0, response_time: float = None) -> bool:
        """Сохранение сообщения"""
        try:
            await self._connection.execute('''
                INSERT INTO messages (user_id, message_type, message_text, tokens_used, response_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, message_type, message_text, tokens_used, response_time))
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения: {e}")
            return False
    
    # Диалоги
    async def save_conversation_message(self, user_id: int, session_id: str, 
                                     role: str, content: str) -> bool:
        """Сохранение сообщения в диалоге"""
        try:
            await self._connection.execute('''
                INSERT INTO conversations (user_id, session_id, role, content)
                VALUES (?, ?, ?, ?)
            ''', (user_id, session_id, role, content))
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения диалога: {e}")
            return False
    
    async def get_conversation_history(self, user_id: int, session_id: str, 
                                      limit: int = 10) -> List[Dict]:
        """Получение истории диалога"""
        try:
            cursor = await self._connection.execute('''
                SELECT role, content, created_at
                FROM conversations
                WHERE user_id = ? AND session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            ''', (user_id, session_id, limit))
            
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения истории диалога: {e}")
            return []
    
    async def clear_conversation(self, user_id: int, session_id: str) -> bool:
        """Очистка истории диалога"""
        try:
            await self._connection.execute('''
                DELETE FROM conversations
                WHERE user_id = ? AND session_id = ?
            ''', (user_id, session_id))
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка очистки диалога: {e}")
            return False
    
    # Кэш
    async def get_cached_response(self, prompt_hash: str) -> Optional[str]:
        """Получение закэшированного ответа"""
        try:
            cursor = await self._connection.execute('''
                SELECT response_text FROM response_cache
                WHERE prompt_hash = ? AND expires_at > CURRENT_TIMESTAMP
            ''', (prompt_hash,))
            
            row = await cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Ошибка получения кэша: {e}")
            return None
    
    async def cache_response(self, prompt_hash: str, response_text: str, ttl_hours: int = 1) -> bool:
        """Сохранение ответа в кэш"""
        try:
            expires_at = datetime.now() + timedelta(hours=ttl_hours)
            await self._connection.execute('''
                INSERT OR REPLACE INTO response_cache (prompt_hash, response_text, expires_at)
                VALUES (?, ?, ?)
            ''', (prompt_hash, response_text, expires_at))
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения в кэш: {e}")
            return False
    
    async def cleanup_expired_cache(self):
        """Очистка устаревшего кэша"""
        try:
            await self._connection.execute('''
                DELETE FROM response_cache WHERE expires_at <= CURRENT_TIMESTAMP
            ''')
            await self._connection.commit()
            logger.info("Очистка устаревшего кэша завершена")
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")
    
    # Статистика
    async def get_statistics(self) -> Dict[str, Any]:
        """Получение общей статистики"""
        try:
            stats = {}
            
            # Количество пользователей
            cursor = await self._connection.execute('SELECT COUNT(*) FROM users')
            stats['total_users'] = (await cursor.fetchone())[0]
            
            # Количество сообщений
            cursor = await self._connection.execute('SELECT COUNT(*) FROM messages')
            stats['total_messages'] = (await cursor.fetchone())[0]
            
            # Активные пользователи за последние 24 часа
            cursor = await self._connection.execute('''
                SELECT COUNT(DISTINCT user_id) FROM users 
                WHERE last_active > datetime('now', '-1 day')
            ''')
            stats['active_users_24h'] = (await cursor.fetchone())[0]
            
            # Среднее время ответа
            cursor = await self._connection.execute('''
                SELECT AVG(response_time) FROM messages 
                WHERE message_type = 'bot' AND response_time IS NOT NULL
            ''')
            avg_time = await cursor.fetchone()
            stats['avg_response_time'] = avg_time[0] if avg_time and avg_time[0] else 0
            
            return stats
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}
    
    async def update_daily_statistics(self):
        """Обновление ежедневной статистики"""
        try:
            today = datetime.now().date()
            
            # Количество сообщений за сегодня
            cursor = await self._connection.execute('''
                SELECT COUNT(*) FROM messages WHERE date(created_at) = ?
            ''', (today,))
            messages_today = (await cursor.fetchone())[0]
            
            # Количество активных пользователей за сегодня
            cursor = await self._connection.execute('''
                SELECT COUNT(DISTINCT user_id) FROM messages WHERE date(created_at) = ?
            ''', (today,))
            users_today = (await cursor.fetchone())[0]
            
            # Среднее время ответа за сегодня
            cursor = await self._connection.execute('''
                SELECT AVG(response_time) FROM messages 
                WHERE message_type = 'bot' AND date(created_at) = ? AND response_time IS NOT NULL
            ''', (today,))
            avg_time = await cursor.fetchone()
            avg_response_time = avg_time[0] if avg_time and avg_time[0] else 0
            
            # Сохранение статистики
            await self._connection.execute('''
                INSERT OR REPLACE INTO statistics (date, total_messages, total_users, avg_response_time)
                VALUES (?, ?, ?, ?)
            ''', (today, messages_today, users_today, avg_response_time))
            
            await self._connection.commit()
            logger.info(f"Ежедневная статистика обновлена за {today}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления статистики: {e}")

# Глобальный экземпляр менеджера БД
_db_manager: Optional[DatabaseManager] = None

async def get_database() -> DatabaseManager:
    """Получить экземпляр менеджера базы данных (синглтон)"""
    global _db_manager
    
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    
    return _db_manager

async def close_database():
    """Закрыть менеджер базы данных"""
    global _db_manager
    
    if _db_manager:
        await _db_manager.close()
        _db_manager = None
