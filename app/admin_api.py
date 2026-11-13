from typing import Any

import segno
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.clock import from_db, iso
from app.context import AppContext, get_ctx, get_session
from app.identities import new_code, new_nick
from app.models import SchoolClass, Student
from app.security import client_ip
from app.standings import build_rankings, solve_seconds, totals
from app.task_sets import delete_task_set

router = APIRouter(prefix="/api/admin")

MAX_CLASS_SIZE = 60


class LoginRequest(BaseModel):
    password: str


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    task_set: str
    size: int = Field(ge=1, le=MAX_CLASS_SIZE)


class ClassUpdate(BaseModel):
    task_set: str | None = None
    size: int | None = Field(default=None, ge=1, le=MAX_CLASS_SIZE)


class TestModeUpdate(BaseModel):
    enabled: bool


class StudentUpdate(BaseModel):
    nick: str | None = Field(default=None, min_length=1, max_length=60)
    active: bool | None = None


def require_admin(authorization: str = Header(default=""), ctx: AppContext = Depends(get_ctx)) -> None:
    token = authorization.removeprefix("Bearer ").strip()
    if not ctx.admin_tokens.valid(token):
        raise HTTPException(401, "Zaloguj się ponownie.")


def get_class(session: Session, class_id: int) -> SchoolClass:
    school_class = session.scalar(
        select(SchoolClass)
        .where(SchoolClass.id == class_id)
        .options(selectinload(SchoolClass.students).selectinload(Student.progress))
    )
    if school_class is None:
        raise HTTPException(404, "Nie ma takiej klasy.")
    return school_class


def check_task_set(ctx: AppContext, key: str) -> None:
    if key not in ctx.task_sets:
        raise HTTPException(422, f"Nie ma zestawu zadań „{key}”.")


def add_students(session: Session, school_class: SchoolClass, size: int) -> None:
    current = len(school_class.students)
    if size < current:
        raise HTTPException(422, f"Liczby uczniów nie można zmniejszyć (jest {current}).")
    for number in range(current + 1, size + 1):
        student = Student(number=number, nick=new_nick(session), code=new_code(session), active=True)
        school_class.students.append(student)
        session.flush()


def class_summary(school_class: SchoolClass) -> dict[str, Any]:
    return {
        "id": school_class.id,
        "name": school_class.name,
        "task_set": school_class.task_set,
        "size": len(school_class.students),
        "active": sum(1 for s in school_class.students if s.active),
    }


@router.post("/login")
def login(body: LoginRequest, request: Request, ctx: AppContext = Depends(get_ctx)):
    if not ctx.admin_tokens.enabled:
        raise HTTPException(503, "Hasło administratora nie jest ustawione (ADMIN_PASSWORD).")
    key = "admin:" + client_ip(request)
    if ctx.login_limiter.blocked(key):
        raise HTTPException(429, "Za dużo prób. Spróbuj za kilka minut.")
    if not ctx.admin_tokens.password_matches(body.password):
        ctx.login_limiter.record_failure(key)
        raise HTTPException(401, "Złe hasło.")
    return {"token": ctx.admin_tokens.issue()}


@router.get("/overview", dependencies=[Depends(require_admin)])
def overview(ctx: AppContext = Depends(get_ctx), session: Session = Depends(get_session)):
    classes = session.scalars(
        select(SchoolClass).options(selectinload(SchoolClass.students)).order_by(SchoolClass.name)
    ).all()
    return {
        "phase": ctx.phase(),
        "test_mode": ctx.test_mode(),
        "today": ctx.today(),
        "days": ctx.settings.days,
        "start_date": ctx.settings.start_date.isoformat(),
        "classes": [class_summary(c) for c in classes],
        "task_sets": [
            {"key": ts.key, "name": ts.name, "days": len(ts.days)} for ts in ctx.task_sets.values()
        ],
    }


@router.post("/classes", dependencies=[Depends(require_admin)])
def create_class(body: ClassCreate, ctx: AppContext = Depends(get_ctx), session: Session = Depends(get_session)):
    check_task_set(ctx, body.task_set)
    name = body.name.strip()
    if session.scalar(select(SchoolClass.id).where(SchoolClass.name == name)) is not None:
        raise HTTPException(409, f"Klasa „{name}” już istnieje.")
    school_class = SchoolClass(name=name, task_set=body.task_set)
    session.add(school_class)
    session.flush()
    add_students(session, school_class, body.size)
    session.commit()
    return class_summary(get_class(session, school_class.id))


@router.patch("/classes/{class_id}", dependencies=[Depends(require_admin)])
def update_class(
    class_id: int, body: ClassUpdate, ctx: AppContext = Depends(get_ctx), session: Session = Depends(get_session)
):
    school_class = get_class(session, class_id)
    if body.task_set is not None:
        check_task_set(ctx, body.task_set)
        school_class.task_set = body.task_set
    if body.size is not None:
        add_students(session, school_class, body.size)
    session.commit()
    return class_summary(get_class(session, class_id))


@router.get("/classes/{class_id}/dashboard", dependencies=[Depends(require_admin)])
def dashboard(class_id: int, ctx: AppContext = Depends(get_ctx), session: Session = Depends(get_session)):
    school_class = get_class(session, class_id)
    days = ctx.settings.days
    per_day = {d: {"opened": 0, "solved": 0} for d in range(1, days + 1)}
    students = []
    for student in school_class.students:
        by_day = {p.day: p for p in student.progress}
        cells = []
        for day in range(1, days + 1):
            progress = by_day.get(day)
            if progress is None:
                cells.append({"day": day, "status": "none"})
                continue
            solved = progress.solved_at is not None
            if student.active:
                per_day[day]["opened"] += 1
                per_day[day]["solved"] += int(solved)
            cells.append(
                {
                    "day": day,
                    "status": "solved" if solved else "opened",
                    "points": progress.points,
                    "wrong_attempts": progress.wrong_attempts,
                    "variant": progress.variant + 1,
                    "opened_at": iso(from_db(progress.opened_at)),
                    "seconds": solve_seconds(student, day),
                }
            )
        students.append(
            {
                "id": student.id,
                "number": student.number,
                "nick": student.nick,
                "code": student.code,
                "active": student.active,
                "days": cells,
                **totals(student),
            }
        )
    return {
        **class_summary(school_class),
        "today": ctx.today(),
        "days": days,
        "students": students,
        "per_day": [{"day": d, **counts} for d, counts in per_day.items()],
    }


@router.patch("/students/{student_id}", dependencies=[Depends(require_admin)])
def update_student(student_id: int, body: StudentUpdate, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(404, "Nie ma takiego ucznia.")
    if body.nick is not None:
        nick = body.nick.strip()
        clash = session.scalar(select(Student.id).where(Student.nick == nick, Student.id != student_id))
        if clash is not None:
            raise HTTPException(409, f"Nick „{nick}” jest już zajęty.")
        student.nick = nick
    if body.active is not None:
        student.active = body.active
    session.commit()
    return {"id": student.id, "nick": student.nick, "active": student.active, "code": student.code}


@router.post("/students/{student_id}/regenerate-code", dependencies=[Depends(require_admin)])
def regenerate_code(student_id: int, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(404, "Nie ma takiego ucznia.")
    student.code = new_code(session)
    session.commit()
    return {"id": student.id, "code": student.code}


@router.get("/classes/{class_id}/cards", dependencies=[Depends(require_admin)])
def cards(class_id: int, request: Request, ctx: AppContext = Depends(get_ctx), session: Session = Depends(get_session)):
    school_class = get_class(session, class_id)
    base = (ctx.settings.public_url or str(request.base_url)).rstrip("/")
    result = []
    for student in school_class.students:
        if not student.active:
            continue
        url = f"{base}/#k={student.code}"
        result.append(
            {
                "number": student.number,
                "nick": student.nick,
                "code": student.code,
                "url": url,
                "qr_svg": segno.make(url, error="m").svg_inline(scale=4, border=2),
            }
        )
    return {"class_name": school_class.name, "site": base, "cards": result}


@router.get("/rankings", dependencies=[Depends(require_admin)])
def rankings(ctx: AppContext = Depends(get_ctx), session: Session = Depends(get_session)):
    students = session.scalars(
        select(Student).options(selectinload(Student.progress), selectinload(Student.school_class))
    ).all()
    return build_rankings(students, ctx.today())


@router.get("/task-sets/{key}", dependencies=[Depends(require_admin)])
def task_set_preview(key: str, ctx: AppContext = Depends(get_ctx)):
    check_task_set(ctx, key)
    task_set = ctx.task_sets[key]
    return {
        "key": key,
        "name": task_set.name,
        "days": [
            {"day": day, "variants": [{"text": v.text, "answer": v.answer, "image": v.image} for v in variants]}
            for day, variants in sorted(task_set.days.items())
        ],
    }


@router.post("/test-mode", dependencies=[Depends(require_admin)])
def set_test_mode(body: TestModeUpdate, ctx: AppContext = Depends(get_ctx)):
    ctx.set_test_mode(body.enabled)
    return {"test_mode": ctx.test_mode(), "phase": ctx.phase()}


@router.delete("/task-sets/{key}", dependencies=[Depends(require_admin)])
def remove_task_set(key: str, ctx: AppContext = Depends(get_ctx), session: Session = Depends(get_session)):
    users = session.scalars(select(SchoolClass.name).where(SchoolClass.task_set == key)).all()
    if users:
        raise HTTPException(409, f"Zestawu używają klasy: {', '.join(sorted(users))}. Najpierw zmień im zestaw.")
    if not delete_task_set(session, key):
        raise HTTPException(404, "Nie ma takiego zestawu.")
    session.commit()
    invalidate = getattr(ctx.task_sets, "invalidate", None)
    if invalidate:
        invalidate()
    return {"deleted": key}
