from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session  # если захотите использовать для token
from app.database import get_session
from app.models import User
from app.auth import create_access_token, hash_password
from app.email_utils import send_password_reset_email  # Предполагаем, что такая функция есть
from fastapi.templating import Jinja2Templates
import os
from jose import ExpiredSignatureError
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError

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
    clean_email = email.lower()  # Приводим email к нижнему регистру
    user = db.query(User).filter(User.email == clean_email).first()

    if user.is_blocked:
        return templates.TemplateResponse("forgot_password.html", {
            "request": request,
            "message": "Пользователь заблокирован!"
        })
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
    send_ok = send_password_reset_email(to_addr=clean_email, token=reset_token)
    if not send_ok:
        raise HTTPException(status_code=500, detail="Ошибка при отправке письма")

    return templates.TemplateResponse("forgot_password.html", {
        "request": request,
        "message": "Проверьте свою почту для дальнейших инструкций"
    })


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(request: Request, token: str):
    """
    Страница, где пользователь вводит новый пароль.
    token берём из query-параметра, например: /reset-password?token=...
    """
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token,
        "error_message": None  # нет ошибки изначально
    })


@router.post("/reset-password", response_class=HTMLResponse)
def reset_password_process(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    db: Session = Depends(get_session)
):
    # 1. Проверяем совпадение паролей
    if password != password2:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": token,
                "error_message": "Пароли не совпадают"
            }
        )

    # 2. Декодируем токен
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), os.getenv("ALGORITHM"))
    except ExpiredSignatureError:
        # Токен просрочен → показываем ту же страницу с сообщением
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": "",
                "error_message": "Время действия ссылки для сброса пароля истекло. Пожалуйста, запросите новую ссылку."
            }
        )
    except JWTError:
        # Токен некорректен
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": "",
                "error_message": "Неверный или повреждённый токен для сброса пароля. Запросите новую ссылку."
            }
        )

    # 3. Проверяем payload
    user_id = payload.get("sub")
    purpose = payload.get("purpose")
    if not user_id or purpose != "reset_password":
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": "",
                "error_message": "Неверный токен (не подходит для сброса пароля)."
            }
        )

    # 4. Находим пользователя
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": "",
                "error_message": "Пользователь не найден."
            }
        )

    # 5. Сохраняем новый пароль
    user.password_hash = hash_password(password)
    db.commit()

    return RedirectResponse("/login", status_code=302)