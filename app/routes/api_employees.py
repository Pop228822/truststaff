from fastapi import APIRouter, Depends, Form, HTTPException
from sqlmodel import Session
from datetime import datetime

from app.database import get_session
from app.routes.api_auth import get_api_user, only_approved_api_user
from app.models import User, Employee, ReputationRecord

router = APIRouter(prefix="/api/employees")

MAX_EMPLOYERS_COUNT = 30

@router.post("/add")
def api_add_employee(
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str = Form(""),  # можно оставить необязательным
    birth_date: str = Form(...),
    contact: str = Form(""),
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_api_user)
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

@router.get("/", response_model=list[dict])
def list_employees_api(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_api_user)
):
    employees = db.query(Employee).filter(Employee.created_by_user_id == current_user.id).all()

    results = []
    for emp in employees:
        records = db.query(ReputationRecord).filter(ReputationRecord.employee_id == emp.id).all()
        results.append({
            "id": emp.id,
            "full_name": emp.full_name,
            "birth_date": emp.birth_date.isoformat(),
            "contact": emp.contact,
            "record_count": len(records),
            "records": [
                {
                    "position": r.position,
                    "hired_at": r.hired_at.isoformat() if r.hired_at else None,
                    "fired_at": r.fired_at.isoformat() if r.fired_at else None,
                    "misconduct": r.misconduct,
                    "commendation": r.commendation,
                }
                for r in records
            ]
        })

    return results

@router.get("/{employee_id}/link-add-record")
def mobile_add_record_link(employee_id: int, current_user: User = Depends(only_approved_api_user)):
    # Проверка прав можно убрать или оставить, если нужно
    return {
        "url": f"truststaff://add-record?employee_id={employee_id}"
    }

from fastapi.responses import StreamingResponse
from fastapi import UploadFile, File, Form, Request, HTTPException, Depends
from sqlmodel import Session
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import pdfkit, io

from app.models import User, Employee

@router.post("/{employee_id}/generate-consent")
def api_generate_consent_pdf(
    employee_id: int,
    employer_company_name: str = Form(...),
    employer_inn: str = Form(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_api_user)
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("consent_template.html")

    html = template.render(
        full_name=employee.full_name,
        birth_date=employee.birth_date,
        contact=employee.contact or "",
        employer_company_name=employer_company_name,
        employer_inn=employer_inn,
        today=datetime.now().strftime("%d.%m.%Y")
    )

    pdf_bytes = pdfkit.from_string(html, False)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=consent_{employee.id}.pdf"}
    )

