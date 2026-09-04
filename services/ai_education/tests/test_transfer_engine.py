"""Tests for TransferAssessmentEngine and transfer scenario loading."""

import pytest

from ai_education.transfer import (
    TRANSFER_DOMAIN_TERMS,
    TransferAssessmentEngine,
    TransferEvaluationResult,
    TransferScenario,
    get_transfer_scenario,
    get_transfer_scenarios,
)
from ai_education.transfer.engine import MIN_MATCHED_TERMS_FOR_SUCCESS

ENGINE = TransferAssessmentEngine()
STUDENT_ID = "transfer-student"
COMPETENCY_ID = "MEC271-PID-REASON"
EXPECTED_IDS = {"industrial_oven", "water_tank_level", "quadrotor_pitch"}


def scenario_by_id(scenario_id: str) -> TransferScenario:
    for scenario in get_transfer_scenarios():
        if scenario.scenario_id == scenario_id:
            return scenario


class TestTransferScenarios:
    def test_prepopulated_scenarios_load(self) -> None:
        scenarios = get_transfer_scenarios()

        assert isinstance(scenarios, list)
        assert len(scenarios) >= 3
        assert all(isinstance(s, TransferScenario) for s in scenarios)
        assert {s.scenario_id for s in scenarios}.issuperset(EXPECTED_IDS)

    def test_all_scenarios_are_fully_specified(self) -> None:
        expected_fields = {
            "title",
            "domain",
            "error_signal_meaning",
            "control_output_meaning",
            "system_inertia",
            "conceptual_challenge",
        }
        for scenario in get_transfer_scenarios():
            for field in expected_fields:
                assert getattr(scenario, field), (
                    f"{scenario.scenario_id} has empty field {field}"
                )

    def test_scenario_domains_are_distinct_plants(self) -> None:
        scenarios = get_transfer_scenarios()
        assert len({s.domain for s in scenarios}) == len(scenarios)

    def test_every_scenario_has_detection_terms(self) -> None:
        for scenario_id in EXPECTED_IDS:
            terms = TRANSFER_DOMAIN_TERMS.get(scenario_id)
            assert terms, f"No detection terms for {scenario_id}"
            assert len(terms) >= MIN_MATCHED_TERMS_FOR_SUCCESS

    def test_unknown_scenario_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            get_transfer_scenario("nuclear_pressurizer")


class TestTransferPromptGeneration:
    def test_default_industrial_oven_prompt(self) -> None:
        prompt = ENGINE.generate_transfer_prompt(STUDENT_ID, COMPETENCY_ID)

        assert isinstance(prompt, dict)
        assert prompt["scenario_id"] == "industrial_oven"
        assert prompt["domain"] == "thermal"
        assert prompt["student_id"] == STUDENT_ID
        assert prompt["competency_id"] == COMPETENCY_ID
        assert "industrial oven" in prompt["title"]
        assert STUDENT_ID in prompt["prompt"]
        assert "thermal inertia" in prompt["prompt"]
        assert "Kp" in prompt["prompt"]
        assert "Ki" in prompt["prompt"]
        assert "Kd" in prompt["prompt"]

    def test_custom_scenario_prompt(self) -> None:
        prompt = ENGINE.generate_transfer_prompt(
            STUDENT_ID, COMPETENCY_ID, scenario_id="quadrotor_pitch"
        )

        assert prompt["scenario_id"] == "quadrotor_pitch"
        assert prompt["domain"] == "aerospace"
        assert "pitch" in prompt["prompt"]

    def test_prompt_bridges_to_motivation_skill(self) -> None:
        prompt = ENGINE.generate_transfer_prompt(STUDENT_ID, COMPETENCY_ID)

        assert "transfer_scenario" not in prompt
        assert "conceptual_challenge" in prompt


class TestTransferEvaluation:
    def test_correct_cross_domain_response_succeeds(self) -> None:
        scenario = scenario_by_id("industrial_oven")
        response = (
            "Thermal inertia makes temperature lag the burner, so the "
            "integral term keeps accumulating until the delay lets the setpoint "
            "catch up to the commanded temperature."
        )

        result = ENGINE.evaluate_transfer_response(
            STUDENT_ID, COMPETENCY_ID, response, scenario
        )

        assert isinstance(result, TransferEvaluationResult)
        assert result.student_id == STUDENT_ID
        assert result.competency_id == COMPETENCY_ID
        assert result.scenario_id == "industrial_oven"
        assert result.is_transfer_successful is True
        assert result.score > 0.5
        assert "thermal" in result.feedback

    def test_flawed_memorized_response_fails(self) -> None:
        scenario = scenario_by_id("industrial_oven")
        response = (
            "I would increase Kp to speed up the motor and reduce the "
            "overshoot on the shaft."
        )

        result = ENGINE.evaluate_transfer_response(
            STUDENT_ID, COMPETENCY_ID, response, scenario
        )

        assert result.is_transfer_successful is False
        assert result.score == 0.0
        assert "thermal" in result.feedback

    def test_partial_transfer_is_not_successful(self) -> None:
        scenario = scenario_by_id("water_tank_level")
        response = "The tank would fill and the level keeps climbing."

        result = ENGINE.evaluate_transfer_response(
            STUDENT_ID, COMPETENCY_ID, response, scenario
        )

        assert result.is_transfer_successful is False
        assert result.score < 0.5

    def test_score_scales_with_matched_terms(self) -> None:
        scenario = scenario_by_id("industrial_oven")
        partial = ENGINE.evaluate_transfer_response(
            STUDENT_ID,
            COMPETENCY_ID,
            "Thermal inertia stores heat in the chamber.",
            scenario,
        )
        full = ENGINE.evaluate_transfer_response(
            STUDENT_ID,
            COMPETENCY_ID,
            "Thermal inertia, delay, and accumulation all shape how the "
            "temperature responds.",
            scenario,
        )

        assert full.score > partial.score
        assert full.score == 1.0

    def test_case_insensitive_matching(self) -> None:
        scenario = scenario_by_id("quadrotor_pitch")
        response = "Differential THRUST applies the torque that pitches the ATTITUDE."

        result = ENGINE.evaluate_transfer_response(
            STUDENT_ID, COMPETENCY_ID, response, scenario
        )

        assert result.is_transfer_successful is True

    def test_empty_response_fails(self) -> None:
        scenario = scenario_by_id("industrial_oven")

        result = ENGINE.evaluate_transfer_response(
            STUDENT_ID, COMPETENCY_ID, "", scenario
        )

        assert result.is_transfer_successful is False
        assert result.score == 0.0