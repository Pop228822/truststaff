from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import date
from collections import defaultdict
import requests
import os

from app.routes.api_auth import get_api_user
from app.models import User

router = APIRouter(prefix="/api")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

feedback_limits = defaultdict(lambda: {"date": None, "count": 0})

class FeedbackRequest(BaseModel):
    message: str
    contact: str = ""

@router.post("/feedback")
def submit_feedback(data: FeedbackRequest, current_user: User = Depends(get_api_user)):
    user_id = current_user.id
    today = date.today()

    user_limit = feedback_limits[user_id]
    if user_limit["date"] != today:
        user_limit["date"] = today
        user_limit["count"] = 0

    if user_limit["count"] >= 3:
        raise HTTPException(status_code=429, detail="Лимит отзывов на сегодня исчерпан.")

    user_limit["count"] += 1

    text = (
        f"📝 Новый отзыв от user_id={user_id}:\n\n{data.message.strip()}\n\n"
        f"Контакт: {data.contact.strip() or 'не указан'}"
    )

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text}
        )

    return {"status": "ok"}
