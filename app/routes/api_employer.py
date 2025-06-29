from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session
import os
import shutil

from app.models import User
from app.routes.api_auth import get_api_user, get_session
from app.routes.onboarding import ALLOWED_EXTENSIONS, generate_safe_filename

router = APIRouter(prefix="/api/employer")

PASSPORT_UPLOAD_DIR = "media/passports"
os.makedirs(PASSPORT_UPLOAD_DIR, exist_ok=True)

@router.post("/submit-verification")
async def submit_verification_api(
    company_name: str = Form(...),
    city: str = Form(...),
    inn_or_ogrn: str = Form(...),
    passport_file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_api_user)
):
    # Проверка верификации
    if current_user.verification_status == "pending":
        return JSONResponse(status_code=400, content={"error": "Заявка уже на рассмотрении"})

    if current_user.verification_status == "approved":
        return JSONResponse(status_code=400, content={"error": "Вы уже верифицированы"})

    # Проверка формата файла
    _, ext = os.path.splitext(passport_file.filename)
    ext = ext.lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(status_code=400, content={"error": f"Недопустимый формат .{ext}"})

    # Проверка размера
    MAX_MB = 10
    MAX_SIZE = MAX_MB * 1024 * 1024
    passport_file.file.seek(0, 2)
    size = passport_file.file.tell()
    passport_file.file.seek(0)
    if size > MAX_SIZE:
        return JSONResponse(status_code=400, content={"error": "Файл больше 10 МБ"})

    # Сохраняем
    filename = generate_safe_filename(passport_file.filename, current_user.id)
    filepath = os.path.join("static", "uploads", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(passport_file.file, f)

    # Обновляем пользователя
    current_user.company_name = company_name
    current_user.city = city
    current_user.inn_or_ogrn = inn_or_ogrn
    current_user.passport_filename = filename
    current_user.verification_status = "pending"
    current_user.rejection_reason = None
    db.commit()

    return JSONResponse(status_code=200, content={"message": "Заявка отправлена"})