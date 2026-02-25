import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Optional, Any
from config import GeminiConfig, ProxyConfig

logger = logging.getLogger(__name__)

class GeminiClient:
    """Асинхронный клиент для Google Gemini API с поддержкой прокси"""
    
    def __init__(self):
        self.api_key = GeminiConfig.API_KEY
        self.api_url = GeminiConfig.API_URL
        self.proxy_url = ProxyConfig.get_proxy_url()
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Контекстный менеджер для создания сессии"""
        await self._create_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер для закрытия сессии"""
        await self.close()
        
    async def _create_session(self):
        """Создание HTTP сессии с прокси"""
        if self.session is None or self.session.closed:
            # Настройка прокси
            connector = None
            timeout = aiohttp.ClientTimeout(total=30)
            
            try:
                # Создаем коннектор
                connector = aiohttp.TCPConnector()
                    
                # Устанавливаем прокси через переменные окружения если нужно
                if ProxyConfig.PROXY_TYPE != 'none':
                    import os
                    os.environ['HTTP_PROXY'] = self.proxy_url
                    os.environ['HTTPS_PROXY'] = self.proxy_url
                    use_proxy = True
                else:
                    # Очищаем переменные прокси
                    import os
                    os.environ.pop('HTTP_PROXY', None)
                    os.environ.pop('HTTPS_PROXY', None)
                    use_proxy = False
                    
                self.session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    trust_env=use_proxy  # Использовать прокси только если настроен
                )
                
                if use_proxy:
                    logger.info(f"Сессия создана с прокси: {self.proxy_url}")
                else:
                    logger.info("Сессия создана без прокси")
                
            except Exception as e:
                logger.error(f"Ошибка создания сессии: {e}")
                # Создаем сессию без прокси как запасной вариант
                self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """Закрытие HTTP сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("HTTP сессия закрыта")
    
    def _prepare_request_data(self, prompt: str, conversation_history: List[Dict] = None, system_prompt: str = None) -> Dict[str, Any]:
        """Подготовка данных для запроса к Gemini API"""
        
        # Формируем содержимое сообщения
        contents = []
        
        # Добавляем системный промпт в начало
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": system_prompt}]
            })
            contents.append({
                "role": "model", 
                "parts": [{"text": "Понял! Буду следовать этому стилю."}]
            })
        elif GeminiConfig.SYSTEM_PROMPT:
            contents.append({
                "role": "user",
                "parts": [{"text": GeminiConfig.SYSTEM_PROMPT}]
            })
            contents.append({
                "role": "model", 
                "parts": [{"text": "Понял! Я буду дружелюбным и полезным ассистентом."}]
            })
        
        # Добавляем историю диалога
        if conversation_history:
            contents.extend(conversation_history)
        
        # Добавляем текущий промпт
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        # Формируем запрос
        request_data = {
            "contents": contents,
            "generationConfig": {
                "temperature": GeminiConfig.TEMPERATURE,
                "maxOutputTokens": GeminiConfig.MAX_TOKENS,
                "topP": GeminiConfig.TOP_P,
                "topK": GeminiConfig.TOP_K,
                "candidateCount": 1,
                "stopSequences": []
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH", 
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        }
        
        return request_data
    
    async def generate_response(self, prompt: str, conversation_history: List[Dict] = None, system_prompt: str = None) -> str:
        """Генерация ответа с помощью Gemini API"""
        
        if not self.session or self.session.closed:
            await self._create_session()
        
        try:
            # Подготовка данных запроса
            request_data = self._prepare_request_data(prompt, conversation_history, system_prompt)
            
            # URL с API ключом
            url = f"{self.api_url}?key={self.api_key}"
            
            # Заголовки
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'GeminiBot/1.0'
            }
            
            logger.info(f"Отправка запроса к Gemini API: {prompt[:100]}...")
            
            # Выполнение запроса через прокси
            proxy_url = self.proxy_url if ProxyConfig.PROXY_TYPE != 'none' else None
            
            async with self.session.post(
                url, 
                json=request_data, 
                headers=headers,
                proxy=proxy_url
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    
                    # Извлечение текста ответа
                    if 'candidates' in result and len(result['candidates']) > 0:
                        candidate = result['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            if len(candidate['content']['parts']) > 0:
                                response_text = candidate['content']['parts'][0].get('text', '')
                                logger.info(f"Получен ответ от Gemini: {response_text[:100]}...")
                                return response_text
                    
                    logger.error(f"Неожиданный формат ответа: {result}")
                    return "Извините, произошла ошибка при обработке ответа от ИИ."
                    
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка API Gemini ({response.status}): {error_text}")
                    
                    # Обработка распространенных ошибок
                    if response.status == 400:
                        return "Извините, запрос некорректен. Попробуйте переформулировать вопрос."
                    elif response.status == 429:
                        return "Слишком много запросов. Подождите немного и попробуйте снова."
                    elif response.status == 403:
                        return "Доступ к API запрещен. Проверьте настройки."
                    else:
                        return f"Ошибка сервера ({response.status}). Попробуйте позже."
                        
        except aiohttp.ClientProxyConnectionError as e:
            logger.error(f"Ошибка подключения к прокси: {e}")
            return "Не удалось подключиться через прокси. Проверьте настройки VPN."
            
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети: {e}")
            return "Проблемы с сетевым подключением. Проверьте интернет и попробуйте снова."
            
        except asyncio.TimeoutError:
            logger.error("Таймаут запроса к Gemini API")
            return "Запрос занял слишком много времени. Попробуйте снова."
            
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            return "Произошла непредвиденная ошибка. Попробуйте позже."
    
    async def test_connection(self) -> bool:
        """Тест подключения к Gemini API"""
        try:
            test_prompt = "Привет! Это тест подключения."
            response = await self.generate_response(test_prompt)
            
            if response and not response.startswith("Извините") and not response.startswith("Ошибка"):
                logger.info("Тестовое подключение к Gemini API успешно")
                return True
            else:
                logger.error(f"Тестовое подключение не удалось: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка тестового подключения: {e}")
            return False

# Глобальный экземпляр клиента
_gemini_client: Optional[GeminiClient] = None

async def get_gemini_client() -> GeminiClient:
    """Получить экземпляр клиента Gemini (синглтон)"""
    global _gemini_client
    
    if _gemini_client is None:
        _gemini_client = GeminiClient()
        await _gemini_client._create_session()
    
    return _gemini_client

async def close_gemini_client():
    """Закрыть клиент Gemini"""
    global _gemini_client
    
    if _gemini_client:
        await _gemini_client.close()
        _gemini_client = None
