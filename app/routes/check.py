from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.database import get_session
from app.models import User, Employee, ReputationRecord, CheckLog
from app.auth import get_session_user
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

router = APIRouter()

@router.get("/check", response_class=HTMLResponse)
def check_form(
    request: Request,
    current_user: Optional[User] = Depends(get_session_user)
):
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
        # Лимит исчерпан
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
    result = []
    for emp in employees:
        records = db.query(ReputationRecord).filter(ReputationRecord.employee_id == emp.id).all()
        result.append({
            "full_name": emp.full_name,
            "birth_date": emp.birth_date,
            "record_count": len(records),
            "records": records
        })

    return templates.TemplateResponse("check.html", {
        "request": request,
        "result": result,
        "user": current_user
    })

