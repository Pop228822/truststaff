"""
Конфигурация FastAPI приложения
"""
from fastapi import FastAPI, Depends
from fastapi.templating import Jinja2Templates

from app.auth_redirect import AuthRedirectMiddleware
from app.limit import rate_limit_100_per_minute
from app.security_headers import SecurityHeadersMiddleware


def create_app() -> FastAPI:
    """Создание и настройка FastAPI приложения"""
    app = FastAPI(
        dependencies=[Depends(rate_limit_100_per_minute)]
    )
    
    # Добавляем middleware
    app.add_middleware(AuthRedirectMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    
    return app


# Глобальный экземпляр templates
templates = Jinja2Templates(directory="templates")
