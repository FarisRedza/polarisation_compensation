import dataclasses


@dataclasses.dataclass(frozen=True)
class JacobianSearchConfig:
    """Configuration for empirical Jacobian-based search."""

    probe_deg: float = 2.0
    measurements: int = 3

    damping: float = 0.05
    max_step_deg: float = 10.0
    max_total_step_deg: float = 15.0

    min_determinant: float = 1e-6
    min_predicted_improvement: float = 0.02


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