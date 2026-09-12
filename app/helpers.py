from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from . import models

DAYS_RU = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

ROLE_RU = {"admin": "Администратор", "teacher": "Учитель", "student": "Ученик", "parent": "Родитель"}

GRADE_VALUES = ["5", "4", "3", "2", "1", "!"]
GRADE_LABELS = {
    "5": "5 (отлично)",
    "4": "4 (хорошо)",
    "3": "3 (удовлетворительно)",
    "2": "2 (неудовлетворительно)",
    "1": "1 (плохо)",
    "!": "Замечание",
}
ATTENDANCE_VALUES = ["present", "absent", "skip", "sick", "excused"]
ATTENDANCE_LABELS = {
    "present": "На уроке",
    "absent": "Не на уроке",
    "skip": "Прогул",
    "sick": "Болезнь",
    "excused": "Уваж. причина",
}
TARGET_ROLE_RU = {"teacher": "Учителям", "student": "Ученикам", "parent": "Родителям"}


def msk(dt: datetime) -> datetime:
    """Время в МСК (UTC+3)."""
    return dt + timedelta(hours=3)


def fmt_dt(dt: datetime) -> str:
    return msk(dt).strftime("%d.%m.%Y %H:%M")


def fmt_date(d) -> str:
    if not d:
        return "—"
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%d.%m.%Y")


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def get_or_create_lesson(db: Session, entry: models.ScheduleEntry, d: date) -> models.Lesson:
    lesson = (
        db.query(models.Lesson)
        .filter(models.Lesson.schedule_entry_id == entry.id, models.Lesson.date == d)
        .first()
    )
    if not lesson:
        lesson = models.Lesson(schedule_entry_id=entry.id, date=d)
        db.add(lesson)
        db.flush()
    return lesson


def teacher_entries_on_day(db: Session, teacher: models.User, d: date):
    return (
        db.query(models.ScheduleEntry)
        .filter(models.ScheduleEntry.day_of_week == d.weekday(), models.ScheduleEntry.teacher_id == teacher.id)
        .order_by(models.ScheduleEntry.lesson_number)
        .all()
    )


def group_entries_on_day(db: Session, group_id: int, d: date):
    return (
        db.query(models.ScheduleEntry)
        .filter(models.ScheduleEntry.day_of_week == d.weekday(), models.ScheduleEntry.group_id == group_id)
        .order_by(models.ScheduleEntry.lesson_number)
        .all()
    )


def notification_targets_text(n: models.Notification) -> str:
    return ", ".join(TARGET_ROLE_RU.get(t.role, t.role) for t in sorted(n.targets, key=lambda x: x.role))


def get_user_notifications(db: Session, user: models.User):
    """Уведомления пользователя: закреплённые сверху, затем новые."""
    role = user.role
    rows = (
        db.query(models.Notification)
        .join(models.NotificationTarget)
        .filter(models.NotificationTarget.role == role)
        .all()
    )
    pinned_ids = {
        p.notification_id
        for p in db.query(models.PinnedNotification).filter(models.PinnedNotification.user_id == user.id).all()
    }
    items = [{"n": n, "pinned": n.id in pinned_ids, "pin_id": n.id} for n in rows]
    items.sort(key=lambda x: x["n"].created_at, reverse=True)
    items.sort(key=lambda x: x["pinned"], reverse=True)
    return items


def count_student_stats(db: Session, student: models.User):
    """Статистика ученика по всем занятиям."""
    attended = excused = sick = unexcused = remarks = 0
    att_rows = (
        db.query(models.Attendance)
        .join(models.Lesson)
        .filter(models.Attendance.student_id == student.id)
        .all()
    )
    for a in att_rows:
        if a.status == "present":
            attended += 1
        elif a.status == "excused":
            excused += 1
        elif a.status == "sick":
            sick += 1
        elif a.status in ("skip", "absent"):
            unexcused += 1
    remarks = (
        db.query(models.Grade)
        .filter(models.Grade.student_id == student.id, models.Grade.value == "!")
        .count()
    )
    return {
        "attended": attended,
        "excused": excused,
        "sick": sick,
        "unexcused": unexcused,
        "remarks": remarks,
    }