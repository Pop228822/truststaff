from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.models import LoginAttempt

MAX_ATTEMPTS = 10
BLOCK_WINDOW_MINUTES = 60

def log_login_attempt(db: Session, email: str, ip_address: str, success: bool):
    attempt = LoginAttempt(
        email=email,
        ip_address=ip_address,
        success=success,
        attempt_time=datetime.utcnow()
    )
    db.add(attempt)
    db.commit()

def is_brute_force(db: Session, email: str, ip_address: str) -> bool:
    time_threshold = datetime.utcnow() - timedelta(minutes=BLOCK_WINDOW_MINUTES)

    statement = select(LoginAttempt).where(
        LoginAttempt.attempt_time >= time_threshold,
        LoginAttempt.success == False,
        ((LoginAttempt.email == email) | (LoginAttempt.ip_address == ip_address))
    )
    recent_failures = db.exec(statement).all()

    return len(recent_failures) >= MAX_ATTEMPTS
