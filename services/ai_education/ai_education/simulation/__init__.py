"""Real-time PID step-response simulation engine (MEC271 plant).

Numerically integrates a continuous plant model under discrete PID control
and reduces the closed-loop trajectory to the ``StepResponseTelemetry``
payload the robotics evidence ingestor consumes. This closes the platform's
P0 gap: the subsystem now generates its own telemetry instead of relying on
an external simulator.
"""

from ai_education.simulation.engine import PIDSimulationEngine, StepResponse
from ai_education.simulation.metrics import StepMetrics, extract_step_metrics
from ai_education.simulation.pid import DiscretePID
from ai_education.simulation.plant import SecondOrderPlant

__all__ = [
    "DiscretePID",
    "PIDSimulationEngine",
    "SecondOrderPlant",
    "StepMetrics",
    "StepResponse",
    "extract_step_metrics",
]