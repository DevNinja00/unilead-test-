"""Diagnostic service — wires the AI Education DiagnosticEngine.

The original mock just reflected the current competency state back. The
wired version scores each answer against the correct option, builds an
initial ``DiagnosticAssessment``, runs it through ``DiagnosticEngine`` to
update the AI Education student model, and derives per-competency
misconceptions from incorrect answers.

The misconception mapping is intentionally simple: each diagnostic question
is tagged with the misconception its wrong answers most commonly indicate
(e.g. answering "Proportional" to the derivative-gain question suggests
``MISSING_DERIVATIVE_UNDERSTANDING``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import Request

from . import ai_education_bridge, student_state
from .mock_data import DIAGNOSTIC_QUESTIONS

_log = logging.getLogger("unilead.diagnostic")

if TYPE_CHECKING:
    pass


# Correct option id per question (the index of the right answer in
# DIAGNOSTIC_QUESTIONS — verified against the question text).
CORRECT_ANSWERS = {
    "q1": "b",  # feedback compares output to reference and corrects error
    "q2": "c",  # derivative responds to how fast error changes
    "q3": "b",  # increasing Kp typically increases overshoot
    "q4": "b",  # tuning goal: meet overshoot/settling/SSE requirements
    "q5": "b",  # rise time = 10% to 90% of final value
}

# Per-question misconception tags — what a wrong answer most commonly
# indicates. Each maps the *most likely* misconception in this domain.
QUESTION_MISCONCEPTIONS = {
    "q1": "feedback_purpose_misunderstood",
    "q2": "derivative_role_misunderstood",
    "q3": "kp_overshoot_relationship_misunderstood",
    "q4": "tuning_objective_misunderstood",
    "q5": "rise_time_definition_misunderstood",
}


def get_questions() -> list[dict]:
    return DIAGNOSTIC_QUESTIONS


def submit_diagnostic(
    answers: list[dict], http_request: Request | None = None, student_id: str | None = None
) -> list[dict]:
    """Score the diagnostic answers, update the AI Education student model,
    and return per-competency results including detected misconceptions.
    """
    from . import student_state as ss

    # Resolve student_id: explicit param > DEFAULT_STUDENT_ID
    if student_id is None:
        student_id = ss.get_default_student_id()
    # Build a lookup of which option the student picked for each question.
    picked: dict[str, str] = {a["question_id"]: a["option_id"] for a in answers}

    # Per-competency accuracy + misconception tags.
    per_comp: dict[str, dict] = {}
    for q in DIAGNOSTIC_QUESTIONS:
        comp_id = q["competency_id"]
        correct = picked.get(q["id"]) == CORRECT_ANSWERS.get(q["id"])
        entry = per_comp.setdefault(comp_id, {"correct": 0, "total": 0, "misconceptions": []})
        entry["total"] += 1
        if correct:
            entry["correct"] += 1
        else:
            tag = QUESTION_MISCONCEPTIONS.get(q["id"])
            if tag and tag not in entry["misconceptions"]:
                entry["misconceptions"].append(tag)

    # If we have a gateway, run the AI Education DiagnosticEngine so its
    # student model reflects the diagnostic too. This is best-effort: if
    # the gateway isn't available (e.g. in unit tests), we still return
    # the Compass-style results derived above.
    if http_request is not None:
        try:
            _run_ai_education_diagnostic(per_comp, http_request, student_id)
            # Sync the (possibly updated) competency state back to Compass.
            ai_education_bridge.sync_compass_state_from_manager(
                ai_education_bridge.get_gateway(http_request, student_id)
            )
        except Exception:
            _log.warning("Diagnostic engine failed; continuing without AI update", exc_info=True)

    # Record an evidence timeline event for the diagnostic submission.
    correct_count = sum(e["correct"] for e in per_comp.values())
    total_count = sum(e["total"] for e in per_comp.values())
    student_state.sync_default_student_snapshot()
    student_state.append_evidence_event(
        student_id=student_id,
        event_type="diagnostic_submitted",
        title="Diagnostic submitted",
        detail=(
            f"Scored {correct_count}/{total_count} on the diagnostic quiz. "
            f"{sum(len(e['misconceptions']) for e in per_comp.values())} misconception(s) detected."
        ),
        result="INFO",
    )

    # Persist the full submission to the DB (every answer + correct flag).
    try:
        from ..db import SessionLocal, crud

        db = SessionLocal()
        try:
            answers_payload = []
            for q in DIAGNOSTIC_QUESTIONS:
                picked_option = picked.get(q["id"])
                correct = picked_option == CORRECT_ANSWERS.get(q["id"])
                answers_payload.append(
                    {
                        "question_id": q["id"],
                        "competency_id": q["competency_id"],
                        "selected_option_id": picked_option or "",
                        "correct": correct,
                        "misconception_tag": (
                            QUESTION_MISCONCEPTIONS.get(q["id"]) if not correct else None
                        ),
                    }
                )
            crud.save_diagnostic_submission(
                db,
                student_id=student_id,
                score=correct_count,
                total=total_count,
                misconceptions_count=sum(len(e["misconceptions"]) for e in per_comp.values()),
                answers=answers_payload,
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        _log.warning(
            "Failed to persist diagnostic submission for student=%s", student_id, exc_info=True
        )

    # Compose the response — one entry per competency that has a question.
    results: list[dict] = []
    for comp in student_state.get_competencies(student_id):
        if comp["id"] not in per_comp:
            continue
        entry = per_comp[comp["id"]]
        accuracy = entry["correct"] / entry["total"] if entry["total"] else 0.0
        results.append(
            {
                "competency_id": comp["id"],
                "competency_name": comp["name"],
                "status": comp["status"],
                "misconceptions": entry["misconceptions"],
                "accuracy": round(accuracy, 3),
            }
        )
    return results


def _run_ai_education_diagnostic(
    per_comp: dict[str, dict], http_request: Request, student_id: str
) -> None:
    """Translate the per-competency accuracy into a DiagnosticEngine run."""
    from ai_education.domain.diagnostic import (
        DiagnosticAssessment,
        DiagnosticEngine,
        DiagnosticItem,
        DiagnosticResponse,
    )

    gateway = ai_education_bridge.get_gateway(http_request, student_id)
    manager = gateway.student_manager

    # Build one DiagnosticItem per competency (binary: pass if accuracy > 0.5).
    items: list[DiagnosticItem] = []
    responses: list[DiagnosticResponse] = []
    for compass_id, entry in per_comp.items():
        mec271_id = ai_education_bridge.compass_id_to_mec271(compass_id)
        passed = entry["correct"] >= entry["total"] / 2
        items.append(
            DiagnosticItem(
                competency_id=mec271_id,
                prompt=f"Diagnostic for {compass_id}",
                options=[],
                correct_option_index=0,
            )
        )
        responses.append(
            DiagnosticResponse(
                item_id=f"diag-{mec271_id}",
                competency_id=mec271_id,
                correct=passed,
            )
        )

    assessment = DiagnosticAssessment(
        student_id=manager.profile.student_id,
        items=items,
        responses=responses,
    )
    DiagnosticEngine().evaluate_diagnostic(
        student_id=manager.profile.student_id,
        assessment=assessment,
        items=items,
        manager=manager,
    )
