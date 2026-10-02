import dataclasses
import typing
import time
import enum

import numpy as np
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
    PROBE_POSITIVE = enum.auto()
    PROBE_NEGATIVE = enum.auto()
    MOVE_POSITIVE = enum.auto()
    MOVE_NEGATIVE = enum.auto()


@dataclasses.dataclass(frozen=True)
class PolCompStatus:
    state: CompensationState
    search_state: typing.Optional[SearchState]

    score: typing.Optional[float]

    search_waveplate_index: int
    search_step_deg: float
    search_measurement_count: int

    search_cycle_improvement: typing.Optional[float]
    search_low_improvement_cycles: int

    best_score: typing.Optional[float]
    best_position: typing.Optional[float]

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

        # Search resolution
        self.initial_search_step_deg = 1
        self.min_search_step_deg = 0.125
        self.search_step_scale = 0.5

        self.search_step_deg = (
            self.initial_search_step_deg
        )
        self.search_measurements = 3

        # Search convergence
        self.search_cycle_improvement_threshold = 0.05
        self.search_converged_cycles = 2

        self.target_qber = target_qber
        self.target_qx = target_qx

        self.lock_measurements = lock_measurements

        self.active = False
        self.state = CompensationState.IDLE

        self._score: typing.Optional[float] = None

        # Current waveplate line search
        self._search_state = SearchState.START
        self._search_waveplate_index = 0

        self._search_reference_score: typing.Optional[
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

        # Complete QWP1 -> HWP -> QWP2 cycle
        self._search_cycle_start_score: typing.Optional[
            float
        ] = None
        self._search_cycle_improvement: typing.Optional[
            float
        ] = None
        self._search_cycle_pending = False
        self._search_low_improvement_cycles = 0

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

        self.search_step_deg = (
            self.initial_search_step_deg
        )

        self._search_state = SearchState.START
        self._search_waveplate_index = 0

        self._search_reference_score = None
        self._search_best_score = None
        self._search_best_position = None

        self._search_cycle_start_score = None
        self._search_cycle_improvement = None
        self._search_cycle_pending = False
        self._search_low_improvement_cycles = 0

        self._search_results.clear()
        self._lock_results.clear()

    def stop(self) -> None:
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
            search_step_deg=self.search_step_deg,
            search_measurement_count=(
                len(self._search_results)
            ),
            search_cycle_improvement=(
                self._search_cycle_improvement
            ),
            search_low_improvement_cycles=(
                self._search_low_improvement_cycles
            ),
            best_score=self._search_best_score,
            best_position=self._search_best_position,
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

        if self.is_moving:
            return

        match self.state:
            case CompensationState.IDLE:
                return

            case CompensationState.SEARCH:
                self._update_search_measurement(
                    result=result,
                )

            case CompensationState.LOCK:
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

    def _update_search(
        self,
        *,
        score: float,
        qber: float,
        qx: float,
    ) -> None:
        # -------------------------------------------------------------
        # Search complete
        # -------------------------------------------------------------
        if self.target_reached(
            qber=qber,
            qx=qx,
        ):
            self._search_best_score = score
            self._search_best_position = (
                self.search_waveplate.position
            )

            self._lock_results.clear()

            self.state = CompensationState.LOCK

            return

        # -------------------------------------------------------------
        # Initial measurement
        # -------------------------------------------------------------
        if self._search_state is SearchState.START:
            # If QWP2 completed the previous cycle, this fresh
            # measurement at the settled position is the endpoint of
            # that cycle.
            if (
                self._search_waveplate_index == 0
                and self._search_cycle_pending
            ):
                self._update_search_cycle(
                    score=score
                )

            # The endpoint of the previous cycle is also the starting
            # point of the next cycle. On the first cycle, simply use
            # the first QWP1 measurement.
            if (
                self._search_waveplate_index == 0
                and self._search_cycle_start_score
                is None
            ):
                self._search_cycle_start_score = score

            self._search_reference_score = score
            self._search_best_score = score
            self._search_best_position = (
                self.search_waveplate.position
            )

            self._search_results.clear()

            self.search_waveplate.move_by(
                self.search_step_deg
            )

            self._search_state = (
                SearchState.PROBE_POSITIVE
            )

            return

        # -------------------------------------------------------------
        # Test positive direction
        # -------------------------------------------------------------
        if (
            self._search_state
            is SearchState.PROBE_POSITIVE
        ):
            assert (
                self._search_reference_score
                is not None
            )
            assert (
                self._search_best_score
                is not None
            )

            if (
                score
                < self._search_reference_score
            ):
                self._search_best_score = score
                self._search_best_position = (
                    self.search_waveplate.position
                )

                self._search_results.clear()

                self.search_waveplate.move_by(
                    self.search_step_deg
                )

                self._search_state = (
                    SearchState.MOVE_POSITIVE
                )

            else:
                # Undo the positive probe and then move the same
                # amount in the negative direction from the original
                # position.
                self._search_results.clear()

                self.search_waveplate.move_by(
                    -2 * self.search_step_deg
                )

                self._search_state = (
                    SearchState.PROBE_NEGATIVE
                )

            return

        # -------------------------------------------------------------
        # Continue positive direction
        # -------------------------------------------------------------
        if (
            self._search_state
            is SearchState.MOVE_POSITIVE
        ):
            assert (
                self._search_best_score
                is not None
            )
            assert (
                self._search_best_position
                is not None
            )

            if score < self._search_best_score:
                self._search_best_score = score
                self._search_best_position = (
                    self.search_waveplate.position
                )

                self._search_results.clear()

                self.search_waveplate.move_by(
                    self.search_step_deg
                )

            else:
                self._search_results.clear()

                self.search_waveplate.move_to(
                    self._search_best_position
                )

                self._next_search_waveplate()

            return

        # -------------------------------------------------------------
        # Test negative direction
        # -------------------------------------------------------------
        if (
            self._search_state
            is SearchState.PROBE_NEGATIVE
        ):
            assert (
                self._search_reference_score
                is not None
            )
            assert (
                self._search_best_score
                is not None
            )

            if (
                score
                < self._search_reference_score
            ):
                self._search_best_score = score
                self._search_best_position = (
                    self.search_waveplate.position
                )

                self._search_results.clear()

                self.search_waveplate.move_by(
                    -self.search_step_deg
                )

                self._search_state = (
                    SearchState.MOVE_NEGATIVE
                )

            else:
                # Neither direction helped. Return to the original
                # position and continue with the next waveplate.
                self._search_results.clear()

                self.search_waveplate.move_by(
                    self.search_step_deg
                )

                self._next_search_waveplate()

            return

        # -------------------------------------------------------------
        # Continue negative direction
        # -------------------------------------------------------------
        if (
            self._search_state
            is SearchState.MOVE_NEGATIVE
        ):
            assert (
                self._search_best_score
                is not None
            )
            assert (
                self._search_best_position
                is not None
            )

            if score < self._search_best_score:
                self._search_best_score = score
                self._search_best_position = (
                    self.search_waveplate.position
                )

                self._search_results.clear()

                self.search_waveplate.move_by(
                    -self.search_step_deg
                )

            else:
                self._search_results.clear()

                self.search_waveplate.move_to(
                    self._search_best_position
                )

                self._next_search_waveplate()

            return

    def _update_search_measurement(
        self,
        *,
        result: BB84DetectionResult,
    ) -> None:
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

        self._update_search(
            score=score,
            qber=qber,
            qx=qx,
        )

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
            self.state = (
                CompensationState.COMPLETE
            )

        else:
            # A failed lock is not evidence that the current search
            # resolution has converged. Resume the current coordinate
            # search without changing the step size or cycle
            # convergence state.
            self._search_state = SearchState.START
            self._search_results.clear()

            self.state = (
                CompensationState.SEARCH
            )

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

    def _next_search_waveplate(
        self,
    ) -> None:
        self._search_waveplate_index += 1

        if (
            self._search_waveplate_index
            >= len(self.waveplates)
        ):
            self._search_waveplate_index = 0

            # QWP2 has completed its line search. The next fresh
            # settled measurement at QWP1 will be used to evaluate
            # the complete search cycle.
            self._search_cycle_pending = True

        self._search_state = SearchState.START

        self._search_reference_score = None
        self._search_best_score = None
        self._search_best_position = None

    def _update_search_cycle(
        self,
        *,
        score: float,
    ) -> None:
        assert (
            self._search_cycle_start_score
            is not None
        )

        if self._search_cycle_start_score > 0:
            relative_improvement = (
                (
                    self._search_cycle_start_score
                    - score
                )
                / self._search_cycle_start_score
            )
        else:
            relative_improvement = 0.0

        self._search_cycle_improvement = (
            relative_improvement
        )

        if (
            relative_improvement
            < self.search_cycle_improvement_threshold
        ):
            self._search_low_improvement_cycles += 1

        else:
            self._search_low_improvement_cycles = 0

        if (
            self._search_low_improvement_cycles
            >= self.search_converged_cycles
        ):
            self._refine_search_step()

            self._search_low_improvement_cycles = 0

        # The endpoint of this cycle is also the starting point of
        # the next cycle.
        self._search_cycle_start_score = score
        self._search_cycle_pending = False

    def _refine_search_step(
        self,
    ) -> None:
        next_step = (
            self.search_step_deg
            * self.search_step_scale
        )

        if (
            next_step
            >= self.min_search_step_deg
        ):
            self.search_step_deg = next_step

        else:
            self.search_step_deg = (
                self.initial_search_step_deg
            )