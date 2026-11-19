import pytest

from polcomp.measurement import make_observation
from polcomp.config import JacobianSearchConfig
from polcomp.states.search.jacobian_search import (
    JacobianCorrection,
    JacobianSearch,
    JacobianSearchState,
    JacobianActionType
)



def test_initial_state():
    search = JacobianSearch(
        JacobianSearchConfig()
    )

    assert search.state == JacobianSearchState()


def test_reset_iteration_preserves_counters():
    search = JacobianSearch(
        JacobianSearchConfig()
    )

    state = search.state

    state.iteration = 4
    state.fallback_count = 2
    state.probe_index = 2
    state.baseline_errors = (1.0, 2.0)
    state.baseline_score = 1.5
    state.baseline_positions = (10.0, 20.0, 30.0)
    state.columns.append((0.1, 0.2))
    state.condition = 5.0
    state.predicted_score = 1.0
    state.step = (1.0, 2.0, 3.0)

    search.reset_iteration()

    assert state.iteration == 4
    assert state.fallback_count == 2

    assert state.probe_index == 0
    assert state.baseline_errors is None
    assert state.baseline_score is None
    assert state.baseline_positions is None
    assert state.columns == []
    assert state.condition is None
    assert state.predicted_score is None
    assert state.step is None


def test_full_reset():
    search = JacobianSearch(
        JacobianSearchConfig()
    )

    search.state.iteration = 5
    search.state.fallback_count = 3
    search.state.columns.append((0.1, 0.2))

    search.reset()

    assert search.state == JacobianSearchState()


def test_search_instances_have_independent_state():
    config = JacobianSearchConfig()

    first = JacobianSearch(config)
    second = JacobianSearch(config)

    first.state.columns.append((0.1, 0.2))
    first.state.iteration = 3

    assert second.state.columns == []
    assert second.state.iteration == 0

def test_jacobian_probe_sequence():
    search = JacobianSearch(
        JacobianSearchConfig()
    )

    action = search.begin_iteration(
        observation=make_observation(
            qber=0.05,
            qx=0.05,
            score=1.0,
        ),
        target_qber=0.05,
        target_qx=0.05,
        baseline_positions=(10.0, 20.0, 30.0),
    )

    assert action.type is JacobianActionType.MOVE_TO
    assert action.motor_index == 0
    assert action.position == 12.0

    action = search.record_probe(
        observation=make_observation(
            qber=0.06,
            qx=0.05,
            score=1.2,
        ),
        target_qber=0.05,
        target_qx=0.05,
    )

    assert action.type is JacobianActionType.MOVE_TO
    assert action.motor_index == 0
    assert action.position == 10.0

    action = search.advance_probe()

    assert action.type is JacobianActionType.MOVE_TO
    assert action.motor_index == 1
    assert action.position == 22.0

def test_observation_normalisation():
    search = JacobianSearch(
        JacobianSearchConfig()
    )

    observation = make_observation(
        qber=0.02,
        qx=0.06,
        score=1.0,
    )

    errors = search._normalise_observation(
        observation,
        target_qber=0.04,
        target_qx=0.03,
    )

    assert errors == pytest.approx(
        (0.5, 2.0)
    )

def test_jacobian_correction_improvement():
    correction = JacobianCorrection(
        iteration=2,
        baseline_score=2.0,
        predicted_score=1.2,
        measured_score=1.5,
        step=(2.0, -1.0, 0.5),
    )

    assert correction.predicted_improvement == pytest.approx(0.8)
    assert correction.actual_improvement == pytest.approx(0.5)

@pytest.mark.parametrize("limit,alphas,expected", [
    (0, [0, 0, 0], [False, False, False]),
    (2, [0, 0], [False, True]),
    (2, [0, 0.25, 0, 0], [False, False, False, True]),
    (2, [0, None, 0], [False, False, False]),
    (1, [0], [True]),
])
def test_rejection_recovery(limit, alphas, expected):
    search = JacobianSearch(JacobianSearchConfig(rejection_limit=limit))
    for alpha, decision in zip(alphas, expected):
        search.reset_iteration()
        assert search.record_line_search(alpha) is decision
    search.reset_rejections()
    assert search.state.consecutive_rejections == 0


@pytest.mark.parametrize("limit", [-1, 1.5, True])
def test_invalid_rejection_limit(limit):
    with pytest.raises(ValueError):
        JacobianSearchConfig(rejection_limit=limit)

@pytest.mark.parametrize('enabled', [False, True])
def test_cauchy_numerical_recovery_once(enabled):
    search = JacobianSearch(JacobianSearchConfig(
        cauchy_recovery=enabled, line_search_mode='extended', min_determinant=1.0))
    search.state.columns = [(0.1, 0), (0, 0), (0, 0)]
    search.state.baseline_errors = (1, 1)
    search.state.baseline_score = 1
    action = search.finish_iteration()
    assert action.type is (JacobianActionType.APPLY_STEP if enabled else JacobianActionType.FALLBACK)
    assert search.state.cauchy_count == int(enabled)
    assert search.try_cauchy().type is JacobianActionType.FALLBACK
    search.reset_iteration()
    assert not search.state.cauchy_attempted
    assert search.state.cauchy_count == int(enabled)


def test_cauchy_after_accepted_dls_solution():
    search = JacobianSearch(JacobianSearchConfig(cauchy_recovery=True, line_search_mode='extended'))
    search.state.columns = [(0.1, 0), (0, 0.2), (0, 0)]
    search.state.baseline_errors = (1, 1)
    search.state.baseline_score = 1
    assert search.finish_iteration().type is JacobianActionType.APPLY_STEP
    assert search.state.cauchy_count == 0
    assert search.try_cauchy().type is JacobianActionType.APPLY_STEP
    assert search.try_cauchy().type is JacobianActionType.FALLBACK
