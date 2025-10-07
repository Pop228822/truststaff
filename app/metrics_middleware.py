"""
Middleware для сбора метрик запросов
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.routes.admin import record_request_metric


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware для сбора метрик запросов"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Обрабатываем запрос
        response = await call_next(request)
        
        # Записываем метрики
        response_time = time.time() - start_time
        
        # Записываем метрику (только если это не сам metrics endpoint)
        if not request.url.path.startswith("/admin/metrics"):
            record_request_metric(
                path=request.url.path,
                method=request.method,
                status_code=response.status_code
            )
        
        return response
