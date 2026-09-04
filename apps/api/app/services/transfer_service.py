"""Transfer service — uses the AI Education TransferAssessmentEngine.

The transfer engine is intentionally deterministic: it does not call out
to an LLM. A response passes when it matches enough expert terms from
the scenario's domain.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from ..schemas.transfer import (
    TransferEvaluationRequest,
    TransferEvaluationResponse,
    TransferScenarioResponse,
)
from . import ai_education_bridge


# All transfer tasks currently route to the same default scenario. Students
# can override via the ``scenario_id`` query parameter to retry with a
# different plant (water tank, quadrotor, ...).
DEFAULT_SCENARIO = "industrial_oven"


def get_scenario(competency_id: str, scenario_id: str | None, http_request: Request, student_id: str) -> dict:
    """Build a transfer scenario prompt for the given competency for ``student_id``."""
    from ai_education.transfer.engine import TransferAssessmentEngine
    from ai_education.transfer.scenarios import get_transfer_scenario

    gateway = ai_education_bridge.get_gateway(http_request, student_id)
    mec271_id = ai_education_bridge.compass_id_to_mec271(competency_id)
    manager = gateway.student_manager

    # Validate competency exists.
    if mec271_id not in manager.profile.competencies:
        raise HTTPException(
            status_code=404,
            detail=f"No competency found with id {competency_id!r}",
        )

    sid = scenario_id or DEFAULT_SCENARIO
    scenario = get_transfer_scenario(sid)
    if scenario is None:
        raise HTTPException(
            status_code=404,
            detail=f"No transfer scenario with id {sid!r}",
        )

    engine = TransferAssessmentEngine()
    # The engine returns a dict with a "prompt" key (and possibly other fields).
    prompt_payload = engine.generate_transfer_prompt(
        student_id=student_id,
        competency_id=mec271_id,
        scenario_id=sid,
    )
    prompt_text = (
        prompt_payload.get("prompt", "")
        if isinstance(prompt_payload, dict)
        else str(prompt_payload)
    )

    return TransferScenarioResponse(
        competency_id=competency_id,
        scenario_id=scenario.scenario_id,
        title=scenario.title,
        domain=scenario.domain,
        prompt=prompt_text,
        error_signal_meaning=scenario.error_signal_meaning,
        control_output_meaning=scenario.control_output_meaning,
        system_inertia=scenario.system_inertia,
        conceptual_challenge=scenario.conceptual_challenge,
    ).model_dump()


def evaluate_response(
    competency_id: str,
    request_data: TransferEvaluationRequest,
    http_request: Request,
    student_id: str,
) -> dict:
    """Evaluate a student's transfer response and record the outcome."""
    from ai_education.transfer.engine import TransferAssessmentEngine
    from ai_education.transfer.scenarios import get_transfer_scenario

    gateway = ai_education_bridge.get_gateway(http_request, student_id)
    mec271_id = ai_education_bridge.compass_id_to_mec271(competency_id)
    manager = gateway.student_manager

    scenario = get_transfer_scenario(request_data.scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=404,
            detail=f"No transfer scenario with id {request_data.scenario_id!r}",
        )

    engine = TransferAssessmentEngine()
    result = engine.evaluate_transfer_response(
        student_id=student_id,
        competency_id=mec271_id,
        response_text=request_data.response_text,
        scenario=scenario,
    )

    # Sync state back to Compass so /api/competencies reflects the transfer outcome
    ai_education_bridge.sync_compass_state_from_manager(gateway)

    # Record an evidence timeline event for the transfer evaluation.
    from . import student_state
    student_state.sync_default_student_snapshot()
    student_state.append_evidence_event(
        student_id=student_id,
        event_type="transfer_evaluated",
        title=f"Transfer ({request_data.scenario_id})",
        detail=(
            f"Submitted {len(request_data.response_text)} chars. "
            f"Result: {'TRANSFER DEMONSTRATED' if result.is_transfer_successful else 'not yet'}. "
            f"Feedback: {result.feedback[:120]}"
        ),
        result="PASS" if result.is_transfer_successful else "FAIL",
        competency_id=competency_id,
    )

    # Persist the transfer evaluation to the DB.
    try:
        from ..db import SessionLocal, crud
        db = SessionLocal()
        try:
            crud.save_transfer_evaluation(
                db,
                student_id=student_id,
                competency_id=competency_id,
                scenario_id=request_data.scenario_id,
                response_text=request_data.response_text,
                passed=bool(result.is_transfer_successful),
                matched_count=int(getattr(result, "score", 0) * 10),
                min_required=2,
                feedback=result.feedback,
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        pass  # DB persistence is best-effort — never break the route

    return TransferEvaluationResponse(
        competency_id=competency_id,
        scenario_id=request_data.scenario_id,
        passed=bool(result.is_transfer_successful),
        matched_terms=[],  # The engine doesn't expose matched terms; we expose score instead
        matched_count=int(result.score * 10) if hasattr(result, "score") else 0,
        min_required=2,
        feedback=result.feedback,
    ).model_dump()
