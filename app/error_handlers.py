"""
Обработчики ошибок приложения
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
import logging


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
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Обработка всех исключений - уведомления отправляет middleware"""
        # Не обрабатываем HTTPException (они уже обработаны выше)
        if isinstance(exc, HTTPException):
            raise exc
        
        # Логируем ошибку (уведомления отправляет ErrorNotificationMiddleware)
        logger.error(f"Unhandled Exception: {exc}", exc_info=True)
        
        # Возвращаем пользователю простую ошибку
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера. Мы уже работаем над её исправлением."}
        )
