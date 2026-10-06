import dataclasses
import typing
import enum

import motor
import qtoolkit


@dataclasses.dataclass(frozen=True)
class BB84DetectionResult:
    data: qtoolkit.timetags.TimetagData
    qber: float
    qx: float
    singles: dict[int, int]
    coincidences: dict[tuple[int, int], int]


class CompensationState(enum.Enum):
    IDLE = enum.auto()
    SEARCH = enum.auto()
    LOCK = enum.auto()
    TRACK = enum.auto()
    RECOVER = enum.auto()
    COMPLETE = enum.auto()


class SearchState(enum.Enum):
    START = enum.auto()
    JOG_POSITIVE = enum.auto()
    RETURN_FROM_POSITIVE = enum.auto()
    JOG_NEGATIVE = enum.auto()
    RETURN_TO_BEST = enum.auto()
    RETURN_TO_LOCK = enum.auto()


@dataclasses.dataclass(frozen=True)
class PolCompStatus:
    state: CompensationState
    search_state: typing.Optional[SearchState]

    score: typing.Optional[float]

    search_waveplate_index: int
    search_measurement_count: int
    search_worsening_count: int

    # Retained for compatibility with the existing logger. Jog SEARCH
    # no longer has a discrete angular step or cycle refinement.
    search_step_deg: typing.Optional[float]
    search_cycle_improvement: typing.Optional[float]
    search_low_improvement_cycles: int

    best_score: typing.Optional[float]
    best_position: typing.Optional[float]

    measurement_position: typing.Optional[float]
    measurement_start_position: typing.Optional[float]
    measurement_end_position: typing.Optional[float]

    is_moving: bool


class PolCompController:
    def __init__(
        self,
        *,
        qwp1: motor.Motor,
        hwp: motor.Motor,
        qwp2: motor.Motor,
        measurements: qtoolkit.polarisation.BB84MeasurementPair,
        target_qber: float = 0.05,
        target_qx: float = 0.05,
        lock_measurements: int = 5,
    ) -> None:
        self.qwp1 = qwp1
        self.hwp = hwp
        self.qwp2 = qwp2
        self.waveplates = (
            self.qwp1,
            self.hwp,
            self.qwp2,
        )

        self.measurements = measurements

        # SEARCH uses stationary measurements to establish a reference,
        # then one BB84 result at a time while continuously jogging.
        self.search_measurements = 3
        self.search_worsening_measurements = 3
        self.search_jog_velocity = 5.0

        self.target_qber = target_qber
        self.target_qx = target_qx

        self.lock_measurements = lock_measurements

        self.active = False
        self.state = CompensationState.IDLE

        self._score: typing.Optional[float] = None

        self._search_state = SearchState.START
        self._search_waveplate_index = 0

        self._search_reference_score: typing.Optional[
            float
        ] = None
        self._search_reference_position: typing.Optional[
            float
        ] = None
        self._search_best_score: typing.Optional[
            float
        ] = None
        self._search_best_position: typing.Optional[
            float
        ] = None

        self._search_results: list[
            BB84DetectionResult
        ] = []
        self._search_worsening_count = 0

        # Position interval associated with the most recent moving
        # measurement. The midpoint is used as the representative angle.
        self._search_previous_position: typing.Optional[
            float
        ] = None
        self._search_measurement_position: typing.Optional[
            float
        ] = None
        self._search_measurement_start_position: typing.Optional[
            float
        ] = None
        self._search_measurement_end_position: typing.Optional[
            float
        ] = None

        self._lock_results: list[
            BB84DetectionResult
        ] = []

    @property
    def search_waveplate(
        self,
    ) -> motor.Motor:
        return self.waveplates[
            self._search_waveplate_index
        ]

    def start(self) -> None:
        self.active = True
        self.state = CompensationState.SEARCH

        self._search_state = SearchState.START
        self._search_waveplate_index = 0

        self._reset_search_line()

        self._search_results.clear()
        self._lock_results.clear()

    def stop(self) -> None:
        for waveplate in self.waveplates:
            if waveplate.is_moving:
                waveplate.stop()

        self.active = False
        self.state = CompensationState.IDLE

    @property
    def is_moving(self) -> bool:
        return any(
            waveplate.is_moving
            for waveplate in self.waveplates
        )

    @property
    def status(
        self,
    ) -> PolCompStatus:
        return PolCompStatus(
            state=self.state,
            search_state=(
                self._search_state
                if self.state is CompensationState.SEARCH
                else None
            ),
            score=self._score,
            search_waveplate_index=(
                self._search_waveplate_index
            ),
            search_measurement_count=(
                len(self._search_results)
            ),
            search_worsening_count=(
                self._search_worsening_count
            ),
            search_step_deg=None,
            search_cycle_improvement=None,
            search_low_improvement_cycles=0,
            best_score=self._search_best_score,
            best_position=self._search_best_position,
            measurement_position=(
                self._search_measurement_position
            ),
            measurement_start_position=(
                self._search_measurement_start_position
            ),
            measurement_end_position=(
                self._search_measurement_end_position
            ),
            is_moving=self.is_moving,
        )

    def objective(
        self,
        qber: float,
        qx: float,
    ) -> float:
        """
        score < 1.0  -> both targets satisfied
        score = 1.0  -> exactly at one target
        score > 1.0  -> at least one target exceeded
        """
        return max(
            qber / self.target_qber,
            qx / self.target_qx,
        )

    def target_reached(
        self,
        qber: float,
        qx: float,
    ) -> bool:
        return (
            self.objective(
                qber,
                qx,
            )
            <= 1
        )

    def update(
        self,
        result: BB84DetectionResult,
    ) -> None:
        if not self.active:
            return

        match self.state:
            case CompensationState.IDLE:
                return

            case CompensationState.SEARCH:
                self._update_search_measurement(
                    result=result,
                )

            case CompensationState.LOCK:
                # LOCK only uses stationary measurements.
                if self.is_moving:
                    return

                self._update_lock(
                    result=result,
                )

            case CompensationState.TRACK:
                raise NotImplementedError

            case CompensationState.RECOVER:
                raise NotImplementedError

            case CompensationState.COMPLETE:
                return

            case _:
                raise ValueError(
                    f'Unknown state: {self.state}'
                )

    def _update_search_measurement(
        self,
        *,
        result: BB84DetectionResult,
    ) -> None:
        # During a jog, consume each BB84 result immediately. The motor
        # position is still available while moving, so associate the
        # result with the midpoint of the travelled interval.
        if self._search_state in (
            SearchState.JOG_POSITIVE,
            SearchState.JOG_NEGATIVE,
        ):
            self._update_jog_measurement(
                result=result,
            )
            return

        # Ignore measurements while move_to() is returning to a known
        # position. Once the motor settles, the next result advances the
        # state machine or becomes the first LOCK result.
        if self.is_moving:
            return

        if (
            self._search_state
            is SearchState.RETURN_FROM_POSITIVE
        ):
            self._start_jog(
                direction=motor.MotorDirection.BACKWARD,
                state=SearchState.JOG_NEGATIVE,
            )
            return

        if (
            self._search_state
            is SearchState.RETURN_TO_BEST
        ):
            self._next_search_waveplate()
            return

        if (
            self._search_state
            is SearchState.RETURN_TO_LOCK
        ):
            self._lock_results.clear()
            self.state = CompensationState.LOCK
            self._update_lock(
                result=result,
            )
            return

        # START uses the same three-result aggregate as the old SEARCH
        # implementation. This gives each line search a less noisy
        # stationary reference before continuous motion begins.
        self._search_results.append(
            result
        )

        if (
            len(self._search_results)
            < self.search_measurements
        ):
            return

        qber, qx = self._aggregate_results(
            self._search_results
        )
        self._search_results.clear()

        score = self.objective(
            qber=qber,
            qx=qx,
        )
        self._score = score

        position = self.search_waveplate.position

        if self.target_reached(
            qber=qber,
            qx=qx,
        ):
            self._search_best_score = score
            self._search_best_position = position
            self._lock_results.clear()
            self.state = CompensationState.LOCK
            return

        self._search_reference_score = score
        self._search_reference_position = position
        self._search_best_score = score
        self._search_best_position = position
        self._search_worsening_count = 0

        self._start_jog(
            direction=motor.MotorDirection.FORWARD,
            state=SearchState.JOG_POSITIVE,
        )

    def _update_jog_measurement(
        self,
        *,
        result: BB84DetectionResult,
    ) -> None:
        current_position = self.search_waveplate.position

        if self._search_previous_position is None:
            self._search_previous_position = current_position
            return

        start_position = self._search_previous_position
        end_position = current_position
        measurement_position = (
            start_position + end_position
        ) / 2

        self._search_previous_position = current_position
        self._search_measurement_start_position = (
            start_position
        )
        self._search_measurement_end_position = (
            end_position
        )
        self._search_measurement_position = (
            measurement_position
        )

        score = self.objective(
            qber=result.qber,
            qx=result.qx,
        )
        self._score = score

        assert self._search_reference_score is not None
        assert self._search_reference_position is not None
        assert self._search_best_score is not None
        assert self._search_best_position is not None

        if score < self._search_best_score:
            self._search_best_score = score
            self._search_best_position = (
                measurement_position
            )
            self._search_worsening_count = 0
        else:
            self._search_worsening_count += 1

        # A moving measurement below the target is only a candidate.
        # Stop immediately, return to its representative angle, and let
        # stationary LOCK measurements decide whether it is valid.
        if self.target_reached(
            qber=result.qber,
            qx=result.qx,
        ):
            self._return_to_position(
                position=self._search_best_position,
                state=SearchState.RETURN_TO_LOCK,
            )
            return

        if (
            self._search_worsening_count
            < self.search_worsening_measurements
        ):
            return

        if (
            self._search_state
            is SearchState.JOG_POSITIVE
        ):
            if (
                self._search_best_score
                < self._search_reference_score
            ):
                self._return_to_position(
                    position=self._search_best_position,
                    state=SearchState.RETURN_TO_BEST,
                )
            else:
                # Positive motion did not improve on the stationary
                # reference. Return to the reference and try negative.
                self._return_to_position(
                    position=self._search_reference_position,
                    state=SearchState.RETURN_FROM_POSITIVE,
                )
            return

        if (
            self._search_state
            is SearchState.JOG_NEGATIVE
        ):
            # If negative improved, return to its best point. Otherwise
            # return to the original reference. In either case this line
            # search is complete and the next waveplate is selected.
            if (
                self._search_best_score
                < self._search_reference_score
            ):
                return_position = (
                    self._search_best_position
                )
            else:
                return_position = (
                    self._search_reference_position
                )

            self._return_to_position(
                position=return_position,
                state=SearchState.RETURN_TO_BEST,
            )
            return

        raise ValueError(
            f'Unexpected jog state: {self._search_state}'
        )

    def _start_jog(
        self,
        *,
        direction: motor.MotorDirection,
        state: SearchState,
    ) -> None:
        self._search_worsening_count = 0

        self._search_previous_position = (
            self.search_waveplate.position
        )
        self._search_measurement_position = None
        self._search_measurement_start_position = None
        self._search_measurement_end_position = None

        self.search_waveplate.jog(
            direction=direction,
            max_velocity=self.search_jog_velocity,
        )
        self._search_state = state

    def _return_to_position(
        self,
        *,
        position: float,
        state: SearchState,
    ) -> None:
        self.search_waveplate.stop()
        self.search_waveplate.move_to(
            position
        )

        self._search_state = state
        self._search_worsening_count = 0
        self._search_previous_position = None

    def _next_search_waveplate(
        self,
    ) -> None:
        self._search_waveplate_index += 1

        if (
            self._search_waveplate_index
            >= len(self.waveplates)
        ):
            self._search_waveplate_index = 0

        self._search_state = SearchState.START
        self._reset_search_line()
        self._search_results.clear()

    def _reset_search_line(
        self,
    ) -> None:
        self._search_reference_score = None
        self._search_reference_position = None
        self._search_best_score = None
        self._search_best_position = None
        self._search_worsening_count = 0

        self._search_previous_position = None
        self._search_measurement_position = None
        self._search_measurement_start_position = None
        self._search_measurement_end_position = None

    def _update_lock(
        self,
        *,
        result: BB84DetectionResult,
    ) -> None:
        self._lock_results.append(
            result
        )

        if (
            len(self._lock_results)
            < self.lock_measurements
        ):
            return

        qber, qx = self._aggregate_results(
            self._lock_results
        )
        self._lock_results.clear()

        self._score = self.objective(
            qber=qber,
            qx=qx,
        )

        if self.target_reached(
            qber=qber,
            qx=qx,
        ):
            self.state = CompensationState.COMPLETE
        else:
            # A failed LOCK returns to a fresh line search from the
            # current, stationary position.
            self._search_state = SearchState.START
            self._reset_search_line()
            self._search_results.clear()
            self.state = CompensationState.SEARCH

    def _aggregate_results(
        self,
        results: typing.Sequence[
            BB84DetectionResult
        ],
    ) -> tuple[float, float]:
        coincidences: dict[
            tuple[int, int],
            int,
        ] = {}

        for result in results:
            for pair, count in (
                result.coincidences.items()
            ):
                coincidences[pair] = (
                    coincidences.get(
                        pair,
                        0,
                    )
                    + count
                )

        zz = (
            qtoolkit.qkd.BasisMetrics
            .from_coincidences(
                coincidences=coincidences,
                pairs=self.measurements.z_pairs,
            )
        )

        xx = (
            qtoolkit.qkd.BasisMetrics
            .from_coincidences(
                coincidences=coincidences,
                pairs=self.measurements.x_pairs,
            )
        )

        return (
            zz.qber,
            xx.qber,
        )