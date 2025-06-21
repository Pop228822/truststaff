import os

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.auth import verify_password, get_session
from datetime import datetime, timedelta
from random import randint

from app.email_utils import send_2fa_code
from app.models import User

router = APIRouter(prefix="/api/auth")

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
def api_login(data: LoginRequest, db: Session = Depends(get_session)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")

    if user.is_blocked:
        raise HTTPException(status_code=403, detail="blocked")

    if not user.is_email_verified:
        raise HTTPException(status_code=403, detail="email_not_verified")

    # 🟡 Если 2FA ещё не был запрошен или истёк — генерируем и отправляем
    if not user.twofa_code or not user.twofa_expires_at or user.twofa_expires_at < datetime.utcnow():
        code = str(randint(100000, 999999))
        user.twofa_code = code
        user.twofa_expires_at = datetime.utcnow() + timedelta(minutes=5)
        db.commit()
        send_2fa_code(user.email, code)

    raise HTTPException(status_code=403, detail="2fa_required")


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_api_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_session)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="invalid_token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.is_blocked:
        raise HTTPException(status_code=401, detail="user_not_found_or_blocked")

    return user

def only_approved_api_user(
    current_user: User = Depends(get_api_user)
) -> User:
    if current_user.verification_status != "approved":
        raise HTTPException(status_code=403, detail="account_not_verified")

    if current_user.is_blocked:
        raise HTTPException(status_code=403, detail="account_blocked")

    return current_user
