import dataclasses
import typing
import enum

from .config import JogSearchConfig


class JogDirection(enum.Enum):
    POSITIVE = enum.auto()
    NEGATIVE = enum.auto()


class JogActionType(enum.Enum):
    CONTINUE = enum.auto()
    RETURN_TO_BEST = enum.auto()
    RETURN_FROM_POSITIVE = enum.auto()
    RETURN_TO_LOCK = enum.auto()


@dataclasses.dataclass(frozen=True)
class JogAction:
    type: JogActionType
    position: typing.Optional[float] = None



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

    def record_measurement(
        self,
        *,
        score: float,
        acceptance_score: float,
        position: float,
        direction: JogDirection,
    ) -> JogAction:
        """Evaluate a rolling-jog measurement and choose the next action."""

        state = self.state

        if (
            state.cycle_best_score is None
            or score < state.cycle_best_score
        ):
            state.cycle_best_score = score

        assert state.reference_score is not None
        assert state.reference_position is not None
        assert state.best_score is not None
        assert state.best_position is not None

        if score < state.best_score:
            state.best_score = score
            state.best_position = position
            state.worsening_count = 0
        else:
            state.worsening_count += 1

        # Preserve the existing order: candidate acceptance is checked
        # before the worsening threshold.
        if acceptance_score <= self.config.candidate_score:
            return JogAction(
                type=JogActionType.RETURN_TO_LOCK,
                position=state.best_position,
            )

        if state.worsening_count < self.config.worsening_measurements:
            return JogAction(type=JogActionType.CONTINUE)

        if direction is JogDirection.POSITIVE:
            if state.best_score < state.reference_score:
                return JogAction(
                    type=JogActionType.RETURN_TO_BEST,
                    position=state.best_position,
                )

            return JogAction(
                type=JogActionType.RETURN_FROM_POSITIVE,
                position=state.reference_position,
            )

        if direction is JogDirection.NEGATIVE:
            if state.best_score < state.reference_score:
                return_position = state.best_position
            else:
                return_position = state.reference_position

            return JogAction(
                type=JogActionType.RETURN_TO_BEST,
                position=return_position,
            )

        raise ValueError(f'Unexpected jog direction: {direction}')