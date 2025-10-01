from datetime import datetime, timedelta
from random import randint
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import requests
import os

from app.database import get_session
from app.models import User
from app.auth import verify_password, create_access_token
from app.brute_force import is_brute_force, log_login_attempt
from app.email_utils import send_2fa_code

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def verify_recaptcha(token: str) -> bool:
    """Проверка reCAPTCHA токена"""
    secret = os.getenv("SECRET_CAPTCHA_KEY")
    if not secret:
        return False
    try:
        resp = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={'secret': secret, 'response': token},
            timeout=3
        )
        result = resp.json()
        return result.get('success', False)
    except Exception as e:
        print(f"reCAPTCHA error: {e}")
        return False


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    """Отображение формы входа"""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    g_recaptcha_response: str = Form(..., alias="g-recaptcha-response"),
    session: Session = Depends(get_session)
):
    """Обработка входа пользователя"""
    ip = request.client.host

    # Проверка на брутфорс
    if is_brute_force(session, email, ip):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Слишком много попыток входа. Попробуйте через 15 минут."
        })

    # Проверка reCAPTCHA
    if not verify_recaptcha(g_recaptcha_response):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Подтвердите, что вы не робот"
        })

    # Поиск пользователя и проверка пароля
    user = session.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        log_login_attempt(session, email, ip, False)
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверный логин или пароль"
        })

    # Проверка блокировки
    if user.is_blocked:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Ваш аккаунт заблокирован администратором."
        })

    # Проверка верификации email
    if not user.is_email_verified:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Подтвердите почту перед входом. Ссылка отправлена на email."
        })

    # Логирование успешной попытки
    log_login_attempt(session, email, ip, True)

    # Генерация и отправка 2FA кода
    code = str(randint(100000, 999999))
    user.twofa_code = code
    user.twofa_expires_at = datetime.utcnow() + timedelta(minutes=5)
    session.commit()
    send_2fa_code(user.email, code)

    return templates.TemplateResponse("enter_2fa.html", {
        "request": request,
        "email": user.email
    })


@router.get("/2fa")
def get_2fa_form(request: Request):
    """Отображение формы 2FA"""
    return templates.TemplateResponse("enter_2fa.html", {"request": request})


@router.post("/2fa")
def verify_2fa(
    request: Request,
    twofa_code: str = Form(...),
    email: str = Form(...),
    session: Session = Depends(get_session)
):
    """Проверка 2FA кода"""
    user = session.query(User).filter(User.email == email).first()
    if not user:
        return templates.TemplateResponse("enter_2fa.html", {
            "request": request,
            "error": "Пользователь не найден",
            "email": email
        })

    # Проверка кода и срока действия
    if user.twofa_code != twofa_code:
        return templates.TemplateResponse("enter_2fa.html", {
            "request": request,
            "error": "Неверный код",
            "email": email
        })

    if user.twofa_expires_at < datetime.utcnow():
        return templates.TemplateResponse("enter_2fa.html", {
            "request": request,
            "error": "Код просрочен, запросите заново",
            "email": email
        })

    # Создание токена и установка куки
    token = create_access_token({"sub": str(user.id)})
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax"
    )

    # Очистка 2FA кода
    user.twofa_code = None
    user.twofa_expires_at = None
    session.commit()

    return response


@router.post("/2fa/resend")
def resend_2fa_code(
    request: Request,
    email: str = Form(...),
    session: Session = Depends(get_session)
):
    """Повторная отправка 2FA кода"""
    user = session.query(User).filter(User.email == email).first()
    if not user:
        return templates.TemplateResponse("enter_2fa.html", {
            "request": request,
            "error": "Пользователь не найден",
            "email": email
        })
    
    # Проверка лимита времени между отправками
    if user.twofa_sent_at:
        elapsed_seconds = (datetime.utcnow() - user.twofa_sent_at).total_seconds()
        if elapsed_seconds < 60:
            remaining = 60 - int(elapsed_seconds)
            return templates.TemplateResponse("enter_2fa.html", {
                "request": request,
                "error": f"Подождите ещё {remaining} сек. перед повторной отправкой.",
                "email": user.email,
                "remain_seconds": remaining
            })

    # Генерация нового кода
    code = str(randint(100000, 999999))
    user.twofa_code = code
    user.twofa_expires_at = datetime.utcnow() + timedelta(minutes=5)
    user.twofa_sent_at = datetime.utcnow()
    session.commit()
    send_2fa_code(user.email, code)
    
    return templates.TemplateResponse("enter_2fa.html", {
        "request": request,
        "email": user.email,
        "info": "Новый код отправлен",
        "remain_seconds": 60
    })


@router.get("/logout")
def logout():
    """Выход из системы"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response
