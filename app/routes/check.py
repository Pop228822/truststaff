from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.database import get_session
from app.models import User, Employee, ReputationRecord, CheckLog
from app.auth import get_session_user, only_approved_user
from fastapi.templating import Jinja2Templates
from sqlalchemy import text, func

templates = Jinja2Templates(directory="templates")
router = APIRouter()

# === Метрики ===

def inc_check_bulk(db: Session, employee_ids: List[int]) -> None:
    if not employee_ids:
        return
    db.execute(
        text("""
            UPDATE employee
            SET checks_count = COALESCE(checks_count, 0) + 1
            WHERE id = ANY(:ids)
        """),
        {"ids": employee_ids}
    )
    db.commit()

def add_like(db: Session, employee_id: int) -> None:
    db.execute(
        text("UPDATE employee SET likes_count = COALESCE(likes_count, 0) + 1 WHERE id = :id"),
        {"id": employee_id}
    )
    db.commit()

def add_dislike(db: Session, employee_id: int) -> None:
    db.execute(
        text("UPDATE employee SET dislikes_count = COALESCE(dislikes_count, 0) + 1 WHERE id = :id"),
        {"id": employee_id}
    )
    db.commit()

# === Роуты ===

@router.get("/check", response_class=HTMLResponse)
def check_form(
    request: Request,
    current_user: Optional[User] = Depends(only_approved_user)
):
    # Сначала проверяем, что пользователь есть
    if not current_user:
        return RedirectResponse("/login", status_code=302)

    if current_user.is_blocked:
        response = RedirectResponse("/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    return templates.TemplateResponse("check.html", {"request": request, "result": None, "user": current_user})


@router.post("/check", response_class=HTMLResponse)
def check_employee(
    request: Request,
    full_name: str = Form(...),
    birth_date: Optional[str] = Form(None),
    db: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_session_user)
):
    if not current_user:
        return RedirectResponse("/login", status_code=302)

    today = date.today()
    start_of_day = datetime(today.year, today.month, today.day)

    count_today = db.query(func.count(CheckLog.id)).filter(
        CheckLog.user_id == current_user.id,
        CheckLog.created_at >= start_of_day
    ).scalar()

    if count_today >= 20:
        return templates.TemplateResponse("check.html", {
            "request": request,
            "result": None,
            "user": current_user,
            "error_message": "Вы превысили лимит бесплатных проверок (20 в день)."
        })

    # Логируем сам факт попытки проверки (по пользователю)
    db.add(CheckLog(user_id=current_user.id))
    db.commit()

    # Поиск сотрудников
    q = db.query(Employee).filter(Employee.full_name.ilike(full_name.strip()))
    if birth_date:
        try:
            bd = datetime.strptime(birth_date, "%Y-%m-%d").date()
            q = q.filter(Employee.birth_date == bd)
        except ValueError:
            return templates.TemplateResponse("check.html", {
                "request": request,
                "result": None,
                "user": current_user,
                "error_message": "Неверная дата. Используйте формат ГГГГ-ММ-ДД."
            })

    employees = q.all()

    # Инкремент «пробивов» за один SQL по найденным id
    inc_check_bulk(db, [e.id for e in employees])

    # Формируем результат
    result = []
    for emp in employees:
        records = db.query(ReputationRecord).filter(ReputationRecord.employee_id == emp.id).all()
        prepared_records = []
        for record in records:
            employer = db.get(User, record.employer_id)  # безопаснее, чем query(...).get(...)
            if employer and employer.is_blocked:
                prepared_records.append({
                    "is_blocked_employer": True,
                    "blocked_message": "Предприниматель заблокирован, отзыв неактуален."
                })
            else:
                prepared_records.append({
                    "is_blocked_employer": False,
                    "employer_id": record.employer_id,
                    "position": record.position,
                    "hired_at": record.hired_at,
                    "fired_at": record.fired_at,
                    "misconduct": record.misconduct,
                    "dismissal_reason": record.dismissal_reason,
                    "commendation": record.commendation,
                })

        result.append({
            "employee_id": emp.id,
            "full_name": emp.full_name,
            "birth_date": emp.birth_date,
            "records": prepared_records,
            "record_count": len(prepared_records),
            # если модель уже с полями — можно вывести их в шаблоне
            "checks_count": getattr(emp, "checks_count", 0),
            "likes_count": getattr(emp, "likes_count", 0),
            "dislikes_count": getattr(emp, "dislikes_count", 0),
        })

    return templates.TemplateResponse("check.html", {
        "request": request,
        "result": result,
        "user": current_user
    })
