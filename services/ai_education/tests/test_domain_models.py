"""Unit tests for the AI/Education domain models and evidence schemas."""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ai_education.domain.enums import CompetencyState, EvidenceType
from ai_education.domain.evidence import PracticalEvidence
from ai_education.domain.models import (
    CompetencyNode,
    CompetencyRecord,
    StudentProfile,
)

ROBOTICS_EVIDENCE_JSON = {
    "task_id": "PID-001",
    "attempt": 1,
    "parameters": {"kp": 2.0, "ki": 0.5, "kd": 0.25},
    "metrics": {"overshoot": 5.2, "settling_time": 3.4, "steady_state_error": 0.01},
    "stable": True,
    "requirements_met": True,
    "result": "PASS",
}


def valid_evidence_payload(**overrides):
    payload = dict(ROBOTICS_EVIDENCE_JSON)
    payload.update(overrides)
    return payload


class TestPracticalEvidenceContract:
    def test_parses_valid_robotics_evidence_json(self):
        evidence = PracticalEvidence.model_validate(ROBOTICS_EVIDENCE_JSON)

        assert evidence.evidence_type == EvidenceType.PRACTICAL_SIMULATION
        assert evidence.task_id == "PID-001"
        assert evidence.attempt == 1
        assert evidence.parameters.kp == 2.0
        assert evidence.parameters.ki == 0.5
        assert evidence.parameters.kd == 0.25
        assert evidence.metrics.overshoot == 5.2
        assert evidence.metrics.settling_time == 3.4
        assert evidence.metrics.steady_state_error == 0.01
        assert evidence.stable is True
        assert evidence.requirements_met is True
        assert evidence.result == "PASS"

    def test_parses_from_raw_json_string(self):
        evidence = PracticalEvidence.model_validate_json(
            json.dumps(ROBOTICS_EVIDENCE_JSON)
        )
        assert evidence.task_id == "PID-001"
        assert evidence.parameters.kp == 2.0

    def test_defaults_evidence_type_to_practical_simulation(self):
        evidence = PracticalEvidence.model_validate(valid_evidence_payload())
        assert evidence.evidence_type == EvidenceType.PRACTICAL_SIMULATION

    def test_timestamp_defaults_to_utc_now(self):
        now = datetime.now(timezone.utc)
        evidence = PracticalEvidence.model_validate(valid_evidence_payload())
        assert evidence.timestamp.tzinfo is not None
        assert evidence.timestamp.tzinfo == timezone.utc
        assert evidence.timestamp >= now

    def test_explicit_evidence_type_is_accepted(self):
        evidence = PracticalEvidence.model_validate(
            valid_evidence_payload(evidence_type="TRANSFER_TASK")
        )
        assert evidence.evidence_type == EvidenceType.TRANSFER_TASK

    def test_json_serialization_round_trip(self):
        evidence = PracticalEvidence.model_validate(valid_evidence_payload())
        restored = PracticalEvidence.model_validate_json(evidence.model_dump_json())
        assert restored == evidence


class TestPracticalEvidenceValidation:
    def test_negative_attempt_raises_validation_error(self):
        with pytest.raises(ValidationError):
            PracticalEvidence.model_validate(valid_evidence_payload(attempt=-1))

    def test_zero_attempt_raises_validation_error(self):
        with pytest.raises(ValidationError):
            PracticalEvidence.model_validate(valid_evidence_payload(attempt=0))

    def test_missing_required_metrics_raises_validation_error(self):
        payload = valid_evidence_payload()
        del payload["metrics"]
        with pytest.raises(ValidationError):
            PracticalEvidence.model_validate(payload)

    def test_wrong_parameter_type_raises_validation_error(self):
        with pytest.raises(ValidationError):
            PracticalEvidence.model_validate(
                valid_evidence_payload(parameters={"kp": "two", "ki": 0.5, "kd": 0.25})
            )

    def test_unknown_evidence_type_raises_validation_error(self):
        with pytest.raises(ValidationError):
            PracticalEvidence.model_validate(
                valid_evidence_payload(evidence_type="MAGIC_TELEMETRY")
            )


class TestCompetencyModels:
    def test_competency_node_defaults(self):
        node = CompetencyNode(id="PID-001", title="PID Tuning")
        assert node.description == ""
        assert node.parent_ids == []

    def test_competency_record_starts_not_demonstrated(self):
        record = CompetencyRecord(competency_id="PID-001")
        assert record.state == CompetencyState.NOT_DEMONSTRATED
        assert record.evidence_history == []

    def test_state_progression_not_demonstrated_to_developing(self):
        record = CompetencyRecord(competency_id="PID-001")
        evidence = PracticalEvidence.model_validate(
            valid_evidence_payload(attempt=1, requirements_met=True, result="PASS")
        )
        state = record.record_evidence(evidence)
        assert state == CompetencyState.DEVELOPING
        assert record.state == CompetencyState.DEVELOPING

    def test_state_progression_developing_to_demonstrated(self):
        record = CompetencyRecord(competency_id="PID-001")
        record.record_evidence(
            PracticalEvidence.model_validate(
                valid_evidence_payload(attempt=1, requirements_met=True, result="PASS")
            )
        )
        record.record_evidence(
            PracticalEvidence.model_validate(
                valid_evidence_payload(attempt=2, requirements_met=True, result="PASS")
            )
        )
        assert record.state == CompetencyState.DEMONSTRATED

    def test_failed_evidence_does_not_progress_state(self):
        record = CompetencyRecord(competency_id="PID-001")
        record.record_evidence(
            PracticalEvidence.model_validate(
                valid_evidence_payload(attempt=1, requirements_met=False, result="FAIL")
            )
        )
        assert record.state == CompetencyState.NOT_DEMONSTRATED

    def test_state_progression_serialization(self):
        record = CompetencyRecord(competency_id="PID-001")
        record.record_evidence(
            PracticalEvidence.model_validate(
                valid_evidence_payload(attempt=1, requirements_met=True, result="PASS")
            )
        )
        serialized = record.model_dump(mode="json")
        assert serialized["state"] == "DEVELOPING"
        assert serialized["competency_id"] == "PID-001"
        assert len(serialized["evidence_history"]) == 1
        assert serialized["evidence_history"][0]["result"] == "PASS"

        restored = CompetencyRecord.model_validate(serialized)
        assert restored.state == CompetencyState.DEVELOPING

    def test_student_profile_defaults_to_mec271(self):
        profile = StudentProfile(student_id="s-12345")
        assert profile.course_id == "MEC271"
        assert profile.competencies == {}

    def test_student_profile_holds_competency_records(self):
        record = CompetencyRecord(competency_id="PID-001")
        profile = StudentProfile(
            student_id="s-12345",
            competencies={"PID-001": record},
        )
        assert profile.competencies["PID-001"] is record

    def test_student_profile_json_round_trip_preserves_state(self):
        record = CompetencyRecord(competency_id="PID-001")
        record.record_evidence(
            PracticalEvidence.model_validate(
                valid_evidence_payload(attempt=1, requirements_met=True, result="PASS")
            )
        )
        profile = StudentProfile(
            student_id="s-12345",
            competencies={"PID-001": record},
        )
        restored = StudentProfile.model_validate_json(profile.model_dump_json())
        assert restored.student_id == "s-12345"
        assert restored.course_id == "MEC271"
        assert (
            restored.competencies["PID-001"].state == CompetencyState.DEVELOPING
        )