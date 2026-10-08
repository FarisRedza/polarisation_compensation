import dataclasses
import typing

from .config import JacobianSearchConfig


Vector2 = tuple[float, float]
Vector3 = tuple[float, float, float]


@dataclasses.dataclass(frozen=True)
class JacobianSolution:
    """Result of an empirical Jacobian correction calculation."""

    step: typing.Optional[Vector3]
    condition: float
    predicted_score: typing.Optional[float]
    predicted_improvement: typing.Optional[float]
    accepted: bool


class JacobianSolver:
    """Calculate a damped least-squares correction for three waveplates.

    The Jacobian has two rows, corresponding to normalized Z/X errors,
    and three columns, corresponding to QWP1, HWP and QWP2.
    """

    def __init__(
        self,
        config: JacobianSearchConfig,
    ) -> None:
        self.config = config

    def solve(
        self,
        *,
        columns: typing.Sequence[Vector2],
        baseline_errors: Vector2,
        baseline_score: float,
    ) -> JacobianSolution:
        if len(columns) != 3:
            raise ValueError(
                'Expected three Jacobian columns'
            )

        jz = [column[0] for column in columns]
        jx = [column[1] for column in columns]

        a = sum(value * value for value in jz)

        b = sum(
            z_value * x_value
            for z_value, x_value in zip(jz, jx)
        )

        d = sum(value * value for value in jx)

        trace = a + d
        determinant = a * d - b * b

        discriminant = max(
            trace * trace - 4.0 * determinant,
            0.0,
        ) ** 0.5

        eig_max = (trace + discriminant) / 2.0
        eig_min = (trace - discriminant) / 2.0

        if eig_min > 0:
            condition = (eig_max / eig_min) ** 0.5
        else:
            condition = float('inf')

        damping2 = self.config.damping ** 2

        aa = a + damping2
        dd = d + damping2
        det = aa * dd - b * b

        if det <= self.config.min_determinant:
            return JacobianSolution(
                step=None,
                condition=condition,
                predicted_score=None,
                predicted_improvement=None,
                accepted=False,
            )

        ez, ex = baseline_errors

        yz = (dd * ez - b * ex) / det
        yx = (-b * ez + aa * ex) / det

        step = [
            -(jz[i] * yz + jx[i] * yx)
            for i in range(3)
        ]

        step = [
            max(
                -self.config.max_step_deg,
                min(self.config.max_step_deg, value),
            )
            for value in step
        ]

        norm = sum(value * value for value in step) ** 0.5

        if norm > self.config.max_total_step_deg:
            scale = self.config.max_total_step_deg / norm
            step = [value * scale for value in step]

        predicted_z = ez + sum(
            jz[i] * step[i]
            for i in range(3)
        )

        predicted_x = ex + sum(
            jx[i] * step[i]
            for i in range(3)
        )

        predicted_score = (
            (predicted_z ** 2 + predicted_x ** 2) / 2.0
        ) ** 0.5

        # Preserve the existing relative-improvement calculation.
        predicted_improvement = (
            baseline_score - predicted_score
        ) / baseline_score

        accepted = (
            predicted_improvement
            >= self.config.min_predicted_improvement
        )

        return JacobianSolution(
            step=tuple(step),
            condition=condition,
            predicted_score=predicted_score,
            predicted_improvement=predicted_improvement,
            accepted=accepted,
        )