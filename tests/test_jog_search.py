import dataclasses

from polcomp.config import JogSearchConfig
from polcomp.jog_search import (
    JogSearch,
    JogSearchState
)


def test_initial_state():
    search = JogSearch(
        JogSearchConfig()
    )

    assert search.state == JogSearchState()

def test_reset_line_preserves_cycle_state():
    search = JogSearch(JogSearchConfig())

    state = search.state

    state.waveplate_index = 2
    state.cycle = 3
    state.cycle_start_score = 2.0
    state.cycle_best_score = 1.5
    state.cycle_improvement = 0.25

    state.reference_score = 2.0
    state.reference_position = 10.0
    state.best_score = 1.5
    state.best_position = 15.0
    state.worsening_count = 2

    state.previous_position = 12.0
    state.measurement_position = 13.0
    state.measurement_start_position = 12.0
    state.measurement_end_position = 14.0

    search.reset_line()

    assert state.waveplate_index == 2
    assert state.cycle == 3
    assert state.cycle_start_score == 2.0
    assert state.cycle_best_score == 1.5
    assert state.cycle_improvement == 0.25

    assert state.reference_score is None
    assert state.reference_position is None
    assert state.best_score is None
    assert state.best_position is None
    assert state.worsening_count == 0

    assert state.previous_position is None
    assert state.measurement_position is None
    assert state.measurement_start_position is None
    assert state.measurement_end_position is None

def test_full_reset():
    search = JogSearch(JogSearchConfig())

    search.state.waveplate_index = 2
    search.state.cycle = 5
    search.state.best_score = 0.5
    search.state.worsening_count = 3

    search.reset()

    assert search.state == JogSearchState()

def test_independent_instances():
    config = JogSearchConfig()

    first = JogSearch(config)
    second = JogSearch(config)

    first.state.waveplate_index = 2
    first.state.cycle = 4
    first.state.best_score = 0.8

    assert second.state.waveplate_index == 0
    assert second.state.cycle == 0
    assert second.state.best_score is None

def test_reset_line_is_idempotent():
    search = JogSearch(JogSearchConfig())

    search.state.best_score = 0.5

    search.reset_line()
    expected = dataclasses.replace(search.state)

    search.reset_line()

    assert search.state == expected
