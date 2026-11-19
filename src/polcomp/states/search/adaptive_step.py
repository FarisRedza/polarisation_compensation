"""Adaptive maximum step size for Jacobian corrections."""

import dataclasses
import math


@dataclasses.dataclass
class AdaptiveStepPolicy:
    """Adjust the step limit using measured prediction accuracy."""

    limits: tuple[float, ...] = (10.0, 12.0, 15.0)
    index: int = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        if not self.limits:
            raise ValueError('At least one step limit is required')

        if any(
            not math.isfinite(value) or value <= 0
            for value in self.limits
        ):
            raise ValueError('Step limits must be finite and positive')

        if tuple(sorted(set(self.limits))) != self.limits:
            raise ValueError(
                'Step limits must be strictly increasing'
            )

        self.reset()

    @property
    def max_total_step_deg(self) -> float:
        return self.limits[self.index]

    def reset(self) -> None:
        """Start each compensation run at the largest step limit."""
        self.index = len(self.limits) - 1

    def update(
        self,
        *,
        predicted_improvement: float,
        actual_improvement: float,
    ) -> float:
        """Update the limit after a completed correction.

        Reduce the limit only when the correction worsens the score.
        Positive improvements preserve the limit unless they achieve
        at least 80% of the predicted improvement.
        """

        if (
            not math.isfinite(predicted_improvement)
            or not math.isfinite(actual_improvement)
            or predicted_improvement <= 1e-9
        ):
            return self.max_total_step_deg

        ratio = actual_improvement / predicted_improvement

        if actual_improvement < 0:
            self.index = max(0, self.index - 1)

        elif ratio >= 0.8:
            self.index = min(
                len(self.limits) - 1,
                self.index + 1,
            )

        return self.max_total_step_deg