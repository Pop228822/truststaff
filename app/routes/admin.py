from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from starlette import status

from app.auth import get_current_user
from app.database import get_session
from app.models import User, Employee

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def ensure_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if current_user.role != "admin":
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
