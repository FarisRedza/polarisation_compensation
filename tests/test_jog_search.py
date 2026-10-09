import dataclasses

from polcomp.measurement import make_observation
from polcomp.config import JogSearchConfig
from polcomp.jog_search import (
    JogSearch,
    JogSearchState,
    JogActionType,
    JogDirection,
)


def make_search() -> JogSearch:
    search = JogSearch(JogSearchConfig())

    state = search.state
    state.reference_score = 1.0
    state.reference_position = 10.0
    state.best_score = 1.0
    state.best_position = 10.0

    return search

def make_test_observation(
    *,
    score: float,
    acceptance_score: float = 1.1,
):
    return make_observation(
        qber=acceptance_score * 0.05,
        qx=0.0,
        score=score,
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

def test_positive_improvement():
    search = make_search()

    action = search.record_measurement(
        observation=make_test_observation(
            score=0.8,
            acceptance_score=1.1,
        ),
        target_qber=0.05,
        target_qx=0.05,
        position=12.0,
        direction=JogDirection.POSITIVE,
    )

    assert action.type is JogActionType.CONTINUE
    assert search.state.best_score == 0.8
    assert search.state.best_position == 12.0
    assert search.state.worsening_count == 0

def test_positive_jog_reverses():
    search = make_search()

    for _ in range(
        search.config.worsening_measurements
    ):

        action = search.record_measurement(
            observation=make_test_observation(
                score=1.2,
                acceptance_score=1.2,
            ),
            target_qber=0.05,
            target_qx=0.05,
            position=12.0,
            direction=JogDirection.POSITIVE,
        )

    assert action.type is JogActionType.RETURN_FROM_POSITIVE
    assert action.position == 10.0

def test_positive_jog_returns_to_best():
    search = make_search()

    search.record_measurement(
        observation=make_test_observation(
            score=0.8,
            acceptance_score=1.1,
        ),
        target_qber=0.05,
        target_qx=0.05,
        position=12.0,
        direction=JogDirection.POSITIVE,
    )

    for _ in range(
        search.config.worsening_measurements
    ):
        action = search.record_measurement(
            observation=make_test_observation(
                score=0.9,
                acceptance_score=1.1,
            ),
            target_qber=0.05,
            target_qx=0.05,
            position=14.0,
            direction=JogDirection.POSITIVE,
        )

    assert action.type is JogActionType.RETURN_TO_BEST
    assert action.position == 12.0

def test_negative_jog_finishes():
    search = make_search()

    search.record_measurement(
        observation=make_test_observation(
            score=0.7,
            acceptance_score=1.1,
        ),
        target_qber=0.05,
        target_qx=0.05,
        position=8.0,
        direction=JogDirection.NEGATIVE,
    )

    for _ in range(
        search.config.worsening_measurements
    ):
        action = search.record_measurement(
            observation=make_test_observation(
                score=0.9,
                acceptance_score=1.1,
            ),
            target_qber=0.05,
            target_qx=0.05,
            position=7.0,
            direction=JogDirection.NEGATIVE,
        )

    assert action.type is JogActionType.RETURN_TO_BEST
    assert action.position == 8.0

def test_candidate_acceptance():
    search = make_search()

    action = search.record_measurement(
        observation=make_test_observation(
            score=0.7,
            acceptance_score=0.8,
        ),
        target_qber=0.05,
        target_qx=0.05,
        position=12.0,
        direction=JogDirection.POSITIVE,
    )

    assert action.type is JogActionType.RETURN_TO_LOCK
    assert action.position == 12.0

def test_equal_score_counts_as_worsening():
    search = make_search()

    action = search.record_measurement(
        observation=make_test_observation(
            score=1.0,
            acceptance_score=1.1,
        ),
        target_qber=0.05,
        target_qx=0.05,
        position=12.0,
        direction=JogDirection.POSITIVE,
    )

    assert action.type is JogActionType.CONTINUE
    assert search.state.worsening_count == 1
    assert search.state.best_position == 10.0

def test_begin_line_initializes_reference():
    search = JogSearch(JogSearchConfig())

    search.begin_line(
        observation=make_test_observation(score=1.5),
        position=20.0,
    )

    state = search.state

    assert state.reference_score == 1.5
    assert state.reference_position == 20.0
    assert state.best_score == 1.5
    assert state.best_position == 20.0
    assert state.worsening_count == 0

    assert state.cycle_start_score == 1.5
    assert state.cycle_best_score == 1.5

def test_begin_line_preserves_cycle_start():
    search = JogSearch(JogSearchConfig())

    search.begin_line(
        observation=make_test_observation(score=1.5),
        position=10.0,
    )

    search.state.waveplate_index = 1

    search.begin_line(
        observation=make_test_observation(score=1.2),
        position=20.0,
    )

    assert search.state.cycle_start_score == 1.5
    assert search.state.cycle_best_score == 1.2
    assert search.state.reference_score == 1.2

def test_begin_jog_resets_measurement_state():
    search = JogSearch(JogSearchConfig())

    state = search.state
    state.worsening_count = 3
    state.measurement_position = 15.0
    state.measurement_start_position = 14.0
    state.measurement_end_position = 16.0

    search.begin_jog(position=20.0)

    assert state.worsening_count == 0
    assert state.previous_position == 20.0
    assert state.measurement_position is None
    assert state.measurement_start_position is None
    assert state.measurement_end_position is None

def test_begin_return_preserves_best_position():
    search = JogSearch(JogSearchConfig())

    state = search.state
    state.best_score = 0.8
    state.best_position = 25.0
    state.worsening_count = 3
    state.previous_position = 24.0

    search.begin_return()

    assert state.worsening_count == 0
    assert state.previous_position is None

    assert state.best_score == 0.8
    assert state.best_position == 25.0

def test_advance_waveplate():
    search = JogSearch(JogSearchConfig())

    assert not search.advance_waveplate(
        waveplate_count=3,
    )
    assert search.state.waveplate_index == 1

    assert not search.advance_waveplate(
        waveplate_count=3,
    )
    assert search.state.waveplate_index == 2

    assert search.advance_waveplate(
        waveplate_count=3,
    )
    assert search.state.waveplate_index == 0
    assert search.state.cycle == 1

def test_cycle_improvement():
    search = JogSearch(JogSearchConfig())

    state = search.state

    state.waveplate_index = 2
    state.cycle_start_score = 2.0
    state.cycle_best_score = 1.5

    completed = search.advance_waveplate(
        waveplate_count=3,
    )

    assert completed
    assert state.cycle_improvement == 0.25
    assert state.cycle == 1

def test_cycle_improvement_zero_start():
    search = JogSearch(JogSearchConfig())

    state = search.state

    state.waveplate_index = 2
    state.cycle_start_score = 0.0
    state.cycle_best_score = 0.0

    search.advance_waveplate(waveplate_count=3)

    assert state.cycle_improvement == 0.0

def test_begin_fallback_cycle_preserves_counter():
    search = JogSearch(JogSearchConfig())

    state = search.state

    state.waveplate_index = 2
    state.cycle = 4
    state.cycle_start_score = 2.0
    state.cycle_best_score = 1.5
    state.cycle_improvement = 0.25

    search.begin_fallback_cycle()

    assert state.waveplate_index == 0
    assert state.cycle == 4

    assert state.cycle_start_score is None
    assert state.cycle_best_score is None
    assert state.cycle_improvement is None

def test_record_motor_position():
    search = JogSearch(JogSearchConfig())

    assert search.record_motor_position(
        position=10.0,
    ) is None

    assert search.record_motor_position(
        position=12.0,
    ) == (10.0, 12.0)

    assert search.record_motor_position(
        position=15.0,
    ) == (12.0, 15.0)

    assert search.state.previous_position == 15.0

def test_record_measurement_position():
    search = JogSearch(JogSearchConfig())

    search.record_measurement_position(
        start_position=10.0,
        end_position=14.0,
    )

    assert search.state.measurement_start_position == 10.0
    assert search.state.measurement_end_position == 14.0
    assert search.state.measurement_position == 12.0

def test_reset_line_clears_position_tracking():
    search = JogSearch(JogSearchConfig())

    search.record_motor_position(position=10.0)

    search.record_measurement_position(
        start_position=10.0,
        end_position=12.0,
    )

    search.reset_line()

    assert search.state.previous_position is None
    assert search.state.measurement_position is None
    assert search.state.measurement_start_position is None
    assert search.state.measurement_end_position is None

def test_acceptance_uses_both_error_targets():
    search = make_search()

    observation = make_observation(
        qber=0.01,
        qx=0.06,
        score=0.5,
    )

    action = search.record_measurement(
        observation=observation,
        target_qber=0.05,
        target_qx=0.05,
        position=12.0,
        direction=JogDirection.POSITIVE,
    )

    # Qx exceeds its target:
    # max(0.01 / 0.05, 0.06 / 0.05) = 1.2.
    #
    # The candidate must not be accepted merely because
    # its search score is low.

    assert action.type is JogActionType.CONTINUE

def test_acceptable_observation_returns_to_lock():
    search = make_search()

    observation = make_observation(
        qber=0.02,
        qx=0.03,
        score=0.5,
    )

    action = search.record_measurement(
        observation=observation,
        target_qber=0.05,
        target_qx=0.05,
        position=12.0,
        direction=JogDirection.POSITIVE,
    )

    assert action.type is JogActionType.RETURN_TO_LOCK
    assert action.position == 12.0