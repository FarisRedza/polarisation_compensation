from polcomp.config import JacobianSearchConfig
from polcomp.jacobian_search import (
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
        baseline_errors=(1.0, 1.0),
        baseline_score=1.0,
        baseline_positions=(10.0, 20.0, 30.0),
    )

    assert action.type is JacobianActionType.MOVE_TO
    assert action.motor_index == 0
    assert action.position == 12.0

    action = search.record_probe(
        probe_errors=(1.2, 1.0),
    )

    assert action.type is JacobianActionType.MOVE_TO
    assert action.motor_index == 0
    assert action.position == 10.0

    action = search.advance_probe()

    assert action.type is JacobianActionType.MOVE_TO
    assert action.motor_index == 1
    assert action.position == 22.0