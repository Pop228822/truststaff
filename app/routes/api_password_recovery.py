import os

from fastapi import APIRouter, HTTPException, Form, Depends
from fastapi.responses import JSONResponse
from jose import jwt, JWTError, ExpiredSignatureError
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_session
from app.models import User
from app.auth import create_access_token, hash_password
from app.email_utils import send_password_reset_email

api_router = APIRouter()

@api_router.post("/api/forgot-password")
def forgot_password_api(
    email: str = Form(...),
    db: Session = Depends(get_session)
):
    user = db.query(User).filter(User.email == email).first()

    # Возвращаем "ok" в любом случае, чтобы не раскрывать наличие пользователя
    if not user:
        return JSONResponse({"status": "ok"})

    if user.is_blocked:
        raise HTTPException(status_code=403, detail="Пользователь заблокирован")

    now = datetime.utcnow()
    if user.password_reset_requested_at:
        diff = now - user.password_reset_requested_at
        if diff < timedelta(minutes=1):
            raise HTTPException(status_code=429, detail="Подождите перед повторной отправкой")

    user.password_reset_requested_at = now
    db.commit()

    reset_token = create_access_token(
        {"sub": str(user.id), "purpose": "reset_password"},
        expires_delta=timedelta(minutes=30)
    )

    send_ok = send_password_reset_email(to_addr=email, token=reset_token)
    if not send_ok:
        raise HTTPException(status_code=500, detail="Ошибка при отправке письма")

    return JSONResponse({"status": "ok"})

@api_router.post("/api/reset-password")
def reset_password_api(
    token: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    db: Session = Depends(get_session)
):
    if password != password2:
        raise HTTPException(status_code=400, detail="Пароли не совпадают")

    try:
        payload = jwt.decode(
            token,
            os.getenv("SECRET_KEY"),
            algorithms=[os.getenv("ALGORITHM")]
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Срок действия ссылки истёк")
    except JWTError:
        raise HTTPException(status_code=400, detail="Некорректный токен")

    user_id = payload.get("sub")
    purpose = payload.get("purpose")

    if not user_id or purpose != "reset_password":
        raise HTTPException(status_code=400, detail="Неверный токен")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.password_hash = hash_password(password)
    db.commit()

    return JSONResponse({"status": "ok"})
