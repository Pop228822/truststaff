from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session  # если захотите использовать для token
from app.database import get_session
from app.models import User
from app.auth import create_access_token, hash_password
from app.email_utils import send_password_reset_email  # Предполагаем, что такая функция есть
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    """Простая страница, где пользователь укажет email для восстановления."""
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@router.post("/forgot-password", response_class=HTMLResponse)
def forgot_password_send(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_session)
):
    user = db.query(User).filter(User.email == email).first()

    # Чтобы не указывать, что пользователя нет, возвращаем "Письмо отправлено".
    if not user:
        return templates.TemplateResponse("forgot_password.html", {
            "request": request,
            "message": "Если пользователь существует, вы получите письмо для восстановления."
        })

    # --- ДОБАВЛЯЕМ ПРОВЕРКУ, не прошло ли 60 секунд c момента последнего запроса ---
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    if user.password_reset_requested_at:
        diff = now - user.password_reset_requested_at
        # Проверяем, если меньше 1 минуты, то не отправляем новое письмо
        if diff < timedelta(minutes=1):
            return templates.TemplateResponse("forgot_password.html", {
                "request": request,
                "message": "Вы уже запрашивали восстановление, подождите немного прежде чем отправлять новый запрос."
            })

    # Если не прошло, или первый раз — продолжаем
    user.password_reset_requested_at = now
    db.commit()

    # Генерируем JWT токен для сброса пароля (expires_delta=30 минут)
    reset_token = create_access_token(
        {"sub": str(user.id), "purpose": "reset_password"},
        expires_delta=timedelta(minutes=30)
    )

    # Отправляем письмо
    send_ok = send_password_reset_email(to_addr=email, token=reset_token)
    if not send_ok:
        raise HTTPException(status_code=500, detail="Ошибка при отправке письма")

    return templates.TemplateResponse("forgot_password.html", {
        "request": request,
        "message": "Проверьте свою почту для дальнейших инструкций"
    })


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(request: Request, token: str, db: Session = Depends(get_session)):
    """
    Рендерим страницу, где пользователь вводит новый пароль.
    token достаём из Query-параметра ?token=...
    """
    # Можно сразу проверить jwt.decode(token), срок действия, purpose="reset_password" и т.д.
    # Но, как минимум, отобразим форму:
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token
    })


from fastapi.responses import RedirectResponse
from jose import jwt, JWTError

@router.post("/reset-password")
def reset_password_process(
    token: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    db: Session = Depends(get_session)
):
    # 1. Проверяем совпадение паролей
    if password != password2:
        raise HTTPException(status_code=400, detail="Пароли не совпадают")

    # 2. Декодируем токен, проверяем срок действия и purpose
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=400, detail="Неверный или просроченный токен")

    # В payload у нас sub=user_id, purpose="reset_password", exp=...
    user_id = payload.get("sub")
    purpose = payload.get("purpose")
    if not user_id or purpose != "reset_password":
        raise HTTPException(status_code=400, detail="Токен не подходит для сброса пароля")

    # 3. Ищем пользователя по user_id
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Пользователь не найден")

    # 4. Сохраняем новый пароль
    user.password_hash = hash_password(password)
    db.commit()

    # 5. Редиректим на /login
    return RedirectResponse("/login", status_code=302)
