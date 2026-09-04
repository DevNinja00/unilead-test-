"""End-to-end live tuning demo for the MEC271 PID plant.

Runs the real stack with no LLM dependency: simulate -> ingest -> reason ->
remediate -> strategy plan, then loops a learner through three attempts (an
over-tuned unstable run, then two consecutive tuned passes) and prints the
platform's diagnosis, remediation, pace, and scaffolding at every step.

Run with ``python -m ai_education.simulation.demo``.
"""

from typing import Dict, List

from ai_education.domain.evidence import PIDParameters
from ai_education.domain.student import StudentModelManager
from ai_education.mastery import MasteryDeterminationEngine
from ai_education.reasoning import EvidenceReasoningEngine
from ai_education.remediation import RemediationEngine
from ai_education.robotics import RoboticsEvidenceIngestor, TelemetryThresholds
from ai_education.simulation.engine import PIDSimulationEngine
from ai_education.strategy import AdaptiveStrategyEngine

DEMO_COMPETENCY_ID = "MEC271-PID-TUNE"


def _line(label: str, value: object, indent: int = 1) -> str:
    return f"{'  ' * indent}{label}: {value}"


def run_demo(
    student_id: str = "demo-student",
    competency_id: str = DEMO_COMPETENCY_ID,
    verbose: bool = True,
) -> Dict[str, object]:
    """Run the scripted tuning story and return the event log."""
    manager = StudentModelManager.create_new_student(student_id)
    engine = PIDSimulationEngine()
    ingestor = RoboticsEvidenceIngestor()
    reasoning = EvidenceReasoningEngine()
    remediation = RemediationEngine()
    strategy = AdaptiveStrategyEngine()
    mastery = MasteryDeterminationEngine()
    thresholds = TelemetryThresholds()

    attempts = [
        (
            "Attempt 1 - over-tuned (Kp=2.0, Ki=12.0, Kd=0.0)",
            PIDParameters(kp=2.0, ki=12.0, kd=0.0),
        ),
        (
            "Attempt 2 - tuned (Kp=1.2, Ki=3.0, Kd=0.2)",
            PIDParameters(kp=1.2, ki=3.0, kd=0.2),
        ),
        (
            "Attempt 3 - tuned repeat (Kp=1.2, Ki=3.0, Kd=0.2)",
            PIDParameters(kp=1.2, ki=3.0, kd=0.2),
        ),
    ]

    log: List[Dict[str, object]] = []
    for label, gains in attempts:
        telemetry = engine.simulate_step(gains)
        passed, evaluation = ingestor.evaluate_telemetry(telemetry, thresholds)
        evidence = ingestor.ingest_and_record(
            student_id=student_id,
            competency_id=competency_id,
            telemetry=telemetry,
            thresholds=thresholds,
            manager=manager,
        )
        reasoning_summary = reasoning.analyze_competency_evidence(
            student_id, competency_id, manager
        )
        remediation_plan = remediation.build_remediation_plan(
            student_id, competency_id, manager, reasoning
        )
        strategy_plan = strategy.generate_strategy_plan(
            student_id, manager, reasoning
        )
        mastery_result = mastery.evaluate_mastery(
            student_id, competency_id, manager
        )

        event = {
            "attempt": label,
            "telemetry": telemetry,
            "evaluation": evaluation,
            "passed": passed,
            "state": manager.get_state(competency_id).value,
            "reasoning": reasoning_summary.model_dump(),
            "remediation": {
                "misconception": remediation_plan.misconception.value,
                "action": remediation_plan.action.value,
                "guided_question": remediation_plan.guided_question,
                "steps": remediation_plan.remediation_steps,
            },
            "strategy": strategy_plan.model_dump(),
            "mastery": mastery_result.model_dump(),
        }
        log.append(event)

        if verbose:
            print(f"\n{label}")
            print(_line("telemetry", (
                f"overshoot={telemetry.overshoot_pct:.1f}% "
                f"settling={telemetry.settling_time_sec:.2f}s "
                f"rise={telemetry.rise_time_sec:.2f}s "
                f"ess={telemetry.steady_state_error:.4f} "
                f"stable={telemetry.is_stable}"
            )))
            print(_line(
                "evaluation",
                f"{'PASS' if passed else 'FAIL'} - {evaluation}",
            ))
            print(_line("competency state", manager.get_state(competency_id).value))
            print(_line("misconception", remediation_plan.misconception.value))
            if not passed:
                print(_line("remediation action", remediation_plan.action.value))
                print(_line("guided question", remediation_plan.guided_question))
                for step in remediation_plan.remediation_steps:
                    print(_line("step", step, indent=2))
            print(_line(
                "strategy",
                f"pace={strategy_plan.current_pace.value} "
                f"scaffolding={strategy_plan.scaffolding_level.value} "
                f"recommended_mode={strategy_plan.recommended_mode.value}",
            ))
            print(_line(
                "mastery",
                f"is_mastered={mastery_result.is_mastered} "
                f"(consecutive_passes={mastery_result.consecutive_passes})",
            ))

    return {"student_id": student_id, "competency_id": competency_id, "events": log}


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()