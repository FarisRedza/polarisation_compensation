def acceptance_score(
    *,
    qber: float,
    qx: float,
    target_qber: float,
    target_qx: float,
) -> float:
    """Return the worst normalized BB84 error."""
    return max(
        qber / target_qber,
        qx / target_qx,
    )


def search_score(
    *,
    qber: float,
    qx: float,
    target_qber: float,
    target_qx: float,
) -> float:
    """Return the RMS of the normalized BB84 errors."""
    qber_normalised = qber / target_qber
    qx_normalised = qx / target_qx

    return (
        (
            qber_normalised ** 2
            + qx_normalised ** 2
        )
        / 2
    ) ** 0.5


def targets_satisfied(
    *,
    qber: float,
    qx: float,
    target_qber: float,
    target_qx: float,
) -> bool:
    """Return whether both BB84 error targets are satisfied."""
    return (
        acceptance_score(
            qber=qber,
            qx=qx,
            target_qber=target_qber,
            target_qx=target_qx,
        )
        <= 1
    )