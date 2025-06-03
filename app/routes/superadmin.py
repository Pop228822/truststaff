from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_session
from app.models import User  # В модели User предполагается поле "is_blocked"
from app.models import Employee  # Если нужно для расширенных методов

router = APIRouter()

def ensure_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """Проверяем, что пользователь – SUPERADMIN."""
    if current_user is None or current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещён, необходима роль superadmin."
        )
    return current_user

@router.post("/superadmin/block/{user_id}")
def block_user(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(ensure_superadmin)
):
    """
    Блокируем пользователя (is_blocked = True).
    Заблокированный пользователь не сможет авторизоваться
    и не сможет совершать действия в своём аккаунте.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Самого супер-админа блокировать нельзя
    if user.role == "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Нельзя блокировать другого супер-админа."
        )

    user.is_blocked = True
    db.commit()

    # После блокировки перенаправляем на список пользователей
    return RedirectResponse("/admin/users/list", status_code=302)

@router.post("/superadmin/unblock/{user_id}")
def unblock_user(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(ensure_superadmin)
):
    """
    Разблокируем пользователя (is_blocked = False).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.is_blocked = False
    db.commit()

    return RedirectResponse("/admin/users/list", status_code=302)
