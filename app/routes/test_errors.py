"""
Тестовые роуты для проверки системы уведомлений об ошибках
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import User
from app.auth import get_current_user_safe

router = APIRouter()


@router.get("/test/error/500")
def test_500_error():
    """Тестовая 500 ошибка"""
    raise Exception("Тестовая 500 ошибка для проверки уведомлений в Telegram")


@router.get("/test/error/division")
def test_division_error():
    """Тестовая ошибка деления на ноль"""
    result = 1 / 0  # Это вызовет ZeroDivisionError
    return {"result": result}


@router.get("/test/error/attribute")
def test_attribute_error():
    """Тестовая AttributeError"""
    user = User()
    return user.nonexistent_attribute  # Это вызовет AttributeError


@router.get("/test/error/http")
def test_http_error():
    """Тестовая HTTP ошибка (не должна отправлять уведомление)"""
    raise HTTPException(status_code=400, detail="Тестовая HTTP ошибка")


@router.get("/test/error/database")
def test_database_error(db: Session = Depends(get_session)):
    """Тестовая ошибка базы данных"""
    # Попытка выполнить некорректный запрос
    db.execute("SELECT * FROM nonexistent_table")


@router.get("/test/error/with-user")
def test_error_with_user(current_user: User = Depends(get_current_user_safe)):
    """Тестовая ошибка с авторизованным пользователем"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    
    raise Exception(f"Тестовая ошибка для пользователя {current_user.name}")


@router.post("/test/error/post")
def test_post_error(request: Request):
    """Тестовая ошибка в POST запросе"""
    raise Exception("Тестовая ошибка в POST запросе")


@router.get("/test/notification/ok")
def test_notification_ok():
    """Тестовый роут без ошибок"""
    return {"status": "ok", "message": "Система уведомлений работает корректно"}
