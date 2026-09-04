"""FastAPI router for the AI/Education gateway.

Every endpoint is thin: it validates the request against the injected
singletons, delegates to the appropriate engine, and composes the response
schemas declared in ``ai_education.api.schemas``. The ``APIGateway`` class
owns the three persistent platform singletons (student model manager, AI
Coach orchestrator, evidence reasoning engine) so all requests share one
consistent backend.
"""

import uuid
from typing import Dict, List

from fastapi import APIRouter, HTTPException

from ai_education.api.schemas import (
    ChatRequest,
    ChatResponse,
    SimulateRequest,
    SimulateResponse,
    StudentProfileResponse,
    TelemetrySubmissionRequest,
    TelemetrySubmissionResponse,
)
from ai_education.coach.modes.base import CoachTurnRequest
from ai_education.coach.orchestrator import AICoachOrchestrator
from ai_education.domain.enums import CompetencyState
from ai_education.domain.evidence import PIDParameters, PracticalEvidence, SimulationMetrics
from ai_education.domain.student import StudentModelManager
from ai_education.reasoning import EvidenceReasoningEngine
from ai_education.robotics import RoboticsEvidenceIngestor, StepResponseTelemetry, TelemetryThresholds
from ai_education.simulation import PIDSimulationEngine
from ai_education.strategy import ScaffoldingLevel, evaluate_pace, evaluate_scaffolding_level

__all__ = ["APIGateway", "build_router"]


def _trailing_failures(evidence_history: List[PracticalEvidence]) -> int:
    """Count trailing attempts that did not meet requirements."""
    count = 0
    for evidence in reversed(evidence_history):
        if evidence.requirements_met:
            break
        count += 1
    return count


def _evidence_id(
    student_id: str, competency_id: str, evidence: PracticalEvidence
) -> str:
    """Deterministic, collision-safe evidence identifier for a submission."""
    seed = (
        f"{student_id}/{competency_id}/{evidence.attempt}@"
        f"{evidence.timestamp.isoformat()}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


class APIGateway:
    """Composes the persistent platform singletons behind the HTTP layer."""

    def __init__(
        self,
        student_manager: StudentModelManager,
        orchestrator: AICoachOrchestrator,
        reasoning_engine: EvidenceReasoningEngine,
    ) -> None:
        self.student_manager: StudentModelManager = student_manager
        self.orchestrator: AICoachOrchestrator = orchestrator
        self.reasoning_engine: EvidenceReasoningEngine = reasoning_engine

    def require_student(self, student_id: str) -> None:
        if self.student_manager.profile.student_id != student_id:
            raise HTTPException(
                status_code=404,
                detail=f"No student profile for student_id {student_id!r}",
            )

    def _aggregate_stats(self) -> Dict[str, int]:
        records = list(self.student_manager.profile.competencies.values())
        return {
            "total_attempts": sum(
                len(record.evidence_history) for record in records
            ),
            "total_failures": sum(
                1
                for record in records
                for evidence in record.evidence_history
                if not evidence.requirements_met
            ),
            "competencies_attempted": sum(
                1 for record in records if record.evidence_history
            ),
            "consecutive_failures": max(
                (_trailing_failures(record.evidence_history) for record in records),
                default=0,
            ),
        }

    def scaffolding_level(self) -> ScaffoldingLevel:
        progression = evaluate_pace(**self._aggregate_stats())
        return evaluate_scaffolding_level(progression)

    async def chat(self, payload: ChatRequest) -> ChatResponse:
        """Delegate one chat turn to the orchestrator and add context."""
        request = CoachTurnRequest(
            student_id=payload.student_id,
            user_message=payload.user_message,
            mode=payload.mode,
        )
        result = await self.orchestrator.process_turn(request)
        return ChatResponse(
            student_id=payload.student_id,
            coach_message=result.coach_message,
            active_mode=result.active_mode,
            scaffolding_level=self.scaffolding_level(),
        )

    def ingest_telemetry(
        self, payload: TelemetrySubmissionRequest
    ) -> TelemetrySubmissionResponse:
        """Evaluate a simulator run, record it, and reason over the evidence."""
        manager = self.student_manager
        record = manager.profile.competencies.get(payload.competency_id)
        if record is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown competency {payload.competency_id!r}",
            )
        telemetry = StepResponseTelemetry(
            overshoot_pct=payload.metrics.overshoot_pct,
            settling_time_sec=payload.metrics.settling_time_sec,
            rise_time_sec=payload.metrics.rise_time_sec,
            steady_state_error=payload.metrics.steady_state_error,
            is_stable=payload.metrics.is_stable,
        )
        passed, _summary = RoboticsEvidenceIngestor().evaluate_telemetry(
            telemetry, TelemetryThresholds()
        )
        evidence = PracticalEvidence(
            task_id=payload.competency_id,
            attempt=len(record.evidence_history) + 1,
            parameters=PIDParameters(
                kp=payload.gains.kp, ki=payload.gains.ki, kd=payload.gains.kd
            ),
            metrics=SimulationMetrics(
                overshoot=payload.metrics.overshoot_pct,
                settling_time=payload.metrics.settling_time_sec,
                steady_state_error=payload.metrics.steady_state_error,
            ),
            stable=payload.metrics.is_stable,
            requirements_met=passed,
            result="PASS" if passed else "FAIL",
        )
        manager.record_evidence(payload.competency_id, evidence)
        summary = self.reasoning_engine.analyze_competency_evidence(
            payload.student_id, payload.competency_id, manager
        )
        return TelemetrySubmissionResponse(
            evidence_id=_evidence_id(payload.student_id, payload.competency_id, evidence),
            diagnosed_misconception=summary.detected_misconception,
            recommended_mode=summary.recommended_mode,
            updated_competency_state=manager.get_state(payload.competency_id),
        )

    def simulate_and_ingest(
        self, payload: SimulateRequest
    ) -> SimulateResponse:
        """Run the built-in PID simulator and ingest the resulting telemetry."""
        manager = self.student_manager
        record = manager.profile.competencies.get(payload.competency_id)
        if record is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown competency {payload.competency_id!r}",
            )
        gains = PIDParameters(
            kp=payload.gains.kp, ki=payload.gains.ki, kd=payload.gains.kd
        )
        telemetry = PIDSimulationEngine(
            setpoint=payload.setpoint,
            dt=payload.dt,
            duration=payload.duration,
        ).simulate_step(gains)
        passed, _summary = RoboticsEvidenceIngestor().evaluate_telemetry(
            telemetry, TelemetryThresholds()
        )
        evidence = PracticalEvidence(
            task_id=payload.competency_id,
            attempt=len(record.evidence_history) + 1,
            parameters=gains,
            metrics=SimulationMetrics(
                overshoot=telemetry.overshoot_pct,
                settling_time=telemetry.settling_time_sec,
                steady_state_error=telemetry.steady_state_error,
            ),
            stable=telemetry.is_stable,
            requirements_met=passed,
            result="PASS" if passed else "FAIL",
        )
        manager.record_evidence(payload.competency_id, evidence)
        summary = self.reasoning_engine.analyze_competency_evidence(
            payload.student_id, payload.competency_id, manager
        )
        return SimulateResponse(
            evidence_id=_evidence_id(payload.student_id, payload.competency_id, evidence),
            diagnosed_misconception=summary.detected_misconception,
            recommended_mode=summary.recommended_mode,
            updated_competency_state=manager.get_state(payload.competency_id),
            telemetry=telemetry,
        )

    def profile(self, student_id: str) -> StudentProfileResponse:
        """Return the learner's full progress snapshot."""
        manager = self.student_manager
        records = list(manager.profile.competencies.values())
        states = [record.state for record in records]
        target = manager.get_next_target_competency()
        return StudentProfileResponse(
            student_id=student_id,
            course_id=manager.profile.course_id,
            total_competencies=len(records),
            demonstrated_count=states.count(CompetencyState.DEMONSTRATED),
            developing_count=states.count(CompetencyState.DEVELOPING),
            not_demonstrated_count=states.count(CompetencyState.NOT_DEMONSTRATED),
            mastered_count=states.count(CompetencyState.MASTERED),
            learning_pace=evaluate_pace(**self._aggregate_stats()),
            scaffolding_level=self.scaffolding_level(),
            unblocked_ids=[node.id for node in manager.get_unblocked_competencies()],
            target_competency_id=target.id if target else None,
            completed_competency_ids=manager.get_completed_competencies(),
        )


def build_router(gateway: APIGateway) -> APIRouter:
    """Build the route table for the AI Education gateway."""
    router = APIRouter()

    @router.get("/health", summary="Service liveness")
    def health() -> Dict[str, str]:
        return {"status": "ok", "service": "ai-education-gateway"}

    @router.post(
        "/coach/chat",
        response_model=ChatResponse,
        summary="Submit one AI Coach turn",
    )
    async def coach_chat(payload: ChatRequest) -> ChatResponse:
        gateway.require_student(payload.student_id)
        return await gateway.chat(payload)

    @router.post(
        "/evidence/telemetry",
        response_model=TelemetrySubmissionResponse,
        summary="Submit one simulator telemetry run",
    )
    async def submit_telemetry(
        payload: TelemetrySubmissionRequest,
    ) -> TelemetrySubmissionResponse:
        gateway.require_student(payload.student_id)
        return gateway.ingest_telemetry(payload)

    @router.post(
        "/evidence/simulate",
        response_model=SimulateResponse,
        summary="Run the built-in PID simulator and ingest the run",
    )
    async def simulate_run(payload: SimulateRequest) -> SimulateResponse:
        gateway.require_student(payload.student_id)
        return gateway.simulate_and_ingest(payload)

    @router.get(
        "/student/{student_id}/profile",
        response_model=StudentProfileResponse,
        summary="Fetch a learner's progress profile",
    )
    def student_profile(student_id: str) -> StudentProfileResponse:
        gateway.require_student(student_id)
        return gateway.profile(student_id)

    return router