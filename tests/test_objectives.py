import pytest

from polcomp.objectives import (
    acceptance_score,
    search_score,
    targets_satisfied,
)


@pytest.mark.parametrize(
    'qber, qx, expected',
    [
        (0.0, 0.0, 0.0),
        (0.01, 0.025, 0.5),
        (0.02, 0.05, 1.0),
        (0.03, 0.025, 1.5),
        (0.01, 0.075, 1.5),
    ],
)
def test_acceptance_score(qber, qx, expected):
    assert acceptance_score(
        qber=qber,
        qx=qx,
        target_qber=0.02,
        target_qx=0.05,
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    'qber, qx, expected',
    [
        (0.0, 0.0, 0.0),
        (0.02, 0.05, 1.0),
        (0.02, 0.0, 2**-0.5),
        (0.0, 0.05, 2**-0.5),
    ],
)
def test_search_score(qber, qx, expected):
    assert search_score(
        qber=qber,
        qx=qx,
        target_qber=0.02,
        target_qx=0.05,
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    'qber, qx, expected',
    [
        (0.0, 0.0, True),
        (0.01, 0.025, True),
        (0.02, 0.05, True),
        (0.020001, 0.05, False),
        (0.02, 0.050001, False),
    ],
)
def test_targets_satisfied(qber, qx, expected):
    assert targets_satisfied(
        qber=qber,
        qx=qx,
        target_qber=0.02,
        target_qx=0.05,
    ) is expected

def test_controller_objective_matches_pure_function(controller):
    qber = 0.03
    qx = 0.04

    expected = acceptance_score(
        qber=qber,
        qx=qx,
        target_qber=controller.target_qber,
        target_qx=controller.target_qx,
    )

    assert controller.objective(qber, qx) == expected


def test_controller_search_objective_matches_pure_function(controller):
    qber = 0.03
    qx = 0.04

    expected = search_score(
        qber=qber,
        qx=qx,
        target_qber=controller.target_qber,
        target_qx=controller.target_qx,
    )

    assert controller.search_objective(qber, qx) == expected


def test_controller_target_reached_matches_pure_function(controller):
    qber = 0.03
    qx = 0.04

    expected = targets_satisfied(
        qber=qber,
        qx=qx,
        target_qber=controller.target_qber,
        target_qx=controller.target_qx,
    )

    assert controller.target_reached(qber, qx) is expected
