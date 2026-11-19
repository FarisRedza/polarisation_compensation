import math

import pytest

from polcomp.config import JacobianSearchConfig
from polcomp.states.search.jacobian import JacobianSolver


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
@pytest.mark.parametrize('limit', [1.0, 5.0, 15.0])
def test_cauchy_limits_and_direction(limit):
    solver = JacobianSolver(JacobianSearchConfig(max_step_deg=2.0))
    result = solver.solve_cauchy(columns=[(.1, 0), (0, .2), (.1, .2)],
                                 baseline_errors=(1, 1), baseline_score=1,
                                 max_total_step_deg=limit)
    assert result.accepted
    assert math.hypot(*result.step) <= limit + 1e-12
    assert max(map(abs, result.step)) <= 2 + 1e-12
    assert result.step[1] == pytest.approx(2 * result.step[0])
    assert result.step[2] == pytest.approx(3 * result.step[0])


def test_cauchy_rank_deficient_exact_minimum():
    solver = JacobianSolver(JacobianSearchConfig())
    result = solver.solve_cauchy(columns=[(1, 0), (0, 0), (0, 0)],
                                 baseline_errors=(1, 1), baseline_score=1)
    assert result.accepted
    assert result.step == pytest.approx((-1, 0, 0))
    assert result.predicted_score == pytest.approx(1 / math.sqrt(2))


def test_cauchy_zero_gradient():
    result = JacobianSolver(JacobianSearchConfig()).solve_cauchy(
        columns=[(0, 0)] * 3, baseline_errors=(1, 1), baseline_score=1)
    assert not result.accepted
    assert result.step is None
