"""Discrete-time PID controller for the step-response simulator.

Position form with three practical safeguards a real embedded controller
needs:

- the derivative term acts on the *measured output*, not the error, so a
  setpoint step never causes a derivative kick,
- the control output is clamped to the actuator range,
- the integral term stops accumulating while the actuator is saturated in
  the direction the error is pushing it (conditional integration).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DiscretePID:
    """A sample-and-hold PID controller evaluated once per timestep."""

    kp: float
    ki: float
    kd: float
    dt: float = 0.01
    output_min: float = 0.0
    output_max: float = 10.0

    def __post_init__(self) -> None:
        if self.dt <= 0:
            raise ValueError("dt must be positive")
        if self.output_max <= self.output_min:
            raise ValueError("output_max must be greater than output_min")
        self.reset()

    def reset(self) -> None:
        """Clear the integral state and derivative memory."""
        self._integral: float = 0.0
        self._prev_measurement: Optional[float] = None

    def update(self, setpoint: float, measurement: float) -> float:
        """Advance one timestep and return the clamped control output."""
        error = setpoint - measurement
        derivative = 0.0
        if self._prev_measurement is not None:
            derivative = (measurement - self._prev_measurement) / self.dt
        self._prev_measurement = measurement

        raw = self.kp * error + self.ki * self._integral - self.kd * derivative
        output = min(max(raw, self.output_min), self.output_max)

        saturated = raw != output
        if saturated and (
            (output == self.output_max and error > 0)
            or (output == self.output_min and error < 0)
        ):
            return output
        self._integral += error * self.dt
        return output