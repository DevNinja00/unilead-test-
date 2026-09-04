"""Per-student AI Education manager pool.

Each logged-in student needs its own AI Education state — the
``StudentModelManager`` keeps competency graph, evidence history, etc. in
memory. The Compass routes no longer share one global manager; instead,
each request resolves the manager from the current user's ``student_id``.

The pool is a plain dict keyed by ``student_id``. It lives on
``app.state.ai_education_managers``. The pool is in-process — when the
server restarts, the in-memory managers are rebuilt from the DB on next
access (see ``load_manager_for_student``).

The DB is the source of truth for *what* the student has demonstrated.
The manager is rebuilt from the DB by re-recording every simulation_run
and transfer_evaluation as PracticalEvidence. (Diagnostic and coach
messages don't carry evidence in the AI Education sense — only simulation
and transfer do.)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from fastapi import Request

_log = logging.getLogger("unilead.manager_pool")

from ai_education import (
    AICoachOrchestrator,
    EvidenceReasoningEngine,
    StudentModelManager,
)
from ai_education.api.router import APIGateway
from ai_education.domain.enums import CompetencyState
from ai_education.llm.base import LLMProvider

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_or_create_manager(request: Request, student_id: str) -> StudentModelManager:
    """Return the in-memory AI Education manager for ``student_id``,
    creating it from the DB state if this is the first request.
    """
    pool = getattr(request.app.state, "ai_education_managers", None)
    if pool is None:
        pool = {}
        request.app.state.ai_education_managers = pool

    if student_id in pool:
        return pool[student_id]

    # Create a fresh manager (all competencies NOT_DEMONSTRATED)
    manager = StudentModelManager.create_new_student(student_id, course_id="MEC271")

    # Replay every persisted simulation run + transfer evaluation so the
    # manager's evidence_history matches the DB.
    _replay_evidence_from_db(request, student_id, manager)

    pool[student_id] = manager
    return manager


def get_or_create_gateway(request: Request, student_id: str) -> APIGateway:
    """Return an AI Education gateway wired for the given student.

    The LLM provider is the global one (set once at startup) — but the
    student_manager + orchestrator + reasoning_engine are per-student.
    """
    manager = get_or_create_manager(request, student_id)
    provider = getattr(request.app.state, "ai_education_llm_provider", None)
    if provider is None:
        # Fall back to mock if no provider was set (defensive)
        from ai_education.llm.config import LLMConfig
        from ai_education.llm.mock import MockLLMProvider

        provider = MockLLMProvider(LLMConfig(provider_type="mock", model_name="api-gateway"))

    orchestrator = AICoachOrchestrator(student_manager=manager, llm_provider=provider)
    reasoning_engine = EvidenceReasoningEngine()
    return APIGateway(
        student_manager=manager,
        orchestrator=orchestrator,
        reasoning_engine=reasoning_engine,
    )


def _replay_evidence_from_db(
    request: Request, student_id: str, manager: StudentModelManager
) -> None:
    """Re-record every persisted simulation run as PracticalEvidence so the
    in-memory manager matches the DB after a restart.

    For each simulation_run row:
      - Build a StepResponseTelemetry from the stored metrics.
      - Build PracticalEvidence with the same attempt number + result.
      - Record it on the matching CompetencyRecord.

    Transfer evaluations don't carry PIDParameters/metrics in the same
    shape, so they're not replayed here — the Compass-side evidence
    timeline (in the DB) is the source of truth for those.
    """
    try:
        from ..db import SessionLocal, crud, models
        from ai_education.domain.evidence import (
            PIDParameters,
            PracticalEvidence,
            SimulationMetrics,
        )
        from ai_education.robotics.telemetry import (
            StepResponseTelemetry,
            TelemetryThresholds,
        )
        from ..services.ai_education_bridge import compass_id_to_mec271

        db = SessionLocal()
        try:
            runs = (
                db.query(models.SimulationRun)
                .filter(models.SimulationRun.student_id == student_id)
                .order_by(models.SimulationRun.id.asc())
                .all()
            )
            for run in runs:
                mec271_id = compass_id_to_mec271(run.competency_id)
                record = manager.profile.competencies.get(mec271_id)
                if record is None:
                    continue
                telemetry = StepResponseTelemetry(
                    overshoot_pct=run.overshoot,
                    settling_time_sec=run.settling_time,
                    rise_time_sec=run.rise_time,
                    steady_state_error=run.steady_state_error,
                    is_stable=run.stable,
                )
                evidence = PracticalEvidence(
                    task_id=run.task_id,
                    attempt=run.attempt,
                    parameters=PIDParameters(kp=run.kp, ki=run.ki, kd=run.kd),
                    metrics=SimulationMetrics(
                        overshoot=run.overshoot,
                        settling_time=run.settling_time,
                        steady_state_error=run.steady_state_error,
                    ),
                    stable=run.stable,
                    requirements_met=run.requirements_met,
                    result=run.result,
                )
                record.record_evidence(evidence)
                # Promote state to match what was earned
                if run.requirements_met:
                    # Two passes → DEMONSTRATED; we don't know how many
                    # consecutive passes happened, so just trust the DB.
                    if record.state == CompetencyState.NOT_DEMONSTRATED:
                        record.state = CompetencyState.DEVELOPING
                    elif record.state == CompetencyState.DEVELOPING:
                        record.state = CompetencyState.DEMONSTRATED
        finally:
            db.close()
    except Exception:
        _log.warning("Failed to replay evidence from DB for student=%s", student_id, exc_info=True)


def clear_manager_from_pool(request: Request, student_id: str) -> None:
    """Drop a student's manager from the in-memory pool (e.g. on logout)."""
    pool = getattr(request.app.state, "ai_education_managers", None)
    if pool is None:
        return
    pool.pop(student_id, None)
