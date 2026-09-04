"""AI-fluency engine: aggregate prompt quality and verification behavior.

``evaluate_prompt_quality`` scores a single prompt on three deterministic
axes — engineering-detail coverage (technical signal specificity), whether
numeric constraints are stated, and whether the phrasing is a concrete
instruction rather than a vague ask. ``generate_fluency_report`` folds a
student's prompt history and telemetry-verification trail into a single
``AIFluencyReport`` with rule-based recommendations.
"""

from typing import List

from pydantic import BaseModel

from ai_education.fluency.metrics import (
    AIFluencyMetrics,
    FluencyLevel,
    compute_prompt_specificity,
    contains_numeric_value,
    extract_technical_signals,
    score_fluency_level,
)

FOLLOW_UP_MARKERS = {
    "try",
    "again",
    "adjust",
    "compare",
    "verify",
    "instead",
    "change",
    "retune",
}

PROMPT_QUALITY_SPECIFICITY_WEIGHT = 0.6
PROMPT_QUALITY_NUMERIC_WEIGHT = 0.2
PROMPT_QUALITY_STRUCTURE_WEIGHT = 0.2
STRUCTURE_MIN_WORDS = 8

OVERALL_PROMPT_WEIGHT = 0.5
OVERALL_VERIFICATION_WEIGHT = 0.3
OVERALL_AUTONOMY_WEIGHT = 0.2

VERIFICATION_THRESHOLD = 0.5
AUTONOMY_THRESHOLD = 0.5
PROMPT_QUALITY_THRESHOLD = 0.5
EXPERT_OVERALL_THRESHOLD = 0.9


class AIFluencyReport(BaseModel):
    """Aggregate report of a student's AI-collaboration fluency."""

    student_id: str
    metrics: AIFluencyMetrics
    recommendations: List[str]


class AIFluencyEngine:
    """Assess and quantify AI fluency from interaction history."""

    @staticmethod
    def _structural_clarity(prompt_text: str) -> float:
        word_count = len(prompt_text.split())
        if word_count >= STRUCTURE_MIN_WORDS:
            return 1.0
        return round(word_count / STRUCTURE_MIN_WORDS, 3)

    def evaluate_prompt_quality(self, prompt_text: str) -> float:
        """Score a single prompt for clarity, specificity, and parameters."""
        if not prompt_text.strip():
            return 0.0
        specificity = compute_prompt_specificity(prompt_text)
        numeric_detail = 1.0 if contains_numeric_value(prompt_text) else 0.0
        structure = self._structural_clarity(prompt_text)
        score = (
            PROMPT_QUALITY_SPECIFICITY_WEIGHT * specificity
            + PROMPT_QUALITY_NUMERIC_WEIGHT * numeric_detail
            + PROMPT_QUALITY_STRUCTURE_WEIGHT * structure
        )
        return round(min(score, 1.0), 3)

    @staticmethod
    def _follow_up_ratio(prompt_history: List[str]) -> float:
        """Fraction of prompts after the first that iterate on prior output."""
        later_prompts = prompt_history[1:]
        if not later_prompts:
            return 0.0
        marked = sum(
            1
            for prompt in later_prompts
            if any(marker in prompt.lower() for marker in FOLLOW_UP_MARKERS)
        )
        return round(marked / len(later_prompts), 3)

    @staticmethod
    def _mean(values: List[float]) -> float:
        if not values:
            return 0.0
        return round(sum(values) / len(values), 3)

    def generate_fluency_report(
        self,
        student_id: str,
        prompt_history: List[str],
        telemetry_evaluations: List[bool],
    ) -> AIFluencyReport:
        """Aggregate prompt and verification history into a fluency report."""
        prompt_quality_score = self._mean(
            [
                self.evaluate_prompt_quality(prompt)
                for prompt in prompt_history
            ]
        )
        critical_verification_score = self._mean(
            [1.0 if verified else 0.0 for verified in telemetry_evaluations]
        )
        autonomy_score = round(
            0.5 * critical_verification_score
            + 0.5 * self._follow_up_ratio(prompt_history),
            3,
        )
        overall_fluency_score = round(
            OVERALL_PROMPT_WEIGHT * prompt_quality_score
            + OVERALL_VERIFICATION_WEIGHT * critical_verification_score
            + OVERALL_AUTONOMY_WEIGHT * autonomy_score,
            3,
        )
        fluency_level = score_fluency_level(overall_fluency_score)

        recommendations: List[str] = []
        if prompt_quality_score < PROMPT_QUALITY_THRESHOLD:
            recommendations.append(
                "Include explicit parameters (Kp, Ki, Kd) and constraints "
                "(overshoot, settling time) in every prompt."
            )
        if critical_verification_score < VERIFICATION_THRESHOLD:
            recommendations.append(
                "Verify AI-generated gains against simulation telemetry "
                "before accepting them."
            )
        if autonomy_score < AUTONOMY_THRESHOLD:
            recommendations.append(
                "Iterate on your own results: adjust gains and compare "
                "outcomes between runs."
            )
        if overall_fluency_score < PROMPT_QUALITY_THRESHOLD:
            recommendations.append(
                "Practice describing the plant and expected response "
                "before prompting."
            )
        if overall_fluency_score >= EXPERT_OVERALL_THRESHOLD:
            recommendations.append(
                "Maintain current practice; model your verification habit "
                "for peers."
            )
        if not recommendations:
            recommendations.append(
                "Continue pairing specific constraints with telemetry checks."
            )

        return AIFluencyReport(
            student_id=student_id,
            metrics=AIFluencyMetrics(
                prompt_quality_score=prompt_quality_score,
                critical_verification_score=critical_verification_score,
                autonomy_score=autonomy_score,
                overall_fluency_score=overall_fluency_score,
                fluency_level=fluency_level,
            ),
            recommendations=recommendations,
        )