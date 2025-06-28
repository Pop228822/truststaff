from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import User, Employee
from app.auth import get_current_user

router = APIRouter()

@router.get("/api/me")
def get_current_user_info(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    employee_count = db.query(Employee).filter(Employee.user_id == current_user.id).count()

    return JSONResponse({
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "company_name": current_user.company_name,
        "city": current_user.city,
        "inn_or_ogrn": current_user.inn_or_ogrn,
        "verification_status": current_user.verification_status,
        "employee_count": employee_count
    })