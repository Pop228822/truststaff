"""
Система уведомлений об ошибках в Telegram
"""
import os
import requests
import traceback
from datetime import datetime
from typing import Optional


# Telegram настройки
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_error_notification(
    error: Exception,
    request: Optional[object] = None,
    user_info: Optional[str] = None
) -> None:
    """
    Отправка уведомления об ошибке в Telegram
    
    Args:
        error: Объект исключения
        request: Объект запроса FastAPI (опционально)
        user_info: Информация о пользователе (опционально)
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        # Получаем информацию об ошибке
        error_type = type(error).__name__
        error_message = str(error)
        error_traceback = traceback.format_exc()
        
        # Информация о запросе
        request_info = ""
        if request:
            # Безопасно получаем IP адрес
            client_ip = "Неизвестно"
            try:
                if hasattr(request, 'client') and request.client:
                    if hasattr(request.client, 'host'):
                        client_ip = request.client.host
                    elif hasattr(request.client, 'get'):
                        client_ip = request.client.get('host', 'Неизвестно')
            except:
                pass
            
            request_info = f"""
🌐 **Запрос:**
• URL: {getattr(request, 'url', 'Неизвестно')}
• Метод: {getattr(request, 'method', 'Неизвестно')}
• IP: {client_ip}
• User-Agent: {request.headers.get('user-agent', 'Неизвестно') if hasattr(request, 'headers') else 'Неизвестно'}"""

        # Информация о пользователе
        user_info_text = f"\n👤 **Пользователь:** {user_info}" if user_info else ""

        # Формируем сообщение
        text = f"""🚨 **КРИТИЧЕСКАЯ ОШИБКА НА СЕРВЕРЕ!**

⏰ **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

❌ **Ошибка:** {error_type}
📝 **Сообщение:** {error_message}
{user_info_text}{request_info}

🔍 **Стек вызовов:**
```
{error_traceback[:1000]}...
```"""

        # Отправляем в Telegram
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        
    except Exception as e:
        # Логируем ошибку, но не выводим в консоль
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка отправки уведомления в Telegram: {e}")


def send_500_error_notification(
    error: Exception,
    request: Optional[object] = None,
    user_info: Optional[str] = None
) -> None:
    """
    Специальное уведомление для 500 ошибок
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        error_type = type(error).__name__
        error_message = str(error)
        
        # Информация о запросе
        request_info = ""
        if request:
            # Безопасно получаем IP адрес
            client_ip = "Неизвестно"
            try:
                if hasattr(request, 'client') and request.client:
                    if hasattr(request.client, 'host'):
                        client_ip = request.client.host
                    elif hasattr(request.client, 'get'):
                        client_ip = request.client.get('host', 'Неизвестно')
            except:
                pass
            
            request_info = f"""
🌐 **Запрос:**
• URL: {getattr(request, 'url', 'Неизвестно')}
• Метод: {getattr(request, 'method', 'Неизвестно')}
• IP: {client_ip}"""

        # Информация о пользователе
        user_info_text = f"\n👤 **Пользователь:** {user_info}" if user_info else ""

        text = f"""🔥 **500 ОШИБКА СЕРВЕРА!**

⏰ **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

❌ **Ошибка:** {error_type}
📝 **Сообщение:** {error_message}
{user_info_text}{request_info}

⚠️ **Требуется немедленное внимание!**"""

        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        
    except Exception as e:
        # Логируем ошибку, но не выводим в консоль
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка отправки 500 уведомления в Telegram: {e}")
