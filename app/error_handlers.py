"""
Обработчики ошибок приложения
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


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
