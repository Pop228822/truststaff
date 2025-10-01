from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from jinja2 import Environment, FileSystemLoader
import pdfkit
import io
from fastapi.responses import StreamingResponse

from app.database import get_session
from app.models import Employee, ReputationRecord, User
from app.auth import get_session_user, only_approved_user, get_current_user_safe, oauth2_scheme_optional
from app.bad_words import BAD_WORDS

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Константы
MAX_EMPLOYERS_COUNT = 30
MAX_TEXT_LENGTH = 500


def contains_bad_words(text: str) -> bool:
    """Проверка на плохие слова"""
    return any(bad in text.lower() for bad in BAD_WORDS)


def enforce_login_and_verification(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_session)
) -> User:
    """Проверка входа и верификации пользователя"""
    user = get_current_user_safe(request=request, token=token, db=db)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    if user.verification_status != "approved":
        raise HTTPException(status_code=302, headers={"Location": "/onboarding"})
    return user


@router.get("/add-employee", response_class=HTMLResponse)
def add_employee_form(request: Request, current_user: User = Depends(get_session_user)):
    """Форма добавления сотрудника"""
    if not current_user:
        return RedirectResponse("/login", status_code=302)
    if current_user.is_blocked:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response
    if current_user.verification_status != "approved":
        return RedirectResponse("/onboarding", status_code=302)
    return templates.TemplateResponse("add_employee.html", {"request": request})


@router.post("/add-employee")
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
    """Добавление нового сотрудника"""
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

    # Валидация даты рождения
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

    # Создание сотрудника
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


@router.get("/employees", response_class=HTMLResponse)
def list_employees(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(enforce_login_and_verification)
):
    """Список сотрудников пользователя"""
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


@router.get("/employee/{employee_id}/add-record", response_class=HTMLResponse)
def record_form(
    request: Request,
    employee_id: int,
    current_user: User = Depends(only_approved_user)
):
    """Форма добавления записи о сотруднике"""
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


@router.post("/employee/{employee_id}/add-record")
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
    """Добавление записи о сотруднике"""
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

    # Валидация длины полей
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

    # Проверка лимита записей
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

    # Создание записи
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


@router.get("/employee/{employee_id}/generate-consent", response_class=HTMLResponse)
def consent_form(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    """Форма согласия сотрудника"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return templates.TemplateResponse("consent_form.html", {
        "request": request,
        "employee_id": employee_id,
        "employee": employee,
        "user": current_user
    })


@router.post("/employee/{employee_id}/generate-consent")
def generate_consent_pdf(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    """Генерация PDF согласия"""
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


@router.get("/record/{record_id}/edit", response_class=HTMLResponse)
def edit_record_form(
    request: Request,
    record_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    """Форма редактирования записи"""
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


@router.post("/record/{record_id}/edit")
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
    """Редактирование записи о сотруднике"""
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

    # Валидация длины полей
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

    # Поиск записи
    record = db.query(ReputationRecord).filter(
        ReputationRecord.id == record_id,
        ReputationRecord.employer_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404)

    # Валидация дат
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

    # Обновление записи
    record.hired_at = hired_dt
    record.fired_at = fired_dt
    record.position = position
    record.misconduct = misconduct or None
    record.dismissal_reason = dismissal_reason or None
    record.commendation = commendation or None

    db.commit()
    return RedirectResponse(url="/employees", status_code=302)


@router.post("/record/{record_id}/delete")
def delete_record(
    record_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    """Удаление записи о сотруднике"""
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
