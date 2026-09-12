from datetime import date, datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..database import get_db
from ..helpers import (
    ATTENDANCE_LABELS,
    DAYS_RU,
    GRADE_LABELS,
    count_student_stats,
    get_or_create_lesson,
    get_user_notifications,
    teacher_entries_on_day,
    week_start,
)
from .. import models
from ..models import get_or_create_settings
from ..templating import render

router = APIRouter(prefix="/teacher", tags=["teacher"])

require_teacher = require_roles("teacher")


def _own_lesson(db: Session, teacher: models.User, lesson_id: int) -> models.Lesson:
    lesson = db.query(models.Lesson).filter(models.Lesson.id == lesson_id).first()
    if not lesson or lesson.schedule_entry.teacher_id != teacher.id:
        raise HTTPException(status_code=404)
    return lesson


def _today_count(db: Session, teacher: models.User) -> int:
    return len(teacher_entries_on_day(db, teacher, date.today()))


def _lesson_rows(db: Session, lesson: models.Lesson):
    """РЎС‚СѓРґРµРЅС‚С‹ РіСЂСѓРїРїС‹ + РёС… С‚РµРєСѓС‰РёРµ РїРѕСЃРµС‰Р°РµРјРѕСЃС‚СЊ Рё РѕС†РµРЅРєР°."""
    students = (
        db.query(models.User)
        .filter(models.User.role == "student", models.User.group_id == lesson.schedule_entry.group_id)
        .order_by(models.User.full_name)
        .all()
    )
    rows = []
    for s in students:
        att = (
            db.query(models.Attendance)
            .filter(models.Attendance.lesson_id == lesson.id, models.Attendance.student_id == s.id)
            .first()
        )
        grade = (
            db.query(models.Grade)
            .filter(models.Grade.lesson_id == lesson.id, models.Grade.student_id == s.id)
            .first()
        )
        rows.append({"student": s, "attendance": att, "grade": grade})
    return rows


# ---------------------------------------------------------------- Р“Р»Р°РІРЅР°СЏ
@router.get("")
def main(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_teacher)):
    notifications = get_user_notifications(db, user)
    return render(
        "teacher/main.html",
        {
            "request": request,
            "user": user,
            "today_count": _today_count(db, user),
            "notifications": notifications,
            "active": "main",
        },
    )


# ---------------------------------------------------------------- РЈСЂРѕРєРё РЅР° СЃРµРіРѕРґРЅСЏ
@router.get("/today")
def today(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_teacher)):
    today = date.today()
    entries = teacher_entries_on_day(db, user, today)
    lessons = []
    for e in entries:
        lesson = get_or_create_lesson(db, e, today)
        lessons.append(lesson)
    db.commit()
    return render(
        "teacher/today.html",
        {"request": request, "user": user, "lessons": lessons, "today": today, "days_ru": DAYS_RU, "active": "today"},
    )


# ---------------------------------------------------------------- РЈСЂРѕРє (РѕС†РµРЅРєРё/РїРѕСЃРµС‰Р°РµРјРѕСЃС‚СЊ)
@router.get("/lesson/{lesson_id}")
def lesson_detail(
    request: Request,
    lesson_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_teacher),
):
    lesson = _own_lesson(db, user, lesson_id)
    rows = _lesson_rows(db, lesson)
    return render(
        "teacher/lesson_detail.html",
        {
            "request": request,
            "user": user,
            "lesson": lesson,
            "rows": rows,
            "attendance_labels": ATTENDANCE_LABELS,
            "grade_labels": GRADE_LABELS,
            "today": date.today(),
            "active": "today",
            "mode": "today",
        },
    )


@router.post("/lesson/{lesson_id}")
def lesson_save(
    request: Request,
    lesson_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_teacher),
    student_ids: List[int] = Form(...),
    attendance: List[str] = Form(default=[]),
    grades: List[str] = Form(default=[]),
    comments: List[str] = Form(default=[]),
):
    lesson = _own_lesson(db, user, lesson_id)
    for i, sid in enumerate(student_ids):
        att = attendance[i] if i < len(attendance) else ""
        grd = grades[i] if i < len(grades) else ""
        cmt = (comments[i] if i < len(comments) else "").strip()
        if att:
            rec = (
                db.query(models.Attendance)
                .filter(models.Attendance.lesson_id == lesson.id, models.Attendance.student_id == sid)
                .first()
            )
            if rec:
                rec.status = att
                rec.comment = cmt
                rec.changed_by = user.id
            else:
                db.add(
                    models.Attendance(
                        lesson_id=lesson.id,
                        student_id=sid,
                        status=att,
                        comment=cmt,
                        changed_by=user.id,
                    )
                )
        if grd:
            rec = (
                db.query(models.Grade)
                .filter(models.Grade.lesson_id == lesson.id, models.Grade.student_id == sid)
                .first()
            )
            if rec:
                rec.value = grd
                rec.comment = cmt
                rec.teacher_id = user.id
            else:
                db.add(
                    models.Grade(
                        lesson_id=lesson.id,
                        student_id=sid,
                        value=grd,
                        comment=cmt,
                        teacher_id=user.id,
                    )
                )
    db.commit()
    return RedirectResponse(f"/teacher/lesson/{lesson_id}", status_code=303)


# ---------------------------------------------------------------- Р Р°СЃРїРёСЃР°РЅРёРµ РЅР° РЅРµРґРµР»СЋ
@router.get("/week")
def week(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_teacher)):
    start = week_start(date.today())
    schedule = {}
    for i in range(7):
        d = start + timedelta(days=i)
        schedule[d] = {"day": d, "entries": teacher_entries_on_day(db, user, d)}

    all_schedule = None
    if user.all_groups_access:
        all_schedule = {}
        for i in range(7):
            d = start + timedelta(days=i)
            groups = db.query(models.Group).order_by(models.Group.name).all()
            rows = []
            for g in groups:
                entries = (
                    db.query(models.ScheduleEntry)
                    .filter(
                        models.ScheduleEntry.day_of_week == d.weekday(),
                        models.ScheduleEntry.group_id == g.id,
                    )
                    .order_by(models.ScheduleEntry.lesson_number)
                    .all()
                )
                if entries:
                    rows.append({"group": g, "entries": entries})
            all_schedule[d] = rows

    return render(
        "teacher/week.html",
        {
            "request": request,
            "user": user,
            "schedule": schedule,
            "all_schedule": all_schedule,
            "days_ru": DAYS_RU,
            "active": "week",
        },
    )


# ---------------------------------------------------------------- Р Р°СЃРїРёСЃР°РЅРёРµ Р·РІРѕРЅРєРѕРІ
@router.get("/bells")
def bells_page(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_teacher)):
    bells = db.query(models.BellSchedule).order_by(models.BellSchedule.lesson_number).all()
    return render(
        "teacher/bells.html",
        {"request": request, "user": user, "bells": bells, "active": "bells"},
    )


# ---------------------------------------------------------------- РњРѕРё СѓС‡РµРЅРёРєРё
@router.get("/students")
def students_page(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_teacher)):
    if user.group_id:
        students = (
            db.query(models.User)
            .filter(models.User.role == "student", models.User.group_id == user.group_id)
            .order_by(models.User.full_name)
            .all()
        )
    else:
        students = []
    rows = []
    for s in students:
        stats = count_student_stats(db, s)
        rows.append({"student": s, "stats": stats})
    return render(
        "teacher/students.html",
        {"request": request, "user": user, "rows": rows, "active": "students"},
    )


# ---------------------------------------------------------------- Р РѕРґРёС‚РµР»Рё
@router.get("/parents")
def parents_page(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_teacher)):
    group_student_ids = []
    if user.group_id:
        group_student_ids = [
            u.id
            for u in db.query(models.User)
            .filter(models.User.role == "student", models.User.group_id == user.group_id)
            .all()
        ]
    if group_student_ids:
        parents = (
            db.query(models.User)
            .filter(models.User.role == "parent", models.User.child_id.in_(group_student_ids))
            .order_by(models.User.full_name)
            .all()
        )
    else:
        parents = []
    return render(
        "teacher/parents.html",
        {"request": request, "user": user, "parents": parents, "active": "parents"},
    )


# ---------------------------------------------------------------- РР·РјРµРЅРёС‚СЊ РѕС†РµРЅРєСѓ
@router.get("/edit_grades")
def edit_grades_page(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_teacher),
    day: str = "",
):
    selected = None
    lesson_list = []
    if day:
        try:
            selected = date.fromisoformat(day)
        except ValueError:
            selected = None
    if selected:
        for e in teacher_entries_on_day(db, user, selected):
            lesson_list.append(get_or_create_lesson(db, e, selected))
        db.commit()
    bells = db.query(models.BellSchedule).order_by(models.BellSchedule.lesson_number).all()
    return render(
        "teacher/edit_grades.html",
        {
            "request": request,
            "user": user,
            "selected": selected,
            "lessons": lesson_list,
            "bells": bells,
            "active": "edit_grades",
        },
    )


@router.get("/edit_grades/lesson/{lesson_id}")
def edit_grades_lesson(
    request: Request,
    lesson_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_teacher),
):
    lesson = _own_lesson(db, user, lesson_id)
    rows = _lesson_rows(db, lesson)
    settings = get_or_create_settings(db)
    age = (date.today() - lesson.date).days
    can_edit = age <= settings.grade_edit_days
    can_request = age <= settings.grade_edit_days + settings.grade_admin_edit_days
    return render(
        "teacher/lesson_edit.html",
        {
            "request": request,
            "user": user,
            "lesson": lesson,
            "rows": rows,
            "attendance_labels": ATTENDANCE_LABELS,
            "grade_labels": GRADE_LABELS,
            "age": age,
            "can_edit": can_edit,
            "can_request": can_request,
            "settings": settings,
            "active": "edit_grades",
        },
    )


@router.post("/edit_grades/lesson/{lesson_id}")
def edit_grades_lesson_save(
    request: Request,
    lesson_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_teacher),
    student_ids: List[int] = Form(...),
    attendance: List[str] = Form(default=[]),
    grades: List[str] = Form(default=[]),
    comments: List[str] = Form(default=[]),
):
    lesson = _own_lesson(db, user, lesson_id)
    settings = get_or_create_settings(db)
    age = (date.today() - lesson.date).days
    can_edit = age <= settings.grade_edit_days
    can_request = age <= settings.grade_edit_days + settings.grade_admin_edit_days
    messages = []

    for i, sid in enumerate(student_ids):
        att = attendance[i] if i < len(attendance) else ""
        grd = grades[i] if i < len(grades) else ""
        cmt = (comments[i] if i < len(comments) else "").strip()

        if att:
            if not cmt:
                messages.append("Р”Р»СЏ РёР·РјРµРЅРµРЅРёСЏ РїРѕСЃРµС‰Р°РµРјРѕСЃС‚Рё РЅСѓР¶РµРЅ РєРѕРјРјРµРЅС‚Р°СЂРёР№")
                continue
            rec = (
                db.query(models.Attendance)
                .filter(models.Attendance.lesson_id == lesson.id, models.Attendance.student_id == sid)
                .first()
            )
            if rec:
                rec.status = att
                rec.comment = cmt
                rec.changed_by = user.id
            else:
                db.add(
                    models.Attendance(
                        lesson_id=lesson.id,
                        student_id=sid,
                        status=att,
                        comment=cmt,
                        changed_by=user.id,
                    )
                )
            messages.append("РџРѕСЃРµС‰Р°РµРјРѕСЃС‚СЊ РѕР±РЅРѕРІР»РµРЅР°")

        if grd:
            if not cmt:
                messages.append("Р”Р»СЏ РёР·РјРµРЅРµРЅРёСЏ РѕС†РµРЅРєРё РЅСѓР¶РµРЅ РєРѕРјРјРµРЅС‚Р°СЂРёР№")
                continue
            rec = (
                db.query(models.Grade)
                .filter(models.Grade.lesson_id == lesson.id, models.Grade.student_id == sid)
                .first()
            )
            if rec and rec.value == grd:
                messages.append("РћС†РµРЅРєР° РЅРµ РёР·РјРµРЅРёР»Р°СЃСЊ")
                continue
            if not rec:
                db.add(
                    models.Grade(
                        lesson_id=lesson.id,
                        student_id=sid,
                        value=grd,
                        comment=cmt,
                        teacher_id=user.id,
                    )
                )
                messages.append("РћС†РµРЅРєР° РґРѕР±Р°РІР»РµРЅР°")
            elif can_edit:
                rec.value = grd
                rec.comment = cmt
                rec.teacher_id = user.id
                messages.append("РћС†РµРЅРєР° РёР·РјРµРЅРµРЅР°")
            elif can_request:
                db.add(
                    models.GradeChangeRequest(
                        grade_id=rec.id,
                        student_id=sid,
                        lesson_id=lesson.id,
                        old_value=rec.value,
                        new_value=grd,
                        comment=cmt,
                        teacher_id=user.id,
                    )
                )
                messages.append("РћС†РµРЅРєР° РѕС‚РїСЂР°РІР»РµРЅР° РЅР° РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°")
            else:
                messages.append("РЎСЂРѕРє РёР·РјРµРЅРµРЅРёСЏ РѕС†РµРЅРєРё РёСЃС‚С‘Рє")

    db.commit()
    return redirect_with_messages(f"/teacher/edit_grades/lesson/{lesson_id}", messages)


def redirect_with_messages(url: str, messages: List[str]) -> RedirectResponse:
    return RedirectResponse(url + "?msg=" + "|".join(messages), status_code=303)