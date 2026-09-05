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
    role: str = "student",
    university_id: int | None = None,
    email_verified: bool = False,
) -> models.User:
    user = models.User(
        email=_normalize_email(email),
        username=_normalize_username(username),
        name=name,
        password_hash=password_hash,
        role=role,
        university_id=university_id,
        email_verified=email_verified,
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


def set_user_verification(
    db: Session,
    *,
    user: models.User,
    code_hash: str,
    expires_at: datetime,
    sent_at: datetime,
) -> None:
    """Store a fresh (unexpired) verification code for a user."""
    user.email_verified = False
    user.email_verification_code_hash = code_hash
    user.email_verification_expires_at = expires_at
    user.email_verification_sent_at = sent_at
    db.flush()


def mark_user_verified(db: Session, *, user: models.User) -> None:
    """Clear the verification code and mark the account as verified."""
    user.email_verified = True
    user.email_verification_code_hash = None
    user.email_verification_expires_at = None
    user.email_verification_sent_at = None
    db.flush()


def set_user_password_reset(
    db: Session,
    *,
    user: models.User,
    code_hash: str,
    expires_at: datetime,
    sent_at: datetime,
) -> None:
    """Store a fresh (unexpired) password-reset code for a user."""
    user.password_reset_code_hash = code_hash
    user.password_reset_expires_at = expires_at
    user.password_reset_sent_at = sent_at
    db.flush()


def clear_user_password_reset(db: Session, *, user: models.User) -> None:
    """Invalidate any pending password-reset code (after use/expiry)."""
    user.password_reset_code_hash = None
    user.password_reset_expires_at = None
    user.password_reset_sent_at = None
    db.flush()


def bump_token_version(db: Session, *, user: models.User) -> None:
    """Invalidate every previously issued JWT for this user."""
    user.token_version += 1
    db.flush()


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
    university_id: int | None = None,
) -> models.Student:
    student = models.Student(
        student_id=student_id,
        user_id=user_id,
        display_name=display_name,
        course_code=course_code,
        course_title=course_title,
        overall_progress=overall_progress,
        university_id=university_id,
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


# ---- Organization (university identity / multi-tenant) ----------------------


def get_university_by_id(db: Session, university_id: int) -> models.University | None:
    return db.query(models.University).filter(models.University.id == university_id).first()


def get_university_by_code(db: Session, code: str) -> models.University | None:
    return (
        db.query(models.University).filter(models.University.code == code.strip().upper()).first()
    )


def list_universities(db: Session) -> list[models.University]:
    return db.query(models.University).order_by(models.University.name).all()


def create_university(
    db: Session, *, code: str, name: str, email_domains: list[str] | None = None
) -> models.University:
    import json

    university = models.University(
        code=code.strip().upper(),
        name=name.strip(),
        email_domains=json.dumps(email_domains or []),
        is_active=True,
    )
    db.add(university)
    db.flush()
    return university


def get_faculties_for_university(db: Session, university_id: int) -> list[models.Faculty]:
    return (
        db.query(models.Faculty)
        .filter(models.Faculty.university_id == university_id)
        .order_by(models.Faculty.name)
        .all()
    )


def create_faculty(db: Session, *, university_id: int, code: str, name: str) -> models.Faculty:
    faculty = models.Faculty(
        university_id=university_id, code=code.strip().upper(), name=name.strip()
    )
    db.add(faculty)
    db.flush()
    return faculty


def get_departments_for_faculty(db: Session, faculty_id: int) -> list[models.Department]:
    return (
        db.query(models.Department)
        .filter(models.Department.faculty_id == faculty_id)
        .order_by(models.Department.name)
        .all()
    )


def create_department(db: Session, *, faculty_id: int, code: str, name: str) -> models.Department:
    dept = models.Department(faculty_id=faculty_id, code=code.strip().upper(), name=name.strip())
    db.add(dept)
    db.flush()
    return dept


def get_courses_for_department(db: Session, department_id: int) -> list[models.Course]:
    return (
        db.query(models.Course)
        .filter(models.Course.department_id == department_id)
        .order_by(models.Course.code)
        .all()
    )


def create_course(
    db: Session,
    *,
    department_id: int,
    code: str,
    title: str,
    credits: int = 3,
) -> models.Course:
    course = models.Course(
        department_id=department_id,
        code=code.strip().upper(),
        title=title.strip(),
        credits=credits,
    )
    db.add(course)
    db.flush()
    return course


def get_sections_for_course(db: Session, course_id: int) -> list[models.Section]:
    return (
        db.query(models.Section)
        .filter(models.Section.course_id == course_id)
        .order_by(models.Section.term, models.Section.code)
        .all()
    )


def create_section(
    db: Session,
    *,
    course_id: int,
    term: str,
    code: str,
    instructor_user_id: int | None = None,
) -> models.Section:
    section = models.Section(
        course_id=course_id,
        term=term.strip().upper(),
        code=code.strip().upper(),
        instructor_user_id=instructor_user_id,
    )
    db.add(section)
    db.flush()
    return section


def get_section_by_id(db: Session, section_id: int) -> models.Section | None:
    return db.query(models.Section).filter(models.Section.id == section_id).first()


def enroll_student_in_section(
    db: Session, *, student_id: str, section_id: int
) -> models.Enrollment:
    existing = (
        db.query(models.Enrollment)
        .filter(
            models.Enrollment.student_id == student_id,
            models.Enrollment.section_id == section_id,
        )
        .first()
    )
    if existing is not None:
        return existing
    enrollment = models.Enrollment(student_id=student_id, section_id=section_id, status="active")
    db.add(enrollment)
    db.flush()
    return enrollment


def unenroll_student_from_section(db: Session, *, student_id: str, section_id: int) -> bool:
    deleted = (
        db.query(models.Enrollment)
        .filter(
            models.Enrollment.student_id == student_id,
            models.Enrollment.section_id == section_id,
        )
        .delete()
    )
    db.flush()
    return deleted > 0


def get_students_in_section(db: Session, section_id: int) -> list[models.Student]:
    return (
        db.query(models.Student)
        .join(models.Enrollment, models.Enrollment.student_id == models.Student.student_id)
        .filter(models.Enrollment.section_id == section_id)
        .order_by(models.Student.display_name)
        .all()
    )


def get_sections_for_student(db: Session, student_id: str) -> list[models.Section]:
    return (
        db.query(models.Section)
        .join(models.Enrollment, models.Enrollment.section_id == models.Section.id)
        .filter(models.Enrollment.student_id == student_id)
        .all()
    )


def get_sections_for_instructor(db: Session, instructor_user_id: int) -> list[models.Section]:
    return (
        db.query(models.Section)
        .filter(models.Section.instructor_user_id == instructor_user_id)
        .order_by(models.Section.term, models.Section.code)
        .all()
    )


def get_students_for_instructor(db: Session, instructor_user_id: int) -> list[models.Student]:
    """All distinct students enrolled in any section the instructor teaches."""
    section_ids = [s.id for s in get_sections_for_instructor(db, instructor_user_id)]
    if not section_ids:
        return []
    return (
        db.query(models.Student)
        .join(models.Enrollment, models.Enrollment.student_id == models.Student.student_id)
        .filter(models.Enrollment.section_id.in_(section_ids))
        .distinct()
        .order_by(models.Student.display_name)
        .all()
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


# ---- Audit log -------------------------------------------------------------

_MAX_DETAIL_LENGTH = 2000


def add_audit_log(
    db: Session,
    *,
    actor_user_id: int | None,
    actor_role: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: str = "",
    ip_address: str | None = None,
    outcome: str = "OK",
    university_id: int | None = None,
) -> models.AuditLog:
    """Record one security-relevant event in the audit trail.

    Caller commits (the callers that write audit rows already own a
    transaction). ``detail`` is truncated to keep the log bounded.
    """
    entry = models.AuditLog(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail[:_MAX_DETAIL_LENGTH],
        ip_address=ip_address,
        outcome=outcome,
        university_id=university_id,
    )
    db.add(entry)
    db.flush()
    return entry
