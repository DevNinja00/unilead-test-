"""Tests for AIFluencyEngine: prompt quality and fluency report generation."""

from ai_education.fluency import (
    AIFluencyEngine,
    AIFluencyReport,
    FluencyLevel,
    compute_prompt_specificity,
    extract_technical_signals,
    score_fluency_level,
)

ENGINE = AIFluencyEngine()
STUDENT_ID = "fluency-student"

VAGUE_PROMPT = "help me with pid"
SPECIFIC_PROMPT = (
    "Tune Kp=1.2, Ki=0.5, Kd=0.1 for MOTOR_TRACK so that settling time is "
    "under 2 seconds, overshoot stays below 5%, and steady-state error is "
    "under 0.02."
)


class TestPromptQualityScoring:
    def test_vague_prompt_scores_low(self) -> None:
        score = ENGINE.evaluate_prompt_quality(VAGUE_PROMPT)
        assert score < 0.4

    def test_specific_engineering_prompt_scores_high(self) -> None:
        score = ENGINE.evaluate_prompt_quality(SPECIFIC_PROMPT)
        assert score > 0.7

    def test_specific_prompt_outranks_vague_prompt(self) -> None:
        vague = ENGINE.evaluate_prompt_quality(VAGUE_PROMPT)
        specific = ENGINE.evaluate_prompt_quality(SPECIFIC_PROMPT)
        assert specific > vague

    def test_empty_prompt_scores_zero(self) -> None:
        assert ENGINE.evaluate_prompt_quality("") == 0.0
        assert ENGINE.evaluate_prompt_quality("   ") == 0.0

    def test_prompt_specificity_matches_parameter_inclusion(self) -> None:
        matched = extract_technical_signals(SPECIFIC_PROMPT)
        assert "Kp" in matched
        assert "Ki" in matched
        assert "Kd" in matched
        assert "settling time" in matched
        assert "overshoot" in matched
        assert compute_prompt_specificity(SPECIFIC_PROMPT) > 0.5


class TestCriticalVerificationTracking:
    def test_verification_score_is_fraction_of_verified_runs(self) -> None:
        all_verified = ENGINE.generate_fluency_report(
            STUDENT_ID, [SPECIFIC_PROMPT], [True, True]
        )
        some_verified = ENGINE.generate_fluency_report(
            STUDENT_ID, [SPECIFIC_PROMPT], [True, False, False]
        )

        assert all_verified.metrics.critical_verification_score == 1.0
        assert some_verified.metrics.critical_verification_score == 0.333
        assert (
            all_verified.metrics.critical_verification_score
            > some_verified.metrics.critical_verification_score
        )

    def test_no_verification_history_scores_zero(self) -> None:
        report = ENGINE.generate_fluency_report(
            STUDENT_ID, [SPECIFIC_PROMPT], []
        )
        assert report.metrics.critical_verification_score == 0.0


class TestFluencyReports:
    def test_novice_profile(self) -> None:
        report = ENGINE.generate_fluency_report(
            STUDENT_ID,
            prompt_history=["help", "what is pid"],
            telemetry_evaluations=[False, False],
        )

        assert report.student_id == STUDENT_ID
        assert report.metrics.fluency_level is FluencyLevel.NOVICE
        assert report.metrics.overall_fluency_score < 0.5
        assert len(report.recommendations) >= 1

    def test_competent_profile(self) -> None:
        report = ENGINE.generate_fluency_report(
            STUDENT_ID,
            prompt_history=[
                "Tune Kp and Ki to meet overshoot under 10% and settling "
                "time under 2 s.",
                "Increase Ki to 0.6 and verify the steady-state error again.",
            ],
            telemetry_evaluations=[True, False],
        )

        assert report.metrics.fluency_level is FluencyLevel.COMPETENT
        assert report.metrics.overall_fluency_score >= 0.5
        assert report.metrics.overall_fluency_score < 0.7

    def test_expert_profile(self) -> None:
        report = ENGINE.generate_fluency_report(
            STUDENT_ID,
            prompt_history=[
                "Tune Kp=1.2, Ki=0.5, Kd=0.1 for MOTOR_TRACK: settling time "
                "under 2 s, overshoot under 5%, steady-state error under "
                "0.02.",
                "Raise Ki to 0.4, keep Kd at 0.1, then verify overshoot "
                "stays below 5%, settling time below 2 s, and steady-state "
                "error below 0.02.",
                "Drop Kp to 1.0 and compare the rise time and overshoot "
                "under 5% against the previous run.",
            ],
            telemetry_evaluations=[True, True, True],
        )

        assert report.metrics.fluency_level is FluencyLevel.EXPERT
        assert report.metrics.overall_fluency_score >= 0.85
        assert report.metrics.prompt_quality_score > 0.7
        assert report.metrics.critical_verification_score == 1.0

    def test_proficiency_level_monotonic_ordering(self) -> None:
        novice = ENGINE.generate_fluency_report(
            STUDENT_ID, ["help"], [False]
        ).metrics.overall_fluency_score
        competent = ENGINE.generate_fluency_report(
            STUDENT_ID,
            ["Tune Kp and overshoot under 10%, settling time under 2 s.",
             "Then verify the result."],
            [True, False],
        ).metrics.overall_fluency_score
        expert = ENGINE.generate_fluency_report(
            STUDENT_ID,
            [SPECIFIC_PROMPT, "Adjust Ki and verify again.",
             "Compare both runs."],
            [True, True],
        ).metrics.overall_fluency_score

        assert novice < competent < expert

    def test_fluency_level_buckets(self) -> None:
        assert score_fluency_level(0.0) is FluencyLevel.NOVICE
        assert score_fluency_level(0.5) is FluencyLevel.COMPETENT
        assert score_fluency_level(0.7) is FluencyLevel.PROFICIENT
        assert score_fluency_level(0.85) is FluencyLevel.EXPERT

    def test_report_is_pydantic_model(self) -> None:
        report = ENGINE.generate_fluency_report(
            STUDENT_ID, [SPECIFIC_PROMPT], [True]
        )
        assert isinstance(report, AIFluencyReport)
        assert report.metrics.fluency_level is FluencyLevel.COMPETENT or (
            report.metrics.fluency_level is FluencyLevel.PROFICIENT
        )

    def test_recommendations_shape_and_content(self) -> None:
        novice = ENGINE.generate_fluency_report(STUDENT_ID, ["help"], [False])
        assert isinstance(novice.recommendations, list)
        assert all(isinstance(item, str) for item in novice.recommendations)
        assert any("Verify" in item for item in novice.recommendations)