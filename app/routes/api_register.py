from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import secrets

from app.database import get_session
from app.models import User, PendingUser
from app.auth import hash_password
from app.email_utils import send_verification_email

router = APIRouter()

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

@router.post("/api/register")
def api_register_user(data: RegisterRequest, session: Session = Depends(get_session)):
    # 1. Проверка дубликатов
    if session.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    if session.query(PendingUser).filter(PendingUser.email == data.email).first():
        raise HTTPException(status_code=400, detail="На этот email уже есть незавершённая регистрация")

    # 2. Генерация токена
    token = secrets.token_urlsafe(32)

    # 3. Создание PendingUser
    pending = PendingUser(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        email_verification_token=token
    )
    session.add(pending)
    session.commit()

    send_verification_email(data.email, token)

    # 5. Ответ
    return JSONResponse(content={"status": "ok"})

@router.get("/api/verify")
def api_verify_email(token: str, session: Session = Depends(get_session)):
    # 1. Поиск в PendingUser
    pending = session.query(PendingUser).filter(
        PendingUser.email_verification_token == token
    ).first()

    if not pending:
        raise HTTPException(status_code=400, detail="Неверный или устаревший токен")

    # 2. Создание User
    user = User(
        name=pending.name,
        email=pending.email,
        password_hash=pending.password_hash,
        is_email_verified=True,
        email_verification_token=None,
        verification_status="unverified",
        role="user",
        created_at=datetime.utcnow()
    )
    session.add(user)

    # 3. Удаление PendingUser
    session.delete(pending)
    session.commit()

    return JSONResponse(content={"status": "ok", "message": "Почта успешно подтверждена"})