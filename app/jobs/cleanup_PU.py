from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.database import get_session
from app.models import PendingUser
import logging

def cleanup_pending_users():
    session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        deleted_count = session.query(PendingUser).filter(
            PendingUser.created_at < cutoff
        ).delete()
        session.commit()
        logging.info(f"Удалено {deleted_count} незавершённых регистраций старше суток")
    finally:
        session.close()
