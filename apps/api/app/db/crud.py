"""CRUD operations for the Unilead platform.

Each function takes a SQLAlchemy ``Session`` as the first argument so
callers control transaction boundaries. Functions don't commit — the
caller is responsible for committing (or rolling back on error).

This keeps the DB layer thin and testable: services call these functions
inside a ``with db:`` block (or use ``Depends(get_db)`` in routers).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models

# ---- User ----------------------------------------------------------------


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def create_user(
    db: Session,
    *,
    email: str,
    username: str,
    name: str,
    password_hash: str | None = None,
) -> models.User:
    user = models.User(
        email=_normalize_email(email),
        username=_normalize_username(username),
        name=name,
        password_hash=password_hash,
    )
    db.add(user)
    db.flush()
    return user


def get_user_by_email(db: Session, email: str) -> models.User | None:
    return (
        db.query(models.User)
        .filter(func.lower(models.User.email) == _normalize_email(email))
        .first()
    )


def get_user_by_username(db: Session, username: str) -> models.User | None:
    return (
        db.query(models.User)
        .filter(func.lower(models.User.username) == _normalize_username(username))
        .first()
    )


def get_user_by_id(db: Session, user_id: int) -> models.User | None:
    return db.query(models.User).filter(models.User.id == user_id).first()


# ---- Student --------------------------------------------------------------


def create_student(
    db: Session,
    *,
    student_id: str,
    user_id: int,
    display_name: str,
    course_code: str = "MEC271",
    course_title: str = "Automatic Control",
    overall_progress: int = 0,
) -> models.Student:
    student = models.Student(
        student_id=student_id,
        user_id=user_id,
        display_name=display_name,
        course_code=course_code,
        course_title=course_title,
        overall_progress=overall_progress,
    )
    db.add(student)
    db.flush()
    return student


def get_student_by_id(db: Session, student_id: str) -> models.Student | None:
    return db.query(models.Student).filter(models.Student.student_id == student_id).first()


def get_students_by_user_id(db: Session, user_id: int) -> list[models.Student]:
    return db.query(models.Student).filter(models.Student.user_id == user_id).all()


def list_all_students(db: Session) -> list[models.Student]:
    return db.query(models.Student).order_by(models.Student.display_name).all()


def update_student_progress(db: Session, student_id: str, overall_progress: int) -> None:
    db.query(models.Student).filter(models.Student.student_id == student_id).update(
        {"overall_progress": overall_progress}
    )


# ---- Competency snapshot --------------------------------------------------


def get_competencies(db: Session, student_id: str) -> list[models.CompetencySnapshot]:
    return (
        db.query(models.CompetencySnapshot)
        .filter(models.CompetencySnapshot.student_id == student_id)
        .order_by(models.CompetencySnapshot.id)
        .all()
    )


def get_all_competencies(db: Session) -> list[models.CompetencySnapshot]:
    return db.query(models.CompetencySnapshot).order_by(models.CompetencySnapshot.id).all()


def upsert_competency(
    db: Session,
    *,
    student_id: str,
    competency_id: str,
    competency_name: str,
    status: str,
    progress: int,
) -> models.CompetencySnapshot:
    existing = (
        db.query(models.CompetencySnapshot)
        .filter(
            models.CompetencySnapshot.student_id == student_id,
            models.CompetencySnapshot.competency_id == competency_id,
        )
        .first()
    )
    if existing is None:
        snap = models.CompetencySnapshot(
            student_id=student_id,
            competency_id=competency_id,
            competency_name=competency_name,
            status=status,
            progress=progress,
        )
        db.add(snap)
        db.flush()
        return snap
    existing.status = status
    existing.progress = progress
    existing.competency_name = competency_name
    db.flush()
    return existing


# ---- Onboarding -----------------------------------------------------------


def save_onboarding(
    db: Session,
    *,
    student_id: str,
    learning_challenge: str,
    preferred_method: str,
    obstacle: str,
    goal: str,
) -> models.OnboardingAnswer:
    existing = (
        db.query(models.OnboardingAnswer)
        .filter(models.OnboardingAnswer.student_id == student_id)
        .first()
    )
    if existing is not None:
        existing.learning_challenge = learning_challenge
        existing.preferred_method = preferred_method
        existing.obstacle = obstacle
        existing.goal = goal
        db.flush()
        return existing
    ans = models.OnboardingAnswer(
        student_id=student_id,
        learning_challenge=learning_challenge,
        preferred_method=preferred_method,
        obstacle=obstacle,
        goal=goal,
    )
    db.add(ans)
    db.flush()
    return ans


# ---- Diagnostic -----------------------------------------------------------


def save_diagnostic_submission(
    db: Session,
    *,
    student_id: str,
    score: int,
    total: int,
    misconceptions_count: int,
    answers: list[dict],
) -> models.DiagnosticSubmission:
    sub = models.DiagnosticSubmission(
        student_id=student_id,
        score=score,
        total=total,
        misconceptions_count=misconceptions_count,
    )
    db.add(sub)
    db.flush()
    for a in answers:
        db.add(
            models.DiagnosticAnswer(
                submission_id=sub.id,
                question_id=a["question_id"],
                competency_id=a["competency_id"],
                selected_option_id=a["selected_option_id"],
                correct=a["correct"],
                misconception_tag=a.get("misconception_tag"),
            )
        )
    db.flush()
    return sub


# ---- Simulation -----------------------------------------------------------


def save_simulation_run(
    db: Session,
    *,
    student_id: str,
    competency_id: str,
    task_id: str,
    attempt: int,
    kp: float,
    ki: float,
    kd: float,
    stable: bool,
    overshoot: float,
    settling_time: float,
    rise_time: float,
    steady_state_error: float,
    requirements_met: bool,
    result: str,
    misconception: str | None,
) -> models.SimulationRun:
    run = models.SimulationRun(
        student_id=student_id,
        competency_id=competency_id,
        task_id=task_id,
        attempt=attempt,
        kp=kp,
        ki=ki,
        kd=kd,
        stable=stable,
        overshoot=overshoot,
        settling_time=settling_time,
        rise_time=rise_time,
        steady_state_error=steady_state_error,
        requirements_met=requirements_met,
        result=result,
        misconception=misconception,
    )
    db.add(run)
    db.flush()
    return run


def list_simulation_runs(
    db: Session, student_id: str, competency_id: str | None = None
) -> list[models.SimulationRun]:
    q = db.query(models.SimulationRun).filter(models.SimulationRun.student_id == student_id)
    if competency_id:
        q = q.filter(models.SimulationRun.competency_id == competency_id)
    return q.order_by(models.SimulationRun.id.desc()).all()


# ---- Transfer -------------------------------------------------------------


def save_transfer_evaluation(
    db: Session,
    *,
    student_id: str,
    competency_id: str,
    scenario_id: str,
    response_text: str,
    passed: bool,
    matched_count: int,
    min_required: int,
    feedback: str,
) -> models.TransferEvaluation:
    ev = models.TransferEvaluation(
        student_id=student_id,
        competency_id=competency_id,
        scenario_id=scenario_id,
        response_text=response_text,
        passed=passed,
        matched_count=matched_count,
        min_required=min_required,
        feedback=feedback,
    )
    db.add(ev)
    db.flush()
    return ev


# ---- Remediation ----------------------------------------------------------


def save_remediation_plan(
    db: Session,
    *,
    student_id: str,
    competency_id: str,
    detected_misconception: str | None,
    recommended_action: str,
    conceptual_focus: str,
    guided_question: str,
    consecutive_failures: int,
    total_attempts: int,
    summary_text: str,
    remediation_steps: list[str],
) -> models.RemediationPlan:
    plan = models.RemediationPlan(
        student_id=student_id,
        competency_id=competency_id,
        detected_misconception=detected_misconception,
        recommended_action=recommended_action,
        conceptual_focus=conceptual_focus,
        guided_question=guided_question,
        consecutive_failures=consecutive_failures,
        total_attempts=total_attempts,
        summary_text=summary_text,
        remediation_steps_json=json.dumps(remediation_steps),
    )
    db.add(plan)
    db.flush()
    return plan


# ---- Coach conversations --------------------------------------------------


def create_conversation(
    db: Session,
    *,
    student_id: str,
    competency_id: str | None,
    initial_mode: str,
) -> models.CoachConversation:
    conv = models.CoachConversation(
        student_id=student_id,
        competency_id=competency_id,
        initial_mode=initial_mode,
    )
    db.add(conv)
    db.flush()
    return conv


def add_message(
    db: Session,
    *,
    conversation_id: int,
    sender: str,
    text: str,
    mode: str | None = None,
    scaffolding_level: str | None = None,
) -> models.CoachMessage:
    msg = models.CoachMessage(
        conversation_id=conversation_id,
        sender=sender,
        text=text,
        mode=mode,
        scaffolding_level=scaffolding_level,
    )
    db.add(msg)
    db.flush()
    return msg


def get_latest_conversation(db: Session, student_id: str) -> models.CoachConversation | None:
    return (
        db.query(models.CoachConversation)
        .filter(models.CoachConversation.student_id == student_id)
        .order_by(models.CoachConversation.id.desc())
        .first()
    )


def list_conversations(db: Session, student_id: str) -> list[models.CoachConversation]:
    return (
        db.query(models.CoachConversation)
        .filter(models.CoachConversation.student_id == student_id)
        .order_by(models.CoachConversation.id.desc())
        .all()
    )


# ---- Evidence events ------------------------------------------------------


def append_evidence_event(
    db: Session,
    *,
    student_id: str,
    event_type: str,
    title: str,
    detail: str,
    result: str = "INFO",
    competency_id: str | None = None,
    timestamp: datetime | None = None,
) -> models.EvidenceEvent:
    ev = models.EvidenceEvent(
        student_id=student_id,
        event_type=event_type,
        title=title,
        detail=detail,
        result=result,
        competency_id=competency_id,
        timestamp=timestamp or datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(ev)
    db.flush()
    return ev


def list_evidence_events(
    db: Session, student_id: str, newest_first: bool = True
) -> list[models.EvidenceEvent]:
    q = db.query(models.EvidenceEvent).filter(models.EvidenceEvent.student_id == student_id)
    if newest_first:
        q = q.order_by(models.EvidenceEvent.id.desc())
    else:
        q = q.order_by(models.EvidenceEvent.id.asc())
    return q.all()
