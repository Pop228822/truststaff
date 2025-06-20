from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date, datetime
from sqlalchemy import func
from typing import Optional

from app.models import Employee, ReputationRecord, User, CheckLog
from app.auth import get_session
from app.routes.api_auth import get_api_user

router = APIRouter(prefix="/api/employees")

class CheckEmployeeRequest(BaseModel):
    full_name: str
    birth_date: Optional[date] = None

@router.post("/check")
def api_check_employee(
    data: CheckEmployeeRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_api_user)
):
    full_name = data.full_name
    birth_date = data.birth_date

    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Лимит проверок
    today = date.today()
    start_of_day = datetime(today.year, today.month, today.day)

    count_today = db.query(func.count(CheckLog.id)).filter(
        CheckLog.user_id == current_user.id,
        CheckLog.created_at >= start_of_day
    ).scalar()

    if count_today >= 1000:
        raise HTTPException(status_code=429, detail="Превышен лимит проверок")

    db.add(CheckLog(user_id=current_user.id))
    db.commit()

    # Поиск
    query = db.query(Employee).filter(Employee.full_name.ilike(f"%{full_name.strip()}%"))
    if birth_date:
        query = query.filter(Employee.birth_date == birth_date)

    employees = query.all()

    result = []
    for emp in employees:
        emp_data = {
            "employee_id": emp.id,
            "full_name": emp.full_name,
            "birth_date": emp.birth_date.isoformat(),
            "record_count": 0,
            "records": []
        }

        records = db.query(ReputationRecord).filter(ReputationRecord.employee_id == emp.id).all()
        for record in records:
            employer = db.get(User, record.employer_id)
            if employer and employer.is_blocked:
                emp_data["records"].append({
                    "is_blocked_employer": True,
                    "blocked_message": "Предприниматель заблокирован, отзыв неактуален."
                })
            else:
                emp_data["records"].append({
                    "is_blocked_employer": False,
                    "employer_id": record.employer_id,
                    "position": record.position,
                    "hired_at": record.hired_at.isoformat(),
                    "fired_at": record.fired_at.isoformat() if record.fired_at else None,
                    "misconduct": record.misconduct,
                    "dismissal_reason": record.dismissal_reason,
                    "commendation": record.commendation,
                })

        emp_data["record_count"] = len(emp_data["records"])
        result.append(emp_data)

    return result