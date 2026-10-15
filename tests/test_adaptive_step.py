import pytest

from polcomp.adaptive_step import AdaptiveStepPolicy


def test_starts_at_baseline_limit():
    policy = AdaptiveStepPolicy()

    assert policy.max_total_step_deg == 15.0


def test_bad_corrections_reduce_limit():
    policy = AdaptiveStepPolicy()

    policy.update(
        predicted_improvement=2.0,
        actual_improvement=-0.5,
    )
    assert policy.max_total_step_deg == 12.0

    policy.update(
        predicted_improvement=2.0,
        actual_improvement=0.2,
    )
    assert policy.max_total_step_deg == 10.0


def test_step_limit_has_lower_bound():
    policy = AdaptiveStepPolicy()

    for _ in range(10):
        policy.update(
            predicted_improvement=2.0,
            actual_improvement=-1.0,
        )

    assert policy.max_total_step_deg == 10.0


def test_good_corrections_restore_limit():
    policy = AdaptiveStepPolicy()

    for _ in range(2):
        policy.update(
            predicted_improvement=2.0,
            actual_improvement=0.0,
        )

    assert policy.max_total_step_deg == 10.0

    policy.update(
        predicted_improvement=2.0,
        actual_improvement=1.8,
    )
    assert policy.max_total_step_deg == 12.0

    policy.update(
        predicted_improvement=2.0,
        actual_improvement=1.8,
    )
    assert policy.max_total_step_deg == 15.0


def test_moderate_improvement_preserves_limit():
    policy = AdaptiveStepPolicy()

    policy.update(
        predicted_improvement=2.0,
        actual_improvement=1.2,
    )

    assert policy.max_total_step_deg == 15.0


@pytest.mark.parametrize(
    'predicted',
    [0.0, -1.0, 1e-12, float('nan')],
)
def test_invalid_predictions_do_not_change_limit(predicted):
    policy = AdaptiveStepPolicy()

    policy.update(
        predicted_improvement=predicted,
        actual_improvement=-1.0,
    )

    assert policy.max_total_step_deg == 15.0


def test_reset_restores_baseline():
    policy = AdaptiveStepPolicy()

    policy.update(
        predicted_improvement=2.0,
        actual_improvement=-1.0,
    )

    policy.reset()

    assert policy.max_total_step_deg == 15.0