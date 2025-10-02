"""
Подключение всех роутеров к приложению
"""
from fastapi import FastAPI

from app.routes import (
    superadmin, pages, register, login, employee_management,
    onboarding, api_register, autocomplete, check, feedback,
    password_recovery, admin, api_feedback, api_auth, api_2fa,
    api_employees, api_check, api_employee, api_employer,
    api_info_of_me, api_password_recovery
)


def setup_routers(app: FastAPI) -> None:
    """Подключение всех роутеров к приложению"""
    
    # Основные роутеры
    app.include_router(superadmin.router)
    app.include_router(pages.router)
    app.include_router(register.router)
    app.include_router(login.router)
    app.include_router(employee_management.router)
    app.include_router(onboarding.router)
    
    # API роутеры
    app.include_router(api_register.router)
    app.include_router(autocomplete.router)
    app.include_router(check.router)
    app.include_router(feedback.router)
    app.include_router(password_recovery.router)
    app.include_router(admin.router)
    app.include_router(api_feedback.router)
    app.include_router(api_auth.router)
    app.include_router(api_2fa.router)
    app.include_router(api_employees.router)
    app.include_router(api_check.router)
    app.include_router(api_employee.router)
    app.include_router(api_employer.router)
    app.include_router(api_info_of_me.router)
    app.include_router(api_password_recovery.api_router)
