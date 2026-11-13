from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SchoolClass(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    task_set: Mapped[str] = mapped_column(String(100))
    students: Mapped[list["Student"]] = relationship(back_populates="school_class", order_by="Student.number")


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("class_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    number: Mapped[int] = mapped_column(Integer)
    nick: Mapped[str] = mapped_column(String(60), unique=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    school_class: Mapped[SchoolClass] = relationship(back_populates="students")
    progress: Mapped[list["DayProgress"]] = relationship(back_populates="student", order_by="DayProgress.day")


class DayProgress(Base):
    __tablename__ = "day_progress"
    __table_args__ = (UniqueConstraint("student_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    day: Mapped[int] = mapped_column(Integer)
    variant: Mapped[int] = mapped_column(Integer)
    opened_at: Mapped[datetime] = mapped_column(DateTime)
    wrong_attempts: Mapped[int] = mapped_column(Integer, default=0)
    solved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    student: Mapped[Student] = relationship(back_populates="progress")


class TaskSetRecord(Base):
    __tablename__ = "task_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    variants: Mapped[list["TaskVariantRecord"]] = relationship(
        back_populates="task_set",
        order_by="(TaskVariantRecord.day, TaskVariantRecord.position)",
        cascade="all, delete-orphan",
    )


class TaskVariantRecord(Base):
    __tablename__ = "task_variants"
    __table_args__ = (UniqueConstraint("task_set_id", "day", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_set_id: Mapped[int] = mapped_column(ForeignKey("task_sets.id", ondelete="CASCADE"), index=True)
    day: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(String(50))
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_set: Mapped[TaskSetRecord] = relationship(back_populates="variants")
