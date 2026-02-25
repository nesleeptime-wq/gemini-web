import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from config import BotConfig

logger = logging.getLogger(__name__)

@dataclass
class UserSession:
    """Класс для хранения сессии пользователя"""
    user_id: int
    session_id: str
    created_at: datetime
    last_activity: datetime
    message_count: int = 0
    context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}
    
    def is_expired(self, timeout_minutes: int = None) -> bool:
        """Проверка истекла ли сессия"""
        timeout = timeout_minutes or BotConfig.SESSION_TIMEOUT // 60
        expiry_time = self.last_activity + timedelta(minutes=timeout)
        return datetime.now() > expiry_time
    
    def update_activity(self):
        """Обновление времени последней активности"""
        self.last_activity = datetime.now()
        self.message_count += 1
    
    def to_dict(self) -> Dict:
        """Преобразование в словарь"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_activity'] = self.last_activity.isoformat()
        return data

class SessionManager:
    """Менеджер сессий пользователей"""
    
    def __init__(self):
        self._sessions: Dict[str, UserSession] = {}  # user_id -> UserSession
        self._lock = asyncio.Lock()
        
    async def get_session(self, user_id: int) -> UserSession:
        """Получить или создать сессию пользователя"""
        async with self._lock:
            user_id_str = str(user_id)
            
            # Проверяем существующую сессию
            if user_id_str in self._sessions:
                session = self._sessions[user_id_str]
                
                # Проверяем не истекла ли сессия
                if session.is_expired():
                    logger.info(f"Сессия пользователя {user_id} истекла, создаем новую")
                    session = await self._create_new_session(user_id)
                    self._sessions[user_id_str] = session
                else:
                    session.update_activity()
                    
                return session
            
            # Создаем новую сессию
            session = await self._create_new_session(user_id)
            self._sessions[user_id_str] = session
            return session
    
    async def _create_new_session(self, user_id: int) -> UserSession:
        """Создание новой сессии"""
        session_id = self._generate_session_id(user_id)
        now = datetime.now()
        
        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            created_at=now,
            last_activity=now
        )
        
        logger.info(f"Создана новая сессия для пользователя {user_id}: {session_id}")
        return session
    
    def _generate_session_id(self, user_id: int) -> str:
        """Генерация ID сессии"""
        timestamp = datetime.now().isoformat()
        data = f"{user_id}_{timestamp}_{hash(user_id)}"
        return hashlib.md5(data.encode()).hexdigest()[:16]
    
    async def clear_session(self, user_id: int) -> bool:
        """Очистка сессии пользователя"""
        async with self._lock:
            user_id_str = str(user_id)
            
            if user_id_str in self._sessions:
                del self._sessions[user_id_str]
                logger.info(f"Сессия пользователя {user_id} очищена")
                return True
            
            return False
    
    async def get_all_sessions(self) -> List[UserSession]:
        """Получить все активные сессии"""
        async with self._lock:
            return list(self._sessions.values())
    
    async def cleanup_expired_sessions(self):
        """Очистка истекших сессий"""
        async with self._lock:
            expired_sessions = []
            
            for user_id_str, session in self._sessions.items():
                if session.is_expired():
                    expired_sessions.append(user_id_str)
            
            for user_id_str in expired_sessions:
                del self._sessions[user_id_str]
                logger.info(f"Удалена истекшая сессия: {user_id_str}")
            
            if expired_sessions:
                logger.info(f"Очищено {len(expired_sessions)} истекших сессий")
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """Получить статистику сессий"""
        async with self._lock:
            total_sessions = len(self._sessions)
            total_messages = sum(session.message_count for session in self._sessions.values())
            
            # Сессии по возрасту
            now = datetime.now()
            recent_sessions = 0  # последние 5 минут
            old_sessions = 0     # старше 30 минут
            
            for session in self._sessions.values():
                age_minutes = (now - session.created_at).total_seconds() / 60
                if age_minutes <= 5:
                    recent_sessions += 1
                elif age_minutes >= 30:
                    old_sessions += 1
            
            return {
                'total_sessions': total_sessions,
                'total_messages': total_messages,
                'recent_sessions': recent_sessions,
                'old_sessions': old_sessions,
                'avg_messages_per_session': total_messages / total_sessions if total_sessions > 0 else 0
            }
    
    async def set_context(self, user_id: int, key: str, value: Any):
        """Установить контекстное значение для сессии"""
        session = await self.get_session(user_id)
        session.context[key] = value
    
    async def get_context(self, user_id: int, key: str, default: Any = None) -> Any:
        """Получить контекстное значение из сессии"""
        session = await self.get_session(user_id)
        return session.context.get(key, default)
    
    async def clear_context(self, user_id: int):
        """Очистить контекст сессии"""
        session = await self.get_session(user_id)
        session.context.clear()

class ConversationManager:
    """Менеджер диалогов и контекста"""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self._conversation_history: Dict[str, List[Dict]] = {}  # session_id -> history
        self._lock = asyncio.Lock()
    
    async def add_message(self, user_id: int, role: str, content: str) -> str:
        """Добавить сообщение в историю диалога"""
        session = await self.session_manager.get_session(user_id)
        session_id = session.session_id
        
        async with self._lock:
            if session_id not in self._conversation_history:
                self._conversation_history[session_id] = []
            
            message = {
                'role': role,
                'content': content,
                'timestamp': datetime.now().isoformat()
            }
            
            self._conversation_history[session_id].append(message)
            
            # Ограничиваем размер истории
            max_history = 20  # последние 20 сообщений
            if len(self._conversation_history[session_id]) > max_history:
                self._conversation_history[session_id] = self._conversation_history[session_id][-max_history:]
            
            logger.debug(f"Добавлено сообщение в диалог {session_id}: {role}")
            return session_id
    
    async def get_conversation_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получить историю диалога пользователя"""
        session = await self.session_manager.get_session(user_id)
        session_id = session.session_id
        
        async with self._lock:
            if session_id in self._conversation_history:
                history = self._conversation_history[session_id]
                # Возвращаем последние 'limit' сообщений
                return history[-limit:] if len(history) > limit else history
            
            return []
    
    async def clear_conversation(self, user_id: int) -> bool:
        """Очистить историю диалога пользователя"""
        session = await self.session_manager.get_session(user_id)
        session_id = session.session_id
        
        async with self._lock:
            if session_id in self._conversation_history:
                del self._conversation_history[session_id]
                logger.info(f"История диалога очищена для пользователя {user_id}")
                return True
            
            return False
    
    async def get_formatted_history(self, user_id: int) -> List[Dict]:
        """Получить отформатированную историю для API"""
        history = await self.get_conversation_history(user_id)
        
        formatted = []
        for msg in history:
            formatted.append({
                'role': msg['role'],
                'parts': [{'text': msg['content']}]
            })
        
        return formatted
    
    async def cleanup_old_conversations(self):
        """Очистка старых диалогов"""
        async with self._lock:
            expired_sessions = []
            
            for session_id in self._conversation_history.keys():
                # Находим соответствующую сессию
                session_found = False
                for session in self.session_manager._sessions.values():
                    if session.session_id == session_id:
                        if session.is_expired():
                            expired_sessions.append(session_id)
                        session_found = True
                        break
                
                # Если сессия не найдена, удаляем диалог
                if not session_found:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self._conversation_history[session_id]
            
            if expired_sessions:
                logger.info(f"Очищено {len(expired_sessions)} старых диалогов")

# Глобальные экземпляры
_session_manager: Optional[SessionManager] = None
_conversation_manager: Optional[ConversationManager] = None

async def get_session_manager() -> SessionManager:
    """Получить экземпляр менеджера сессий"""
    global _session_manager
    
    if _session_manager is None:
        _session_manager = SessionManager()
    
    return _session_manager

async def get_conversation_manager() -> ConversationManager:
    """Получить экземпляр менеджера диалогов"""
    global _conversation_manager
    
    if _conversation_manager is None:
        session_manager = await get_session_manager()
        _conversation_manager = ConversationManager(session_manager)
    
    return _conversation_manager

async def cleanup_sessions():
    """Очистка всех сессий и диалогов"""
    session_manager = await get_session_manager()
    conversation_manager = await get_conversation_manager()
    
    await session_manager.cleanup_expired_sessions()
    await conversation_manager.cleanup_old_conversations()
    
    logger.info("Очистка сессий и диалогов завершена")
