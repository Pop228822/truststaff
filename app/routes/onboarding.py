import os
import shutil
import requests
from fastapi import APIRouter, Request, Form, File, UploadFile, Depends
from starlette.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_session
from app.models import User
from app.auth import get_session_user

templates = Jinja2Templates(directory="templates")

router = APIRouter()

# Telegram настройки
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

import uuid

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


def send_telegram_notification(user: User, company_name: str, city: str, inn_or_ogrn: str):
    """Отправка уведомления в Telegram о новой заявке на верификацию"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    from datetime import datetime
    
    text = (
        f"🔔 Новая заявка на верификацию!\n\n"
        f"👤 Пользователь: {user.name} (ID: {user.id})\n"
        f"📧 Email: {user.email}\n"
        f"🏢 Компания: {company_name}\n"
        f"🏙️ Город: {city}\n"
        f"📋 ИНН/ОГРН: {inn_or_ogrn}\n"
        f"📄 Документ: {user.passport_filename}\n\n"
        f"⏰ Время подачи: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text}
        )
    except Exception as e:
        print(f"Ошибка отправки уведомления в Telegram: {e}")


def generate_safe_filename(original_filename: str, user_id: int) -> str:
    """
    Генерируем название вида "passport_<user_id>_<UUID>.<ext>"
    (если расширение разрешено, иначе без него).
    """
    # Извлекаем расширение
    _, ext = os.path.splitext(original_filename)
    ext = ext.lower().lstrip(".")  # убираем точку

    # Генерируем UUID
    new_name = f"passport_{user_id}_{uuid.uuid4().hex}"

    # Если расширение разрешено — добавим
    if ext in ALLOWED_EXTENSIONS:
        return f"{new_name}.{ext}"
    else:
        return new_name

@router.get("/onboarding", response_class=HTMLResponse)
def onboarding_form(
    request: Request,
    current_user: User = Depends(get_session_user)
):
    if not current_user:
        return RedirectResponse("/login", status_code=302)

    if current_user.is_blocked:
        response = RedirectResponse("/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    if current_user.verification_status == "approved":
        return RedirectResponse("/", status_code=302)

    if current_user.verification_status == "pending":
        return templates.TemplateResponse("onboarding_pending.html", {
            "request": request,
            "user": current_user
        })

    # Иначе показываем саму форму
    return templates.TemplateResponse("onboarding.html", {
        "request": request,
        "user": current_user
    })

@router.post("/onboarding")
def submit_onboarding(
        request: Request,
        company_name: str = Form(...),
        city: str = Form(...),
        inn_or_ogrn: str = Form(...),
        passport_file: UploadFile = File(...),
        db: Session = Depends(get_session),
        current_user: User = Depends(get_session_user)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if user.verification_status == "pending":
        return templates.TemplateResponse("onboarding_pending.html", {
            "request": request,
            "user": user,
            "message": "Ваша заявка уже на рассмотрении. Повторно отправлять не нужно."
        })

    if user.verification_status == "approved":
        return RedirectResponse("/", status_code=302)

    _, ext = os.path.splitext(passport_file.filename)
    ext = ext.lower().lstrip(".")

    if ext not in ALLOWED_EXTENSIONS:
        return templates.TemplateResponse("onboarding.html", {
            "request": request,
            "user": current_user,
            "error_message": f"Недопустимый формат файла: .{ext}. "
                             f"Разрешено: {', '.join(ALLOWED_EXTENSIONS)}."
        })

    MAX_MB = 20
    MAX_SIZE = MAX_MB * 1024 * 1024

    # Определяем размер
    passport_file.file.seek(0, 2)  # Перемещаем указатель в конец файла
    file_size = passport_file.file.tell()  # Считываем позицию (размер)
    passport_file.file.seek(0)  # Возвращаемся в начало файла

    if file_size > MAX_SIZE:
        # Превышен лимит — возвращаем шаблон или выбрасываем ошибку
        return templates.TemplateResponse("onboarding.html", {
            "request": request,
            "user": current_user,
            "error_message": f"Файл превышает {MAX_MB} МБ. Попробуйте другой документ."
        })

    # Можно добавить «безопасное» имя вместо простого:
    filename = generate_safe_filename(passport_file.filename, current_user.id)
    # Или используем генерацию безопасного имени (см. ниже)

    filepath = os.path.join("static", "uploads", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(passport_file.file, buffer)

    user.company_name = company_name
    user.city = city
    user.inn_or_ogrn = inn_or_ogrn
    user.passport_filename = filename
    user.verification_status = "pending"
    user.rejection_reason = None
    db.commit()

    # Отправляем уведомление в Telegram
    send_telegram_notification(user, company_name, city, inn_or_ogrn)

    return templates.TemplateResponse("onboarding_submitted.html", {"request": request})
