from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models import PendingUser
import logging


def cleanup_pending_users():
    session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        deleted_count = session.query(PendingUser).filter(
            PendingUser.created_at < cutoff
        ).delete(synchronize_session=False)
        session.commit()
        msg = f"Удалено {deleted_count} PendingUser старше 30 минут (до {cutoff.isoformat()}Z)"
        logging.info(msg)
        print(msg)
    finally:
        session.close()


if __name__ == "__main__":
    cleanup_pending_users()