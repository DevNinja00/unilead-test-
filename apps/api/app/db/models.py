"""SQLAlchemy ORM models for the Unilead platform.

Schema overview:

  University            - tenant org (super_admin creates; users/students belong)
  Faculty               - university -> faculty
  Department            - faculty -> department
  Course                - department -> course
  Section               - course -> section (one instructor)
  Enrollment            - student <-> section membership (access boundary)
  User                  - auth account (email + password hash + token version)
  Student              - one User → many Students (currently 1:1 in practice)
  CompetencySnapshot   - per-student, per-competency status + progress
  OnboardingAnswer     - one row per student (set once at onboarding)
  DiagnosticSubmission  - one row per diagnostic quiz submission (1-5 answers)
  DiagnosticAnswer     - one row per question answered in a submission
  SimulationRun        - one row per PID simulation run
  TransferEvaluation   - one row per transfer task submission
  RemediationPlan      - one row per remediation plan generated
  CoachConversation    - one row per coach session (group of turns)
  CoachMessage         - one row per message in a conversation
  EvidenceEvent        - chronological feed entry (one per notable event)
  AuditLog             - security-relevant actions (auth + org + instructor)
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    """Timezone-naive UTC now — matches SQLite's default datetime format."""
    return datetime.now(UTC).replace(tzinfo=None)


class University(Base):
    """A tenant organization (university). Everything hangs off this."""

    __tablename__ = "universities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email_domains: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    faculties: Mapped[list[Faculty]] = relationship(
        "Faculty", back_populates="university", cascade="all, delete-orphan"
    )


class Faculty(Base):
    """A faculty within a university (e.g. Engineering)."""

    __tablename__ = "faculties"
    __table_args__ = (
        UniqueConstraint("university_id", "code", name="uq_faculties_university_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(
        ForeignKey("universities.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    university: Mapped[University] = relationship("University", back_populates="faculties")
    departments: Mapped[list[Department]] = relationship(
        "Department", back_populates="faculty", cascade="all, delete-orphan"
    )


class Department(Base):
    """A department within a faculty (e.g. Mechanical Engineering)."""

    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("faculty_id", "code", name="uq_departments_faculty_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculties.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    faculty: Mapped[Faculty] = relationship("Faculty", back_populates="departments")
    courses: Mapped[list[Course]] = relationship(
        "Course", back_populates="department", cascade="all, delete-orphan"
    )


class Course(Base):
    """A course within a department (e.g. MEC271 Automatic Control)."""

    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("department_id", "code", name="uq_courses_department_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    department: Mapped[Department] = relationship("Department", back_populates="courses")
    sections: Mapped[list[Section]] = relationship(
        "Section", back_populates="course", cascade="all, delete-orphan"
    )


class Section(Base):
    """One teaching section of a course, taught by one instructor."""

    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("course_id", "term", "code", name="uq_sections_course_term_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    term: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    instructor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    course: Mapped[Course] = relationship("Course", back_populates="sections")
    instructor: Mapped[User | None] = relationship("User", foreign_keys=[instructor_user_id])
    enrollments: Mapped[list[Enrollment]] = relationship(
        "Enrollment", back_populates="section", cascade="all, delete-orphan"
    )


class Enrollment(Base):
    """Student ↔ section membership — the access boundary for course data."""

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "section_id", name="uq_enrollments_student_section"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("students.student_id"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    student: Mapped[Student] = relationship("Student", back_populates="enrollments")
    section: Mapped[Section] = relationship("Section", back_populates="enrollments")


class User(Base):
    """Auth account — email + hashed password. One user can own many students."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="student")
    # "student" or "instructor" — gates access to instructor endpoints

    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # nullable so seeded demo accounts (without passwords) can exist for read-only views

    # Email verification — set once at signup via a confirmation code.
    # The plaintext code is never stored: only its SHA-256 hash, so a DB
    # leak can't be replayed without the code that was emailed to the user.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verification_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_verification_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Password reset — same pattern as verification: a hashed, expiring code.
    password_reset_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_reset_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_password_change_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Session/token lifecycle: every JWT carries this number at issue time.
    # Bumping it (e.g. after a password reset) revokes every previously
    # issued token for the account in one step — no per-token blacklist.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Tenant membership: the university this account belongs to (null until
    # the default organization backfill / explicit provisioning assigns one).
    university_id: Mapped[int | None] = mapped_column(
        ForeignKey("universities.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    students: Mapped[list[Student]] = relationship("Student", back_populates="user")


class Student(Base):
    """A learner record. ``student_id`` is the stable public identifier
    used by the AI Education engine (e.g. ``api-gateway-student``)."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    course_code: Mapped[str] = mapped_column(String(32), nullable=False, default="MEC271")
    course_title: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Automatic Control"
    )
    overall_progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Tenant membership: the university this learner belongs to.
    university_id: Mapped[int | None] = mapped_column(
        ForeignKey("universities.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="students")
    enrollments: Mapped[list[Enrollment]] = relationship(
        "Enrollment", back_populates="student", cascade="all, delete-orphan"
    )
    sections: Mapped[list[Section]] = relationship(
        "Section",
        secondary="enrollments",
        primaryjoin="Enrollment.student_id == Student.student_id",
        secondaryjoin="Enrollment.section_id == Section.id",
        viewonly=True,
    )
    competencies: Mapped[list[CompetencySnapshot]] = relationship(
        "CompetencySnapshot", back_populates="student", cascade="all, delete-orphan"
    )
    onboarding: Mapped[OnboardingAnswer | None] = relationship(
        "OnboardingAnswer", back_populates="student", uselist=False, cascade="all, delete-orphan"
    )
    diagnostic_submissions: Mapped[list[DiagnosticSubmission]] = relationship(
        "DiagnosticSubmission", back_populates="student", cascade="all, delete-orphan"
    )
    simulation_runs: Mapped[list[SimulationRun]] = relationship(
        "SimulationRun", back_populates="student", cascade="all, delete-orphan"
    )
    transfer_evaluations: Mapped[list[TransferEvaluation]] = relationship(
        "TransferEvaluation", back_populates="student", cascade="all, delete-orphan"
    )
    remediation_plans: Mapped[list[RemediationPlan]] = relationship(
        "RemediationPlan", back_populates="student", cascade="all, delete-orphan"
    )
    coach_conversations: Mapped[list[CoachConversation]] = relationship(
        "CoachConversation", back_populates="student", cascade="all, delete-orphan"
    )
    evidence_events: Mapped[list[EvidenceEvent]] = relationship(
        "EvidenceEvent", back_populates="student", cascade="all, delete-orphan"
    )


class CompetencySnapshot(Base):
    """Per-student, per-competency status + progress (current view)."""

    __tablename__ = "competency_snapshots"
    __table_args__ = (
        UniqueConstraint("student_id", "competency_id", name="uq_student_competency"),
        Index("ix_cs_student_status", "student_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("students.student_id"), nullable=False, index=True
    )
    competency_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    competency_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    student: Mapped[Student] = relationship("Student", back_populates="competencies")


class OnboardingAnswer(Base):
    """The four onboarding answers. One row per student."""

    __tablename__ = "onboarding_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("students.student_id"), unique=True, nullable=False
    )
    learning_challenge: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_method: Mapped[str] = mapped_column(Text, nullable=False)
    obstacle: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    student: Mapped[Student] = relationship("Student", back_populates="onboarding")


class DiagnosticSubmission(Base):
    """One diagnostic quiz submission (1-5 answers)."""

    __tablename__ = "diagnostic_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("students.student_id"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # correct count
    total: Mapped[int] = mapped_column(Integer, nullable=False)  # total questions
    misconceptions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    student: Mapped[Student] = relationship("Student", back_populates="diagnostic_submissions")
    answers: Mapped[list[DiagnosticAnswer]] = relationship(
        "DiagnosticAnswer", back_populates="submission", cascade="all, delete-orphan"
    )


class DiagnosticAnswer(Base):
    """One answer within a diagnostic submission."""

    __tablename__ = "diagnostic_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_submissions.id"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(String(32), nullable=False)
    competency_id: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_option_id: Mapped[str] = mapped_column(String(32), nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    misconception_tag: Mapped[str | None] = mapped_column(String(128), nullable=True)

    submission: Mapped[DiagnosticSubmission] = relationship(
        "DiagnosticSubmission", back_populates="answers"
    )


class SimulationRun(Base):
    """One PID simulation run — gains, metrics, result, misconception."""

    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("students.student_id"), nullable=False, index=True
    )
    competency_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, default="pid-001")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)

    # Gains
    kp: Mapped[float] = mapped_column(Float, nullable=False)
    ki: Mapped[float] = mapped_column(Float, nullable=False)
    kd: Mapped[float] = mapped_column(Float, nullable=False)

    # Metrics
    stable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    overshoot: Mapped[float] = mapped_column(Float, nullable=False)
    settling_time: Mapped[float] = mapped_column(Float, nullable=False)
    rise_time: Mapped[float] = mapped_column(Float, nullable=False)
    steady_state_error: Mapped[float] = mapped_column(Float, nullable=False)

    # Outcome
    requirements_met: Mapped[bool] = mapped_column(Boolean, nullable=False)
    result: Mapped[str] = mapped_column(String(8), nullable=False)  # PASS / FAIL
    misconception: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    student: Mapped[Student] = relationship("Student", back_populates="simulation_runs")


class TransferEvaluation(Base):
    """One transfer task submission — scenario + response + evaluation."""

    __tablename__ = "transfer_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("students.student_id"), nullable=False, index=True
    )
    competency_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_required: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    student: Mapped[Student] = relationship("Student", back_populates="transfer_evaluations")


class RemediationPlan(Base):
    """One remediation plan generated for a failing competency."""

    __tablename__ = "remediation_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("students.student_id"), nullable=False, index=True
    )
    competency_id: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_misconception: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recommended_action: Mapped[str] = mapped_column(String(64), nullable=False)
    conceptual_focus: Mapped[str] = mapped_column(Text, nullable=False)
    guided_question: Mapped[str] = mapped_column(Text, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    remediation_steps_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    student: Mapped[Student] = relationship("Student", back_populates="remediation_plans")


class CoachConversation(Base):
    """A coach conversation (group of turns). One student may have many."""

    __tablename__ = "coach_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("students.student_id"), nullable=False, index=True
    )
    competency_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    initial_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="LEARN")
    finished: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    student: Mapped[Student] = relationship("Student", back_populates="coach_conversations")
    messages: Mapped[list[CoachMessage]] = relationship(
        "CoachMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="CoachMessage.id",
    )


class CoachMessage(Base):
    """One message in a coach conversation (student or coach)."""

    __tablename__ = "coach_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("coach_conversations.id"), nullable=False, index=True
    )
    sender: Mapped[str] = mapped_column(String(16), nullable=False)  # "student" / "coach"
    text: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scaffolding_level: Mapped[str | None] = mapped_column(String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    conversation: Mapped[CoachConversation] = relationship(
        "CoachConversation", back_populates="messages"
    )


class EvidenceEvent(Base):
    """One event on a student's evidence timeline."""

    __tablename__ = "evidence_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("students.student_id"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    competency_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(String(8), nullable=False, default="INFO")

    student: Mapped[Student] = relationship("Student", back_populates="evidence_events")


class AuditLog(Base):
    """Security-relevant action log.

    Records who did what, when, and with what outcome, for auth and
    instructor-read events. ``actor_user_id`` is nullable because events
    like failed logins may not resolve to a known user.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False, default="student")
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="OK")

    # Org scope: the university within which the event occurred (nullable
    # for global/system events that have no tenant).
    university_id: Mapped[int | None] = mapped_column(
        ForeignKey("universities.id"), nullable=True, index=True
    )
