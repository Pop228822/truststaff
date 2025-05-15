from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import get_session
from app.models import PendingUser
import logging

def cleanup_pending_users():
    # Берём сессию из общего pool-а или открываем сами
    with get_session() as session:
        cutoff = datetime.utcnow() - timedelta(days=1)
        deleted_count = session.query(PendingUser).filter(
            PendingUser.created_at < cutoff
        ).delete()
        session.commit()

        logging.info(f"Удалено {deleted_count} незавершённых регистраций старше суток")
