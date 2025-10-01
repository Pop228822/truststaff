from datetime import datetime

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth_redirect import AuthRedirectMiddleware
from app.limit import rate_limit_100_per_minute

load_dotenv()
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
from app.models import ReputationRecord, User, Employee, PendingUser
from app.security_headers import SecurityHeadersMiddleware

app = FastAPI(
    dependencies=[Depends(rate_limit_100_per_minute)]
)

app.add_middleware(AuthRedirectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
templates = Jinja2Templates(directory="templates")
from app.routes import superadmin, pages, register, login, employee_management
app.include_router(superadmin.router)
app.include_router(pages.router)
app.include_router(register.router)
app.include_router(login.router)
app.include_router(employee_management.router)

from fastapi.responses import RedirectResponse

from app.routes import onboarding
app.include_router(onboarding.router)


@app.exception_handler(404)
async def not_found(request: Request, exc: HTTPException):
    """Отдаём HTML-страницу 404 с кнопкой «На главную»."""
    return templates.TemplateResponse(
        "404.html",
        {"request": request},
        status_code=404
    )

from app.routes import api_register
app.include_router(api_register.router)

from app.routes import autocomplete
app.include_router(autocomplete.router)

from app.routes.check import router as check_router
app.include_router(check_router)

from app.routes import feedback
app.include_router(feedback.router)

from app.routes import password_recovery
app.include_router(password_recovery.router)

from app.routes import admin
app.include_router(admin.router)

from app.routes import api_feedback
app.include_router(api_feedback.router)

from app.routes import api_auth
app.include_router(api_auth.router)

from app.routes import api_2fa
app.include_router(api_2fa.router)

from app.routes import api_employees
app.include_router(api_employees.router)

from app.routes import api_check
app.include_router(api_check.router)

from app.routes import api_employee
app.include_router(api_employee.router)

from app.routes import api_employer
app.include_router(api_employer.router)

from app.routes import api_info_of_me
app.include_router(api_info_of_me.router)

from app.routes import api_password_recovery
app.include_router(api_password_recovery.api_router)

from app.jobs.cleanup_PU import cleanup_pending_users
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()

@app.on_event("startup")
def startup_event():
    scheduler.add_job(cleanup_pending_users, 'interval', minutes=10)
    scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()


from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")
