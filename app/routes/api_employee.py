from fastapi import APIRouter, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from sqlmodel import Session

from app.models import User, ReputationRecord
from app.routes.api_auth import get_api_user, get_session, only_approved_api_user

router = APIRouter(prefix="/api")


@router.post("/employee/{employee_id}/add-record")
def add_record_api(
    employee_id: int,
    position: str = Form(...),
    hired_at: str = Form(...),
    fired_at: Optional[str] = Form(None),
    misconduct: Optional[str] = Form(None),
    dismissal_reason: Optional[str] = Form(None),
    commendation: Optional[str] = Form(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_api_user)
):
    if current_user.is_blocked:
        return JSONResponse(status_code=403, content={"error": "Пользователь заблокирован"})

    existing_records_count = db.query(ReputationRecord).filter(
        ReputationRecord.employee_id == employee_id,
        ReputationRecord.employer_id == current_user.id
    ).count()

    if existing_records_count >= 2:
        return JSONResponse(status_code=400, content={
            "error": "Вы уже добавили 2 записи об этом сотруднике"
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

    return JSONResponse(status_code=201, content={"message": "Запись успешно добавлена"})

@router.delete("/records/{record_id}/delete")
def api_delete_record(
    record_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_api_user)
):
    record = db.query(ReputationRecord).filter(
        ReputationRecord.id == record_id,
        ReputationRecord.employer_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    db.delete(record)
    db.commit()
    return {"detail": "Запись удалена"}
