"""HTTP gateway: a typed REST surface over the AI/Education platform.

The gateway exposes four endpoints (health, coach chat, telemetry
submission, and student profiles) backed by the platform's persistent
singletons. It is the only layer that imports FastAPI, keeping the domain
engines transport-free.
"""

from ai_education.api.app import create_app
from ai_education.api.router import APIGateway
from ai_education.api.schemas import (
    ChatRequest,
    ChatResponse,
    MetricEvidence,
    PIDGains,
    StudentProfileResponse,
    TelemetrySubmissionRequest,
    TelemetrySubmissionResponse,
)

__all__ = [
    "APIGateway",
    "ChatRequest",
    "ChatResponse",
    "MetricEvidence",
    "PIDGains",
    "StudentProfileResponse",
    "TelemetrySubmissionRequest",
    "TelemetrySubmissionResponse",
    "create_app",
]