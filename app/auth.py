import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import Optional
from fastapi.security import HTTPBearer
from starlette.responses import RedirectResponse

from app.database import get_session
from app.models import User

# Загружаем переменные окружения
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str):
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

class OptionalBearer(HTTPBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        try:
            return await super().__call__(request)
        except HTTPException:
            return None

oauth2_scheme_optional = OptionalBearer()

# ----------------- helpers.py -----------------
def _extract_token(request: Request, header_token: Optional[str]) -> Optional[str]:
    """Берём JWT либо из Authorization, либо из cookie."""
    if header_token:
        return header_token
    return request.cookies.get("access_token")


from fastapi.security import HTTPAuthorizationCredentials

def decode_token(token: str | HTTPAuthorizationCredentials) -> Optional[int]:
    try:
        if isinstance(token, HTTPAuthorizationCredentials):
            token = token.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub")) if payload.get("sub") else None
    except (JWTError, ValueError, AttributeError):
        return None
# ----------------------------------------------

def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_session)
) -> User:
    token = _extract_token(request, token)
    if not token:
        raise HTTPException(status_code=401, detail="Нет токена")

    user_id = decode_token(token)
    if not user_id:
        # сбрасываем битый токен
        response = RedirectResponse("/login", status_code=302)
        response.delete_cookie("access_token")
        raise HTTPException(status_code=401, detail="Неверный токен")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        response = RedirectResponse("/login", status_code=302)
        response.delete_cookie("access_token")
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    if user.is_blocked:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован.")

    return user

def get_current_user_safe(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_session)
) -> Optional[User]:
    token = _extract_token(request, token)
    if not token:
        return None

    user_id = decode_token(token)
    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()


def get_session_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_session)
) -> Optional[User]:
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    return db.query(User).filter(User.id == int(user_id)).first()

def only_approved_user(
    request: Request,
    db: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user_safe)
) -> User:
    if not current_user:
        # пользователь исчез или токен некорректен → на логин
        response = RedirectResponse("/login", status_code=302)
        response.delete_cookie("access_token")
        raise HTTPException(status_code=302, headers={"Location": "/login"})

    if current_user.verification_status != "approved":
        raise HTTPException(status_code=302, headers={"Location": "/onboarding"})

    if current_user.is_blocked:
        raise HTTPException(status_code=302, headers={"Location": "/login"})

    return current_user


def optional_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_session)
) -> Optional[User]:
    return get_current_user_safe(request=request, token=token, db=db)

