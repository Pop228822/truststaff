from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date, datetime
from sqlalchemy import func
from typing import Optional, List

from app.models import Employee, ReputationRecord, User, CheckLog
from app.auth import get_session, get_session_user

router = APIRouter(prefix="/api/employees")

class CheckEmployeeRequest(BaseModel):
    full_name: str
    birth_date: Optional[str] = None  # формат: YYYY-MM-DD

class ReputationRecordOut(BaseModel):
    is_blocked_employer: bool
    blocked_message: Optional[str] = None

    employer_id: Optional[int] = None
    position: Optional[str] = None
    hired_at: Optional[str] = None
    fired_at: Optional[str] = None
    misconduct: Optional[str] = None
    dismissal_reason: Optional[str] = None
    commendation: Optional[str] = None

class EmployeeCheckResponse(BaseModel):
    full_name: str
    birth_date: str
    record_count: int
    records: List[ReputationRecordOut]

@router.post("/check", response_model=List[EmployeeCheckResponse])
def api_check_employee(
    data: CheckEmployeeRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_session_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    today = date.today()
    start_of_day = datetime(today.year, today.month, today.day)

    count_today = db.query(func.count(CheckLog.id)).filter(
        CheckLog.user_id == current_user.id,
        CheckLog.created_at >= start_of_day
    ).scalar()

    if count_today >= 20:
        raise HTTPException(status_code=429, detail="Превышен лимит бесплатных проверок (20 в день)")

    db.add(CheckLog(user_id=current_user.id))
    db.commit()

    query = db.query(Employee).filter(Employee.full_name.ilike(data.full_name.strip()))
    if data.birth_date:
        query = query.filter(Employee.birth_date == data.birth_date)

    employees = query.all()
    response = []

    for emp in employees:
        records = db.query(ReputationRecord).filter(ReputationRecord.employee_id == emp.id).all()
        output_records = []

        for record in records:
            employer = db.query(User).get(record.employer_id)
            if employer and employer.is_blocked:
                output_records.append(ReputationRecordOut(
                    is_blocked_employer=True,
                    blocked_message="Предприниматель заблокирован, отзыв неактуален."
                ))
            else:
                output_records.append(ReputationRecordOut(
                    is_blocked_employer=False,
                    employer_id=record.employer_id,
                    position=record.position,
                    hired_at=str(record.hired_at) if record.hired_at else None,
                    fired_at=str(record.fired_at) if record.fired_at else None,
                    misconduct=record.misconduct,
                    dismissal_reason=record.dismissal_reason,
                    commendation=record.commendation,
                ))

        response.append(EmployeeCheckResponse(
            full_name=emp.full_name,
            birth_date=str(emp.birth_date),
            record_count=len(output_records),
            records=output_records
        ))

    return response