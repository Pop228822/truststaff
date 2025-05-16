from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
import requests
import os
from datetime import date
from collections import defaultdict

from starlette.templating import Jinja2Templates

from app.auth import get_current_user
from app.models import User


router = APIRouter()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

templates = Jinja2Templates(directory="templates")
# Хранилище лимитов (только для примера, после перезапуска обнуляется)
feedback_limits = defaultdict(lambda: {"date": None, "count": 0})


@router.post("/feedback")
async def feedback(
    request: Request,
    message: str = Form(...),
    contact: str = Form(""),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        # Неавторизованные пользователи не могут оставлять отзывы
        raise HTTPException(status_code=401, detail="Необходима авторизация")

    user_id = current_user.id
    today = date.today()

    # Достаем из feedback_limits для данного user_id
    user_limit = feedback_limits[user_id]

    # Если дата в записи не совпадает с сегодняшней — обнуляем
    if user_limit["date"] != today:
        user_limit["date"] = today
        user_limit["count"] = 0

    # Если count уже 3, блокируем
    if user_limit["count"] >= 3:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "feedback_error": "Вы исчерпали лимит отзывов на сегодня."
            }
        )

    # Иначе увеличиваем счётчик и отправляем отзыв
    user_limit["count"] += 1

    text = (
        f"📝 Новый отзыв от user_id={user_id}:\n\n{message.strip()}\n\n"
        f"Контакт: {contact.strip() or 'не указан'}"
    )

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text}
        )

    return RedirectResponse("/", status_code=302)
