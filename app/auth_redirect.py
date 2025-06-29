from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from jose import jwt, JWTError, ExpiredSignatureError
from fastapi import Request
from app.models import User
from app.database import engine  # 👈 берем engine отсюда
from sqlmodel import Session
import os

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")


class AuthRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path.startswith("/api") or path.startswith("/login") or path.startswith("/static"):
            return await call_next(request)

        token = request.cookies.get("access_token")
        if not token:
            return await call_next(request)

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if not user_id:
                raise JWTError()
        except ExpiredSignatureError:
            response = RedirectResponse("/login", status_code=302)
            response.delete_cookie("access_token")
            return response
        except JWTError:
            response = RedirectResponse("/login", status_code=302)
            response.delete_cookie("access_token")
            return response

        with Session(engine) as db:
            user = db.get(User, int(user_id))
            if not user or user.is_blocked:
                response = RedirectResponse("/login", status_code=302)
                response.delete_cookie("access_token")
                return response

        return await call_next(request)
