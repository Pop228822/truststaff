from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import pdfkit
from sqlalchemy.orm import Session
import shutil
import os

from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_safe,
    only_approved_user,
    get_session_user,
    oauth2_scheme_optional
)
from app.database import get_session
from app.models import ReputationRecord, User, Employee

app = FastAPI()
templates = Jinja2Templates(directory="templates")

from app.auth import optional_user

@app.get("/", response_class=HTMLResponse)
def root(
    request: Request,
    user: Optional[User] = Depends(optional_user)
):
    return templates.TemplateResponse("base.html", {
        "request": request,
        "user": user,
        "verification_status": user.verification_status if user else None,
        "rejection_reason": user.rejection_reason if user else None
    })


@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    existing = session.query(User).filter(User.email == email).first()
    if existing:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Email уже зарегистрирован"})

    new_user = User(name=name,
                    email=email,
                    password_hash=hash_password(password),
                    role="user",
                    verification_status="unverified")

    session.add(new_user)
    session.commit()
    return RedirectResponse("/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

from app.brute_force import is_brute_force, log_login_attempt

@app.post("/login")
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    ip = request.client.host

    if is_brute_force(session, email, ip):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Слишком много попыток входа. Попробуйте через 15 минут."
        })

    user = session.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        log_login_attempt(session, email, ip, False)
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверный логин или пароль"
        })

    log_login_attempt(session, email, ip, True)

    token = create_access_token({"sub": str(user.id)})
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response

@app.get("/add-employee", response_class=HTMLResponse)
def add_employee_form(request: Request, current_user: User = Depends(get_session_user)):
    if not current_user:
        return RedirectResponse("/login", status_code=302)
    if current_user.verification_status != "approved":
        return RedirectResponse("/onboarding", status_code=302)
    return templates.TemplateResponse("add_employee.html", {"request": request})

@app.post("/add-employee")
def add_employee(
    request: Request,
    full_name: str = Form(...),
    birth_date: str = Form(...),
    contact: str = Form(""),
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    employee = Employee(
        full_name=full_name,
        birth_date=birth_date,
        contact=contact,
        created_by_user_id=current_user.id
    )
    db.add(employee)
    db.commit()
    return RedirectResponse("/employees", status_code=302)

from fastapi.responses import RedirectResponse

def enforce_login_and_verification(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_session)
) -> User:
    user = get_current_user_safe(request=request, token=token, db=db)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    if user.verification_status != "approved":
        raise HTTPException(status_code=302, headers={"Location": "/onboarding"})
    return user

@app.get("/employees", response_class=HTMLResponse)
def list_employees(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(enforce_login_and_verification)
):
    employees = db.query(Employee).filter(Employee.created_by_user_id == current_user.id).all()
    for emp in employees:
        emp.records = db.query(ReputationRecord).filter(ReputationRecord.employee_id == emp.id).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "employees": employees
    })

@app.get("/employee/{employee_id}/add-record", response_class=HTMLResponse)
def record_form(request: Request, employee_id: int):
    return templates.TemplateResponse("add_record.html", {"request": request, "employee_id": employee_id})

@app.post("/employee/{employee_id}/add-record")
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
    return RedirectResponse(url=f"/employees", status_code=302)

@app.get("/employee/{employee_id}/generate-consent", response_class=HTMLResponse)
def consent_form(request: Request, employee_id: int, db: Session = Depends(get_session), current_user: User = Depends(only_approved_user)):
    return templates.TemplateResponse("consent_form.html", {
        "request": request,
        "employee_id": employee_id,
        "user": current_user
    })

from fastapi.responses import StreamingResponse
import io

@app.post("/employee/{employee_id}/generate-consent")
def generate_consent_pdf(
    request: Request,
    employee_id: int,
    employer_name: str = Form(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("consent_template.html")
    html_content = template.render(
        full_name=employee.full_name,
        birth_date=employee.birth_date,
        contact=employee.contact or "",
        employer_name=employer_name,
        today=datetime.now().strftime("%d.%m.%Y")
    )

    pdf_bytes = pdfkit.from_string(html_content, False)
    pdf_stream = io.BytesIO(pdf_bytes)

    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=consent_{employee.id}.pdf"}
    )


from app.auth import get_session_user

@app.get("/check", response_class=HTMLResponse)
def check_form(
    request: Request,
    current_user: Optional[User] = Depends(get_session_user)
):
    if not current_user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("check.html", {"request": request, "result": None, "user": current_user})


@app.post("/check", response_class=HTMLResponse)
def check_employee(
    request: Request,
    full_name: str = Form(...),
    birth_date: Optional[str] = Form(None),
    db: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_session_user)
):
    if not current_user:
        return RedirectResponse("/login", status_code=302)

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

@app.get("/onboarding", response_class=HTMLResponse)
def onboarding_form(request: Request, current_user: User = Depends(get_session_user)):
    if current_user and current_user.verification_status == "approved":
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("onboarding.html", {"request": request, "user": current_user})

@app.post("/onboarding")
def submit_onboarding(
    request: Request,
    company_name: str = Form(...),
    city: str = Form(...),
    inn_or_ogrn: str = Form(...),
    passport_file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_session_user)
):
    filename = f"passport_{current_user.id}_{passport_file.filename}"
    filepath = os.path.join("static", "uploads", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(passport_file.file, buffer)

    user = db.query(User).filter(User.id == current_user.id).first()
    user.company_name = company_name
    user.city = city
    user.inn_or_ogrn = inn_or_ogrn
    user.passport_filename = filename
    user.verification_status = "pending"
    user.rejection_reason = None
    db.commit()

    return templates.TemplateResponse("onboarding_submitted.html", {"request": request})

@app.get("/record/{record_id}/edit", response_class=HTMLResponse)
def edit_record_form(
    record_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    record = db.query(ReputationRecord).filter(
        ReputationRecord.id == record_id,
        ReputationRecord.employer_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404)

    return templates.TemplateResponse("edit_record.html", {
        "request": request,
        "record": record
    })


@app.post("/record/{record_id}/edit")
def edit_record(
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
    record = db.query(ReputationRecord).filter(
        ReputationRecord.id == record_id,
        ReputationRecord.employer_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404)

    try:
        record.hired_at = datetime.strptime(hired_at, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректная дата приёма")

    record.fired_at = datetime.strptime(fired_at, "%Y-%m-%d") if fired_at else None
    record.position = position
    record.misconduct = misconduct or None
    record.dismissal_reason = dismissal_reason or None
    record.commendation = commendation or None

    db.commit()
    return RedirectResponse(url="/employees", status_code=302)


@app.post("/record/{record_id}/delete")
def delete_record(
    record_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    record = db.query(ReputationRecord).filter(
        ReputationRecord.id == record_id,
        ReputationRecord.employer_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404)

    db.delete(record)
    db.commit()
    return RedirectResponse(url="/employees", status_code=302)

from app.routes import feedback

app.include_router(feedback.router)

from app.routes import admin
app.include_router(admin.router)

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")
