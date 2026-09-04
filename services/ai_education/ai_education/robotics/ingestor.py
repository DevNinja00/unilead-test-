"""Robotics evidence ingestor: telemetry -> validated domain evidence.

``RoboticsEvidenceIngestor`` evaluates a ``StepResponseTelemetry`` reading
against ``TelemetryThresholds``, builds a frozen ``PracticalEvidence``
instance, and applies it to the student's competency state through the
``StudentModelManager``. The raw telemetry carries no PID gains, so the
evidence's ``PIDParameters`` field is populated with neutral zero gains;
tuning parameters are not part of the simulator telemetry contract here.
"""

from typing import Tuple

from ai_education.domain.evidence import (
    PIDParameters,
    PracticalEvidence,
    SimulationMetrics,
)
from ai_education.domain.student import StudentModelManager
from ai_education.robotics.telemetry import StepResponseTelemetry, TelemetryThresholds


class RoboticsEvidenceIngestor:
    """Bridges simulator telemetry into the competency evidence feed."""

    def evaluate_telemetry(
        self,
        telemetry: StepResponseTelemetry,
        thresholds: TelemetryThresholds,
    ) -> Tuple[bool, str]:
        """Evaluate telemetry against thresholds.

        Returns ``(passed, summary)`` where ``summary`` is a deterministic,
        human-readable breakdown of every metric check and its result.
        """
        failures: list[str] = []
        if thresholds.require_stable and not telemetry.is_stable:
            failures.append("system was not stable")
        if telemetry.overshoot_pct > thresholds.max_overshoot_pct:
            failures.append(
                f"overshoot {telemetry.overshoot_pct:.1f}% exceeds max "
                f"{thresholds.max_overshoot_pct:.1f}%"
            )
        if telemetry.settling_time_sec > thresholds.max_settling_time_sec:
            failures.append(
                f"settling time {telemetry.settling_time_sec:.2f}s exceeds max "
                f"{thresholds.max_settling_time_sec:.2f}s"
            )
        if telemetry.steady_state_error > thresholds.max_steady_state_error:
            failures.append(
                f"steady-state error {telemetry.steady_state_error:.4f} exceeds max "
                f"{thresholds.max_steady_state_error:.4f}"
            )
        if failures:
            return False, "step response FAILED: " + "; ".join(failures)
        return True, (
            f"step response PASSED: overshoot {telemetry.overshoot_pct:.1f}% "
            f"(max {thresholds.max_overshoot_pct:.1f}%), settling time "
            f"{telemetry.settling_time_sec:.2f}s (max "
            f"{thresholds.max_settling_time_sec:.2f}s), steady-state error "
            f"{telemetry.steady_state_error:.4f} (max "
            f"{thresholds.max_steady_state_error:.4f}), stable"
        )

    def ingest_and_record(
        self,
        student_id: str,
        competency_id: str,
        telemetry: StepResponseTelemetry,
        thresholds: TelemetryThresholds,
        manager: StudentModelManager,
    ) -> PracticalEvidence:
        """Evaluate telemetry, record it, and return the created evidence.

        Metrics map onto ``SimulationMetrics`` (overshoot, settling time,
        steady-state error); ``is_stable`` maps onto the ``stable`` flag.
        The attempt number is derived from the evidence already recorded for
        the competency so consecutive ingests produce 1-based attempts.
        """
        passed, _summary = self.evaluate_telemetry(telemetry, thresholds)
        record = manager.profile.competencies.get(competency_id)
        attempt = (len(record.evidence_history) + 1) if record else 1
        evidence = PracticalEvidence(
            task_id=competency_id,
            attempt=attempt,
            parameters=PIDParameters(kp=0.0, ki=0.0, kd=0.0),
            metrics=SimulationMetrics(
                overshoot=telemetry.overshoot_pct,
                settling_time=telemetry.settling_time_sec,
                steady_state_error=telemetry.steady_state_error,
            ),
            stable=telemetry.is_stable,
            requirements_met=passed,
            result="PASS" if passed else "FAIL",
        )
        manager.record_evidence(competency_id, evidence)
        return evidence