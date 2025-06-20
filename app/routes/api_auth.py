from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.auth import verify_password, get_session, create_access_token
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