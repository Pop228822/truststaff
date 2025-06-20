from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.auth import verify_password, get_session, create_access_token
from datetime import datetime, timedelta
from random import randint

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

    if user.twofa_code:
        raise HTTPException(status_code=403, detail="2fa_required")

    token = create_access_token(user.id)
    return {"access_token": token}