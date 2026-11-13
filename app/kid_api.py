from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.answers import is_correct, parse_answer
from app.clock import from_db, iso, to_db
from app.context import AppContext, get_ctx, get_session
from app.identities import normalize_code
from app.models import DayProgress, Student
from app.scoring import breakdown, day_points, multiplier, streak_before
from app.security import client_ip
from app.standings import build_rankings

router = APIRouter(prefix="/api")


class LoginRequest(BaseModel):
    code: str


class AnswerRequest(BaseModel):
    answer: str


def find_student(session: Session, code: str) -> Student | None:
    return session.scalar(
        select(Student)
        .where(Student.code == normalize_code(code), Student.active.is_(True))
        .options(selectinload(Student.progress), selectinload(Student.school_class))
    )


def current_student(
    request: Request,
    x_code: str = Header(default=""),
    ctx: AppContext = Depends(get_ctx),
    session: Session = Depends(get_session),
) -> Student:
    ip = client_ip(request)
    if ctx.login_limiter.blocked(ip):
        raise HTTPException(429, "Za dużo prób. Spróbuj ponownie za kilka minut.")
    student = find_student(session, x_code)
    if student is None:
        ctx.login_limiter.record_failure(ip)
        raise HTTPException(401, "Nie znamy takiego kodu.")
    return student


def solved_days(student: Student) -> set[int]:
    return {p.day for p in student.progress if p.solved_at is not None}


def progress_for(student: Student, day: int) -> DayProgress | None:
    return next((p for p in student.progress if p.day == day), None)


def require_today(ctx: AppContext, day: int) -> None:
    if ctx.phase() != "running" or day != ctx.today():
        raise HTTPException(403, "To okienko jest teraz zamknięte.")


def task_payload(ctx: AppContext, student: Student, progress: DayProgress) -> dict[str, Any]:
    task_set = ctx.task_sets[student.school_class.task_set]
    variant = task_set.variant(progress.day, progress.variant)
    streak = streak_before(solved_days(student), progress.day)
    return {
        "day": progress.day,
        "text": variant.text,
        "opened_at": iso(from_db(progress.opened_at)),
        "server_now": iso(ctx.clock()),
        "wrong_attempts": progress.wrong_attempts,
        "solved": progress.solved_at is not None,
        "points": progress.points,
        "streak": streak,
        "multiplier": round(multiplier(streak), 4),
        "breakdown": solved_breakdown(progress, streak),
    }


def solved_breakdown(progress: DayProgress, streak: int) -> dict[str, Any] | None:
    if progress.solved_at is None:
        return None
    elapsed = int((from_db(progress.solved_at) - from_db(progress.opened_at)).total_seconds())
    return breakdown(elapsed, progress.wrong_attempts, streak)


@router.post("/login")
def login(body: LoginRequest, request: Request, ctx: AppContext = Depends(get_ctx), session: Session = Depends(get_session)):
    student = current_student(request, body.code, ctx, session)
    return {"code": student.code, "nick": student.nick}


@router.get("/me")
def me(student: Student = Depends(current_student), ctx: AppContext = Depends(get_ctx)):
    today = ctx.today()
    solved = solved_days(student)
    days = []
    for day in range(1, ctx.settings.days + 1):
        progress = progress_for(student, day)
        if day > today:
            status = "locked"
        elif progress is not None and progress.solved_at is not None:
            status = "solved"
        elif day == today:
            status = "opened" if progress is not None else "available"
        else:
            status = "missed"
        days.append({"day": day, "status": status, "points": progress.points if progress else None})

    current_streak = streak_before(solved, today + 1) if today in solved else streak_before(solved, today)
    return {
        "nick": student.nick,
        "class_name": student.school_class.name,
        "number": student.number,
        "phase": ctx.phase(),
        "today": today,
        "start_date": ctx.settings.start_date.isoformat(),
        "days": days,
        "total_points": sum(p.points or 0 for p in student.progress),
        "solved": len(solved),
        "streak": current_streak,
        "today_multiplier": round(multiplier(streak_before(solved, today)), 4),
    }


@router.post("/days/{day}/open")
def open_day(
    day: int,
    student: Student = Depends(current_student),
    ctx: AppContext = Depends(get_ctx),
    session: Session = Depends(get_session),
):
    require_today(ctx, day)
    progress = progress_for(student, day)
    if progress is None:
        task_set = ctx.task_sets[student.school_class.task_set]
        progress = DayProgress(
            student_id=student.id,
            day=day,
            variant=task_set.variant_number(student.number, day),
            opened_at=to_db(ctx.clock()),
            wrong_attempts=0,
        )
        session.add(progress)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        session.refresh(student)
        progress = progress_for(student, day)
    return task_payload(ctx, student, progress)


@router.post("/days/{day}/answer")
def answer_day(
    day: int,
    body: AnswerRequest,
    student: Student = Depends(current_student),
    ctx: AppContext = Depends(get_ctx),
    session: Session = Depends(get_session),
):
    require_today(ctx, day)
    progress = progress_for(student, day)
    if progress is None:
        raise HTTPException(409, "Najpierw otwórz okienko.")
    if progress.solved_at is not None:
        streak = streak_before(solved_days(student), day)
        return {
            "correct": True,
            "points": progress.points,
            "already_solved": True,
            "streak": streak + 1,
            "breakdown": solved_breakdown(progress, streak),
        }

    given = parse_answer(body.answer)
    if given is None:
        raise HTTPException(422, "Wpisz liczbę, np. 12 albo 3,5.")

    task_set = ctx.task_sets[student.school_class.task_set]
    expected = task_set.variant(day, progress.variant).answer

    if not is_correct(given, expected):
        session.execute(
            update(DayProgress)
            .where(DayProgress.id == progress.id)
            .values(wrong_attempts=DayProgress.wrong_attempts + 1)
        )
        session.commit()
        session.refresh(progress)
        return {"correct": False, "wrong_attempts": progress.wrong_attempts}

    now = ctx.clock()
    elapsed = int((now - from_db(progress.opened_at)).total_seconds())
    streak = streak_before(solved_days(student), day)
    points = day_points(elapsed, progress.wrong_attempts, streak)
    result = session.execute(
        update(DayProgress)
        .where(DayProgress.id == progress.id, DayProgress.solved_at.is_(None))
        .values(solved_at=to_db(now), points=points)
    )
    session.commit()
    session.refresh(progress)
    return {
        "correct": True,
        "points": progress.points,
        "already_solved": result.rowcount == 0,
        "streak": streak + 1,
        "breakdown": solved_breakdown(progress, streak),
    }


@router.get("/rankings")
def rankings(
    student: Student = Depends(current_student),
    ctx: AppContext = Depends(get_ctx),
    session: Session = Depends(get_session),
):
    students = session.scalars(
        select(Student).options(selectinload(Student.progress), selectinload(Student.school_class))
    ).all()
    return build_rankings(students, ctx.today(), me=student)


@router.get("/info")
def info(ctx: AppContext = Depends(get_ctx)):
    return {"phase": ctx.phase(), "today": ctx.today(), "start_date": ctx.settings.start_date.isoformat(), "days": ctx.settings.days}


