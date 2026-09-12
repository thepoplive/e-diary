from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..database import get_db
from ..helpers import ATTENDANCE_LABELS, DAYS_RU, GRADE_LABELS, fmt_date
from .. import models
from ..routers.school import main_context, today_rows, week_rows
from ..templating import render

router = APIRouter(prefix="/parent", tags=["parent"])

require_parent = require_roles("parent")


@router.get("")
def main(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_parent)):
    ctx = main_context(db, user)
    return render(
        "parent/main.html",
        {"request": request, "user": user, "active": "main", **ctx},
    )


@router.get("/bells")
def bells_page(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_parent)):
    bells = db.query(models.BellSchedule).order_by(models.BellSchedule.lesson_number).all()
    return render(
        "parent/bells.html",
        {"request": request, "user": user, "bells": bells, "active": "bells"},
    )


@router.get("/today")
def today(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_parent)):
    ctx = main_context(db, user)
    rows = today_rows(db, ctx["child"])
    return render(
        "parent/today.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
            "attendance_labels": ATTENDANCE_LABELS,
            "grade_labels": GRADE_LABELS,
            "active": "today",
            **ctx,
        },
    )


@router.get("/week")
def week(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_parent)):
    ctx = main_context(db, user)
    if ctx["child"] and ctx["child"].group_id:
        days = week_rows(db, ctx["child"], date.today())
    else:
        days = []
    return render(
        "parent/week.html",
        {"request": request, "user": user, "days": days, "days_ru": DAYS_RU, "active": "week", **ctx},
    )


@router.get("/grades")
def grades(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_parent), day: str = ""):
    ctx = main_context(db, user)
    ref = None
    if day:
        try:
            ref = date.fromisoformat(day)
        except ValueError:
            ref = None
    if ref is None:
        ref = date.today()
    days_rows = week_rows(db, ctx["child"], ref) if ctx["child"] and ctx["child"].group_id else []
    return render(
        "parent/grades.html",
        {
            "request": request,
            "user": user,
            "days": days_rows,
            "ref": ref,
            "fmt_date": fmt_date,
            "attendance_labels": ATTENDANCE_LABELS,
            "days_ru": DAYS_RU,
            "active": "grades",
            **ctx,
        },
    )