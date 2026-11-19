"""Pluggable decisions for Jacobian correction line search.

Strategies only choose trial scales; the controller owns motor movement,
measurement acquisition, best-position bookkeeping, and diagnostics.
"""

import abc
import enum


class LineSearchMode(str, enum.Enum):
    DISABLED = 'disabled'
    SINGLE = 'single'
    EXTENDED = 'extended'
    CAPPED = 'capped'


class LineSearchStrategy(abc.ABC):
    """Policy for choosing and accepting line-search trials."""

    def begin(self, *, baseline_score: float, full_score: float) -> float | None:
        """Choose the first trial scale after the full Jacobian step."""
        return 1.5 if full_score < baseline_score else 0.5

    def accepts(self, *, alpha: float) -> bool:
        """Whether a trial at this scale may become the accepted point."""
        return True

    @abc.abstractmethod
    def next_alpha(
        self,
        *,
        alpha: float,
        score: float,
        previous_score: float,
        target_reached: bool,
    ) -> float | None:
        """Choose the next trial scale, or finish the line search."""


class SingleLineSearch(LineSearchStrategy):
    def next_alpha(
        self, *, alpha: float, score: float,
        previous_score: float, target_reached: bool,
    ) -> float | None:
        return None


class ExtendedLineSearch(LineSearchStrategy):
    def next_alpha(
        self, *, alpha: float, score: float,
        previous_score: float, target_reached: bool,
    ) -> float | None:
        if (
            alpha >= 1.5
            and score < previous_score
            and alpha < 2.5
            and not target_reached
        ):
            return min(alpha + 0.5, 2.5)
        return None


class CappedLineSearch(ExtendedLineSearch):
    def accepts(self, *, alpha: float) -> bool:
        return alpha <= 1.5


def create_line_search(
    mode: LineSearchMode | str,
) -> LineSearchStrategy | None:
    """Create the requested strategy; disabled needs no strategy."""
    mode = LineSearchMode(mode)
    match mode:
        case LineSearchMode.DISABLED:
            return None
        case LineSearchMode.SINGLE:
            return SingleLineSearch()
        case LineSearchMode.EXTENDED:
            return ExtendedLineSearch()
        case LineSearchMode.CAPPED:
            return CappedLineSearch()
    raise ValueError(f'Unknown line-search mode: {mode!r}')
