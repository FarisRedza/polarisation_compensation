import dataclasses


@dataclasses.dataclass(frozen=True)
class JacobianSearchConfig:
    """Configuration for empirical Jacobian-based search."""

    probe_deg: float = 2.0
    measurements: int = 3

    damping: float = 0.05
    max_step_deg: float = 10.0
    max_total_step_deg: float = 15.0
    adaptive_step: bool = False
    experimental_line_search: bool = False
    line_search_mode: str | None = None
    line_search_min_relative_improvement: float = 0.2

    min_determinant: float = 1e-6
    min_predicted_improvement: float = 0.02
    rejection_limit: int = 0
    cauchy_recovery: bool = False

    def __post_init__(self) -> None:
        if self.cauchy_recovery and self.line_search_mode not in (
            "extended", "backtracking"
        ):
            raise ValueError("Cauchy recovery requires extended or backtracking line search")
        if type(self.rejection_limit) is not int or self.rejection_limit < 0:
            raise ValueError("rejection_limit must be a non-negative integer")


@dataclasses.dataclass(frozen=True)
class JogSearchConfig:
    """Configuration for the rolling-jog fallback search."""

    reference_measurements: int = 3
    jog_measurements: int = 3
    worsening_measurements: int = 3

    jog_velocity: float = 5.0
    candidate_score: float = 0.90


@dataclasses.dataclass(frozen=True)
class LockConfig:
    """Configuration for stationary lock verification."""

    measurements: int = 5


@dataclasses.dataclass(frozen=True)
class PolCompConfig:
    """Configuration for the polarization compensation controller."""

    target_qber: float = 0.05
    target_qx: float = 0.05

    jacobian: JacobianSearchConfig = (
        dataclasses.field(
            default_factory=JacobianSearchConfig
        )
    )

    jog: JogSearchConfig = (
        dataclasses.field(
            default_factory=JogSearchConfig
        )
    )

    lock: LockConfig = (
        dataclasses.field(
            default_factory=LockConfig
        )
    )