from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import secrets
from email_validator import validate_email, EmailNotValidError

from app.database import get_session
from app.models import User, PendingUser
from app.auth import hash_password
from app.email_utils import send_verification_email
from app.bad_words import BAD_WORDS

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Константы валидации
MAX_NAME_LENGTH = 50
MIN_NAME_LENGTH = 2
MAX_EMAIL_LENGTH = 254


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    """Отображение формы регистрации"""
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register", response_class=HTMLResponse)
def register_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    """Обработка регистрации пользователя"""
    clean_name = name.strip()
    clean_email = email.lower()

    # Валидация имени
    if len(clean_name) < MIN_NAME_LENGTH or len(clean_name) > MAX_NAME_LENGTH:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": f"Имя должно быть от {MIN_NAME_LENGTH} до {MAX_NAME_LENGTH} символов"
        })

    # Проверка на плохие слова в имени
    if any(bad_word in clean_name.lower() for bad_word in BAD_WORDS):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Имя содержит недопустимые слова"
        })

    # Валидация email
    if len(clean_email) == 0 or len(clean_email) > MAX_EMAIL_LENGTH:
        return templates.TemplateResponse("register.html", {
            "request": request, 
            "error": "Некорректный email"
        })

    try:
        validate_email(clean_email, check_deliverability=False)
    except EmailNotValidError:
        return templates.TemplateResponse("register.html", {
            "request": request, 
            "error": "Некорректный email"
        })

    # Проверка существующих пользователей
    existing_user = session.query(User).filter(User.email == clean_email).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Email уже зарегистрирован"
        })

    existing_pending = session.query(PendingUser).filter(PendingUser.email == clean_email).first()
    if existing_pending:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "На этот email уже есть незавершённая регистрация. Проверьте почту."
        })

    # Создание pending пользователя
    token = secrets.token_urlsafe(32)
    pending = PendingUser(
        name=clean_name,
        email=clean_email,
        password_hash=hash_password(password),
        email_verification_token=token
    )
    session.add(pending)
    session.commit()

    # Отправка email для верификации
    send_verification_email(clean_email, token)

    return templates.TemplateResponse("register_success.html", {
        "request": request,
        "message": "Проверьте почту для подтверждения регистрации."
    })


@router.get("/verify", response_class=HTMLResponse)
def verify_email(request: Request, token: str, session: Session = Depends(get_session)):
    """Подтверждение email адреса"""
    # Поиск pending пользователя
    pending = session.query(PendingUser).filter(
        PendingUser.email_verification_token == token
    ).first()

    if not pending:
        return templates.TemplateResponse("verify.html", {
            "request": request,
            "success": False,
            "message": "Неверный или устаревший токен"
        })

    # Создание настоящего пользователя
    new_user = User(
        name=pending.name,
        email=pending.email.lower(),  # Убеждаемся что email в нижнем регистре
        password_hash=pending.password_hash,
        is_email_verified=True,
        email_verification_token=None,
        verification_status="unverified",
        role="user",
        created_at=datetime.utcnow()
    )
    session.add(new_user)

    # Удаление pending пользователя
    session.delete(pending)
    session.commit()

    return templates.TemplateResponse("verify.html", {
        "request": request,
        "success": True,
        "message": "Почта успешно подтверждена. Теперь вы можете войти."
    })
