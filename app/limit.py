from fastapi import FastAPI, Request, HTTPException, status, Depends
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import get_session
from app.models import RateLimit

MAX_REQUESTS_PER_MINUTE = 100

async def rate_limit_100_per_minute(
        request: Request,
        db: Session = Depends(get_session),
):
    client_ip = request.client.host
    now = datetime.utcnow()

    record = db.query(RateLimit).filter(RateLimit.ip_address == client_ip).first()
    if not record:
        # Если записи нет, создаём
        record = RateLimit(ip_address=client_ip, request_count=1, window_start=now)
        db.add(record)
        db.commit()
        return  # Запрос пропускаем, т.к. это 1-й запрос в новом окне

    # Проверяем, не старше ли "окно" 1 минуты
    # Если "now" - window_start >= 60 секунд, начинаем заново
    elapsed = now - record.window_start
    if elapsed.total_seconds() >= 60:
        # Окно истекло, сбрасываем счётчик
        record.request_count = 1
        record.window_start = now
        db.commit()
        return

    # Иначе "окно" ещё активно
    if record.request_count >= MAX_REQUESTS_PER_MINUTE:
        # Превышен лимит
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Превышено 100 запросов в минуту"
        )

    # Увеличиваем счётчик
    record.request_count += 1
    db.commit()
