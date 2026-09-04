"""Deterministic, offline-safe coach responses for demo hardening.

``FallbackEngine`` replaces an unavailable LLM provider with high-quality,
mode-specific pedagogical guidance. Responses are fully deterministic: the
same inputs always yield the same ``CoachResponse``, so demonstrations and
offline test runs stay reproducible and never depend on network state.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ai_education.domain.enums import CoachMode
from ai_education.reasoning import PIDMisconception
from ai_education.strategy import ScaffoldingLevel

DEFAULT_ACTIONS_BY_MODE: Dict[CoachMode, List[str]] = {
    CoachMode.LEARN: [
        "Review the concept at the target competency's level",
        "Ask a conceptual check-in question",
    ],
    CoachMode.HINT: [
        "Offer a single small hint phrased as a question",
        "Let the student propose the next gain change",
    ],
    CoachMode.PRACTICE: [
        "Run a tuning attempt in the simulator",
        "Explain your reasoning for each gain change before running",
        "Predict the step response before you apply the change",
    ],
    CoachMode.REFLECT: [
        "Summarize what you learned this session",
        "Identify one thing that surprised you",
    ],
    CoachMode.REMEDIATE: [
        "Diagnose the misconception behind the last failure",
        "Rebuild the foundational concept with quick exercises",
    ],
    CoachMode.TRANSFER: [
        "Generalize the learned principle to a new scenario",
        "Explain how the concept would behave in a different plant",
    ],
}

_SCAFFOLD_PREAMBLES: Dict[ScaffoldingLevel, str] = {
    ScaffoldingLevel.HIGH: (
        "Offline fallback mode | maximum scaffolding: every step is walked "
        "through explicitly."
    ),
    ScaffoldingLevel.MEDIUM: (
        "Offline fallback mode | structured support: a self-contained line of "
        "reasoning follows."
    ),
    ScaffoldingLevel.LOW: (
        "Offline fallback mode | minimal support: concise, high-level guidance "
        "follows."
    ),
}

_MODE_GUIDANCE: Dict[CoachMode, str] = {
    CoachMode.LEARN: (
        "Let us build the idea behind {competency} from first principles. Read "
        "the concept, then answer one check-in question before touching any "
        "gains."
    ),
    CoachMode.HINT: (
        "Change one gain at a time and watch how overshoot, settling time, and "
        "steady-state error respond before you change anything else."
    ),
    CoachMode.PRACTICE: (
        "Run one tuning attempt for {competency}. Predict the step response "
        "before you apply the change and explain the reasoning behind each "
        "gain." 
    ),
    CoachMode.REFLECT: (
        "Summarise the key PID insight from this session and name one surprise "
        "about the plant's response."
    ),
    CoachMode.REMEDIATE: (
        "We are targeting {misconception} before moving on. Rebuild the concept "
        "with a short guided exercise, then retry the last attempt."
    ),
    CoachMode.TRANSFER: (
        "Generalise the {competency} principle to a new plant: describe how "
        "each gain would behave in a different system and which failure modes "
        "to watch for."
    ),
}

_MISCONCEPTION_HINTS: Dict[PIDMisconception, str] = {
    PIDMisconception.EXCESSIVE_PROPORTIONAL_GAIN: (
        "excessive proportional gain (reduce Kp and redistribute action "
        "across the gains)"
    ),
    PIDMisconception.MISSING_INTEGRAL_ACTION: (
        "missing integral action (the steady-state offset will not clear "
        "without Ki)"
    ),
    PIDMisconception.INSUFFICIENT_DERIVATIVE_DAMPING: (
        "insufficient derivative damping (raise Kd so the ring-down settles "
        "sooner)"
    ),
    PIDMisconception.UNSTABLE_TUNING: (
        "unstable tuning (the gains are wildly out of range; drop Kp and "
        "re-tune step by step)"
    ),
    PIDMisconception.NONE: (
        "the step response itself (verify it stays inside the target band)"
    ),
}


class CoachResponse(BaseModel):
    """A coached reply served when the LLM provider is unavailable.

    Mirrors the shape of ``ai_education.coach.modes.base.CoachTurnResponse``
    while carrying the extra fallback metadata the gateway needs to report a
    degraded-but-operational turn.
    """

    student_id: str
    competency_id: Optional[str] = None
    coach_message: str
    active_mode: CoachMode
    misconception: Optional[PIDMisconception] = None
    scaffolding_level: ScaffoldingLevel = ScaffoldingLevel.MEDIUM
    suggested_actions: List[str] = Field(default_factory=list)
    from_fallback: bool = True


class FallbackEngine:
    """Generates deterministic, mode-appropriate pedagogy on LLM failure."""

    def generate_fallback_response(
        self,
        student_id: str,
        competency_id: str,
        mode: CoachMode,
        misconception: Optional[PIDMisconception] = None,
        scaffolding: ScaffoldingLevel = ScaffoldingLevel.MEDIUM,
    ) -> CoachResponse:
        """Build a valid coach reply without ever calling the LLM provider."""
        core = self._compose_core(mode, competency_id, misconception)
        coach_message = f"{_SCAFFOLD_PREAMBLES[scaffolding]}\n{core}"
        return CoachResponse(
            student_id=student_id,
            competency_id=competency_id or None,
            coach_message=coach_message,
            active_mode=mode,
            misconception=misconception,
            scaffolding_level=scaffolding,
            suggested_actions=list(DEFAULT_ACTIONS_BY_MODE[mode]),
            from_fallback=True,
        )

    @staticmethod
    def _compose_core(
        mode: CoachMode,
        competency_id: Optional[str],
        misconception: Optional[PIDMisconception],
    ) -> str:
        guidance = _MODE_GUIDANCE[mode]
        if mode is CoachMode.REMEDIATE:
            focus = _MISCONCEPTION_HINTS.get(
                misconception, _MISCONCEPTION_HINTS[PIDMisconception.NONE]
            )
            return guidance.format(misconception=focus)
        return guidance.format(competency=competency_id or "this competency")