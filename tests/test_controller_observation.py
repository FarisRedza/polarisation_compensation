from unittest.mock import Mock

import pytest

from polcomp.polcomp import PolCompController


@pytest.fixture
def controller():
    """Construct a controller without running a simulation."""
    return PolCompController(
        qwp1=Mock(),
        hwp=Mock(),
        qwp2=Mock(),
        measurements=Mock(),
    )


def test_search_observation_uses_search_objective(controller, monkeypatch):
    monkeypatch.setattr(
        controller,
        '_aggregate_results',
        lambda results: (0.02, 0.04),
    )

    observation = controller._observe_results(
        results=[],
        search=True,
    )

    assert observation.qber == 0.02
    assert observation.qx == 0.04

    assert observation.score == pytest.approx(
        controller.search_objective(
            qber=0.02,
            qx=0.04,
        )
    )

def test_lock_observation_uses_acceptance_objective(controller, monkeypatch):
    monkeypatch.setattr(
        controller,
        '_aggregate_results',
        lambda results: (0.02, 0.04),
    )

    observation = controller._observe_results(
        results=[],
        search=False,
    )

    assert observation.score == pytest.approx(
        controller.objective(
            qber=0.02,
            qx=0.04,
        )
    )