"""Discrete-time step-response simulation engine (real PID + plant).

``PIDSimulationEngine`` numerically integrates a continuous plant driven by
a discrete-time PID controller and reduces the closed-loop trajectory to a
``StepResponseTelemetry`` payload - the exact contract the evidence
ingestor consumes. This closes the platform's P0 gap: the subsystem now
generates its own telemetry instead of relying on an external simulator.
"""

from typing import Iterator, List, Optional

from pydantic import BaseModel, ConfigDict

from ai_education.domain.evidence import PIDParameters
from ai_education.robotics.telemetry import StepResponseTelemetry
from ai_education.simulation.metrics import (
    StepMetrics,
    extract_step_metrics,
)
from ai_education.simulation.pid import DiscretePID
from ai_education.simulation.plant import SecondOrderPlant


class StepResponse(BaseModel):
    """The full simulated closed-loop trajectory plus its telemetry."""

    model_config = ConfigDict(frozen=True)

    times: List[float]
    output: List[float]
    control: List[float]
    telemetry: StepResponseTelemetry


def _rk4_step(
    plant: SecondOrderPlant,
    state: tuple[float, float],
    control: float,
    dt: float,
) -> tuple[float, float]:
    """Advance the plant state by ``dt`` with ``control`` held constant (ZOH)."""
    x1, x2 = state
    k1a, k1b = plant.derivatives((x1, x2), control)
    k2a, k2b = plant.derivatives((x1 + 0.5 * dt * k1a, x2 + 0.5 * dt * k1b), control)
    k3a, k3b = plant.derivatives((x1 + 0.5 * dt * k2a, x2 + 0.5 * dt * k2b), control)
    k4a, k4b = plant.derivatives((x1 + dt * k3a, x2 + dt * k3b), control)
    return (
        x1 + dt / 6.0 * (k1a + 2.0 * k2a + 2.0 * k3a + k4a),
        x2 + dt / 6.0 * (k1b + 2.0 * k2b + 2.0 * k3b + k4b),
    )


class PIDSimulationEngine:
    """Simulates closed-loop step responses for arbitrary PID gains."""

    def __init__(
        self,
        plant: Optional[SecondOrderPlant] = None,
        setpoint: float = 1.0,
        dt: float = 0.01,
        duration: float = 5.0,
    ) -> None:
        self.plant: SecondOrderPlant = plant or SecondOrderPlant()
        self.setpoint: float = setpoint
        self.dt: float = dt
        self.duration: float = duration

    def simulate(
        self,
        pid: PIDParameters,
        *,
        plant: Optional[SecondOrderPlant] = None,
        setpoint: Optional[float] = None,
        dt: Optional[float] = None,
        duration: Optional[float] = None,
    ) -> StepResponse:
        """Numerically integrate one closed-loop step response."""
        sim_plant = plant or self.plant
        ref = self.setpoint if setpoint is None else setpoint
        step = self.dt if dt is None else dt
        horizon = self.duration if duration is None else duration

        controller = DiscretePID(kp=pid.kp, ki=pid.ki, kd=pid.kd, dt=step)
        state: tuple[float, float] = (0.0, 0.0)
        control = 0.0

        times: List[float] = []
        output: List[float] = []
        control_log: List[float] = []

        steps = int(round(horizon / step))
        elapsed = 0.0
        for _ in range(steps + 1):
            times.append(elapsed)
            output.append(state[0])
            control_log.append(control)
            state = _rk4_step(sim_plant, state, control, step)
            control = controller.update(ref, state[0])
            elapsed = round(elapsed + step, 6)

        metrics: StepMetrics = extract_step_metrics(times, output, ref)
        telemetry = StepResponseTelemetry(
            overshoot_pct=metrics.overshoot_pct,
            settling_time_sec=metrics.settling_time_sec,
            rise_time_sec=metrics.rise_time_sec,
            steady_state_error=metrics.steady_state_error,
            is_stable=metrics.is_stable,
        )
        return StepResponse(
            times=times,
            output=output,
            control=control_log,
            telemetry=telemetry,
        )

    def simulate_step(
        self,
        pid: PIDParameters,
        **kwargs,
    ) -> StepResponseTelemetry:
        """Simulate one step response and return just its telemetry payload."""
        return self.simulate(pid, **kwargs).telemetry

    def step_samples(
        self,
        pid: PIDParameters,
        *,
        real_time: bool = False,
        **kwargs,
    ) -> Iterator[tuple[float, float, float]]:
        """Stream ``(elapsed, output, control)`` samples like a live sensor.

        With ``real_time=True`` the generator paces itself with ``time.sleep``
        so a demo can watch the response unfold at wall-clock speed.
        """
        sim_plant = self.plant
        ref = self.setpoint if "setpoint" not in kwargs else kwargs["setpoint"]
        step = self.dt if "dt" not in kwargs else kwargs["dt"]
        horizon = self.duration if "duration" not in kwargs else kwargs["duration"]
        if "plant" in kwargs and kwargs["plant"] is not None:
            sim_plant = kwargs["plant"]

        controller = DiscretePID(kp=pid.kp, ki=pid.ki, kd=pid.kd, dt=step)
        state: tuple[float, float] = (0.0, 0.0)
        control = 0.0
        elapsed = 0.0
        steps = int(round(horizon / step))
        while steps >= 0:
            yield elapsed, state[0], control
            state = _rk4_step(sim_plant, state, control, step)
            control = controller.update(ref, state[0])
            elapsed = round(elapsed + step, 6)
            if real_time:
                import time

                time.sleep(step)
            steps -= 1