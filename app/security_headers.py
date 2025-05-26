import secrets
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ):
        # 1. Генерируем одноразовый nonce для скриптов и стилей
        nonce = secrets.token_urlsafe(16)

        # 2. Сохраняем nonce в request.state, чтобы вытащить в шаблонах
        request.state.csp_nonce = nonce

        # 3. Вызываем следующий обработчик
        response = await call_next(request)

        # 4. Прописываем заголовки безопасности
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # (Опционально) Ограничиваем доступ к камере/микрофону/геолокации
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # 5. Добавляем CSP без unsafe-inline, но с nonce
        # Подставляем сгенерированный nonce в script-src и style-src
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' https://www.google.com https://www.gstatic.com 'nonce-{nonce}'; "
            f"style-src 'self' 'nonce-{nonce}'; "
            f"img-src 'self' data:; "
            f"font-src 'self'; "
            f"connect-src 'self'; "
            f"frame-ancestors 'self'; "
            f"frame-src https://www.google.com https://www.gstatic.com;"
        )

        return response
