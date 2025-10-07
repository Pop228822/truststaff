"""
Middleware для перехвата ошибок и отправки уведомлений в Telegram
"""
import traceback
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

from app.error_notifications import send_500_error_notification


class ErrorNotificationMiddleware(BaseHTTPMiddleware):
    """Middleware для перехвата ошибок и отправки уведомлений"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            print(f"🚨 ERROR MIDDLEWARE перехватил ошибку!")
            print(f"🚨 Ошибка: {exc}")
            print(f"🚨 Тип ошибки: {type(exc)}")
            
            try:
                # Получаем информацию о пользователе
                user_info = None
                try:
                    from app.auth import get_current_user_safe
                    current_user = get_current_user_safe(request)
                    if current_user:
                        user_info = f"{current_user.name} ({current_user.email})"
                except:
                    pass
                
                # Отправляем уведомление в Telegram
                print(f"🚨 Отправляем уведомление через middleware...")
                send_500_error_notification(exc, request, user_info)
                
            except Exception as notification_error:
                print(f"❌ Ошибка при отправке уведомления через middleware: {notification_error}")
            
            # Возвращаем ошибку пользователю
            return JSONResponse(
                status_code=500,
                content={"detail": "Внутренняя ошибка сервера. Мы уже работаем над её исправлением."}
            )
