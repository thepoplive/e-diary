from datetime import date, timedelta

from sqlalchemy.orm import Session

from .. import models
from ..helpers import get_user_notifications, group_entries_on_day, week_start


def child_of(db: Session, user: models.User):
    """Ребёнок родителя (или сам ученик)."""
    if user.role == "student":
        return user
    if user.role == "parent" and user.child_id:
        return db.query(models.User).filter(models.User.id == user.child_id).first()
    return None


def today_count(db: Session, student: models.User) -> int:
    if not student or not student.group_id:
        return 0
    return len(group_entries_on_day(db, student.group_id, date.today()))


def today_rows(db: Session, student: models.User):
    """Уроки на сегодня с посещаемостью и оценкой."""
    if not student or not student.group_id:
        return []
    today = date.today()
    entries = group_entries_on_day(db, student.group_id, today)
    rows = []
    for e in entries:
        lesson = (
            db.query(models.Lesson)
            .filter(models.Lesson.schedule_entry_id == e.id, models.Lesson.date == today)
            .first()
        )
        att = grade = None
        if lesson:
            att = (
                db.query(models.Attendance)
                .filter(models.Attendance.lesson_id == lesson.id, models.Attendance.student_id == student.id)
                .first()
            )
            grade = (
                db.query(models.Grade)
                .filter(models.Grade.lesson_id == lesson.id, models.Grade.student_id == student.id)
                .first()
            )
        rows.append({"entry": e, "lesson": lesson, "attendance": att, "grade": grade})
    return rows


def week_rows(db: Session, student: models.User, ref: date):
    """Расписание недели + оценки по дням."""
    if not student or not student.group_id:
        return []
    start = week_start(ref)
    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        entries = group_entries_on_day(db, student.group_id, d)
        rows = []
        for e in entries:
            lesson = (
                db.query(models.Lesson)
                .filter(models.Lesson.schedule_entry_id == e.id, models.Lesson.date == d)
                .first()
            )
            att = grade = None
            if lesson:
                att = (
                    db.query(models.Attendance)
                    .filter(models.Attendance.lesson_id == lesson.id, models.Attendance.student_id == student.id)
                    .first()
                )
                grade = (
                    db.query(models.Grade)
                    .filter(models.Grade.lesson_id == lesson.id, models.Grade.student_id == student.id)
                    .first()
                )
            rows.append({"entry": e, "lesson": lesson, "attendance": att, "grade": grade})
        if rows:
            days.append({"date": d, "rows": rows})
    return days


def main_context(db: Session, user: models.User):
    child = child_of(db, user)
    return {
        "child": child,
        "today_count": today_count(db, child),
        "notifications": get_user_notifications(db, user),
    }