from typing import List

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import create_token, get_current_user, verify_password
from ..config import TOKEN_COOKIE
from ..database import get_db
from .. import models
from ..templating import render

router = APIRouter()


def home_url(user: models.User) -> str:
    if user.role == "admin":
        return "/setup/bells" if not user.setup_done else "/admin"
    return f"/{user.role}"


@router.get("/")
def root(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(TOKEN_COOKIE)
    user = None
    if token:
        user = get_current_user(request, db)
    if user:
        return RedirectResponse(home_url(user), status_code=302)
    return RedirectResponse("/login", status_code=302)


@router.get("/login")
def login_page(request: Request):
    return render("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    login: str = Form(...),
    password: str = Form(...),
):
    user = db.query(models.User).filter(models.User.login == login.strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return render(
            "login.html",
            {"request": request, "error": "РќРµРІРµСЂРЅС‹Р№ Р»РѕРіРёРЅ РёР»Рё РїР°СЂРѕР»СЊ"},
            status_code=401,
        )
    token = create_token(user.id)
    response = RedirectResponse(home_url(user), status_code=302)
    response.set_cookie(TOKEN_COOKIE, token, httponly=True, max_age=60 * 60 * 24 * 14, samesite="lax")
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(TOKEN_COOKIE)
    return response


# ---- РџРµСЂРІРёС‡РЅР°СЏ РЅР°СЃС‚СЂРѕР№РєР° СЂР°СЃРїРёСЃР°РЅРёСЏ Р·РІРѕРЅРєРѕРІ (РїРµСЂРІС‹Р№ РІС…РѕРґ РіР»Р°РІРЅРѕРіРѕ Р°РґРјРёРЅР°) ----

def _redirect_if_setup_done(user: models.User):
    if user.setup_done:
        return RedirectResponse("/admin", status_code=302)
    return None


@router.get("/setup/bells")
def setup_bells(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(status_code=403)
    if user.setup_done:
        return RedirectResponse("/admin", status_code=302)
    bells = (
        db.query(models.BellSchedule)
        .order_by(models.BellSchedule.lesson_number)
        .all()
    )
    return render(
        "admin/setup_bells.html",
        {"request": request, "user": user, "bells": bells},
    )


@router.post("/setup/bells")
def setup_bells_submit(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
    lesson_number: List[int] = Form(default=[]),
    start_time: List[str] = Form(default=[]),
    end_time: List[str] = Form(default=[]),
):
    if user.role != "admin":
        raise HTTPException(status_code=403)
    db.query(models.BellSchedule).delete()
    pairs = []
    for num, start, end in zip(lesson_number, start_time, end_time):
        try:
            num = int(num)
        except (TypeError, ValueError):
            continue
        start = (start or "").strip()
        end = (end or "").strip()
        if start and end:
            pairs.append((num, start, end))
    pairs.sort(key=lambda x: x[0])
    for num, start, end in pairs:
        db.add(models.BellSchedule(lesson_number=num, start_time=start, end_time=end))
    user.setup_done = True
    db.commit()
    return RedirectResponse("/admin", status_code=302)