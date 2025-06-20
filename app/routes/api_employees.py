# app/routes/api_employees.py

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlmodel import Session
from datetime import datetime

from app.database import get_session
from app.routes.api_auth import get_api_user
from app.models import User, Employee

router = APIRouter(prefix="/api/employees")

@router.get("/me")
def my_profile(current_user: User = Depends(get_api_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "company": current_user.company_name,
    }

MAX_EMPLOYERS_COUNT = 30

@router.post("/add")
def api_add_employee(
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str = Form(""),  # можно оставить необязательным
    birth_date: str = Form(...),
    contact: str = Form(""),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_api_user)
):
    # Проверка лимита
    employee_count = db.query(Employee).filter(Employee.created_by_user_id == current_user.id).count()
    if employee_count >= MAX_EMPLOYERS_COUNT:
        raise HTTPException(status_code=400, detail="employee_limit_reached")

    full_name = f"{last_name} {first_name} {middle_name}".strip()
    try:
        parsed_birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_birth_date_format")

    employee = Employee(
        full_name=full_name,
        birth_date=parsed_birth_date,
        contact=contact,
        created_by_user_id=current_user.id
    )
    db.add(employee)
    db.commit()

    return {"status": "success", "employee_id": employee.id}