import pytest

from polcomp.polcomp import JacobianLineSearchResult


def test_forward_extension_diagnostics():
    result = JacobianLineSearchResult(
        iteration=3,
        baseline_score=5.0,
        full_score=3.0,
        trial_score=2.0,
        trial_alpha=1.5,
        accepted_alpha=1.5,
        extra_travel_deg=7.5,
    )

    assert result.trial_improvement == pytest.approx(1.0)
    assert result.accepted_score == pytest.approx(2.0)


def test_backtracking_diagnostics():
    result = JacobianLineSearchResult(
        iteration=4,
        baseline_score=5.0,
        full_score=6.0,
        trial_score=4.0,
        trial_alpha=0.5,
        accepted_alpha=0.5,
        extra_travel_deg=7.5,
    )

    assert result.trial_improvement == pytest.approx(2.0)
    assert result.accepted_score == pytest.approx(4.0)


def test_rejected_trial_diagnostics():
    result = JacobianLineSearchResult(
        iteration=5,
        baseline_score=5.0,
        full_score=3.0,
        trial_score=4.0,
        trial_alpha=1.5,
        accepted_alpha=1.0,
        extra_travel_deg=15.0,
    )

    assert result.trial_improvement == pytest.approx(-1.0)
    assert result.accepted_score == pytest.approx(3.0)


from polcomp.polcomp import (
    JacobianLineSearchResult,
    JacobianLineSearchTrial,
)


def test_multiple_forward_trials():
    result = JacobianLineSearchResult(
        iteration=3,
        baseline_score=5.0,
        full_score=4.0,
        trial_score=3.2,
        trial_alpha=2.5,
        accepted_alpha=2.0,
        extra_travel_deg=20.0,
        trials=(
            JacobianLineSearchTrial(1.5, 3.5),
            JacobianLineSearchTrial(2.0, 3.0),
            JacobianLineSearchTrial(2.5, 3.2),
        ),
    )

    assert result.accepted_score == pytest.approx(3.0)
    assert result.accepted_alpha == 2.0
    assert len(result.trials) == 3