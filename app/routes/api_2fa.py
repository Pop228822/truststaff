# routers/api_2fa.py
from random import randint

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.email_utils import send_2fa_code
from app.models import User
from app.auth import get_session, create_access_token

router = APIRouter(prefix="/api/auth")

class TwoFactorRequest(BaseModel):
    email: str
    code: str

@router.post("/verify-2fa")
def verify_2fa_api(data: TwoFactorRequest, db: Session = Depends(get_session)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    if user.twofa_code != data.code:
        raise HTTPException(status_code=401, detail="invalid_code")

    if user.twofa_expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="code_expired")

    user.twofa_code = None
    user.twofa_expires_at = None
    db.commit()

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token}

class EmailRequest(BaseModel):
    email: str

@router.post("/resend-2fa")
def resend_2fa(data: EmailRequest, db: Session = Depends(get_session)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    if not user.is_email_verified or user.is_blocked:
        raise HTTPException(status_code=403, detail="not_allowed")

    code = str(randint(100000, 999999))
    user.twofa_code = code
    user.twofa_expires_at = datetime.utcnow() + timedelta(minutes=5)
    db.commit()
    send_2fa_code(user.email, code)

    return {"status": "resent"}