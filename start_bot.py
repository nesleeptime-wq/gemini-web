#!/usr/bin/env python3
"""
Простой скрипт для запуска бота с обработкой ошибок
"""
import sys
import signal

from bot import GeminiBot

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения"""
    print("\n🛑 Получен сигнал завершения...")
    sys.exit(0)

def main():
    """Главная функция"""
    # Устанавливаем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        print("🚀 Запуск Telegram бота...")
        
        # Создаем и запускаем бота
        bot = GeminiBot()
        bot.run()
        
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
