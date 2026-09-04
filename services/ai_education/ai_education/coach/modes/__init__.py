"""Per-mode coach handlers and the handler registry factory.

The package exposes the mode-handler classes plus ``build_handler_registry``,
the single place where ``AICoachOrchestrator`` maps a ``CoachMode`` to a
``BaseModeHandler`` implementation.
"""

from typing import Dict, Type

from ai_education.coach.modes.base import (
    DEFAULT_ACTIONS_BY_MODE,
    BaseModeHandler,
    CoachTurnRequest,
    CoachTurnResponse,
)
from ai_education.coach.modes.hint import HintHandler
from ai_education.coach.modes.learn import LearnHandler
from ai_education.coach.modes.practice import PracticeHandler
from ai_education.coach.modes.reflect import ReflectHandler
from ai_education.coach.modes.remediate import RemediateHandler
from ai_education.coach.modes.transfer import TransferHandler
from ai_education.domain.enums import CoachMode

MODE_HANDLER_CLASSES: Dict[CoachMode, Type[BaseModeHandler]] = {
    CoachMode.LEARN: LearnHandler,
    CoachMode.HINT: HintHandler,
    CoachMode.PRACTICE: PracticeHandler,
    CoachMode.REFLECT: ReflectHandler,
    CoachMode.REMEDIATE: RemediateHandler,
    CoachMode.TRANSFER: TransferHandler,
}


def build_handler_registry() -> Dict[CoachMode, BaseModeHandler]:
    """Instantiate one handler per ``CoachMode``, keyed by the mode."""
    return {mode: cls() for mode, cls in MODE_HANDLER_CLASSES.items()}


__all__ = [
    "BaseModeHandler",
    "CoachTurnRequest",
    "CoachTurnResponse",
    "DEFAULT_ACTIONS_BY_MODE",
    "HintHandler",
    "LearnHandler",
    "MODE_HANDLER_CLASSES",
    "PracticeHandler",
    "ReflectHandler",
    "RemediateHandler",
    "TransferHandler",
    "build_handler_registry",
]