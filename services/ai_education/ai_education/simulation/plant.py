"""Continuous-time plant models for the step-response simulator.

The default model is a normalized, lightly damped second-order process that
represents the MEC271 drive/resonance plant. Its closed-loop PID behavior
reproduces the textbook failure modes the diagnosis layer reasons about:

- proportional-only control leaves steady-state error,
- excessive proportional gain raises overshoot sharply,
- missing integral action never zeroes the steady-state error,
- insufficient derivative damping leaves a slow oscillatory tail,
- excessive integral gain drives the loop into a growing limit cycle.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SecondOrderPlant:
    """A normalized second-order plant ``G(s) = gain / (s^2 + 2zw s + w^2)``.

    ``gain`` defaults to ``natural_frequency**2`` so the plant's DC gain is
    unity: a constant control of ``u`` drives the output to ``u``.
    """

    natural_frequency: float = 8.0
    damping_ratio: float = 0.3
    gain: Optional[float] = None

    def __post_init__(self) -> None:
        if self.natural_frequency <= 0:
            raise ValueError("natural_frequency must be positive")
        if self.damping_ratio <= 0:
            raise ValueError("damping_ratio must be positive")
        if self.gain is None:
            object.__setattr__(self, "gain", self.natural_frequency**2)
        if self.gain <= 0:
            raise ValueError("gain must be positive")

    def derivatives(
        self,
        state: tuple[float, float],
        control: float,
    ) -> tuple[float, float]:
        """Return the time derivatives for the ``(position, velocity)`` state."""
        x1, x2 = state
        dx1 = x2
        dx2 = (
            -2.0 * self.damping_ratio * self.natural_frequency * x2
            - self.natural_frequency**2 * x1
            + self.gain * control
        )
        return dx1, dx2