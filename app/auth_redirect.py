from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from jose import ExpiredSignatureError, JWTError, jwt
from fastapi import Request
from app.models import User
from app.database import get_session
from sqlalchemy.orm import Session
import os

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

class AuthRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # пропускаем API и /login
        if path.startswith("/api") or path.startswith("/login") or path.startswith("/static"):
            return await call_next(request)

        token = request.cookies.get("access_token")
        if not token:
            return await call_next(request)  # не логин — пускаем, пусть шаблон сам решает

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if not user_id:
                raise JWTError()
        except ExpiredSignatureError:
            response = RedirectResponse(url="/login", status_code=302)
            response.delete_cookie("access_token")
            return response
        except JWTError:
            response = RedirectResponse(url="/login", status_code=302)
            response.delete_cookie("access_token")
            return response

        # проверим блокировку (опционально)
        db: Session = get_session()
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user or user.is_blocked:
            response = RedirectResponse(url="/login", status_code=302)
            response.delete_cookie("access_token")
            return response

        # всё ок
        return await call_next(request)
