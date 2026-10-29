"""Regression tests for line-search strategy decisions."""

import pytest

from polcomp.line_search import (
    CappedLineSearch,
    ExtendedLineSearch,
    LineSearchMode,
    SingleLineSearch,
    create_line_search,
)


def test_factory():
    assert create_line_search('disabled') is None
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


@pytest.mark.parametrize('cls', [ExtendedLineSearch, CappedLineSearch])
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
