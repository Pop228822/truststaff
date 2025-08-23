from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.database import get_session
from app.models import User, Employee, ReputationRecord, CheckLog
from app.auth import get_session_user, only_approved_user
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

router = APIRouter()


from sqlalchemy import text

def inc_check(db, employee_id: int):
    db.execute(
        text("""
            UPDATE employee
            SET checks_count = checks_count + 1,
                last_checked_at = NOW()
            WHERE id = :id
        """),
        {"id": employee_id}
    )
    db.commit()

def add_like(db, employee_id: int):
    db.execute(
        text("""
            UPDATE employee
            SET likes_count = likes_count + 1
            WHERE id = :id
        """),
        {"id": employee_id}
    )
    db.commit()

def add_dislike(db, employee_id: int):
    db.execute(
        text("""
            UPDATE employee
            SET dislikes_count = dislikes_count + 1
            WHERE id = :id
        """),
        {"id": employee_id}
    )
    db.commit()

@router.get("/check", response_class=HTMLResponse)
def check_form(
    request: Request,
    current_user: Optional[User] = Depends(only_approved_user)
):
    if current_user.is_blocked:
        response = RedirectResponse("/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    if not current_user:
        return RedirectResponse("/login", status_code=302)
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

    from sqlalchemy import func

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

    new_log = CheckLog(user_id=current_user.id)
    db.add(new_log)
    db.commit()

    query = db.query(Employee).filter(Employee.full_name.ilike(full_name.strip()))
    if birth_date:
        query = query.filter(Employee.birth_date == birth_date)

    employees = query.all()

    for emp in employees:
        inc_check(db, emp.id)

    result = []
    for emp in employees:
        records = db.query(ReputationRecord).filter(ReputationRecord.employee_id == emp.id).all()
        prepared_records = []
        for record in records:
            # Проверяем работодателя, который оставил запись (record.employer_id)
            employer = db.query(User).get(record.employer_id)

            if employer.is_blocked:
                # Если работодатель заблокирован, выводим сообщение вместо данных
                prepared_records.append({
                    "is_blocked_employer": True,
                    "blocked_message": "Предприниматель заблокирован, отзыв неактуален."
                })
            else:
                # Обычная информация
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
            "full_name": emp.full_name,
            "birth_date": emp.birth_date,
            "records": prepared_records,
            "record_count": len(prepared_records)
        })

    return templates.TemplateResponse("check.html", {
        "request": request,
        "result": result,
        "user": current_user
    })


