"""AI Coach service — wired to the AI Education orchestrator.

The original mock returned a fixed ``COACH_SCRIPT`` indexed by ``turn_index``.
This wired version builds a ``CoachTurnRequest`` for the
``AICoachOrchestrator`` and translates its ``CoachTurnResponse`` back into
the Compass-facing ``CoachResponse`` shape.

Falls back to a deterministic script if anything goes wrong with the LLM
provider — the orchestrator already does this internally via
``FallbackEngine``, but we add a second safety net here so the route never
500s on a coach error.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import TYPE_CHECKING

from fastapi import Request

from ..schemas.coach import CoachResponse
from . import ai_education_bridge, student_state
from .mock_data import COACH_SCRIPT

_log = logging.getLogger("unilead.coach")

if TYPE_CHECKING:
    from ai_education.coach.orchestrator import AICoachOrchestrator
    from ai_education.domain.enums import CoachMode


# Map CoachMode strings (from the request schema) → CoachMode enum values.
def _resolve_mode(mode_str: str | None):
    from ai_education.domain.enums import CoachMode

    if mode_str is None:
        return None
    return CoachMode[mode_str]


# Track turn indices per student for backwards-compatible UI fields.
# LRU-bounded to prevent unbounded memory growth.
class _BoundedTurnCounters(OrderedDict):
    def __init__(self, maxsize: int = 500):
        super().__init__()
        self._maxsize = maxsize

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self._maxsize:
            self.popitem(last=False)


_TURN_COUNTERS: _BoundedTurnCounters = _BoundedTurnCounters()


def _sanitize_log_input(text: str) -> str:
    """Strip control characters and truncate to prevent log injection."""
    clean = "".join(c for c in text if c.isprintable() or c in "\n\t")
    return clean[:200]


def _next_turn_index(student_id: str) -> int:
    _TURN_COUNTERS[student_id] = _TURN_COUNTERS.get(student_id, 0) + 1
    return _TURN_COUNTERS[student_id]


def _reset_turn_index(student_id: str) -> None:
    _TURN_COUNTERS.pop(student_id, None)


async def process_turn(request_data, http_request: Request, student_id: str) -> dict:
    """Process one coach turn via the AI Education orchestrator for the
    given student_id."""
    gateway = ai_education_bridge.get_gateway(http_request, student_id)
    orchestrator: "AICoachOrchestrator" = gateway.orchestrator

    # Resolve target competency
    compass_comp_id = request_data.competency_id
    if compass_comp_id is None:
        compass_comp_id = ai_education_bridge.active_compass_competency_id(gateway)
    mec271_comp_id = ai_education_bridge.compass_id_to_mec271(compass_comp_id)

    # Resolve mode
    mode_enum = _resolve_mode(request_data.mode)

    # Build the orchestrator request
    from ai_education.coach.modes.base import CoachTurnRequest

    coach_request = CoachTurnRequest(
        student_id=student_id,
        user_message=request_data.message,
        mode=mode_enum,
    )

    try:
        turn_response = await orchestrator.process_turn(coach_request)
        coach_message = turn_response.coach_message
        active_mode = turn_response.active_mode.name if turn_response.active_mode else "LEARN"
        suggested_actions = list(turn_response.suggested_actions or [])
    except Exception:
        # Fallback: cycle through the original script so the UI keeps working
        # even if the LLM provider is unavailable mid-conversation.
        _log.warning("Coach orchestrator failed, using fallback script", exc_info=True)
        idx = _next_turn_index(student_id) - 1
        coach_message = COACH_SCRIPT[min(idx, len(COACH_SCRIPT) - 1)]
        active_mode = (mode_enum.name if mode_enum else "PRACTICE")
        suggested_actions = []

    # Determine scaffolding level
    scaffolding = "MEDIUM"
    try:
        scaffolding = gateway.scaffolding_level().name
    except Exception:
        _log.debug("Could not determine scaffolding level", exc_info=True)

    # Determine if the active competency is now demonstrated
    from ai_education.domain.enums import CompetencyState

    manager = gateway.student_manager
    record = manager.profile.competencies.get(mec271_comp_id)
    finished = bool(record and record.state in (CompetencyState.DEMONSTRATED, CompetencyState.MASTERED))
    if finished:
        _reset_turn_index(student_id)

    turn_index = _next_turn_index(student_id) - 1

    # Append an evidence timeline event so the Evidence Timeline UI shows
    # the coach interaction.
    from . import student_state
    student_state.append_evidence_event(
        student_id=student_id,
        event_type="coach_turn",
        title=f"Coach turn ({active_mode})",
        detail=(
            f"Student asked: \"{_sanitize_log_input(request_data.message[:80])}\". "
            f"Coach replied ({len(coach_message)} chars, scaffolding={scaffolding})."
        ),
        result="INFO",
        competency_id=compass_comp_id,
    )

    # Persist the coach turn to the DB (conversation + messages).
    try:
        from ..db import SessionLocal, crud
        db = SessionLocal()
        try:
            # Find or create the student's latest conversation.
            conv = crud.get_latest_conversation(db, student_id)
            if conv is None or conv.finished:
                conv = crud.create_conversation(
                    db,
                    student_id=student_id,
                    competency_id=compass_comp_id,
                    initial_mode=active_mode,
                )
            # Save the student's message + the coach's reply.
            crud.add_message(
                db,
                conversation_id=conv.id,
                sender="student",
                text=request_data.message,
            )
            crud.add_message(
                db,
                conversation_id=conv.id,
                sender="coach",
                text=coach_message,
                mode=active_mode,
                scaffolding_level=scaffolding,
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        _log.warning("Failed to persist coach turn to DB for student=%s", student_id, exc_info=True)

    return CoachResponse(
        message=coach_message,
        active_mode=active_mode,
        target_competency_id=compass_comp_id,
        scaffolding_level=scaffolding,
        suggested_actions=suggested_actions,
        turn_index=turn_index,
        total_turns=0,  # free-form, no fixed script length
        finished=finished,
    ).model_dump()
