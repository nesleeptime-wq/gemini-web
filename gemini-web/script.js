// Глобальные переменные
let conversationHistory = [];
let currentPersonality = 'default';
let isLoading = false;

// Инициализация при загрузке страницы
window.onload = function() {
    // Проверяем наличие API ключа
    if (!hasApiKey()) {
        showWelcomeMessage();
    } else {
        hideWelcomeMessage();
        enableInput();
    }
    
    // Загружаем сохраненные данные
    loadSavedData();
    updateContextInfo();
};

// Показ приветственного сообщения
function showWelcomeMessage() {
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.style.display = 'block';
    }
}

// Скрыть приветственного сообщения
function hideWelcomeMessage() {
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
    }
}

// Диалог для ввода API ключа
function showApiKeyDialog() {
    showSettings();
}

// Отправка сообщения
async function sendMessage() {
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    
    if (!message || isLoading) return;
    
    if (!hasApiKey()) {
        showApiKeyDialog();
        return;
    }
    
    disableInput();
    addMessage('user', message);
    
    try {
        const response = await callGeminiAPI(message);
        addMessage('bot', response);
        
        // Обновляем историю
        conversationHistory.push({ role: 'user', parts: [{ text: message }] });
        conversationHistory.push({ role: 'model', parts: [{ text: response }] });
        
        // Ограничиваем историю
        if (conversationHistory.length > CONFIG.MAX_HISTORY_LENGTH) {
            conversationHistory = conversationHistory.slice(-CONFIG.MAX_HISTORY_LENGTH);
        }
        
        updateContextInfo();
        saveData();
        
    } catch (error) {
        console.error('Ошибка:', error);
        addMessage('bot', 'Ошибка: ' + error.message);
    }
    
    input.value = '';
    enableInput();
}

// Вызов Gemini API
async function callGeminiAPI(message) {
    const apiKey = getApiKey();
    const url = `${CONFIG.GEMINI_API_URL}?key=${apiKey}`;
    
    // Формируем содержимое сообщения
    const contents = [];
    
    // Добавляем системный промпт
    const systemPrompt = CONFIG.PERSONALITIES[currentPersonality];
    contents.push({
        role: "user",
        parts: [{ text: systemPrompt }]
    });
    contents.push({
        role: "model",
        parts: [{ text: "Понял! Буду следовать этому стилю." }]
    });
    
    // Добавляем историю
    contents.push(...conversationHistory);
    
    // Добавляем текущее сообщение
    contents.push({
        role: "user",
        parts: [{ text: message }]
    });
    
    const requestData = {
        contents: contents,
        generationConfig: CONFIG.MODEL_CONFIG,
        safetySettings: [
            {
                category: "HARM_CATEGORY_HARASSMENT",
                threshold: "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                category: "HARM_CATEGORY_HATE_SPEECH",
                threshold: "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                category: "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold: "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                category: "HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold: "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
    };
    
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
    });
    
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error?.message || 'Ошибка API');
    }
    
    const data = await response.json();
    return data.candidates[0].content.parts[0].text;
}

// Добавление сообщения в чат
function addMessage(type, content) {
    const messagesContainer = document.getElementById('chat-messages');
    
    // Удаляем приветственное сообщение если есть
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.textContent = content; // Используем textContent для сохранения переносов строк
    
    const messageTime = document.createElement('div');
    messageTime.className = 'message-time';
    messageTime.textContent = new Date().toLocaleTimeString('ru-RU');
    
    messageDiv.appendChild(messageContent);
    messageDiv.appendChild(messageTime);
    messagesContainer.appendChild(messageDiv);
    
    // Прокрутка вниз
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Изменение личности
function changePersonality(personality) {
    // Удаляем активный класс у всех кнопок
    document.querySelectorAll('.personality-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Добавляем активный класс выбранной кнопке
    const selectedBtn = document.querySelector(`[data-personality="${personality}"]`);
    if (selectedBtn) {
        selectedBtn.classList.add('active');
    }
    
    currentPersonality = personality;
    saveData();
    showNotification(`Стиль изменен на: ${getPersonalityName(personality)}`, 'success');
}

// Получение названия личности
function getPersonalityName(personality) {
    const names = {
        'default': 'Стандартный',
        'poet': 'Поэт',
        'teacher': 'Учитель',
        'friend': 'Друг',
        'professional': 'Профессионал'
    };
    return names[personality] || 'Стандартный';
}

// Очистка контекста
function clearContext() {
    conversationHistory = [];
    document.getElementById('chat-messages').innerHTML = '';
    
    // Показываем приветственное сообщение
    showWelcomeMessage();
    
    updateContextInfo();
    saveData();
    showNotification('Контекст очищен', 'success');
}

// Обновление информации о контексте
function updateContextInfo() {
    document.getElementById('context-messages').textContent = conversationHistory.length;
    
    const percentage = Math.min(100, (conversationHistory.length / CONFIG.MAX_HISTORY_LENGTH) * 100);
    document.getElementById('context-percentage').textContent = Math.round(percentage) + '%';
    document.getElementById('context-progress').style.width = percentage + '%';
}

// Включение/выключение input
function enableInput() {
    const input = document.getElementById('message-input');
    const button = document.getElementById('send-button');
    
    if (input) input.disabled = false;
    if (button) button.disabled = false;
    
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.classList.remove('show');
    
    isLoading = false;
}

function disableInput() {
    const input = document.getElementById('message-input');
    const button = document.getElementById('send-button');
    
    if (input) input.disabled = true;
    if (button) button.disabled = true;
    
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.classList.add('show');
    
    isLoading = true;
}

// Обработка нажатия Enter
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
    
    // Автоматическое увеличение высоты textarea
    const textarea = event.target;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 128) + 'px';
}

// Показ уведомлений
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// Сохранение данных в localStorage
function saveData() {
    const data = {
        conversationHistory: conversationHistory,
        currentPersonality: currentPersonality
    };
    localStorage.setItem('gemini_chat_data', JSON.stringify(data));
}

// Загрузка сохраненных данных
function loadSavedData() {
    const savedData = localStorage.getItem('gemini_chat_data');
    if (savedData) {
        try {
            const data = JSON.parse(savedData);
            conversationHistory = data.conversationHistory || [];
            currentPersonality = data.currentPersonality || 'default';
            
            // Восстанавливаем личность
            changePersonality(currentPersonality);
            
            // Восстанавливаем сообщения
            if (conversationHistory.length > 0) {
                hideWelcomeMessage();
                for (let i = 0; i < conversationHistory.length; i += 2) {
                    if (conversationHistory[i] && conversationHistory[i + 1]) {
                        addMessage('user', conversationHistory[i].parts[0].text);
                        addMessage('bot', conversationHistory[i + 1].parts[0].text);
                    }
                }
            }
        } catch (error) {
            console.error('Ошибка загрузки данных:', error);
        }
    }
}

// Модальное окно настроек
function showSettings() {
    const modal = document.getElementById('settings-modal');
    const apiKeyInput = document.getElementById('api-key-input');
    
    if (modal && apiKeyInput) {
        modal.classList.add('show');
        apiKeyInput.value = getApiKey();
    }
}

function hideSettings() {
    const modal = document.getElementById('settings-modal');
    if (modal) {
        modal.classList.remove('show');
    }
}

function saveApiKey() {
    const apiKeyInput = document.getElementById('api-key-input');
    const apiKey = apiKeyInput.value.trim();
    
    if (apiKey) {
        setApiKey(apiKey);
        hideSettings();
        hideWelcomeMessage();
        enableInput();
        showNotification('API ключ сохранен', 'success');
    } else {
        showNotification('Введите API ключ', 'error');
    }
}

// Закрытие модального окна по клику вне его
document.addEventListener('click', function(event) {
    const modal = document.getElementById('settings-modal');
    if (modal && event.target === modal) {
        hideSettings();
    }
});

// Добавляем стили для уведомлений
const style = document.createElement('style');
style.textContent = `
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 1000;
        max-width: 300px;
        opacity: 0;
        transform: translateX(100%);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    
    .notification.show {
        opacity: 1;
        transform: translateX(0);
    }
    
    .notification-success {
        background: linear-gradient(135deg, #10b981, #059669);
    }
    
    .notification-error {
        background: linear-gradient(135deg, #ef4444, #dc2626);
    }
    
    .notification-info {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
    }
`;
document.head.appendChild(style);
