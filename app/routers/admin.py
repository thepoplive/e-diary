from datetime import date, datetime
from typing import List

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user, hash_password, require_roles
from ..database import get_db
from ..helpers import DAYS_RU, ROLE_RU, fmt_date, fmt_dt, notification_targets_text
from .. import models
from ..models import get_or_create_settings
from ..templating import render

router = APIRouter(prefix="/admin", tags=["admin"])

require_admin = require_roles("admin")


def setup_guard(user: models.User):
    if not user.setup_done:
        return RedirectResponse("/setup/bells", status_code=302)
    return None


def _check_login_unique(db: Session, login: str, exclude_id: int | None = None) -> str | None:
    login = login.strip()
    q = db.query(models.User).filter(models.User.login == login)
    if exclude_id:
        q = q.filter(models.User.id != exclude_id)
    if q.first():
        return f"Р›РѕРіРёРЅ В«{login}В» СѓР¶Рµ Р·Р°РЅСЏС‚"
    return None


def _get_or_create_group(db: Session, name: str) -> models.Group:
    name = name.strip()
    if not name:
        return None
    g = db.query(models.Group).filter(models.Group.name == name).first()
    if not g:
        g = models.Group(name=name)
        db.add(g)
        db.flush()
    return g


# ---------------------------------------------------------------- Р”Р°С€Р±РѕСЂРґ
@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    if r := setup_guard(user):
        return r
    stats = {
        "teachers": db.query(models.User).filter(models.User.role == "teacher").count(),
        "students": db.query(models.User).filter(models.User.role == "student").count(),
        "parents": db.query(models.User).filter(models.User.role == "parent").count(),
        "groups": db.query(models.Group).count(),
        "grades": db.query(models.Grade).count(),
        "remarks": db.query(models.Grade).filter(models.Grade.value == "!").count(),
    }
    return render(
        "admin/dashboard.html",
        {"request": request, "user": user, "stats": stats, "active": "dashboard"},
    )


# ---------------------------------------------------------------- РџРѕР»СЊР·РѕРІР°С‚РµР»Рё
@router.get("/users")
def users_page(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    if r := setup_guard(user):
        return r
    teachers = db.query(models.User).filter(models.User.role == "teacher").order_by(models.User.full_name).all()
    students = db.query(models.User).filter(models.User.role == "student").order_by(models.User.full_name).all()
    parents = db.query(models.User).filter(models.User.role == "parent").order_by(models.User.full_name).all()
    groups = db.query(models.Group).order_by(models.Group.name).all()
    return render(
        "admin/users.html",
        {
            "request": request,
            "user": user,
            "teachers": teachers,
            "students": students,
            "parents": parents,
            "groups": groups,
            "active": "users",
        },
    )


@router.get("/users/create")
def user_create_page(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    role: str = "teacher",
):
    if r := setup_guard(user):
        return r
    if role not in ("teacher", "student", "parent"):
        role = "teacher"
    groups = db.query(models.Group).order_by(models.Group.name).all()
    students = db.query(models.User).filter(models.User.role == "student").order_by(models.User.full_name).all()
    return render(
        "admin/user_create.html",
        {
            "request": request,
            "user": user,
            "role": role,
            "groups": groups,
            "students": students,
            "active": "users",
        },
    )


@router.post("/users/create")
def user_create_submit(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    role: str = Form(...),
    full_name: str = Form(...),
    phone: str = Form(""),
    birth_date: str = Form(""),
    login: str = Form(...),
    password: str = Form(...),
    group_name: str = Form(""),
    child_id: str = Form(""),
):
    if r := setup_guard(user):
        return r
    if role not in ("teacher", "student", "parent"):
        raise HTTPException(status_code=400)
    if not full_name.strip() or not login.strip() or not password:
        return render(
            "admin/user_create.html",
            {
                "request": request,
                "user": user,
                "role": role,
                "groups": db.query(models.Group).order_by(models.Group.name).all(),
                "students": db.query(models.User).filter(models.User.role == "student").all(),
                "active": "users",
                "error": "Р—Р°РїРѕР»РЅРёС‚Рµ Р¤РРћ, Р»РѕРіРёРЅ Рё РїР°СЂРѕР»СЊ",
            },
            status_code=400,
        )
    if err := _check_login_unique(db, login):
        return render(
            "admin/user_create.html",
            {
                "request": request,
                "user": user,
                "role": role,
                "groups": db.query(models.Group).order_by(models.Group.name).all(),
                "students": db.query(models.User).filter(models.User.role == "student").all(),
                "active": "users",
                "error": err,
            },
            status_code=400,
        )
    bd = None
    if birth_date:
        try:
            bd = date.fromisoformat(birth_date)
        except ValueError:
            bd = None

    grp = _get_or_create_group(db, group_name)
    child = None
    if child_id:
        child = db.query(models.User).filter(models.User.id == int(child_id)).first()

    new_user = models.User(
        login=login.strip(),
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        phone=phone.strip(),
        birth_date=bd,
        role=role,
        group_id=grp.id if grp else None,
    )
    db.add(new_user)
    db.flush()

    if role == "parent" and child:
        new_user.child_id = child.id
        child.parent_id = new_user.id
        if not new_user.group_id:
            new_user.group_id = child.group_id
    if role == "student" and child:
        new_user.child_id = None
        new_user.parent_id = None

    db.commit()
    return render(
        "admin/user_created.html",
        {
            "request": request,
            "user": user,
            "created": new_user,
            "login": new_user.login,
            "password": password,
            "active": "users",
        },
    )


@router.post("/users/edit")
def user_edit_submit(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    user_id: int = Form(...),
    login: str = Form(...),
    password: str = Form(""),
    group_name: str = Form(""),
    all_groups_access: str = Form(""),
    child_id: str = Form(""),
):
    if r := setup_guard(user):
        return r
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404)
    if err := _check_login_unique(db, login, exclude_id=target.id):
        return RedirectResponse("/admin/users?error=" + err, status_code=303)
    target.login = login.strip()
    if password:
        target.password_hash = hash_password(password)
    grp = _get_or_create_group(db, group_name)
    target.group_id = grp.id if grp else target.group_id

    if target.role == "teacher":
        target.all_groups_access = bool(all_groups_access)
    if target.role == "parent" and child_id:
        child = db.query(models.User).filter(models.User.id == int(child_id)).first()
        if child and child.role == "student":
            if target.child_id and target.child_id != child.id:
                old_child = db.query(models.User).get(target.child_id)
                if old_child:
                    old_child.parent_id = None
            target.child_id = child.id
            child.parent_id = target.id
            if not target.group_id:
                target.group_id = child.group_id
    if target.role == "student" and child_id:
        parent = db.query(models.User).filter(models.User.id == int(child_id)).first()
        if parent and parent.role == "parent":
            if target.parent_id and target.parent_id != parent.id:
                old_parent = db.query(models.User).get(target.parent_id)
                if old_parent:
                    old_parent.child_id = None
            target.parent_id = parent.id
            parent.child_id = target.id
    db.commit()
    return RedirectResponse("/admin/users", status_code=303)


# ---------------------------------------------------------------- РЈРІРµРґРѕРјР»РµРЅРёСЏ
@router.get("/notifications")
def notifications_page(
    request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_admin)
):
    if r := setup_guard(user):
        return r
    all_notifs = db.query(models.Notification).order_by(models.Notification.created_at.desc()).all()
    pinned_notif_ids = {
        p.notification_id
        for p in db.query(models.PinnedNotification).all()
    }
    return render(
        "admin/notifications.html",
        {
            "request": request,
            "user": user,
            "notifications": all_notifs,
            "pinned_notif_ids": pinned_notif_ids,
            "active": "notifications",
        },
    )


@router.post("/notifications/send")
def notification_send(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    topic: str = Form(...),
    message: str = Form(...),
    targets: List[str] = Form(default=[]),
):
    if r := setup_guard(user):
        return r
    roles = [t for t in targets if t in ("teacher", "student", "parent")]
    if not roles or not topic.strip() or not message.strip():
        return RedirectResponse("/admin/notifications?error=Р—Р°РїРѕР»РЅРёС‚Рµ С‚РµРјСѓ, С‚РµРєСЃС‚ Рё РІС‹Р±РµСЂРёС‚Рµ РїРѕР»СѓС‡Р°С‚РµР»РµР№", status_code=303)
    n = models.Notification(
        topic=topic.strip(), message=message.strip(), created_by_id=user.id
    )
    for role in roles:
        n.targets.append(models.NotificationTarget(role=role))
    db.add(n)
    db.commit()
    return RedirectResponse("/admin/notifications", status_code=303)


@router.post("/notifications/pin")
def notification_pin(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    notification_id: int = Form(...),
):
    if r := setup_guard(user):
        return r
    n = db.query(models.Notification).filter(models.Notification.id == notification_id).first()
    if not n:
        raise HTTPException(status_code=404)
    target_roles = [t.role for t in n.targets]
    users = db.query(models.User).filter(models.User.role.in_(target_roles)).all()
    for u in users:
        pinned_count = (
            db.query(models.PinnedNotification)
            .filter(models.PinnedNotification.user_id == u.id)
            .count()
        )
        if pinned_count < 3:
            exists = (
                db.query(models.PinnedNotification)
                .filter(
                    models.PinnedNotification.user_id == u.id,
                    models.PinnedNotification.notification_id == n.id,
                )
                .first()
            )
            if not exists:
                db.add(models.PinnedNotification(notification_id=n.id, user_id=u.id))
    db.commit()
    return RedirectResponse("/admin/notifications", status_code=303)


@router.post("/notifications/unpin")
def notification_unpin(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    notification_id: int = Form(...),
):
    if r := setup_guard(user):
        return r
    db.query(models.PinnedNotification).filter(
        models.PinnedNotification.notification_id == notification_id
    ).delete()
    db.commit()
    return RedirectResponse("/admin/notifications", status_code=303)


# ---------------------------------------------------------------- Р Р°СЃРїРёСЃР°РЅРёРµ СѓСЂРѕРєРѕРІ
@router.get("/schedule")
def schedule_page(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    day: int = None,
):
    if r := setup_guard(user):
        return r
    if day is None:
        day = date.today().weekday()
    day = int(day)
    groups = db.query(models.Group).order_by(models.Group.name).all()
    table = []
    for g in groups:
        entries = (
            db.query(models.ScheduleEntry)
            .filter(
                models.ScheduleEntry.day_of_week == day,
                models.ScheduleEntry.group_id == g.id,
            )
            .order_by(models.ScheduleEntry.lesson_number)
            .all()
        )
        table.append({"group": g, "entries": entries})
    teachers = db.query(models.User).filter(models.User.role == "teacher").order_by(models.User.full_name).all()
    return render(
        "admin/schedule.html",
        {
            "request": request,
            "user": user,
            "table": table,
            "day": day,
            "days": list(range(7)),
            "days_ru": DAYS_RU,
            "teachers": teachers,
            "groups": groups,
            "active": "schedule",
        },
    )


@router.get("/schedule/add")
def schedule_add_page(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
):
    if r := setup_guard(user):
        return r
    groups = db.query(models.Group).order_by(models.Group.name).all()
    teachers = db.query(models.User).filter(models.User.role == "teacher").order_by(models.User.full_name).all()
    return render(
        "admin/schedule_add.html",
        {
            "request": request,
            "user": user,
            "groups": groups,
            "teachers": teachers,
            "days_ru": DAYS_RU,
            "active": "schedule",
        },
    )


@router.post("/schedule/add")
def schedule_add_submit(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    day: int = Form(...),
    group_id: int = Form(...),
    subjects: List[str] = Form(default=[]),
    teacher_ids: List[str] = Form(default=[]),
    rooms: List[str] = Form(default=[]),
):
    if r := setup_guard(user):
        return r
    for i, (subject, teacher_id, room) in enumerate(zip(subjects, teacher_ids, rooms), start=1):
        if not (subject or "").strip():
            continue
        existing = (
            db.query(models.ScheduleEntry)
            .filter(
                models.ScheduleEntry.day_of_week == day,
                models.ScheduleEntry.lesson_number == i,
                models.ScheduleEntry.group_id == group_id,
            )
            .first()
        )
        tid = int(teacher_id) if teacher_id else None
        if existing:
            existing.subject = subject.strip()
            existing.teacher_id = tid
            existing.room = (room or "").strip()
        else:
            db.add(
                models.ScheduleEntry(
                    day_of_week=day,
                    lesson_number=i,
                    group_id=group_id,
                    subject=subject.strip(),
                    teacher_id=tid,
                    room=(room or "").strip(),
                )
            )
    db.commit()
    return RedirectResponse(f"/admin/schedule?day={day}", status_code=303)


@router.post("/schedule/edit")
def schedule_edit_submit(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    entry_id: int = Form(...),
    subject: str = Form(...),
    teacher_id: str = Form(""),
    room: str = Form(""),
):
    if r := setup_guard(user):
        return r
    entry = db.query(models.ScheduleEntry).filter(models.ScheduleEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404)
    if subject.strip():
        entry.subject = subject.strip()
    entry.teacher_id = int(teacher_id) if teacher_id else None
    entry.room = (room or "").strip()
    db.commit()
    return RedirectResponse(f"/admin/schedule?day={entry.day_of_week}", status_code=303)


# ---------------------------------------------------------------- РљР°РЅРёРєСѓР»С‹
@router.get("/holidays")
def holidays_page(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    if r := setup_guard(user):
        return r
    holidays = db.query(models.Holiday).order_by(models.Holiday.start_date).all()
    return render(
        "admin/holidays.html",
        {"request": request, "user": user, "holidays": holidays, "active": "holidays"},
    )


@router.post("/holidays/add")
def holiday_add(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    start_date: str = Form(...),
    end_date: str = Form(...),
):
    if r := setup_guard(user):
        return r
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return RedirectResponse("/admin/holidays?error=РќРµРєРѕСЂСЂРµРєС‚РЅР°СЏ РґР°С‚Р°", status_code=303)
    if end < start:
        start, end = end, start
    db.add(models.Holiday(start_date=start, end_date=end))
    db.commit()
    return RedirectResponse("/admin/holidays", status_code=303)


@router.post("/holidays/edit")
def holiday_edit(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    holiday_id: int = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
):
    if r := setup_guard(user):
        return r
    h = db.query(models.Holiday).filter(models.Holiday.id == holiday_id).first()
    if not h:
        raise HTTPException(status_code=404)
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return RedirectResponse("/admin/holidays?error=РќРµРєРѕСЂСЂРµРєС‚РЅР°СЏ РґР°С‚Р°", status_code=303)
    if end < start:
        start, end = end, start
    h.start_date = start
    h.end_date = end
    db.commit()
    return RedirectResponse("/admin/holidays", status_code=303)


# ---------------------------------------------------------------- Р Р°СЃРїРёСЃР°РЅРёРµ Р·РІРѕРЅРєРѕРІ (РІРЅРµСЃРµРЅРёРµ РїСЂР°РІРѕРє)
@router.get("/bells")
def admin_bells_page(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    if r := setup_guard(user):
        return r
    bells = db.query(models.BellSchedule).order_by(models.BellSchedule.lesson_number).all()
    return render(
        "admin/bells.html",
        {"request": request, "user": user, "bells": bells, "active": "bells"},
    )


@router.post("/bells")
def admin_bells_save(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    lesson_number: List[int] = Form(default=[]),
    start_time: List[str] = Form(default=[]),
    end_time: List[str] = Form(default=[]),
):
    if r := setup_guard(user):
        return r
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
    db.commit()
    return RedirectResponse("/admin/bells", status_code=303)


# ---------------------------------------------------------------- РќР°СЃС‚СЂРѕР№РєРё
@router.get("/settings")
def settings_page(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    if r := setup_guard(user):
        return r
    s = get_or_create_settings(db)
    return render(
        "admin/settings.html",
        {"request": request, "user": user, "settings": s, "active": "settings"},
    )


@router.post("/settings/save")
def settings_save(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    grade_edit_days: int = Form(...),
    grade_admin_edit_days: int = Form(...),
):
    if r := setup_guard(user):
        return r
    s = get_or_create_settings(db)
    s.grade_edit_days = max(1, min(grade_edit_days, 365))
    s.grade_admin_edit_days = max(1, min(grade_admin_edit_days, 365))
    db.commit()
    return RedirectResponse("/admin/settings", status_code=303)


# ---------------------------------------------------------------- Р—Р°СЏРІРєРё РЅР° РёР·РјРµРЅРµРЅРёРµ РѕС†РµРЅРѕРє
@router.get("/grade_changes")
def grade_changes_page(request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    if r := setup_guard(user):
        return r
    changes = (
        db.query(models.GradeChangeRequest)
        .filter(models.GradeChangeRequest.status == "pending")
        .order_by(models.GradeChangeRequest.created_at)
        .all()
    )
    rows = []
    for c in changes:
        lesson = db.query(models.Lesson).filter(models.Lesson.id == c.lesson_id).first()
        student = db.query(models.User).filter(models.User.id == c.student_id).first()
        teacher = db.query(models.User).filter(models.User.id == c.teacher_id).first()
        rows.append(
            {
                "id": c.id,
                "student": student,
                "lesson": lesson,
                "subject": lesson.schedule_entry.subject if lesson else "вЂ”",
                "old_value": c.old_value,
                "new_value": c.new_value,
                "comment": c.comment,
                "teacher": teacher,
                "created_at": c.created_at,
            }
        )
    return render(
        "admin/grade_changes.html",
        {"request": request, "user": user, "rows": rows, "active": "grade_changes"},
    )


@router.post("/grade_changes/approve")
def grade_change_approve(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    change_id: int = Form(...),
):
    if r := setup_guard(user):
        return r
    change = db.query(models.GradeChangeRequest).filter(models.GradeChangeRequest.id == change_id).first()
    if not change or change.status != "pending":
        raise HTTPException(status_code=404)
    grade = db.query(models.Grade).filter(models.Grade.id == change.grade_id).first()
    if grade:
        grade.value = change.new_value
        grade.comment = change.comment
    change.status = "approved"
    change.decided_at = datetime.utcnow()
    db.commit()
    return RedirectResponse("/admin/grade_changes", status_code=303)


@router.post("/grade_changes/reject")
def grade_change_reject(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
    change_id: int = Form(...),
):
    if r := setup_guard(user):
        return r
    change = db.query(models.GradeChangeRequest).filter(models.GradeChangeRequest.id == change_id).first()
    if not change or change.status != "pending":
        raise HTTPException(status_code=404)
    change.status = "rejected"
    change.decided_at = datetime.utcnow()
    db.commit()
    return RedirectResponse("/admin/grade_changes", status_code=303)