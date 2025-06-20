# routers/api_2fa.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
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