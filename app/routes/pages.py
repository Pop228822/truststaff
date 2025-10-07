from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth import optional_user
from app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def root(
    request: Request,
    user: Optional[User] = Depends(optional_user)
):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "verification_status": user.verification_status if user else None,
        "rejection_reason": user.rejection_reason if user else None
    })


@router.get("/policy", response_class=HTMLResponse)
def policy(request: Request):
    return templates.TemplateResponse("policy.html", {"request": request})


@router.get("/terms", response_class=HTMLResponse)
def terms(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})
