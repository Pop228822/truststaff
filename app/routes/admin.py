from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from starlette import status
from datetime import datetime, timedelta
from collections import defaultdict
import time
from sqlalchemy import func

from app.auth import get_current_user
from app.database import get_session
from app.models import User, Employee, ReputationRecord

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Простое хранилище метрик (в продакшене лучше Redis/InfluxDB)
# С защитой от переполнения памяти
metrics_store = {
    "request_count": defaultdict(int),
    "error_count": defaultdict(int),
    "start_time": datetime.now()
}

# Максимальное количество уникальных endpoints для хранения
MAX_ENDPOINTS = 1000


def ensure_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if current_user.role != "admin" and current_user.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return current_user


@router.get("/admin/review", response_class=HTMLResponse)
def review_employers(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    current_user = ensure_admin(current_user)
    pending = db.query(User).filter(User.verification_status == "pending").all()
    return templates.TemplateResponse("admin_review.html", {"request": request, "pending": pending})


@router.post("/admin/approve/{user_id}")
def approve_user(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(ensure_admin)
):
    user = db.query(User).get(user_id)
    if user:
        user.verification_status = "approved"
        user.is_approved = True
        user.rejection_reason = None
        db.commit()
    return RedirectResponse("/admin/review", status_code=302)


from fastapi import Form

@router.post("/admin/reject/{user_id}")
def reject_user(
    user_id: int,
    rejection_reason: str = Form(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(ensure_admin)
):
    user = db.query(User).get(user_id)
    if user:
        user.verification_status = "rejected"
        user.rejection_reason = rejection_reason
        user.is_approved = False
        db.commit()
    return RedirectResponse("/admin/review", status_code=302)


@router.get("/admin/search/user", response_class=HTMLResponse)
def search_user_form(request: Request,
                     current_user: User = Depends(ensure_admin)):
    """Страница с формой поиска по email"""
    return templates.TemplateResponse("admin_search_user.html",
                                      {"request": request})

@router.post("/admin/search/user", response_class=HTMLResponse)
def search_user_result(request: Request,
                       email: str = Form(...),
                       db: Session = Depends(get_session),
                       current_user: User = Depends(ensure_admin)):
    """Обрабатываем форму, показываем пользователя и его сотрудников"""
    email_clean = email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    if user is None:
        return templates.TemplateResponse("admin_search_user.html",
                                          {"request": request,
                                           "error": f"Пользователь {email_clean} не найден."})

    employees = db.query(Employee).filter(Employee.created_by_user_id == user.id).all()

    return templates.TemplateResponse("admin_search_user_result.html",
                                      {"request": request,
                                       "searched_email": email_clean,
                                       "found_user": user,
                                       "employees": employees})


@router.get("/admin/users/list", response_class=HTMLResponse)
def admin_users_list(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(ensure_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    partial: bool = Query(False)
):
    total_count = db.query(User).count()

    users = (
        db.query(User)
        .order_by(
            (User.verification_status == "approved").desc(),
            User.created_at.desc()
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    has_more = (skip + limit) < total_count

    if partial:
        # Возвращаем кусок <li>...</li>
        return templates.TemplateResponse(
            "admin_users_list_partial.html",
            {
                "request": request,
                "users": users
            }
        )
    else:
        # Возвращаем полный шаблон
        return templates.TemplateResponse("admin_users_list.html", {
            "request": request,
            "users": users,
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
            "total_count": total_count,
            "current_user": current_user
        })


# --- 2. Страница подробностей о пользователе ---
@router.get("/admin/user/{user_id}", response_class=HTMLResponse)
def admin_user_details(
    request: Request,
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(ensure_admin)
):
    """
    Отображаем детали пользователя, его сотрудников и репутационные записи,
    переиспользуя логику, которая раньше была в search_user_result.
    """
    found_user = db.query(User).filter(User.id == user_id).first()
    if not found_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    employees = (
        db.query(Employee)
        .filter(Employee.created_by_user_id == found_user.id)
        .all()
    )

    return templates.TemplateResponse("admin_search_user_result.html", {
        "request": request,
        "searched_email": found_user.email,
        "found_user": found_user,
        "employees": employees
    })


@router.get("/admin/metrics", response_class=HTMLResponse)
def admin_metrics_html(
    request: Request,
    current_user: User = Depends(ensure_admin)
):
    """HTML страница с метриками (только для админов)"""
    uptime = datetime.now() - metrics_store["start_time"]
    
    metrics_data = {
        "uptime_seconds": uptime.total_seconds(),
        "uptime_human": str(uptime).split('.')[0],  # Убираем микросекунды
        "total_requests": sum(metrics_store["request_count"].values()),
        "total_errors": sum(metrics_store["error_count"].values()),
        "requests_by_endpoint": dict(metrics_store["request_count"]),
        "errors_by_status": dict(metrics_store["error_count"]),
        "admin_viewing": current_user.email,
        "timestamp": datetime.now().isoformat()
    }
    
    return templates.TemplateResponse("admin_metrics.html", {
        "request": request,
        "metrics": metrics_data,
        "user": current_user
    })


@router.get("/admin/metrics/api")
def admin_metrics_api(
    current_user: User = Depends(ensure_admin)
):
    """API endpoint с метриками (только для админов)"""
    uptime = datetime.now() - metrics_store["start_time"]
    
    return {
        "uptime_seconds": uptime.total_seconds(),
        "uptime_human": str(uptime).split('.')[0],  # Убираем микросекунды
        "total_requests": sum(metrics_store["request_count"].values()),
        "total_errors": sum(metrics_store["error_count"].values()),
        "requests_by_endpoint": dict(metrics_store["request_count"]),
        "errors_by_status": dict(metrics_store["error_count"]),
        "admin_viewing": current_user.email,
        "timestamp": datetime.now().isoformat()
    }


def record_request_metric(path: str, method: str, status_code: int):
    """
    Функция для записи метрики запроса (можно вызывать из middleware)
    С защитой от переполнения памяти
    """
    key = f"{method} {path}"
    
    # Защита от переполнения памяти
    if len(metrics_store["request_count"]) >= MAX_ENDPOINTS:
        # Если превысили лимит, удаляем самый редкий endpoint
        if key not in metrics_store["request_count"]:
            # Находим минимальный счетчик
            min_key = min(
                metrics_store["request_count"], 
                key=metrics_store["request_count"].get
            )
            # Удаляем его, чтобы освободить место
            del metrics_store["request_count"][min_key]
    
    metrics_store["request_count"][key] += 1
    
    if status_code >= 400:
        metrics_store["error_count"][str(status_code)] += 1


@router.get("/admin/business-metrics", response_class=HTMLResponse)
def admin_business_metrics(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(ensure_admin)
):
    """Бизнес-метрики (только для админов)"""
    
    # Общая статистика пользователей
    total_users = db.query(User).count()
    verified_users = db.query(User).filter(User.verification_status == "approved").count()
    pending_verification = db.query(User).filter(User.verification_status == "pending").count()
    
    # Статистика сотрудников
    total_employees = db.query(Employee).count()
    total_records = db.query(ReputationRecord).count()
    
    # Средние показатели
    avg_employees_per_user = round(total_employees / total_users, 2) if total_users > 0 else 0
    
    # Новые пользователи
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    
    new_users_today = db.query(User).filter(
        func.date(User.created_at) == today
    ).count() if hasattr(User, 'created_at') else 0
    
    new_users_week = db.query(User).filter(
        func.date(User.created_at) >= week_ago
    ).count() if hasattr(User, 'created_at') else 0
    
    # Распределение по ролям
    users_by_role = {}
    roles = db.query(User.role, func.count(User.id)).group_by(User.role).all()
    for role, count in roles:
        users_by_role[role or 'user'] = count
    
    # Распределение по статусу верификации
    users_by_verification = {}
    verifications = db.query(
        User.verification_status, 
        func.count(User.id)
    ).group_by(User.verification_status).all()
    for status, count in verifications:
        users_by_verification[status or 'none'] = count
    
    # Топ активных пользователей
    top_users = db.query(
        User.email,
        User.company_name,
        func.count(Employee.id).label('employee_count')
    ).outerjoin(
        Employee, User.id == Employee.created_by_user_id
    ).group_by(
        User.id, User.email, User.company_name
    ).order_by(
        func.count(Employee.id).desc()
    ).limit(10).all()
    
    # Конверсия в верификацию
    conversion_rate = (verified_users / total_users * 100) if total_users > 0 else 0
    
    metrics_data = {
        "total_users": total_users,
        "verified_users": verified_users,
        "pending_verification": pending_verification,
        "total_employees": total_employees,
        "total_records": total_records,
        "avg_employees_per_user": avg_employees_per_user,
        "new_users_today": new_users_today,
        "new_users_week": new_users_week,
        "users_by_role": users_by_role,
        "users_by_verification": users_by_verification,
        "top_users": [
            {
                "email": user.email,
                "company_name": user.company_name,
                "employee_count": user.employee_count
            }
            for user in top_users
        ],
        "conversion_rate": round(conversion_rate, 1),
        "admin_viewing": current_user.email,
        "timestamp": datetime.now().isoformat()
    }
    
    return templates.TemplateResponse("admin_business_metrics.html", {
        "request": request,
        "metrics": metrics_data,
        "user": current_user
    })
