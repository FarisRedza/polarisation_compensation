import dataclasses
import typing
import enum

from .config import JacobianSearchConfig
from .jacobian import JacobianSolver, Vector2, Vector3


class JacobianActionType(enum.Enum):
    MOVE_TO = enum.auto()
    APPLY_STEP = enum.auto()
    FALLBACK = enum.auto()


@dataclasses.dataclass(frozen=True)
class JacobianAction:
    type: JacobianActionType
    motor_index: typing.Optional[int] = None
    position: typing.Optional[float] = None
    step: typing.Optional[Vector3] = None


@dataclasses.dataclass
class JacobianSearchState:
    """Runtime state for empirical Jacobian search."""

    iteration: int = 0
    probe_index: int = 0

    baseline_errors: typing.Optional[Vector2] = None
    baseline_score: typing.Optional[float] = None
    baseline_positions: typing.Optional[Vector3] = None

    columns: list[Vector2] = dataclasses.field(
        default_factory=list
    )

    condition: typing.Optional[float] = None
    predicted_score: typing.Optional[float] = None
    step: typing.Optional[Vector3] = None

    fallback_count: int = 0


class JacobianSearch:
    """Manage emperical Jacobian search and correction decisions.

    Motor execution and measurement acquisition are handled by
    PolCompController.
    """

    def __init__(
        self,
        config: JacobianSearchConfig,
    ) -> None:
        self.config = config
        self.solver = JacobianSolver(config)
        self.state = JacobianSearchState()

    def reset(self) -> None:
        """Reset all Jacobian state for a new compensation run."""
        self.state = JacobianSearchState()

    def reset_iteration(self) -> None:
        """Clear measurements and diagnostics for a new Jacobian."""
        state = self.state

        state.probe_index = 0
        state.baseline_errors = None
        state.baseline_score = None
        state.baseline_positions = None
        state.columns.clear()

        state.condition = None
        state.predicted_score = None
        state.step = None

    def begin_iteration(
        self,
        *,
        baseline_errors: Vector2,
        baseline_score: float,
        baseline_positions: Vector3,
    ) -> JacobianAction:
        self.reset_iteration()

        state = self.state

        state.baseline_errors = baseline_errors
        state.baseline_score = baseline_score
        state.baseline_positions = baseline_positions

        return self.start_probe()

    def start_probe(self) -> JacobianAction:
        state = self.state

        assert state.baseline_positions is not None

        index = state.probe_index

        return JacobianAction(
            type=JacobianActionType.MOVE_TO,
            motor_index=index,
            position=(
                state.baseline_positions[index]
                + self.config.probe_deg
            ),
        )

    def record_probe(
        self,
        *,
        probe_errors: Vector2,
    ) -> JacobianAction:
        state = self.state

        assert state.baseline_errors is not None
        assert state.baseline_positions is not None

        base_z, base_x = state.baseline_errors
        probe_z, probe_x = probe_errors

        state.columns.append(
            (
                (probe_z - base_z) / self.config.probe_deg,
                (probe_x - base_x) / self.config.probe_deg,
            )
        )

        index = state.probe_index

        return JacobianAction(
            type=JacobianActionType.MOVE_TO,
            motor_index=index,
            position=state.baseline_positions[index],
        )

    def advance_probe(self) -> JacobianAction:
        state = self.state

        state.probe_index += 1

        if state.probe_index < 3:
            return self.start_probe()

        return self.finish_iteration()

    def finish_iteration(self) -> JacobianAction:
        state = self.state

        assert state.baseline_errors is not None
        assert state.baseline_score is not None

        if len(state.columns) != 3:
            return JacobianAction(
                type=JacobianActionType.FALLBACK,
            )

        solution = self.solver.solve(
            columns=state.columns,
            baseline_errors=state.baseline_errors,
            baseline_score=state.baseline_score,
        )

        state.condition = solution.condition
        state.predicted_score = solution.predicted_score
        state.step = solution.step

        if not solution.accepted:
            return JacobianAction(
                type=JacobianActionType.FALLBACK,
            )

        assert solution.step is not None

        return JacobianAction(
            type=JacobianActionType.APPLY_STEP,
            step=solution.step,
        )