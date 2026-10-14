import enum

from .measurement import Observation
from .objectives import targets_satisfied


class LockDecision(enum.Enum):
    COMPLETE = enum.auto()
    RETRY_SEARCH = enum.auto()


def evaluate_lock(
    *,
    observation: Observation,
    target_qber: float,
    target_qx: float,
) -> LockDecision:
    """Evaluate a completed stationary LOCK measurement window."""

    if targets_satisfied(
        qber=observation.qber,
        qx=observation.qx,
        target_qber=target_qber,
        target_qx=target_qx,
    ):
        return LockDecision.COMPLETE

    return LockDecision.RETRY_SEARCH