from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)


class BellSchedule(Base):
    __tablename__ = "bell_schedule"

    id = Column(Integer, primary_key=True)
    lesson_number = Column(Integer, nullable=False)
    start_time = Column(String, nullable=False)  # "08:30"
    end_time = Column(String, nullable=False)  # "09:15"


class User(Base):
    __tablename__ = "users"

    ROLES = ("admin", "teacher", "student", "parent")

    id = Column(Integer, primary_key=True)
    login = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    phone = Column(String, default="")
    birth_date = Column(Date, nullable=True)
    role = Column(String, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    child_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    all_groups_access = Column(Boolean, default=False)  # только для учителей
    setup_done = Column(Boolean, default=False)  # настройка расписания звонков (админ)
    created_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", foreign_keys=[group_id])
    child = relationship(
        "User", remote_side=[id], foreign_keys=[child_id], uselist=False, post_update=True
    )
    parent = relationship(
        "User", remote_side=[id], foreign_keys=[parent_id], uselist=False, post_update=True
    )

    @property
    def short_name(self) -> str:
        parts = self.full_name.split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1][0]}."
        return self.full_name


class ScheduleEntry(Base):
    __tablename__ = "schedule_entries"
    __table_args__ = (
        UniqueConstraint("day_of_week", "lesson_number", "group_id", name="uq_schedule"),
    )

    id = Column(Integer, primary_key=True)
    day_of_week = Column(Integer, nullable=False)  # 0 = Пн ... 6 = Вс
    lesson_number = Column(Integer, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    subject = Column(String, nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    room = Column(String, default="")

    group = relationship("Group")
    teacher = relationship("User", foreign_keys=[teacher_id])


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("schedule_entry_id", "date", name="uq_lesson"),
    )

    id = Column(Integer, primary_key=True)
    schedule_entry_id = Column(Integer, ForeignKey("schedule_entries.id"), nullable=False)
    date = Column(Date, nullable=False)

    schedule_entry = relationship("ScheduleEntry")


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("lesson_id", "student_id", name="uq_att"),
    )

    id = Column(Integer, primary_key=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False)
    comment = Column(String, default="")
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint("lesson_id", "student_id", name="uq_grade"),
    )

    id = Column(Integer, primary_key=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    value = Column(String, nullable=False)  # "5","4","3","2","1","!"
    comment = Column(String, default="")
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_remark(self) -> bool:
        return self.value == "!"


class GradeChangeRequest(Base):
    __tablename__ = "grade_change_requests"

    id = Column(Integer, primary_key=True)
    grade_id = Column(Integer, ForeignKey("grades.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    old_value = Column(String, nullable=False)
    new_value = Column(String, nullable=False)
    comment = Column(String, default="")
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="pending")  # pending / approved / rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    topic = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    targets = relationship("NotificationTarget", cascade="all, delete-orphan")


class NotificationTarget(Base):
    __tablename__ = "notification_targets"

    id = Column(Integer, primary_key=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=False)
    role = Column(String, nullable=False)  # teacher / student / parent


class PinnedNotification(Base):
    __tablename__ = "pinned_notifications"
    __table_args__ = (
        UniqueConstraint("notification_id", "user_id", name="uq_pin"),
    )

    id = Column(Integer, primary_key=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Holiday(Base):
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    grade_edit_days = Column(Integer, default=7)
    grade_admin_edit_days = Column(Integer, default=14)


def get_or_create_settings(db) -> Settings:
    s = db.query(Settings).first()
    if not s:
        s = Settings(id=1)
        db.add(s)
        db.commit()
    return s