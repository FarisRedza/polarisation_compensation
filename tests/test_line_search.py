"""Regression tests for line-search strategy decisions."""

import pytest

from polcomp.states.search.line_search import (
    CappedLineSearch,
    ConditionalLineSearch,
    ExtendedLineSearch,
    LineSearchMode,
    SingleLineSearch,
    create_line_search,
)


def test_factory():
    assert create_line_search('disabled') is None
    assert isinstance(create_line_search('conditional'), ConditionalLineSearch)
    assert isinstance(create_line_search('single'), SingleLineSearch)
    assert isinstance(create_line_search('extended'), ExtendedLineSearch)
    assert isinstance(create_line_search('capped'), CappedLineSearch)
    assert isinstance(create_line_search(LineSearchMode.SINGLE), SingleLineSearch)
    with pytest.raises(ValueError):
        create_line_search('unknown')


@pytest.mark.parametrize('mode', ['single', 'extended', 'capped'])
def test_first_trial(mode):
    strategy = create_line_search(mode)
    assert strategy is not None
    assert strategy.begin(baseline_score=1.0, full_score=0.8) == 1.5
    assert strategy.begin(baseline_score=1.0, full_score=1.0) == 0.5
    assert strategy.begin(baseline_score=1.0, full_score=1.2) == 0.5


def test_single_stops_after_one_trial():
    strategy = SingleLineSearch()
    assert strategy.next_alpha(
        alpha=1.5, score=0.6, previous_score=0.8,
        target_reached=False,
    ) is None


@pytest.mark.parametrize('cls', [ExtendedLineSearch, CappedLineSearch, ConditionalLineSearch])
def test_forward_exploration(cls):
    strategy = cls()
    assert strategy.next_alpha(
        alpha=1.5, score=0.6, previous_score=0.8,
        target_reached=False,
    ) == 2.0
    assert strategy.next_alpha(
        alpha=2.0, score=0.5, previous_score=0.6,
        target_reached=False,
    ) == 2.5
    for alpha, score, previous, reached in [
        (0.5, 0.2, 0.8, False),
        (1.5, 0.8, 0.8, False),
        (1.5, 0.9, 0.8, False),
        (1.5, 0.6, 0.8, True),
        (2.5, 0.4, 0.5, False),
    ]:
        assert strategy.next_alpha(
            alpha=alpha, score=score, previous_score=previous,
            target_reached=reached,
        ) is None


def test_capped_acceptance():
    assert ExtendedLineSearch().accepts(alpha=2.5)
    assert SingleLineSearch().accepts(alpha=1.5)
    assert CappedLineSearch().accepts(alpha=1.5)
    assert not CappedLineSearch().accepts(alpha=2.0)
    assert not CappedLineSearch().accepts(alpha=2.5)


@pytest.mark.parametrize('baseline, full, expected', [
    (1.0, 0.7, None),
    (1.0, 0.8, None),
    (1.0, 0.9, 1.5),
    (1.0, 1.0, 0.5),
    (1.0, 1.1, 0.5),
    (0.0, 0.0, 0.5),
])
def test_conditional_begin(baseline, full, expected):
    strategy = ConditionalLineSearch()
    assert strategy.begin(baseline_score=baseline, full_score=full) == expected


def test_conditional_configurable_threshold():
    strategy = create_line_search('conditional', min_relative_improvement=0.3)
    assert strategy.begin(baseline_score=1.0, full_score=0.8) == 1.5
    assert strategy.accepts(alpha=2.5)


@pytest.mark.parametrize('threshold', [-0.1, 1.1, float('nan')])
def test_invalid_conditional_threshold(threshold):
    with pytest.raises(ValueError):
        ConditionalLineSearch(threshold)
