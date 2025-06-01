import secrets
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # 1. Одноразовый nonce, прокидываем в шаблоны ({{ request.state.csp_nonce }})
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        # 2. Вызываем следующий обработчик
        response = await call_next(request)

        # 3. Базовые заголовки безопасности
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # 4. CSP-заголовок
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' https://*.google.com https://*.gstatic.com 'nonce-{nonce}' 'strict-dynamic'; "
            f"style-src 'self' 'nonce-{nonce}'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "connect-src 'self' https://*.google.com https://*.gstatic.com; "
            "frame-src 'self' https://*.google.com https://*.gstatic.com; "
            "upgrade-insecure-requests;"
        )

        # 5. Убираем «Server: uvicorn», если он присутствует
        if "server" in response.headers:
            del response.headers["server"]

        return response
