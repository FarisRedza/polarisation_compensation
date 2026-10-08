import dataclasses
import typing

from .config import JogSearchConfig


@dataclasses.dataclass
class JogSearchState:
    """Runtime state for rolling-jog fallback search."""

    waveplate_index: int = 0

    reference_score: typing.Optional[float] = None
    reference_position: typing.Optional[float] = None

    best_score: typing.Optional[float] = None
    best_position: typing.Optional[float] = None

    worsening_count: int = 0

    cycle: int = 0
    cycle_start_score: typing.Optional[float] = None
    cycle_best_score: typing.Optional[float] = None
    cycle_improvement: typing.Optional[float] = None

    previous_position: typing.Optional[float] = None

    measurement_position: typing.Optional[float] = None
    measurement_start_position: typing.Optional[float] = None
    measurement_end_position: typing.Optional[float] = None


class JogSearch:
    """Own runtime state for rolling-jog search"""

    def __init__(
        self,
        config: JogSearchConfig,
    ) -> None:
        self.config = config
        self.state = JogSearchState()

    def reset(self) -> None:
        """Reset the complete jog-search state"""
        self.state = JogSearchState()

    def reset_line(self) -> None:
        """Reset state associated with the current waveplate."""
        state = self.state

        state.reference_score = None
        state.reference_position = None

        state.best_score = None
        state.best_position = None

        state.worsening_count = 0

        state.previous_position = None

        state.measurement_position = None
        state.measurement_start_position = None
        state.measurement_end_position = None