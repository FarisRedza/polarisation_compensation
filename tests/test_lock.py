from unittest.mock import Mock

import pytest

from polcomp.lock import LockDecision, evaluate_lock
from polcomp.measurement import make_observation
from polcomp.polcomp import CompensationState, SearchState


@pytest.mark.parametrize(
    'qber, qx, expected',
    [
        (0.0, 0.0, LockDecision.COMPLETE),
        (0.01, 0.025, LockDecision.COMPLETE),
        (0.02, 0.05, LockDecision.COMPLETE),
        (0.020001, 0.05, LockDecision.RETRY_SEARCH),
        (0.02, 0.050001, LockDecision.RETRY_SEARCH),
        (0.03, 0.075, LockDecision.RETRY_SEARCH),
    ],
)
def test_evaluate_lock(qber, qx, expected):
    observation = make_observation(
        qber=qber,
        qx=qx,
        score=0.0,
    )

    decision = evaluate_lock(
        observation=observation,
        target_qber=0.02,
        target_qx=0.05,
    )

    assert decision is expected

def test_controller_lock_complete(controller, monkeypatch):
    observation = make_observation(
        qber=0.0,
        qx=0.0,
        score=0.0,
    )

    monkeypatch.setattr(
        controller,
        "_observe_results",
        Mock(return_value=observation),
    )

    controller.state = CompensationState.LOCK
    controller._lock_results = [
        Mock()
        for _ in range(controller.lock_measurements - 1)
    ]

    controller._update_lock(result=Mock())

    assert controller.state is CompensationState.COMPLETE
    assert controller._lock_results == []
    assert controller._score == 0.0


def test_controller_lock_retry(controller, monkeypatch):
    observation = make_observation(
        qber=1.0,
        qx=1.0,
        score=10.0,
    )

    monkeypatch.setattr(
        controller,
        "_observe_results",
        Mock(return_value=observation),
    )

    controller.state = CompensationState.LOCK
    controller._using_jog_fallback = True
    controller._search_state = SearchState.JOG_POSITIVE
    controller._search_results = [Mock()]

    controller._lock_results = [
        Mock()
        for _ in range(controller.lock_measurements - 1)
    ]

    controller._update_lock(result=Mock())

    assert controller.state is CompensationState.SEARCH
    assert controller._search_state is SearchState.START
    assert not controller._using_jog_fallback
    assert controller._search_results == []
    assert controller._lock_results == []
    assert controller._score == 10.0