"""Per-student AI Education manager pool.

Each logged-in student needs its own AI Education state — the
``StudentModelManager`` keeps competency graph, evidence history, etc. in
memory. The Compass routes no longer share one global manager; instead,
each request resolves the manager from the current user's ``student_id``.

The pool is a plain dict keyed by ``student_id`` with LRU eviction
(max 200 entries). It lives on ``app.state.ai_education_managers``.
The pool is in-process — when the server restarts, the in-memory
managers are rebuilt from the DB on next access
(see ``load_manager_for_student``).

The DB is the source of truth for *what* the student has demonstrated.
The manager is rebuilt from the DB by re-recording every simulation run
as PracticalEvidence, then re-applying the latest diagnostic placement
and each transfer promotion to match the persisted Compass snapshot.
(Coach messages don't carry evidence in the AI Education sense.)
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import TYPE_CHECKING

from ai_education import (
    AICoachOrchestrator,
    EvidenceReasoningEngine,
    StudentModelManager,
)
from ai_education.api.router import APIGateway
from ai_education.domain.enums import CompetencyState
from fastapi import Request

_log = logging.getLogger("unilead.manager_pool")

if TYPE_CHECKING:
    pass

_MAX_POOL_SIZE = 200


class _BoundedManagerPool(OrderedDict):
    """LRU-bounded dict for the in-memory manager pool."""

    def __init__(self, maxsize: int = _MAX_POOL_SIZE):
        super().__init__()
        self._maxsize = maxsize

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self._maxsize:
            self.popitem(last=False)


def get_or_create_manager(request: Request, student_id: str) -> StudentModelManager:
    """Return the in-memory AI Education manager for ``student_id``,
    creating it from the DB state if this is the first request.
    """
    pool = getattr(request.app.state, "ai_education_managers", None)
    if pool is None:
        pool = _BoundedManagerPool()
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

    The latest diagnostic placement and every transfer promotion are then
    re-applied so the rebuilt manager matches the persisted Compass state.
    """
    try:
        from ai_education.domain.evidence import (
            PIDParameters,
            PracticalEvidence,
            SimulationMetrics,
        )

        from ..db import SessionLocal, models
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

            # The DiagnosticEngine writes state directly (without evidence),
            # so a fresh manager would otherwise lose that placement. Re-apply
            # the most recent diagnostic submission so the manager matches the
            # persisted Compass snapshot.
            _replay_latest_diagnostic(db, student_id, manager)

            # Transfer evaluations are likewise not carried as PracticalEvidence
            # (no PID metrics shape); re-apply their promotions instead.
            _replay_transfer_promotions(db, student_id, manager)
        finally:
            db.close()
    except Exception:
        _log.warning("Failed to replay evidence from DB for student=%s", student_id, exc_info=True)


def _replay_latest_diagnostic(db, student_id: str, manager: StudentModelManager) -> None:
    """Re-apply the most recent diagnostic placement onto ``manager``.

    Mirrors DiagnosticEngine.evaluate_diagnostic semantics using the
    persisted per-answer correctness: all correct → DEMONSTRATED, partially
    correct → DEVELOPING, none → NOT_DEMONSTRATED, then enforces the
    prerequisite safety rule in topological order.
    """
    from ai_education.domain.diagnostic import DiagnosticEngine

    from ..db import models
    from ..services.ai_education_bridge import compass_id_to_mec271

    sub = (
        db.query(models.DiagnosticSubmission)
        .filter(models.DiagnosticSubmission.student_id == student_id)
        .order_by(models.DiagnosticSubmission.id.desc())
        .first()
    )
    if sub is None:
        return

    try:
        comps = (
            db.query(models.DiagnosticAnswer)
            .filter(models.DiagnosticAnswer.submission_id == sub.id)
            .all()
        )

        # Aggregate per-competency correctness across the submission.
        raw_correct: dict[str, tuple[int, int]] = {}
        for a in comps:
            mec271_id = compass_id_to_mec271(a.competency_id)
            correct, total = raw_correct.get(mec271_id, (0, 0))
            raw_correct[mec271_id] = (correct + (1 if a.correct else 0), total + 1)

        raw: dict[str, CompetencyState] = {}
        for mec271_id, (correct, total) in raw_correct.items():
            if correct == 0:
                raw[mec271_id] = CompetencyState.NOT_DEMONSTRATED
            elif correct == total:
                raw[mec271_id] = CompetencyState.DEMONSTRATED
            else:
                raw[mec271_id] = CompetencyState.DEVELOPING

        # Enforce the prerequisite safety rule in topological order, exactly
        # like DiagnosticEngine.evaluate_diagnostic.
        topo_order = DiagnosticEngine._topological_order(manager.graph)
        final: dict[str, CompetencyState] = {}
        for node_id in topo_order:
            node = manager.graph.get_node(node_id)
            if node is None:
                continue
            prerequisites_ok = all(
                final.get(parent_id) == CompetencyState.DEMONSTRATED
                for parent_id in node.parent_ids
            )
            if not prerequisites_ok:
                final[node_id] = CompetencyState.NOT_DEMONSTRATED
            elif node_id in raw:
                final[node_id] = raw[node_id]

        if not final:
            return
        for node_id, state in final.items():
            record = manager.profile.competencies.get(node_id)
            if record is not None:
                record.state = state
    except Exception:
        _log.warning(
            "Failed to replay diagnostic placement for student=%s", student_id, exc_info=True
        )


def _replay_transfer_promotions(db, student_id: str, manager: StudentModelManager) -> None:
    """Re-apply transfer-evaluation promotions onto ``manager``.

    Mirrors transfer_service.evaluate_response: each passed evaluation moves
    the record one step NOT_DEMONSTRATED → DEVELOPING → DEMONSTRATED.
    """
    from ..db import models
    from ..services.ai_education_bridge import compass_id_to_mec271

    evals = (
        db.query(models.TransferEvaluation)
        .filter(models.TransferEvaluation.student_id == student_id)
        .order_by(models.TransferEvaluation.id.asc())
        .all()
    )
    for ev in evals:
        if not ev.passed:
            continue
        mec271_id = compass_id_to_mec271(ev.competency_id)
        record = manager.profile.competencies.get(mec271_id)
        if record is None:
            continue
        if record.state == CompetencyState.NOT_DEMONSTRATED:
            record.state = CompetencyState.DEVELOPING
        elif record.state == CompetencyState.DEVELOPING:
            record.state = CompetencyState.DEMONSTRATED


def clear_manager_from_pool(request: Request, student_id: str) -> None:
    """Drop a student's manager from the in-memory pool (e.g. on logout)."""
    pool = getattr(request.app.state, "ai_education_managers", None)
    if pool is None:
        return
    pool.pop(student_id, None)
