"""
Обработчики ошибок приложения
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
import traceback
import logging

from app.error_notifications import send_500_error_notification, send_error_notification

templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


def setup_error_handlers(app: FastAPI) -> None:
    """Настройка обработчиков ошибок"""
    
    @app.exception_handler(404)
    async def not_found(request: Request, exc: HTTPException):
        """Отдаём HTML-страницу 404 с кнопкой «На главную»."""
        return templates.TemplateResponse(
            "404.html",
            {"request": request},
            status_code=404
        )
    
    @app.exception_handler(500)
    async def internal_server_error(request: Request, exc: Exception):
        """Обработка 500 ошибок с отправкой уведомления в Telegram"""
        print(f"🚨 500 ERROR HANDLER вызван!")
        print(f"🚨 Ошибка: {exc}")
        print(f"🚨 Тип ошибки: {type(exc)}")
        
        try:
            # Получаем информацию о пользователе из токена (если есть)
            user_info = None
            try:
                from app.auth import get_current_user_safe
                current_user = get_current_user_safe(request)
                if current_user:
                    user_info = f"{current_user.name} ({current_user.email})"
            except:
                pass
            
            # Отправляем уведомление в Telegram
            send_500_error_notification(exc, request, user_info)
            
            # Логируем ошибку
            logger.error(f"500 Error: {exc}", exc_info=True)
            
        except Exception as notification_error:
            logger.error(f"Ошибка при отправке уведомления: {notification_error}")
        
        # Возвращаем пользователю простую ошибку
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера. Мы уже работаем над её исправлением."}
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Обработка всех остальных исключений"""
        # Не обрабатываем HTTPException (они уже обработаны выше)
        if isinstance(exc, HTTPException):
            raise exc
        
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
            
            # Отправляем уведомление для критических ошибок
            if not isinstance(exc, (HTTPException,)):
                send_error_notification(exc, request, user_info)
            
            # Логируем ошибку
            logger.error(f"Unhandled Exception: {exc}", exc_info=True)
            
        except Exception as notification_error:
            logger.error(f"Ошибка при отправке уведомления: {notification_error}")
        
        # Возвращаем 500 ошибку
        return JSONResponse(
            status_code=500,
            content={"detail": "Произошла непредвиденная ошибка. Мы уже работаем над её исправлением."}
        )
