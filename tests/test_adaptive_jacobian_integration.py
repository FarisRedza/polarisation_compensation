import pytest

from polcomp.config import JacobianSearchConfig
from polcomp.jacobian import JacobianSolver
from polcomp.jacobian_search import (
    JacobianCorrection,
    JacobianSearch,
)


def correction(
    predicted_improvement: float,
    actual_improvement: float,
) -> JacobianCorrection:
    return JacobianCorrection(
        iteration=1,
        baseline_score=2.0,
        predicted_score=2.0 - predicted_improvement,
        measured_score=2.0 - actual_improvement,
        step=(5.0, 0.0, 0.0),
    )


def test_adaptation_disabled_by_default():
    search = JacobianSearch(JacobianSearchConfig())

    search.record_correction(correction(1.0, -1.0))

    assert search.max_total_step_deg == 15.0


def test_bad_correction_reduces_search_limit():
    search = JacobianSearch(
        JacobianSearchConfig(adaptive_step=True)
    )

    search.record_correction(correction(1.0, -1.0))

    assert search.max_total_step_deg == 12.0


def test_good_correction_restores_search_limit():
    search = JacobianSearch(
        JacobianSearchConfig(adaptive_step=True)
    )

    search.record_correction(correction(1.0, -1.0))
    assert search.max_total_step_deg == 12.0

    search.record_correction(correction(1.0, 0.9))
    assert search.max_total_step_deg == 15.0


def test_search_reset_restores_initial_limit():
    search = JacobianSearch(
        JacobianSearchConfig(adaptive_step=True)
    )

    search.record_correction(correction(1.0, -1.0))
    assert search.max_total_step_deg == 12.0

    search.reset()

    assert search.max_total_step_deg == 15.0


def test_solver_respects_override():
    solver = JacobianSolver(JacobianSearchConfig())

    kwargs = dict(
        columns=(
            (0.1, 0.0),
            (0.0, 0.1),
            (0.0, 0.0),
        ),
        baseline_errors=(2.0, 2.0),
        baseline_score=2.0,
    )

    baseline = solver.solve(**kwargs)
    limited = solver.solve(
        **kwargs,
        max_total_step_deg=10.0,
    )

    assert baseline.step is not None
    assert limited.step is not None

    baseline_norm = sum(x * x for x in baseline.step) ** 0.5
    limited_norm = sum(x * x for x in limited.step) ** 0.5

    # The individual 10° limits constrain the baseline
    # correction before the 15° total limit is reached.
    assert baseline_norm == pytest.approx(200 ** 0.5)

    # The overridden 10° total limit must be enforced.
    assert limited_norm == pytest.approx(10.0)

    # The override must reduce the correction magnitude.
    assert limited_norm < baseline_norm


def test_adaptive_configuration_rejects_other_upper_limit():
    with pytest.raises(ValueError):
        JacobianSearch(
            JacobianSearchConfig(
                adaptive_step=True,
                max_total_step_deg=12.0,
            )
        )


def test_solver_override_from_saturated_baseline():
    solver = JacobianSolver(
        JacobianSearchConfig(
            max_step_deg=20.0,
            max_total_step_deg=15.0,
        )
    )

    kwargs = dict(
        columns=(
            (0.1, 0.0),
            (0.0, 0.1),
            (0.0, 0.0),
        ),
        baseline_errors=(2.0, 2.0),
        baseline_score=2.0,
    )

    baseline = solver.solve(**kwargs)
    limited = solver.solve(
        **kwargs,
        max_total_step_deg=10.0,
    )

    assert baseline.step is not None
    assert limited.step is not None

    baseline_norm = sum(x * x for x in baseline.step) ** 0.5
    limited_norm = sum(x * x for x in limited.step) ** 0.5

    assert baseline_norm == pytest.approx(15.0)
    assert limited_norm == pytest.approx(10.0)