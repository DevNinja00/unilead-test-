"""Transfer assessment engine: appraise cross-domain PID generalization.

``TransferAssessmentEngine`` poses a structured cross-domain challenge built
from a ``TransferScenario`` and then judges the student's qualitative
explanation against the vocabulary that domain experts use to reason about the
same control principle (inertia, accumulation, delay). The evaluation is fully
deterministic: it measures how many of the scenario's expected terms appear in
the response rather than relying on an LLM.
"""

from typing import Dict, List

from pydantic import BaseModel

from ai_education.transfer.scenarios import (
    TRANSFER_DOMAIN_TERMS,
    TransferScenario,
    get_transfer_scenario,
)

MIN_MATCHED_TERMS_FOR_SUCCESS = 2


class TransferEvaluationResult(BaseModel):
    """The verdict and rationale for one cross-domain transfer response."""

    student_id: str
    competency_id: str
    scenario_id: str
    is_transfer_successful: bool
    score: float
    feedback: str


class TransferAssessmentEngine:
    """Generate cross-domain prompts and evaluate student explanations."""

    @staticmethod
    def generate_transfer_prompt(
        student_id: str,
        competency_id: str,
        scenario_id: str = "industrial_oven",
    ) -> dict:
        """Build a structured cross-domain challenge prompt for the AI Coach."""
        scenario = get_transfer_scenario(scenario_id)
        prompt_lines = [
            f"{student_id}, you mastered PID tuning on the motor-speed plant.",
            (
                "Now tune the same controller for a different plant: "
                f"{scenario.title}."
            ),
            f"Domain: {scenario.domain}.",
            f"Error signal: {scenario.error_signal_meaning}",
            f"Control output: {scenario.control_output_meaning}",
            f"System inertia: {scenario.system_inertia}",
            f"Challenge: {scenario.conceptual_challenge}",
            (
                "Predict how each gain (Kp, Ki, Kd) behaves in this new plant "
                "before any feedback is given."
            ),
        ]
        return {
            "student_id": student_id,
            "competency_id": competency_id,
            "scenario_id": scenario.scenario_id,
            "title": scenario.title,
            "domain": scenario.domain,
            "error_signal_meaning": scenario.error_signal_meaning,
            "control_output_meaning": scenario.control_output_meaning,
            "system_inertia": scenario.system_inertia,
            "conceptual_challenge": scenario.conceptual_challenge,
            "prompt": "\n".join(prompt_lines),
        }

    def evaluate_transfer_response(
        self,
        student_id: str,
        competency_id: str,
        response_text: str,
        scenario: TransferScenario,
    ) -> TransferEvaluationResult:
        """Score a qualitative explanation for cross-domain understanding."""
        normalized = response_text.lower()
        expected_terms = TRANSFER_DOMAIN_TERMS.get(
            scenario.scenario_id, set()
        )
        matched: List[str] = [
            term
            for term in sorted(expected_terms)
            if term in normalized
        ]

        total_terms = len(expected_terms)
        score = (
            round(len(matched) / total_terms, 3) if total_terms else 0.0
        )
        is_transfer_successful = (
            len(matched) >= MIN_MATCHED_TERMS_FOR_SUCCESS
        )

        if is_transfer_successful:
            joined_matched = ", ".join(matched)
            feedback = (
                f"Response demonstrates generalization in the {scenario.domain} "
                f"domain; the explanation connects '{joined_matched}' to the "
                "same PID principle behind the motor-speed plant."
            )
        else:
            missing = sorted(set(expected_terms) - set(matched))
            if not missing:
                feedback = (
                    "Response did not engage with the scenario; reframe it "
                    "using the plant's inertia and dynamics."
                )
            else:
                joined_missing = ", ".join(missing)
                feedback = (
                    f"Response is only partially transferred; it does not "
                    f"connect '{joined_missing}' to the {scenario.domain} plant."
                )

        return TransferEvaluationResult(
            student_id=student_id,
            competency_id=competency_id,
            scenario_id=scenario.scenario_id,
            is_transfer_successful=is_transfer_successful,
            score=score,
            feedback=feedback,
        )