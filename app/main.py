from datetime import datetime, timedelta
from random import randint

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pdfkit
from pydantic.networks import MAX_EMAIL_LENGTH
from sqlalchemy.orm import Session
import os

from app.auth_redirect import AuthRedirectMiddleware
from app.limit import rate_limit_100_per_minute

load_dotenv()
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_safe,
    only_approved_user,
    get_session_user,
    oauth2_scheme_optional
)
from app.database import get_session
from app.models import ReputationRecord, User, Employee, PendingUser
from app.security_headers import SecurityHeadersMiddleware

app = FastAPI(
    dependencies=[Depends(rate_limit_100_per_minute)]
)

app.add_middleware(AuthRedirectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
templates = Jinja2Templates(directory="templates")
from app.routes import superadmin, pages
app.include_router(superadmin.router)
app.include_router(pages.router)

MAX_EMPLOYERS_COUNT = 30



@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


import secrets
from app.email_utils import send_verification_email, send_2fa_code
from app.bad_words import BAD_WORDS

MAX_NAME_LENGTH = 50
MIN_NAME_LENGTH = 2
MAX_EMAIL_LENGTH = 254

from email_validator import validate_email, EmailNotValidError

@app.post("/register", response_class=HTMLResponse)
def register_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    clean_name = name.strip()
    clean_email = email.lower()

    if len(clean_name) < MIN_NAME_LENGTH or len(clean_name) > MAX_NAME_LENGTH:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": f"Имя должно быть от {MIN_NAME_LENGTH} до {MAX_NAME_LENGTH} символов"
        })

    if any(bad_word in clean_name.lower() for bad_word in BAD_WORDS):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Имя содержит недопустимые слова"
        })

    if len(clean_email) == 0 or len(clean_email) > MAX_EMAIL_LENGTH:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Некорректный email"})

    try:
        validate_email(clean_email, check_deliverability=False)
    except EmailNotValidError:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Некорректный email"})

    existing_user = session.query(User).filter(User.email == email).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Email уже зарегистрирован"
        })

    existing_pending = session.query(PendingUser).filter(PendingUser.email == email).first()
    if existing_pending:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "На этот email уже есть незавершённая регистрация. Проверьте почту."
        })

    token = secrets.token_urlsafe(32)

    pending = PendingUser(
        name=clean_name,
        email=email,
        password_hash=hash_password(password),
        email_verification_token=token
    )
    session.add(pending)
    session.commit()

    send_verification_email(email, token)

    return templates.TemplateResponse("register_success.html", {
        "request": request,
        "message": "Проверьте почту для подтверждения регистрации."
    })

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory="templates")

@app.get("/verify", response_class=HTMLResponse)
def verify_email(request: Request, token: str, session: Session = Depends(get_session)):
    # 1. Ищем в PendingUser
    pending = session.query(PendingUser).filter(
        PendingUser.email_verification_token == token
    ).first()

    if not pending:
        return templates.TemplateResponse("verify.html", {
            "request": request,
            "success": False,
            "message": "Неверный или устаревший токен"
        })

    # 2. Создаём настоящего User
    new_user = User(
        name=pending.name,
        email=pending.email,
        password_hash=pending.password_hash,
        is_email_verified=True,
        email_verification_token=None,
        verification_status="unverified",  # Или как у вас
        role="user",
        created_at=datetime.utcnow()
    )
    session.add(new_user)

    # 3. Удаляем PendingUser
    session.delete(pending)
    session.commit()

    return templates.TemplateResponse("verify.html", {
        "request": request,
        "success": True,
        "message": "Почта успешно подтверждена. Теперь вы можете войти."
    })

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

from app.brute_force import is_brute_force, log_login_attempt

@app.post("/login")
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    g_recaptcha_response: str = Form(..., alias="g-recaptcha-response"),
    session: Session = Depends(get_session)
):
    ip = request.client.host

    if is_brute_force(session, email, ip):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Слишком много попыток входа. Попробуйте через 15 минут."
        })

    if not verify_recaptcha(g_recaptcha_response):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Подтвердите, что вы не робот"
        })

    user = session.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        log_login_attempt(session, email, ip, False)
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверный логин или пароль"
        })

    if user.is_blocked:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Ваш аккаунт заблокирован администратором."
        })

    if not user.is_email_verified:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Подтвердите почту перед входом. Ссылка отправлена на email."
        })

    log_login_attempt(session, email, ip, True)

    code = str(randint(100000, 999999))
    user.twofa_code = code
    user.twofa_expires_at = datetime.utcnow() + timedelta(minutes=5)
    session.commit()
    send_2fa_code(user.email, code)

    return templates.TemplateResponse("enter_2fa.html", {
        "request": request,
        "email": user.email
    })

@app.get("/2fa")
def get_2fa_form(request: Request):
    return templates.TemplateResponse("enter_2fa.html", {"request": request})

@app.post("/2fa")
def verify_2fa(
    request: Request,
    twofa_code: str = Form(...),
    email: str = Form(...),
    session: Session = Depends(get_session)
):
    user = session.query(User).filter(User.email == email).first()
    if not user:
        return templates.TemplateResponse("enter_2fa.html", {
            "request": request,
            "error": "Пользователь не найден",
            "email": email
        })

    # Проверяем код и срок
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

    # Если всё верно — "финализируем" вход: создаём access_token и ставим куку
    token = create_access_token({"sub": str(user.id)})
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax"
    )

    # После входа можно сбросить 2fa_code, чтобы не использовать повторно
    user.twofa_code = None
    user.twofa_expires_at = None
    session.commit()

    return response

@app.post("/2fa/resend")
def resend_2fa_code(
    request: Request,
    email: str = Form(...),
    session: Session = Depends(get_session)
):
    user = session.query(User).filter(User.email == email).first()
    if not user:
        return templates.TemplateResponse("enter_2fa.html", {
            "request": request,
            "error": "Пользователь не найден",
            "email": email
        })
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

import requests

def verify_recaptcha(token: str) -> bool:
    secret = os.getenv("SECRET_CAPTCHA_KEY")
    if not secret:
        # Можно raise, но обычно просто не пускаем
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
        # print(f"reCAPTCHA error: {e}")
        return False

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response

@app.get("/add-employee", response_class=HTMLResponse)
def add_employee_form(request: Request, current_user: User = Depends(get_session_user)):
    if not current_user:
        return RedirectResponse("/login", status_code=302)
    if current_user.is_blocked:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response
    if current_user.verification_status != "approved":
        return RedirectResponse("/onboarding", status_code=302)
    return templates.TemplateResponse("add_employee.html", {"request": request})


def contains_bad_words(text: str) -> bool:
    return any(bad in text.lower() for bad in BAD_WORDS)


@app.post("/add-employee")
def add_employee(
    request: Request,
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str = Form(""),
    birth_date: str = Form(...),
    contact: str = Form(""),
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    employee_count = db.query(Employee).filter(Employee.created_by_user_id == current_user.id).count()
    if employee_count >= MAX_EMPLOYERS_COUNT:
        return templates.TemplateResponse("add_employee.html", {
            "request": request,
            "error": "Вы уже добавили 30 сотрудников. Свяжитесь с поддержкой для увеличения лимита."
        })

    # Проверка ФИО
    for value in [last_name, first_name, middle_name]:
        if len(value) > 50:
            return templates.TemplateResponse("add_employee.html", {
                "request": request,
                "error": "Слишком длинное имя или фамилия"
            })
        if contains_bad_words(value):
            return templates.TemplateResponse("add_employee.html", {
                "request": request,
                "error": "Имя содержит недопустимые слова"
            })

    try:
        dt = datetime.strptime(birth_date, "%Y-%m-%d").date()
        today = datetime.now().date()
        age = today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))

        if dt > today:
            return templates.TemplateResponse("add_employee.html", {
                "request": request,
                "error": "Дата рождения не может быть в будущем"
            })

        if age < 14:
            return templates.TemplateResponse("add_employee.html", {
                "request": request,
                "error": "Возраст сотрудника должен быть не меньше 14 лет"
            })

        if age > 100:
            return templates.TemplateResponse("add_employee.html", {
                "request": request,
                "error": "Возраст сотрудника не может быть больше 100 лет"
            })

    except ValueError:
        return templates.TemplateResponse("add_employee.html", {
            "request": request,
            "error": "Некорректный формат даты. Используйте ГГГГ-ММ-ДД"
        })

    # Проверка контакта
    if contact and (len(contact) > 100 or contains_bad_words(contact)):
        return templates.TemplateResponse("add_employee.html", {
            "request": request,
            "error": "Контакт содержит недопустимые слова или слишком длинный"
        })

    full_name = " ".join([last_name.strip(), first_name.strip(), middle_name.strip()]).strip()

    employee = Employee(
        full_name=full_name,
        birth_date=birth_date,
        contact=contact,
        created_by_user_id=current_user.id
    )
    db.add(employee)
    db.commit()

    return RedirectResponse("/employees", status_code=302)

from fastapi.responses import RedirectResponse

def enforce_login_and_verification(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_session)
) -> User:
    user = get_current_user_safe(request=request, token=token, db=db)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    if user.verification_status != "approved":
        raise HTTPException(status_code=302, headers={"Location": "/onboarding"})
    return user

@app.get("/employees", response_class=HTMLResponse)
def list_employees(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(enforce_login_and_verification)
):
    if current_user.is_blocked:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response
    employees = db.query(Employee).filter(Employee.created_by_user_id == current_user.id).all()
    for emp in employees:
        emp.records = db.query(ReputationRecord).filter(ReputationRecord.employee_id == emp.id).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "employees": employees
    })

MAX_TEXT_LENGTH = 500

@app.get("/employee/{employee_id}/add-record", response_class=HTMLResponse)
def record_form(
    request: Request,
    employee_id: int,
    current_user: User = Depends(only_approved_user)
):
    return templates.TemplateResponse("add_record.html", {
        "request": request,
        "employee_id": employee_id,
        "error": None,
        "position": "",
        "hired_at": "",
        "fired_at": "",
        "misconduct": "",
        "dismissal_reason": "",
        "commendation": ""
    })

@app.post("/employee/{employee_id}/add-record")
def add_record(
    request: Request,
    employee_id: int,
    position: str = Form(...),
    hired_at: str = Form(...),
    fired_at: Optional[str] = Form(None),
    misconduct: Optional[str] = Form(None),
    dismissal_reason: Optional[str] = Form(None),
    commendation: Optional[str] = Form(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    if current_user.is_blocked:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    position = position.strip()
    hired_at = hired_at.strip()
    fired_at = (fired_at or "").strip()
    misconduct = (misconduct or "").strip()
    dismissal_reason = (dismissal_reason or "").strip()
    commendation = (commendation or "").strip()

    for field_name, field_value in {
        "Должность": position,
        "Нарушение": misconduct,
        "Причина увольнения": dismissal_reason,
        "Поощрение": commendation
    }.items():
        if field_value and len(field_value) > MAX_TEXT_LENGTH:
            return templates.TemplateResponse("add_record.html", {
                "request": request,
                "employee_id": employee_id,
                "error": f"{field_name} не может превышать {MAX_TEXT_LENGTH} символов",
                "position": position,
                "hired_at": hired_at,
                "fired_at": fired_at,
                "misconduct": misconduct,
                "dismissal_reason": dismissal_reason,
                "commendation": commendation
            })

    existing_records_count = db.query(ReputationRecord).filter(
        ReputationRecord.employee_id == employee_id,
        ReputationRecord.employer_id == current_user.id
    ).count()

    if existing_records_count >= 2:
        return templates.TemplateResponse("add_record.html", {
            "request": request,
            "employee_id": employee_id,
            "error": "Вы уже добавили 2 записи об этом сотруднике. Дальше добавлять нельзя.",
            "position": position,
            "hired_at": hired_at,
            "fired_at": fired_at,
            "misconduct": misconduct,
            "dismissal_reason": dismissal_reason,
            "commendation": commendation
        })

    record = ReputationRecord(
        employee_id=employee_id,
        employer_id=current_user.id,
        position=position,
        hired_at=hired_at,
        fired_at=fired_at or None,
        misconduct=misconduct or None,
        dismissal_reason=dismissal_reason or None,
        commendation=commendation or None
    )
    db.add(record)
    db.commit()
    return RedirectResponse(url="/employees", status_code=302)

@app.get("/employee/{employee_id}/generate-consent", response_class=HTMLResponse)
def consent_form(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return templates.TemplateResponse("consent_form.html", {
        "request": request,
        "employee_id": employee_id,
        "employee": employee,
        "user": current_user
    })


from fastapi.responses import StreamingResponse
import io

from fastapi import Form

@app.post("/employee/{employee_id}/generate-consent")
def generate_consent_pdf(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("consent_template.html")

    html_content = template.render(
        full_name=employee.full_name,
        birth_date=employee.birth_date,
        contact=employee.contact or "",
        today=datetime.now().strftime("%d.%m.%Y")
    )

    pdf_bytes = pdfkit.from_string(html_content, False)
    pdf_stream = io.BytesIO(pdf_bytes)

    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=consent_{employee.id}.pdf"}
    )

from app.routes import onboarding
app.include_router(onboarding.router)

@app.get("/record/{record_id}/edit", response_class=HTMLResponse)
def edit_record_form(
    request: Request,
    record_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    if current_user.is_blocked:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response
    record = db.query(ReputationRecord).filter(
        ReputationRecord.id == record_id,
        ReputationRecord.employer_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("edit_record.html", {
        "request": request,
        "record": record,
        "error": None
    })

@app.post("/record/{record_id}/edit")
def edit_record(
    request: Request,
    record_id: int,
    position: str = Form(...),
    hired_at: str = Form(...),
    fired_at: Optional[str] = Form(None),
    misconduct: Optional[str] = Form(None),
    dismissal_reason: Optional[str] = Form(None),
    commendation: Optional[str] = Form(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    if current_user.is_blocked:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    position = position.strip()
    hired_at = hired_at.strip()
    fired_at = (fired_at or "").strip()
    misconduct = (misconduct or "").strip()
    dismissal_reason = (dismissal_reason or "").strip()
    commendation = (commendation or "").strip()

    for name, val in {
        "Должность": position,
        "Нарушение": misconduct,
        "Причина увольнения": dismissal_reason,
        "Поощрение": commendation
    }.items():
        if val and len(val) > MAX_TEXT_LENGTH:
            record = db.query(ReputationRecord).filter(
                ReputationRecord.id == record_id,
                ReputationRecord.employer_id == current_user.id
            ).first()
            if not record:
                raise HTTPException(status_code=404)
            return templates.TemplateResponse("edit_record.html", {
                "request": request,
                "record": record,
                "error": f"{name} не может превышать {MAX_TEXT_LENGTH} символов"
            })

    record = db.query(ReputationRecord).filter(
        ReputationRecord.id == record_id,
        ReputationRecord.employer_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404)

    try:
        hired_dt = datetime.strptime(hired_at, "%Y-%m-%d")
    except ValueError:
        return templates.TemplateResponse("edit_record.html", {
            "request": request,
            "record": record,
            "error": "Некорректная дата приёма"
        })

    fired_dt = None
    if fired_at:
        try:
            fired_dt = datetime.strptime(fired_at, "%Y-%m-%d")
        except ValueError:
            return templates.TemplateResponse("edit_record.html", {
                "request": request,
                "record": record,
                "error": "Некорректная дата увольнения"
            })

    record.hired_at = hired_dt
    record.fired_at = fired_dt
    record.position = position
    record.misconduct = misconduct or None
    record.dismissal_reason = dismissal_reason or None
    record.commendation = commendation or None

    db.commit()
    return RedirectResponse(url="/employees", status_code=302)


@app.post("/record/{record_id}/delete")
def delete_record(
    record_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    if current_user.is_blocked:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response
    record = db.query(ReputationRecord).filter(
        ReputationRecord.id == record_id,
        ReputationRecord.employer_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404)

    db.delete(record)
    db.commit()
    return RedirectResponse(url="/employees", status_code=302)


@app.exception_handler(404)
async def not_found(request: Request, exc: HTTPException):
    """Отдаём HTML-страницу 404 с кнопкой «На главную»."""
    return templates.TemplateResponse(
        "404.html",
        {"request": request},
        status_code=404
    )

from app.routes import api_register
app.include_router(api_register.router)

from app.routes import autocomplete
app.include_router(autocomplete.router)

from app.routes.check import router as check_router
app.include_router(check_router)

from app.routes import feedback
app.include_router(feedback.router)

from app.routes import password_recovery
app.include_router(password_recovery.router)

from app.routes import admin
app.include_router(admin.router)

from app.routes import api_feedback
app.include_router(api_feedback.router)

from app.routes import api_auth
app.include_router(api_auth.router)

from app.routes import api_2fa
app.include_router(api_2fa.router)

from app.routes import api_employees
app.include_router(api_employees.router)

from app.routes import api_check
app.include_router(api_check.router)

from app.routes import api_employee
app.include_router(api_employee.router)

from app.routes import api_employer
app.include_router(api_employer.router)

from app.routes import api_info_of_me
app.include_router(api_info_of_me.router)

from app.routes import api_password_recovery
app.include_router(api_password_recovery.api_router)

from app.jobs.cleanup_PU import cleanup_pending_users
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()

@app.on_event("startup")
def startup_event():
    scheduler.add_job(cleanup_pending_users, 'interval', minutes=10)
    scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()


from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")
