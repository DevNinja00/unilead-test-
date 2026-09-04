"""Demo hardening & offline fallbacks for the AI/Education subsystem.

When the LLM provider fails (network drop, timeout, malformed response) the
coach must degrade gracefully instead of surfacing a 500. This package owns
the deterministic fallback engine and the demo/offline fixtures that keep
live demonstrations running with zero downtime.
"""

from ai_education.fallbacks.engine import CoachResponse, FallbackEngine
from ai_education.fallbacks.fixtures import (
    get_demo_student_profiles,
    get_demo_telemetry_samples,
)

__all__ = [
    "CoachResponse",
    "FallbackEngine",
    "get_demo_student_profiles",
    "get_demo_telemetry_samples",
]