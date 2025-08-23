from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.database import get_session
from app.models import User, Employee, ReputationRecord, CheckLog
from app.auth import get_session_user, only_approved_user
from fastapi.templating import Jinja2Templates
from sqlalchemy import text, func

templates = Jinja2Templates(directory="templates")
router = APIRouter()

# === Метрики ===

def inc_check(db, employee_id: int) -> None:
    db.execute(text("""
        UPDATE employee
        SET checks_count = COALESCE(checks_count, 0) + 1
        WHERE id = :id
    """), {"id": employee_id})


def set_reaction(db: Session, employee_id: int, employer_id: int, new_reaction: str) -> None:
    assert new_reaction in ("like", "dislike")

    # читаем текущую реакцию
    row = db.execute(
        text("""
            SELECT reaction FROM employee_reaction
            WHERE employee_id = :e AND employer_id = :u
        """),
        {"e": employee_id, "u": employer_id}
    ).first()

    if row is None:
        # не голосовал — вставляем и инкрементим нужный счётчик
        db.execute(
            text("""
                INSERT INTO employee_reaction (employee_id, employer_id, reaction)
                VALUES (:e, :u, :r)
            """),
            {"e": employee_id, "u": employer_id, "r": new_reaction}
        )
        if new_reaction == "like":
            db.execute(text("UPDATE employee SET likes_count = likes_count + 1 WHERE id = :e"), {"e": employee_id})
        else:
            db.execute(text("UPDATE employee SET dislikes_count = dislikes_count + 1 WHERE id = :e"), {"e": employee_id})

    else:
        old = row[0]
        if old == new_reaction:
            # повторное нажатие того же — ничего не делаем
            pass
        else:
            # смена реакции: +1 к новой, -1 к старой
            db.execute(
                text("""
                    UPDATE employee_reaction
                    SET reaction = :r, updated_at = NOW()
                    WHERE employee_id = :e AND employer_id = :u
                """),
                {"e": employee_id, "u": employer_id, "r": new_reaction}
            )
            if new_reaction == "like":
                db.execute(text("""
                    UPDATE employee SET likes_count = likes_count + 1,
                                        dislikes_count = GREATEST(dislikes_count - 1, 0)
                    WHERE id = :e
                """), {"e": employee_id})
            else:
                db.execute(text("""
                    UPDATE employee SET dislikes_count = dislikes_count + 1,
                                        likes_count = GREATEST(likes_count - 1, 0)
                    WHERE id = :e
                """), {"e": employee_id})

    db.commit()

# === Роуты ===

@router.post("/employee/{emp_id}/react")
def react_employee(
    emp_id: int,
    request: Request,
    reaction: str = Form(...),                      # 'like' или 'dislike'
    db: Session = Depends(get_session),
    current_user: User = Depends(only_approved_user)
):
    if reaction not in ("like", "dislike"):
        return RedirectResponse(request.headers.get("referer") or "/check", status_code=303)
    set_reaction(db, emp_id, current_user.id, reaction)
    return RedirectResponse(request.headers.get("referer") or "/check", status_code=303)


@router.get("/check", response_class=HTMLResponse)
def check_form(
    request: Request,
    current_user: Optional[User] = Depends(only_approved_user)
):
    # Сначала проверяем, что пользователь есть
    if not current_user:
        return RedirectResponse("/login", status_code=302)

    if current_user.is_blocked:
        response = RedirectResponse("/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    return templates.TemplateResponse("check.html", {"request": request, "result": None, "user": current_user})


@router.post("/check", response_class=HTMLResponse)
def check_employee(
    request: Request,
    full_name: str = Form(...),
    birth_date: Optional[str] = Form(None),
    db: Session = Depends(get_session),
    current_user: Optional[User] = Depends(only_approved_user)
):
    if not current_user:
        return RedirectResponse("/login", status_code=302)

    today = date.today()
    start_of_day = datetime(today.year, today.month, today.day)

    count_today = db.query(func.count(CheckLog.id)).filter(
        CheckLog.user_id == current_user.id,
        CheckLog.created_at >= start_of_day
    ).scalar()

    if count_today >= 20:
        return templates.TemplateResponse("check.html", {
            "request": request,
            "result": None,
            "user": current_user,
            "error_message": "Вы превысили лимит бесплатных проверок (20 в день)."
        })

    db.add(CheckLog(user_id=current_user.id))
    db.commit()

    q = db.query(Employee).filter(Employee.full_name.ilike(full_name.strip()))
    if birth_date:
        try:
            bd = datetime.strptime(birth_date, "%Y-%m-%d").date()
            q = q.filter(Employee.birth_date == bd)
        except ValueError:
            return templates.TemplateResponse("check.html", {
                "request": request,
                "result": None,
                "user": current_user,
                "error_message": "Неверная дата. Используйте формат ГГГГ-ММ-ДД."
            })

    employees = q.all()

    for emp in employees:
        inc_check(db, emp.id)
    db.commit()

    emp_ids = [e.id for e in employees]

    counts = {}
    if emp_ids:
        rows = db.execute(
            text("""
                SELECT id, checks_count, likes_count, dislikes_count
                FROM employee
                WHERE id = ANY(:ids)
            """),
            {"ids": emp_ids}
        ).fetchall()
        counts = {row[0]: {"checks": row[1], "likes": row[2], "dislikes": row[3]} for row in rows}

    my_reactions = {}
    if emp_ids:
        rows = db.execute(
            text("""
                SELECT employee_id, reaction
                FROM employee_reaction
                WHERE employer_id = :u AND employee_id = ANY(:ids)
            """),
            {"u": current_user.id, "ids": emp_ids}
        ).fetchall()
        my_reactions = {row[0]: row[1] for row in rows}

    result = []
    for emp in employees:
        records = db.query(ReputationRecord).filter(ReputationRecord.employee_id == emp.id).all()
        prepared_records = []
        for record in records:
            employer = db.get(User, record.employer_id)
            if employer and employer.is_blocked:
                prepared_records.append({
                    "is_blocked_employer": True,
                    "blocked_message": "Предприниматель заблокирован, отзыв неактуален."
                })
            else:
                prepared_records.append({
                    "is_blocked_employer": False,
                    "employer_id": record.employer_id,
                    "position": record.position,
                    "hired_at": record.hired_at,
                    "fired_at": record.fired_at,
                    "misconduct": record.misconduct,
                    "dismissal_reason": record.dismissal_reason,
                    "commendation": record.commendation,
                })

        c = counts.get(emp.id, {"checks": getattr(emp, "checks_count", 0),
                                "likes": getattr(emp, "likes_count", 0),
                                "dislikes": getattr(emp, "dislikes_count", 0)})

        result.append({
            "employee_id": emp.id,
            "full_name": emp.full_name,
            "birth_date": emp.birth_date,
            "records": prepared_records,
            "record_count": len(prepared_records),
            "checks_count": c["checks"],
            "likes_count": c["likes"],
            "dislikes_count": c["dislikes"],
            "my_reaction": my_reactions.get(emp.id),
        })

    return templates.TemplateResponse("check.html", {
        "request": request,
        "result": result,
        "user": current_user
    })
