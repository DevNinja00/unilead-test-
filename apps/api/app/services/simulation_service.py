"""PID simulation service — wired to the AI Education simulation engine.

The original mock returned a fixed ``SIMULATION_RESULT`` dict; this wired
version:

1. Builds a ``DiscretePID`` + ``SecondOrderPlant`` from the request.
2. Runs ``PIDSimulationEngine.simulate()`` with RK4 integration.
3. Extracts ``StepMetrics`` (overshoot, settling time, rise time, SSE, stable).
4. Evaluates the metrics against ``TelemetryThresholds``.
5. Builds a ``PracticalEvidence`` record and ingests it via
   ``RoboticsEvidenceIngestor.ingest_and_record()`` so the AI Education
   student model reflects the run.
6. Runs the ``MasteryDeterminationEngine`` to see if this attempt promoted
   the competency.
7. Syncs the new state back to the Compass ``student_state`` so
   ``/api/competencies`` and ``/api/progress`` show fresh data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import Request

from ..schemas.simulation import SimulationResult
from . import ai_education_bridge

_log = logging.getLogger("unilead.simulation")

if TYPE_CHECKING:
    pass


def _build_pid(kp: float, ki: float, kd: float):
    from ai_education.simulation.pid import DiscretePID

    return DiscretePID(kp=kp, ki=ki, kd=kd, output_min=-10.0, output_max=10.0)


def _build_plant():
    from ai_education.simulation.plant import SecondOrderPlant

    # Defaults: natural_frequency=8.0, damping_ratio=0.3 (DC gain = 1).
    # The plant is intentionally under-damped so the student has to work
    # to meet the overshoot requirement.
    return SecondOrderPlant(natural_frequency=8.0, damping_ratio=0.3)


def _simulate(kp: float, ki: float, kd: float):
    from ai_education.simulation.engine import PIDSimulationEngine

    pid = _build_pid(kp, ki, kd)
    plant = _build_plant()
    engine = PIDSimulationEngine()
    return engine.simulate(
        pid,
        plant=plant,
        setpoint=1.0,
        dt=0.01,
        duration=4.0,
    )


def _diagnose_misconception(telemetry):
    from ai_education.reasoning.misconceptions import diagnose_misconception

    try:
        m = diagnose_misconception(telemetry)
        return m.name if m and m.name != "NONE" else None
    except Exception:
        _log.debug("Could not diagnose misconception", exc_info=True)
        return None


def run_simulation(request_data, http_request: Request, student_id: str) -> dict:
    """Run a real PID simulation and record the evidence for ``student_id``."""
    from ai_education.robotics.ingestor import RoboticsEvidenceIngestor
    from ai_education.robotics.telemetry import TelemetryThresholds

    gateway = ai_education_bridge.get_gateway(http_request, student_id)
    compass_comp_id = request_data.competency_id or "pid-tuning"
    mec271_comp_id = ai_education_bridge.compass_id_to_mec271(compass_comp_id)

    # 1) Simulate
    step_response = _simulate(request_data.kp, request_data.ki, request_data.kd)

    # 2) Translate StepResponse → StepResponseTelemetry (the shape the
    #    robotics ingestor expects).
    from ai_education.robotics.telemetry import StepResponseTelemetry

    telemetry = StepResponseTelemetry(
        overshoot_pct=step_response.telemetry.overshoot_pct,
        settling_time_sec=step_response.telemetry.settling_time_sec,
        rise_time_sec=step_response.telemetry.rise_time_sec,
        steady_state_error=step_response.telemetry.steady_state_error,
        is_stable=step_response.telemetry.is_stable,
    )

    # 3) Evaluate against task thresholds (defaults: OS<10%, ST<2s, SSE<0.02)
    thresholds = TelemetryThresholds()
    ingestor = RoboticsEvidenceIngestor()
    passed, _summary = ingestor.evaluate_telemetry(telemetry, thresholds)

    # 4) Record evidence in the AI Education student model
    ingestor.ingest_and_record(
        student_id=student_id,
        competency_id=mec271_comp_id,
        telemetry=telemetry,
        thresholds=thresholds,
        manager=gateway.student_manager,
    )

    # 5) Run the mastery engine to potentially promote the competency
    try:
        from ai_education.mastery.engine import MasteryDeterminationEngine

        MasteryDeterminationEngine().evaluate_mastery(
            student_id=student_id,
            competency_id=mec271_comp_id,
            manager=gateway.student_manager,
        )
    except Exception:
        _log.debug("Mastery engine failure should never break the simulation response", exc_info=True)

    # 6) Sync state back to Compass student_state
    ai_education_bridge.sync_compass_state_from_manager(gateway)

    # 6c) Count attempts (now that the evidence has been recorded) and
    # append an evidence timeline event so the Evidence Timeline UI shows it.
    record = gateway.student_manager.profile.competencies.get(mec271_comp_id)
    attempt = len(record.evidence_history) if record else 1

    from . import student_state
    student_state.append_evidence_event(
        student_id=student_id,
        event_type="simulation_run",
        title=f"Simulation run #{attempt}",
        detail=(
            f"Kp={request_data.kp:.2f} Ki={request_data.ki:.2f} Kd={request_data.kd:.2f} → "
            f"overshoot {telemetry.overshoot_pct:.1f}% / "
            f"settling {telemetry.settling_time_sec:.2f}s / "
            f"SSE {telemetry.steady_state_error:.4f}. "
            f"{'Met requirements.' if passed else 'Failed requirements.'}"
        ),
        result="PASS" if passed else "FAIL",
        competency_id=compass_comp_id,
    )

    # 6d) Persist the full simulation run to the DB.
    try:
        from ..db import SessionLocal, crud
        db = SessionLocal()
        try:
            crud.save_simulation_run(
                db,
                student_id=student_id,
                competency_id=compass_comp_id,
                task_id=request_data.task_id,
                attempt=attempt,
                kp=request_data.kp,
                ki=request_data.ki,
                kd=request_data.kd,
                stable=telemetry.is_stable,
                overshoot=telemetry.overshoot_pct,
                settling_time=telemetry.settling_time_sec,
                rise_time=telemetry.rise_time_sec,
                steady_state_error=telemetry.steady_state_error,
                requirements_met=passed,
                result="PASS" if passed else "FAIL",
                misconception=None,  # filled below
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        _log.warning("Failed to persist simulation run for student=%s", student_id, exc_info=True)

    # 7) Detect misconception (only meaningful on FAIL)
    misconception = None if passed else _diagnose_misconception(telemetry)

    return SimulationResult(
        stable=telemetry.is_stable,
        overshoot=round(telemetry.overshoot_pct, 3),
        settling_time=round(telemetry.settling_time_sec, 3),
        rise_time=round(telemetry.rise_time_sec, 3),
        steady_state_error=round(telemetry.steady_state_error, 4),
        kp=request_data.kp,
        ki=request_data.ki,
        kd=request_data.kd,
        requirements_met=passed,
        result="PASS" if passed else "FAIL",
        attempt=attempt,
        competency_id=compass_comp_id,
        misconception=misconception,
    ).model_dump()
