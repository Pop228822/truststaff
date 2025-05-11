from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas import UserCreate, UserLogin
from app.models import User
from app.database import get_session
from app.auth import hash_password, verify_password, create_access_token

router = APIRouter()

@router.post("/register")
def register(user: UserCreate, session: Session = Depends(get_session)):
    existing = session.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(
        name=user.name,
        email=user.email,
        password_hash=hash_password(user.password)
    )
    session.add(new_user)
    session.commit()
    return {"msg": "registered"}

@router.post("/login")
def login(user: UserLogin, session: Session = Depends(get_session)):
    db_user = session.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(db_user.id)})
    return {"access_token": token, "token_type": "bearer"}
