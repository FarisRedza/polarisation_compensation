"""Tests for correction-specific diagnostics (Stage 5A.3.4)."""

import pytest

from polcomp.jacobian_search import JacobianCorrection
from diagnose_compensation import sample_to_row


def test_correction_preserves_condition_and_step():
    correction = JacobianCorrection(
        iteration=2,
        baseline_score=2.0,
        predicted_score=1.2,
        measured_score=1.5,
        step=(5.0, -10.0, 15.0),
        condition=4.5,
    )
    assert correction.condition == 4.5
    assert correction.step == (5.0, -10.0, 15.0)
    assert correction.predicted_improvement == pytest.approx(0.8)
    assert correction.actual_improvement == pytest.approx(0.5)


def test_diagnostic_csv_exports_correction_fields():
    from types import SimpleNamespace

    correction = JacobianCorrection(
        iteration=2,
        baseline_score=2.0,
        predicted_score=1.2,
        measured_score=1.5,
        step=(5.0, -10.0, 15.0),
        condition=4.5,
    )
    sample = SimpleNamespace(
        elapsed_s=1.0,
        controller_state='SEARCH',
        search_state='START',
        qber=0.1,
        qx=0.2,
        search_score=2.0,
        acceptance_score=3.0,
        controller_score=2.0,
        jacobian_iteration=2,
        jacobian_condition=None,
        jacobian_fallback_count=0,
        jacobian_max_total_step_deg=15.0,
        jacobian_predicted_score=None,
        jacobian_step=None,
        compensation_positions=(0.0, 0.0, 0.0),
        jacobian_correction=correction,
    )
    row = sample_to_row(sample)
    assert row['correction_condition'] == 4.5
    assert row['correction_step_qwp1_deg'] == 5.0
    assert row['correction_step_hwp_deg'] == -10.0
    assert row['correction_step_qwp2_deg'] == 15.0
    assert row['jacobian_max_total_step_deg'] == 15.0
