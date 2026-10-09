from unittest.mock import Mock

import pytest
import qtoolkit

from polcomp import measurement
import polcomp.polcomp as controller_module


@pytest.fixture
def controller():
    """Construct a controller without running a simulation."""
    return controller_module.PolCompController(
        qwp1=Mock(),
        hwp=Mock(),
        qwp2=Mock(),
        measurements=Mock(),
    )


def test_search_observation_uses_search_objective(
    controller,
    monkeypatch,
):
    counts = qtoolkit.timetags.MeasurementCounts(
        singles={1: 100},
        coincidences={(1, 2): 50},
        duration_s=0.1,
        coincidence_window_ps=500,
    )

    def fake_aggregate(*, results, z_pairs, x_pairs):
        return measurement.AggregatedBB84Measurement(
            qber=0.02,
            qx=0.04,
            counts=counts,
        )

    monkeypatch.setattr(
        controller_module,
        'aggregate_bb84_measurements',
        fake_aggregate,
    )

    observation = controller._observe_results(
        results=[],
        search=True,
    )

    assert observation.qber == 0.02
    assert observation.qx == 0.04
    assert observation.counts is counts

    assert observation.score == pytest.approx(
        controller.search_objective(
            qber=0.02,
            qx=0.04,
        )
    )

def test_lock_observation_uses_acceptance_objective(
    controller,
    monkeypatch,
):
    def fake_aggregate(*, results, z_pairs, x_pairs):
        return measurement.AggregatedBB84Measurement(
            qber=0.02,
            qx=0.04,
        )

    monkeypatch.setattr(
        controller_module,
        "aggregate_bb84_measurements",
        fake_aggregate,
    )

    observation = controller._observe_results(
        results=[],
        search=False,
    )

    assert observation.qber == 0.02
    assert observation.qx == 0.04

    assert observation.score == pytest.approx(
        controller.objective(
            qber=0.02,
            qx=0.04,
        )
    )