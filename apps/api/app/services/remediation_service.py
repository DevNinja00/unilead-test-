"""Remediation service — uses the AI Education RemediationEngine.

Builds a ``RemediationPlan`` from the student's recent failure evidence
and translates it to the Compass-facing schema. The plan picks one of four
actions based on the detected misconception (e.g. EXCESSIVE_PROPORTIONAL_GAIN
→ ADJUST_PARAMETER_STEP with a focus on reducing Kp).

The ``conceptual_focus`` and ``diagnostic_question`` come from the
remediation strategy table (not the plan itself) — the plan only carries
the misconception + action + steps.

After computing the response, the plan is persisted to the DB
(``remediation_plans`` table) so the instructor dashboard can see it.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from ..schemas.remediation import RemediationPlanResponse
from . import ai_education_bridge


def _persist_plan(*, competency_id, plan, summary, conceptual_focus, guided_question, student_id) -> None:
    """Persist the remediation plan to the DB (best-effort)."""
    try:
        from ..db import SessionLocal, crud
        db = SessionLocal()
        try:
            crud.save_remediation_plan(
                db,
                student_id=student_id,
                competency_id=competency_id,
                detected_misconception=summary.detected_misconception,
                recommended_action=plan.action.value if hasattr(plan.action, "value") else str(plan.action),
                conceptual_focus=conceptual_focus,
                guided_question=guided_question,
                consecutive_failures=summary.consecutive_failures,
                total_attempts=summary.total_attempts,
                summary_text=summary.summary_text,
                remediation_steps=list(plan.remediation_steps or []),
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        pass  # DB persistence is best-effort — never break the route


def build_plan(competency_id: str, http_request: Request, student_id: str) -> dict:
    """Build a remediation plan for the given competency for ``student_id``."""
    from ai_education.reasoning.engine import EvidenceReasoningEngine
    from ai_education.reasoning.misconceptions import PIDMisconception
    from ai_education.remediation.engine import RemediationEngine
    from ai_education.remediation.strategies import get_remediation_strategy

    gateway = ai_education_bridge.get_gateway(http_request, student_id)
    mec271_id = ai_education_bridge.compass_id_to_mec271(competency_id)
    manager = gateway.student_manager

    # Verify this competency has failing evidence to remediate.
    record = manager.profile.competencies.get(mec271_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"No competency found with id {competency_id!r}",
        )

    if not record.evidence_history:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No simulation evidence yet for {competency_id!r}. "
                "Run a simulation before requesting remediation."
            ),
        )

    # Build the plan using the real engine.
    reasoning_engine = EvidenceReasoningEngine()
    remediation_engine = RemediationEngine()
    plan = remediation_engine.build_remediation_plan(
        student_id=manager.profile.student_id,
        competency_id=mec271_id,
        manager=manager,
        reasoning_engine=reasoning_engine,
    )

    # Pull the reasoning summary for the human-readable text + stats.
    summary = reasoning_engine.analyze_competency_evidence(
        student_id=manager.profile.student_id,
        competency_id=mec271_id,
        manager=manager,
    )

    # Look up the conceptual_focus + diagnostic_question from the strategy table.
    conceptual_focus = ""
    guided_question = plan.guided_question
    try:
        misconception_name = summary.detected_misconception or plan.misconception.name
        if misconception_name and misconception_name != "NONE":
            misconception_enum = PIDMisconception[misconception_name]
            strategy = get_remediation_strategy(misconception_enum)
            conceptual_focus = strategy.get("conceptual_focus", "")
            if not guided_question:
                guided_question = strategy.get("diagnostic_question", "")
    except (KeyError, ValueError):
        pass

    # Persist the plan to the DB (best-effort).
    _persist_plan(
        competency_id=competency_id,
        plan=plan,
        summary=summary,
        conceptual_focus=conceptual_focus,
        guided_question=guided_question,
        student_id=student_id,
    )

    return RemediationPlanResponse(
        competency_id=competency_id,
        detected_misconception=summary.detected_misconception,
        recommended_action=plan.action.value if hasattr(plan.action, "value") else str(plan.action),
        conceptual_focus=conceptual_focus,
        guided_question=guided_question,
        remediation_steps=list(plan.remediation_steps or []),
        consecutive_failures=summary.consecutive_failures,
        total_attempts=summary.total_attempts,
        summary_text=summary.summary_text,
    ).model_dump()
