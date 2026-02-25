import asyncio
import logging
import time
import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

from config import AppConfig, BotConfig, GeminiConfig
from gemini_client import get_gemini_client, close_gemini_client
from database import get_database, close_database
from session_manager import get_session_manager, get_conversation_manager, cleanup_sessions

# Настройка логирования
logging.basicConfig(
    format=BotConfig.LOG_FORMAT,
    level=getattr(logging, BotConfig.LOG_LEVEL)
)
logger = logging.getLogger(__name__)

class GeminiBot:
    """Основной класс Telegram бота с Gemini AI"""
    
    def __init__(self):
        self.app = Application.builder().token(BotConfig.TOKEN).build()
        self.gemini_client = None
        self.database = None
        self.session_manager = None
        self.conversation_manager = None
        self.user_profiles = {}  # Хранение профилей пользователей
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        
        # Команды
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("clear", self.clear_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command, filters=filters.User(BotConfig.ADMIN_ID)))
        self.app.add_handler(CommandHandler("info", self.info_command))
        self.app.add_handler(CommandHandler("profile", self.profile_command))
        self.app.add_handler(CommandHandler("profiles", self.profiles_command))
        self.app.add_handler(CommandHandler("web", self.web_command))
        
        # Callback кнопки
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Текстовые сообщения
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
        
        # Обработчик ошибок
        self.app.add_error_handler(self.error_handler)
    
    async def initialize(self):
        """Инициализация компонентов бота"""
        try:
            # Валидация конфигурации
            AppConfig.validate_all()
            
            # Инициализация компонентов
            self.gemini_client = await get_gemini_client()
            self.database = await get_database()
            self.session_manager = await get_session_manager()
            self.conversation_manager = await get_conversation_manager()
            
            # Тест подключения к Gemini
            if await self.gemini_client.test_connection():
                logger.info("✅ Подключение к Gemini API успешно")
            else:
                logger.warning("⚠️ Проблемы с подключением к Gemini API")
            
            logger.info("🚀 Бот инициализирован и готов к работе")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота: {e}")
            raise
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        
        try:
            # Сохранение пользователя в БД
            await self.database.add_user(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "",
                last_name=user.last_name or ""
            )
            
            # Создание приветственного сообщения
            welcome_text = f"""🤖 *Добро пожаловать, {user.first_name}!*

Я ваш персональный ИИ-ассистент на базе Google Gemini 🧠

*О себе:*
Я — современный искусственный интеллект, созданный для помощи в различных сферах деятельности. Обладаю глубокими знаниями и способностью адаптироваться под ваши потребности.

*Мои возможности:*
• Анализ и решение сложных задач
• Составление текстов любой тематики
• Переводы и адаптация контента
• Помощь в учебе и работе
• Творческая работа и идеи

*Доступные команды:*
/start — Перезапуск бота
/help — Подробная справка
/clear — Очистка истории диалога
/info — Статистика использования
/profile — Текущий стиль общения
/profiles — Все доступные стили
/web — Профессиональный веб-интерфейс

*Стили общения:*
По умолчанию использую профессиональный стиль общения без лишних элементов оформления.

Просто напишите ваше сообщение, и я помогу решить любую задачу!"""
            
            keyboard = [
                [InlineKeyboardButton("🌐 Веб-интерфейс", url="https://nesleeptime-wq.github.io/gemini-web/")],
                [InlineKeyboardButton("📖 Помощь", callback_data="help")],
                [InlineKeyboardButton("💬 Начать диалог", callback_data="chat")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            
            logger.info(f"Новый пользователь: {user.id} ({user.username})")
            
        except Exception as e:
            logger.error(f"Ошибка в start_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🤖 **Помощь по боту**

**Основные команды:**
/start - Перезапустить бота
/help - Показать это сообщение
/clear - Очистить историю диалога
/info - Информация о боте

**Как использовать:**
1. Просто напишите любое сообщение
2. Я запомню контекст нашего диалога
3. Могу отвечать на вопросы и помогать с задачами

**Возможности:**
• 💬 Общение на русском языке
• 🧠 Использует Google Gemini AI
• 📝 Помнит историю диалога
• 🔄 Работает через VPN прокси
• ⚡ Быстрые ответы

**Ограничения:**
• Максимальная длина сообщения: 4096 символов
• История диалога хранится 20 сообщений
• Сессия истекает через 30 минут бездействия

**Поддержка:**
Если возникли проблемы, напишите администратору.
        """
        
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Очистка истории диалога"""
        user_id = update.effective_user.id
        
        try:
            # Очистка в менеджере диалогов
            await self.conversation_manager.clear_conversation(user_id)
            
            # Очистка в БД
            session = await self.session_manager.get_session(user_id)
            await self.database.clear_conversation(user_id, session.session_id)
            
            await update.message.reply_text(
                "🧹 **История диалога очищена!**\n\nНачнем новый разговор! 😊",
                parse_mode="Markdown"
            )
            
            logger.info(f"Пользователь {user_id} очистил историю диалога")
            
        except Exception as e:
            logger.error(f"Ошибка очистки диалога: {e}")
            await update.message.reply_text("❌ Не удалось очистить историю. Попробуйте позже.")
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Информация о боте"""
        try:
            stats = await self.database.get_statistics()
            
            info_text = f"""
🤖 **Информация о боте**

**Версия:** 1.0.0
**AI модель:** Google Gemini Pro
**Разработчик:** AI Assistant

📊 **Статистика:**
👥 Пользователей: {stats.get('total_users', 0)}
💬 Сообщений: {stats.get('total_messages', 0)}
⏱️ Среднее время ответа: {stats.get('avg_response_time', 0):.2f}с
🔥 Активных за 24ч: {stats.get('active_users_24h', 0)}

**Технологии:**
• Python 3.8+ (async)
• python-telegram-bot
• Google Gemini API
• SQLite + aiosqlite
• VPN прокси поддержка

**Статус:** 🟢 Онлайн
            """
            
            await update.message.reply_text(info_text, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Ошибка в info_command: {e}")
            await update.message.reply_text("❌ Не удалось получить информацию.")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда статистики для администратора"""
        try:
            # Получение различной статистики
            db_stats = await self.database.get_statistics()
            session_stats = await self.session_manager.get_session_stats()
            
            stats_text = f"""
📊 **Административная статистика**

**База данных:**
👥 Всего пользователей: {db_stats.get('total_users', 0)}
💬 Всего сообщений: {db_stats.get('total_messages', 0)}
🔥 Активных 24ч: {db_stats.get('active_users_24h', 0)}
⏱️ Средний ответ: {db_stats.get('avg_response_time', 0):.2f}с

**Сессии:**
� Активных сессий: {session_stats['total_sessions']}
�📝 Всего сообщений: {session_stats['total_messages']}
🆕 Новых (5мин): {session_stats['recent_sessions']}
📅 Старых (30мин+): {session_stats['old_sessions']}
📈 Средних/сессия: {session_stats['avg_messages_per_session']:.1f}

**Система:**
🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🤖 Статус: 🟢 Онлайн
            """
            
            await update.message.reply_text(stats_text, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Ошибка в stats_command: {e}")
            await update.message.reply_text("❌ Ошибка получения статистики")
    
    async def web_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправка ссылки на веб-интерфейс"""
        web_url = "https://nesleeptime-wq.github.io/gemini-web/"
        
        keyboard = [
            [InlineKeyboardButton("🌐 Открыть веб-интерфейс", url=web_url)],
            [InlineKeyboardButton("📖 Помощь", callback_data="help")],
            [InlineKeyboardButton("💬 Начать диалог", callback_data="chat")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🌐 *Веб-интерфейс Gemini AI*\n\n"
            f"Для более удобного общения с AI используйте наш веб-сайт:\n"
            f"🔗 {web_url}\n\n"
            f"✨ *Преимущества веб-версии:*\n"
            f"• 🎨 Красивый дизайн\n"
            f"• 📱 Оптимизация для мобильных\n"
            f"• 💾 Сохранение истории\n"
            f"• 🎭 Быстрая смена личностей",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
        logger.info(f"Пользователь {update.effective_user.id} запросил веб-интерфейс")
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка профиля пользователя"""
        user_id = update.effective_user.id
        
        try:
            # Получаем профиль из аргументов
            if context.args and len(context.args) > 0:
                profile_name = context.args[0].lower()
                if self._set_user_profile(user_id, profile_name):
                    profile_info = self._get_profile_info(profile_name)
                    await update.message.reply_text(
                        f"✅ *Профиль изменен:* {profile_info['name']}\n"
                        f"📝 {profile_info['description']}",
                        parse_mode="Markdown"
                    )
                else:
                    await update.message.reply_text(
                        "❌ Неизвестный профиль. Используйте /profiles для списка."
                    )
            else:
                # Показываем текущий профиль
                current_profile = self.user_profiles.get(user_id, 'default')
                profile_info = self._get_profile_info(current_profile)
                await update.message.reply_text(
                    f"🎭 *Текущий профиль:* {profile_info['name']}\n"
                    f"📝 {profile_info['description']}\n\n"
                    "Используйте: /profile <имя_профиля>",
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"Ошибка в profile_command: {e}")
            await update.message.reply_text("❌ Ошибка установки профиля")
    
    async def profiles_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать доступные профили"""
        profiles_text = """
🎭 **Доступные профили:**

🤖 **default** - Стандартный ассистент
🎭 **poet** - Поэт (отвечает стихами)
👨‍🏫 **teacher** - Учитель (объясняет пошагово)  
👫 **friend** - Друг (неформальное общение)
👔 **professional** - Профессионал (деловой стиль)

**Использование:**
`/profile <имя_профиля>"

**Пример:**
`/profile poet`
        """
        
        await update.message.reply_text(profiles_text, parse_mode="Markdown")
    
    def _set_user_profile(self, user_id: int, profile_name: str) -> bool:
        """Установить профиль пользователя"""
        valid_profiles = ['default', 'poet', 'teacher', 'friend', 'professional']
        if profile_name in valid_profiles:
            self.user_profiles[user_id] = profile_name
            return True
        return False
    
    def _get_profile_info(self, profile_name: str) -> dict:
        """Получить информацию о профиле"""
        profiles = {
            'default': {
                'name': 'Стандартный',
                'description': 'Дружелюбный и полезный ассистент',
                'icon': '🤖'
            },
            'poet': {
                'name': 'Поэт',
                'description': 'Отвечает в стихотворной форме',
                'icon': '🎭'
            },
            'teacher': {
                'name': 'Учитель',
                'description': 'Объясняет сложные вещи пошагово',
                'icon': '👨‍🏫'
            },
            'friend': {
                'name': 'Друг',
                'description': 'Неформальное общение с юмором',
                'icon': '👫'
            },
            'professional': {
                'name': 'Профессионал',
                'description': 'Формальные и структурированные ответы',
                'icon': '👔'
            }
        }
        return profiles.get(profile_name, profiles['default'])
    
    def _get_system_prompt(self, user_id: int) -> str:
        """Получить системный промпт для пользователя"""
        profile_name = self.user_profiles.get(user_id, 'default')
        
        profiles_prompts = {
            'default': "Ты — дружелюбный и полезный ИИ-ассистент. Отвечай на русском языке просто и понятно. Будь вежливым и терпеливым. Помогай решать любые вопросы.",
            'poet': "Ты — поэт. Отвечай на русском языке в стихотворной форме. Используй красивые метафоры и рифмы. Будь творческим и вдохновляющим.",
            'teacher': "Ты — учитель. Отвечай на русском языке просто и понятно, объясняй сложные вещи пошагово. Будь терпеливым и поддерживающим.",
            'friend': "Ты — лучший друг. Отвечай на русском языке неформально, дружелюбно, с юмором. Используй эмодзи и будь поддерживающим.",
            'professional': "Ты — профессиональный консультант. Отвечай на русском языке формально, по делу, структурированно. Давай точную и полезную информацию."
        }
        
        return profiles_prompts.get(profile_name, profiles_prompts['default'])
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на inline кнопки"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "help":
            # Отправляем help сообщение напрямую, не через help_command
            help_text = """
🤖 **Помощь по Gemini боту**

**Команды:**
/start - Перезапуск бота
/help - Это сообщение
/clear - Очистить историю диалога
/info - Информация о боте
/profile - Текущий профиль
/profiles - Доступные профили

**Профили:**
🤖 default - Стандартный ассистент
🎭 poet - Поэт (отвечает стихами)
👨‍🏫 teacher - Учитель (объясняет пошагово)
👫 friend - Друг (неформальное общение)
👔 professional - Профессионал (деловой стиль)

**Использование профилей:**
/profile poet

**Возможности:**
• 💬 Общение на русском языке
• 🧠 Использует Google Gemini AI
• 📝 Помнит историю диалога
• 🔄 Работает через VPN прокси
• ⚡ Быстрые ответы

**Ограничения:**
• Максимальная длина сообщения: 4096 символов
• История диалога хранится 20 сообщений
• Сессия истекает через 30 минут бездействия

**Поддержка:**
Если возникли проблемы, напишите администратору.
            """
            
            await query.edit_message_text(help_text, parse_mode="Markdown")
            
        elif query.data == "chat":
            await query.edit_message_text(
                "💬 **Отлично! Просто напишите мне любое сообщение!**\n\nЯ готов помочь вам с любыми вопросами! 😊",
                parse_mode="Markdown"
            )
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Основной обработчик сообщений"""
        user = update.effective_user
        message_text = update.message.text
        
        try:
            # Проверка длины сообщения
            if len(message_text) > BotConfig.MAX_MESSAGE_LENGTH:
                await update.message.reply_text(
                    f"❌ Слишком длинное сообщение. Максимум {BotConfig.MAX_MESSAGE_LENGTH} символов."
                )
                return
            
            # Проверка безопасности (простая)
            if self._is_blocked_content(message_text):
                await update.message.reply_text(
                    "❌ Ваше сообщение содержит запрещенный контент."
                )
                return
            
            # Проверяем кэш перед запросом к API
            cache_key = hashlib.md5(message_text.encode()).hexdigest()
            cached_response = await self.database.get_cached_response(cache_key)
            
            if cached_response:
                await update.message.reply_text(cached_response)
                logger.info(f"Ответ из кэша для {user.id}")
                return
            
            # Получаем или создаем сессию
            session = await self.session_manager.get_session(user.id)
            
            # Получаем историю диалога
            conversation_history = await self.conversation_manager.get_conversation(user.id, session.session_id)
            
            # Получаем системный промпт для профиля
            system_prompt = self._get_system_prompt(user.id)
            
            # Отправка индикатора набора текста
            await update.message.chat_action("typing")
            
            # Генерация ответа
            start_time = time.time()
            response = await self.gemini_client.generate_response(
                prompt=message_text,
                conversation_history=conversation_history,
                system_prompt=system_prompt
            )
            response_time = time.time() - start_time
            
            # Сохранение ответа в кэш на 1 час
            await self.database.cache_response(cache_key, response, ttl=3600)
            
            # Сохранение сообщения в БД
            await self.database.add_message(
                user_id=user.id,
                session_id=session.session_id,
                message_type="user",
                content=message_text
            )
            await self.database.add_message(
                user_id=user.id,
                session_id=session.session_id,
                message_type="bot",
                content=response
            )
            
            # Обновление истории диалога
            await self.conversation_manager.add_message(user.id, session.session_id, message_text, "user")
            await self.conversation_manager.add_message(user.id, session.session_id, response, "model")
            
            # Отправка ответа пользователю с форматированием
            formatted_response = self._format_response(response)
            await update.message.reply_text(formatted_response)
            
            logger.info(f"Обработано сообщение от {user.id}, время ответа: {response_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Ошибка обработке сообщения от {user.id}: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке сообщения. Попробуйте позже."
            )
    
    def _format_response(self, response: str) -> str:
        """Профессиональное форматирование ответа для Telegram"""
        # Очищаем от лишних пробелов в начале и конце
        response = response.strip()
        
        # Полностью убираем markdown символы для чистого текста
        response = response.replace('**', '')  # Удаляем жирный текст
        response = response.replace('*', '')   # Удаляем курсив
        response = response.replace('`', '')    # Удаляем код
        
        # Исправляем длинные тире на обычные
        response = response.replace('—', '—')  # эм-тире оставляем для красоты
        response = response.replace('–', '–')    # эн-тире оставляем
        
        # Заменяем множественные пробелы на одинарные
        import re
        response = re.sub(r'\s+', ' ', response)
        
        # Очищаем от пустых строк в начале и конце
        lines = response.split('\n')
        # Удаляем пустые строки в начале
        while lines and not lines[0].strip():
            lines.pop(0)
        # Удаляем пустые строки в конце  
        while lines and not lines[-1].strip():
            lines.pop()
        
        # Собираем обратно с правильными переносами
        response = '\n'.join(lines)
        
        # Дополнительная очистка от артефактов
        response = response.replace(' \n', '\n')  # пробел перед переносом
        response = response.replace('\n ', '\n')   # пробел после переноса
        
        # Финальная очистка - удаляем все спецсимволы которые могут сломать Telegram
        response = re.sub(r'[^\w\s\-\.\,\!\?\n\r]', '', response)
        
        return response
    
    def _is_blocked_content(self, text: str) -> bool:
        """Простая проверка на запрещенный контент"""
        blocked_keywords = [
            'спам', 'реклама', 'порно', 'насилие', 'терроризм',
            ' наркотики', 'взрыв', 'убийство'
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in blocked_keywords)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Ошибка {context.error}")
        
        if update:
            try:
                await update.message.reply_text(
                    "❌ Произошла непредвиденная ошибка. Попробуйте позже."
                )
            except:
                pass
    
    async def cleanup_task(self):
        """Фоновая задача для очистки"""
        while True:
            try:
                await cleanup_sessions()
                await self.database.cleanup_expired_cache()
                await self.database.update_daily_statistics()
                await asyncio.sleep(3600)  # Каждый час
            except Exception as e:
                logger.error(f"Ошибка в cleanup_task: {e}")
                await asyncio.sleep(300)  # Повторить через 5 минут
    
    def run(self):
        """Запуск бота"""
        # Инициализация в синхронном режиме
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.initialize())
            logger.info("🚀 Бот запускается...")
            self.app.run_polling(allowed_updates=Update.ALL_TYPES)
        except KeyboardInterrupt:
            logger.info("🛑 Остановка бота...")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            # Закрытие ресурсов
            loop.run_until_complete(close_gemini_client())
            loop.run_until_complete(close_database())
            loop.close()
            logger.info("👋 Бот остановлен")

if __name__ == '__main__':
    bot = GeminiBot()
    bot.run()
