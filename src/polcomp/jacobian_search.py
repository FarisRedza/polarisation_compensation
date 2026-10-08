import dataclasses
import typing

from .config import JacobianSearchConfig
from .jacobian import JacobianSolver, Vector2, Vector3


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
    """Own Jacobian search state and its numerical solver.

    Probe sequencing and motor commands remain in PolCompController
    until the next decomposition stage.
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