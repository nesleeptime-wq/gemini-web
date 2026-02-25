// Конфигурация приложения
const CONFIG = {
    // URL Gemini API
    GEMINI_API_URL: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
    
    // Настройки модели
    MODEL_CONFIG: {
        temperature: 0.7,
        maxOutputTokens: 2048,
        topP: 0.8,
        topK: 40
    },
    
    // Профессиональные личности
    PERSONALITIES: {
        'default': "Ты — профессиональный ассистент. Отвечай на русском языке точно, по делу, структурированно. Будь вежливым и помогающим. Используй формальный стиль общения.",
        'poet': "Ты — поэт. Отвечай на русском языке в стихотворной форме. Используй красивые метафоры, рифмы и художественные образы. Будь творческим и вдохновляющим.",
        'teacher': "Ты — учитель. Отвечай на русском языке просто и понятно, объясняй сложные вещи пошагово. Будь терпеливым, поддерживающим и методичным.",
        'friend': "Ты — близкий друг. Отвечай на русском языке неформально, дружелюбно, с юмором. Используй простую речь, поддерживай и проявляй заботу.",
        'professional': "Ты — бизнес-консультант. Отвечай на русском языке официально, делово, компетентно. Давай точную информацию, практические советы и экспертные оценки."
    },
    
    // Настройки приложения
    MAX_HISTORY_LENGTH: 20,
    MAX_MESSAGE_LENGTH: 4096
};

// Управление API ключом
function getApiKey() {
    return localStorage.getItem('gemini_api_key') || '';
}

function setApiKey(apiKey) {
    localStorage.setItem('gemini_api_key', apiKey);
}

function hasApiKey() {
    const key = getApiKey();
    return key && key.length > 0;
}

function removeApiKey() {
    localStorage.removeItem('gemini_api_key');
}
