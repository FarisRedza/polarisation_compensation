import math

import pytest

from polcomp.config import JacobianSearchConfig
from polcomp.jacobian import JacobianSolver


def test_jacobian_solver_reduces_error():
    solver = JacobianSolver(
        JacobianSearchConfig()
    )

    result = solver.solve(
        columns=[
            (0.1, 0.0),
            (0.0, 0.1),
            (0.0, 0.0),
        ],
        baseline_errors=(1.0, 1.0),
        baseline_score=1.0,
    )

    assert result.accepted
    assert result.step is not None

    assert result.step[0] < 0
    assert result.step[1] < 0

    assert result.predicted_score is not None
    assert result.predicted_score < 1.0


def test_jacobian_solver_handles_zero_jacobian():
    solver = JacobianSolver(
        JacobianSearchConfig()
    )

    result = solver.solve(
        columns=[
            (0.0, 0.0),
            (0.0, 0.0),
            (0.0, 0.0),
        ],
        baseline_errors=(1.0, 1.0),
        baseline_score=1.0,
    )

    assert not result.accepted

    assert result.step == (0.0, 0.0, 0.0)
    assert math.isinf(result.condition)

    assert result.predicted_score == 1.0
    assert result.predicted_improvement == 0.0

def test_jacobian_solver_rejects_small_determinant():
    config = JacobianSearchConfig(
        min_determinant=1e-4,
    )

    solver = JacobianSolver(config)

    result = solver.solve(
        columns=[
            (0.0, 0.0),
            (0.0, 0.0),
            (0.0, 0.0),
        ],
        baseline_errors=(1.0, 1.0),
        baseline_score=1.0,
    )

    assert not result.accepted
    assert result.step is None
    assert math.isinf(result.condition)

    assert result.predicted_score is None
    assert result.predicted_improvement is None

def test_jacobian_solver_limits_total_step():
    config = JacobianSearchConfig(
        max_step_deg=10.0,
        max_total_step_deg=5.0,
    )

    solver = JacobianSolver(config)

    result = solver.solve(
        columns=[
            (0.1, 0.0),
            (0.0, 0.1),
            (0.0, 0.0),
        ],
        baseline_errors=(1.0, 1.0),
        baseline_score=1.0,
    )

    assert result.step is not None

    norm = math.sqrt(
        sum(value ** 2 for value in result.step)
    )

    assert norm <= 5.0 + 1e-12


def test_jacobian_solver_rejects_insufficient_improvement():
    config = JacobianSearchConfig(
        min_predicted_improvement=0.99,
    )

    solver = JacobianSolver(config)

    result = solver.solve(
        columns=[
            (0.1, 0.0),
            (0.0, 0.1),
            (0.0, 0.0),
        ],
        baseline_errors=(1.0, 1.0),
        baseline_score=1.0,
    )

    assert not result.accepted


def test_jacobian_solver_requires_three_columns():
    solver = JacobianSolver(
        JacobianSearchConfig()
    )

    with pytest.raises(ValueError):
        solver.solve(
            columns=[
                (0.1, 0.0),
                (0.0, 0.1),
            ],
            baseline_errors=(1.0, 1.0),
            baseline_score=1.0,
        )