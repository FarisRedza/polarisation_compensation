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