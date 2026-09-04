"""Bridge between the Compass MVP state and the AI Education engine.

The Compass MVP (originally Platform/backend) keeps its student state in
``student_state.py`` as a plain Python dict, with competency IDs like
``"feedback-fundamentals"``. The AI Education engine (``services/ai_education``)
keeps its own state in a ``StudentModelManager`` (Pydantic), with competency
IDs like ``"MEC271-FB"``. The two state stores must be kept in sync so the
existing Compass routes (``/api/competencies``, ``/api/progress``) reflect
what the AI Education engines actually do.

This module is the only place that knows about both worlds. Everything else
in ``services/`` talks to either Compass state or the AI Education gateway —
never both.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import Request

from .mock_data import INITIAL_COMPETENCIES

_log = logging.getLogger("unilead.ai_education_bridge")

if TYPE_CHECKING:
    from ai_education.api.router import APIGateway

# --- Competency ID mapping ------------------------------------------------
# Compass IDs (kebab-case, frontend-facing) ↔ MEC271 node IDs (AI Education).
COMPASS_TO_MEC271: dict[str, str] = {
    "feedback-fundamentals": "MEC271-FB",
    "pid-fundamentals": "MEC271-PID-FUND",
    "pid-reasoning": "MEC271-PID-REASON",
    "pid-tuning": "MEC271-PID-TUNE",
    "response-analysis": "MEC271-RESP-ANALYSIS",
}
MEC271_TO_COMPASS: dict[str, str] = {v: k for k, v in COMPASS_TO_MEC271.items()}

# --- Status mapping -------------------------------------------------------
# AI Education CompetencyState (UPPERCASE) ↔ Compass status (lowercase).
# Compass has one extra status ("needs_practice") that AI Education treats as
# "developing with a high failure rate" — we synthesise it from the reasoning
# engine's consecutive-failure count.
STATE_TO_COMPASS = {
    "NOT_DEMONSTRATED": "not_started",
    "DEVELOPING": "developing",
    "DEMONSTRATED": "demonstrated",
    "MASTERED": "demonstrated",  # Compass has no "mastered" — collapse to demonstrated
}

# --- Public helpers -------------------------------------------------------

_KNOWN_COMPASS_IDS = set(COMPASS_TO_MEC271.keys())


def is_valid_competency_id(compass_id: str) -> bool:
    """Check whether a competency_id is a known Compass competency."""
    return compass_id in _KNOWN_COMPASS_IDS


def get_gateway(request: Request, student_id: str | None = None) -> APIGateway:
    """Return the AI Education gateway for ``student_id``.

    If ``student_id`` is None, falls back to the legacy default gateway on
    ``app.state.ai_education_gateway`` (used by the legacy /api/ai-education/*
    routes). For Compass routes, the caller should pass the current user's
    student_id, which resolves a per-student gateway from the pool.
    """
    if student_id is None:
        # Legacy path: use the default singleton.
        gateway = getattr(request.app.state, "ai_education_gateway", None)
        if gateway is None:  # pragma: no cover — defensive
            from fastapi import HTTPException

            raise HTTPException(
                status_code=503,
                detail="AI Education gateway is not initialised on the server.",
            )
        return gateway

    # Per-user path: resolve from the pool (creates one if needed).
    from .manager_pool import get_or_create_gateway

    return get_or_create_gateway(request, student_id)


def compass_id_to_mec271(compass_id: str) -> str:
    """Translate a Compass competency id to its MEC271 node id."""
    return COMPASS_TO_MEC271.get(compass_id, compass_id)


def mec271_id_to_compass(mec271_id: str) -> str:
    """Translate an MEC271 node id back to its Compass id."""
    return MEC271_TO_COMPASS.get(mec271_id, mec271_id)


def compass_status_from_manager(compass_id: str, gateway: APIGateway) -> str:
    """Look up the current Compass status for ``compass_id`` based on the
    AI Education manager's profile, deriving ``needs_practice`` from the
    reasoning engine's consecutive-failure count.
    """
    mec271_id = compass_id_to_mec271(compass_id)
    manager = gateway.student_manager
    record = manager.profile.competencies.get(mec271_id)
    if record is None:
        return "not_started"

    state_name = record.state.name  # e.g. "DEVELOPING"
    base = STATE_TO_COMPASS.get(state_name, "not_started")

    # "needs_practice" is a Compass-only concept: ≥2 consecutive failures on
    # a competency that's still developing.
    if base == "developing":
        from ai_education.reasoning.engine import EvidenceReasoningEngine

        reasoning = EvidenceReasoningEngine()
        summary = reasoning.analyze_competency_evidence(
            student_id=manager.profile.student_id,
            competency_id=mec271_id,
            manager=manager,
        )
        if summary.consecutive_failures >= 2:
            return "needs_practice"

    return base


def compass_progress_from_manager(compass_id: str, gateway: APIGateway) -> int:
    """Derive a 0-100 progress number from the AI Education record state and
    evidence history. Used to refresh the Compass ``student_state`` after a
    simulation or transfer event.
    """
    mec271_id = compass_id_to_mec271(compass_id)
    manager = gateway.student_manager
    record = manager.profile.competencies.get(mec271_id)
    if record is None:
        return 0

    state = record.state.name
    passes = sum(1 for e in record.evidence_history if e.requirements_met)
    attempts = len(record.evidence_history)

    if state == "MASTERED":
        return 100
    if state == "DEMONSTRATED":
        return min(100, 85 + passes * 5)
    if state == "DEVELOPING":
        # 30 base + 15 per pass, capped at 80
        return min(80, 30 + passes * 15)
    if attempts > 0:
        # at least one attempt, but still NOT_DEMONSTRATED → small progress
        return min(25, attempts * 5)
    return 0


def sync_compass_state_from_manager(gateway: APIGateway, student_id: str | None = None) -> None:
    """Refresh the Compass ``student_state`` (DB-backed) from the AI
    Education manager. Call this after every event that mutates the manager
    (simulation run, transfer evaluation, diagnostic submission).

    If ``student_id`` is None, uses the manager's own student_id.
    Recomputes overall progress as the mean of per-competency progress and
    persists every change to the DB.
    """
    if student_id is None:
        student_id = gateway.student_manager.profile.student_id
    try:
        from ..db import SessionLocal, crud

        db = SessionLocal()
        try:
            competencies = crud.get_competencies(db, student_id)
            if not competencies:
                return
            total_progress = 0
            for c in competencies:
                mec271_id = compass_id_to_mec271(c.competency_id)
                record = gateway.student_manager.profile.competencies.get(mec271_id)
                if record is None:
                    total_progress += c.progress
                    continue
                # Only update competencies the manager has evidence for
                # (otherwise untouched competencies keep their seed values).
                if record.evidence_history:
                    new_status = compass_status_from_manager(c.competency_id, gateway)
                    new_progress = compass_progress_from_manager(c.competency_id, gateway)
                    crud.upsert_competency(
                        db,
                        student_id=student_id,
                        competency_id=c.competency_id,
                        competency_name=c.competency_name,
                        status=new_status,
                        progress=new_progress,
                    )
                    total_progress += new_progress
                else:
                    total_progress += c.progress

            new_overall = total_progress // len(competencies) if competencies else 0
            crud.update_student_progress(db, student_id, new_overall)
            db.commit()
        finally:
            db.close()
    except Exception:
        _log.warning("sync_compass_state failed", exc_info=True)


def active_compass_competency_id(gateway: APIGateway) -> str:
    """Return the Compass competency id the AI Education manager is currently
    targeting. Falls back to the first non-demonstrated Compass competency
    if the manager doesn't have a target.
    """
    try:
        target_node = gateway.student_manager.get_next_target_competency()
        if target_node is not None:
            return mec271_id_to_compass(target_node.id)
    except Exception:
        pass
    # Fall back to the first competency with status not "demonstrated"
    for c in INITIAL_COMPETENCIES:
        if c["status"] != "demonstrated":
            return c["id"]
    return INITIAL_COMPETENCIES[0]["id"]
