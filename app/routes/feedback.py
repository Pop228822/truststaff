from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
import requests
import os

from dotenv import load_dotenv
load_dotenv()

router = APIRouter()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


@router.post("/feedback")
async def feedback(
        request: Request,
        message: str = Form(...),
        contact: str = Form("")
):
    text = f"📝 Новый отзыв с сайта:\n\n{message.strip()}\n\nКонтакт: {contact.strip() or 'не указан'}"

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text}
        )

    return RedirectResponse("/", status_code=302)
