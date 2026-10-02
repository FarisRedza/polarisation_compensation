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

    search_step_deg: float

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
        self.search_step_deg = 1

        self.target_qber = target_qber
        self.target_qx = target_qx

        self.lock_measurements = lock_measurements

        self.active = False
        self.state = CompensationState.IDLE

        self._score: typing.Optional[float] = None

        self._search_state = SearchState.START
        self._search_waveplate_index = 0

        self._search_score: typing.Optional[float] = None
        self._search_best_score: typing.Optional[float] = None
        self._search_best_position: typing.Optional[float] = None

        self._lock_results: list[BB84DetectionResult] = []

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
        self._search_reference_score = None
        self._search_best_score = None

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
            search_step_deg=self.search_step_deg,
            best_score=self._search_best_score,
            best_position=self._search_best_position,
            is_moving=self.is_moving,
        )

    def objective(
            self,
            qber: float,
            qx: float
    ) -> float:
        """
        score < 1.0  → both targets satisfied
        score = 1.0  → exactly at one target
        score > 1.0  → at least one target exceeded
        """
        return max(qber/self.target_qber, qx/self.target_qx)

    def target_reached(
        self,
        qber: float,
        qx: float,
    ) -> bool:
        return self.objective(qber, qx) <= 1

    def update(
            self,
            result: BB84DetectionResult
    ) -> None:
        qber = result.qber
        qx = result.qx

        if not self.active:
            return

        if self.is_moving:
            return

        score = self.objective(
            qber=qber,
            qx=qx,
        )
        self._score = score

        match self.state:
            case CompensationState.IDLE:
                return

            case CompensationState.SEARCH:
                 self._update_search(
                    score=score,
                    qber=qber,
                    qx=qx,
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
                raise ValueError(f'Unknown state: {self.state}')

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
            self.state = CompensationState.LOCK
            # self.state = CompensationState.COMPLETE
            return

        # -------------------------------------------------------------
        # Initial measurement
        # -------------------------------------------------------------
        if self._search_state is SearchState.START:
            self._search_reference_score = score
            self._search_best_score = score
            self._search_best_position = self.qwp1.position

            self.qwp1.move_by(
                self.search_step_deg
            )

            self._search_state = SearchState.PROBE_POSITIVE
            return

        # -------------------------------------------------------------
        # Test positive direction
        # -------------------------------------------------------------
        if self._search_state is SearchState.PROBE_POSITIVE:
            assert self._search_reference_score is not None
            assert self._search_best_score is not None

            if score < self._search_reference_score:
                self._search_best_score = score
                self._search_best_position = self.qwp1.position

                self.qwp1.move_by(
                    self.search_step_deg
                )

                self._search_state = SearchState.MOVE_POSITIVE

            else:
                # Undo the positive probe and then move the same amount
                # in the negative direction from the original position.
                self.qwp1.move_by(
                    -2 * self.search_step_deg
                )

                self._search_state = SearchState.PROBE_NEGATIVE

            return

        # -------------------------------------------------------------
        # Continue positive direction
        # -------------------------------------------------------------
        if self._search_state is SearchState.MOVE_POSITIVE:
            assert self._search_best_score is not None
            assert self._search_best_position is not None

            if score < self._search_best_score:
                self._search_best_score = score
                self._search_best_position = self.qwp1.position

                self.qwp1.move_by(
                    self.search_step_deg
                )

            else:
                self.qwp1.move_to(
                    self._search_best_position
                )

                # For the first version, stop searching here.
                self._search_state = SearchState.START

            return

        # -------------------------------------------------------------
        # Test negative direction
        # -------------------------------------------------------------
        if self._search_state is SearchState.PROBE_NEGATIVE:
            assert self._search_reference_score is not None
            assert self._search_best_score is not None

            if score < self._search_reference_score:
                self._search_best_score = score
                self._search_best_position = self.qwp1.position

                self.qwp1.move_by(
                    -self.search_step_deg
                )

                self._search_state = SearchState.MOVE_NEGATIVE

            else:
                # Neither direction helped.
                self.qwp1.move_by(
                    self.search_step_deg
                )

                self._search_state = SearchState.START

            return

        # -------------------------------------------------------------
        # Continue negative direction
        # -------------------------------------------------------------
        if self._search_state is SearchState.MOVE_NEGATIVE:
            assert self._search_best_score is not None
            assert self._search_best_position is not None

            if score < self._search_best_score:
                self._search_best_score = score
                self._search_best_position = self.qwp1.position

                self.qwp1.move_by(
                    -self.search_step_deg
                )

            else:
                self.qwp1.move_to(
                    self._search_best_position
                )

                self._search_state = SearchState.START

            return

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

        coincidences: dict[
            tuple[int, int],
            int,
        ] = {}

        for lock_result in self._lock_results:
            for pair, count in (
                lock_result.coincidences.items()
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

        qber = zz.qber
        qx = xx.qber

        self._score = self.objective(
            qber=qber,
            qx=qx,
        )

        self._lock_results.clear()

        if self.target_reached(
            qber=qber,
            qx=qx,
        ):
            self.state = (
                CompensationState.COMPLETE
            )

        else:
            self.state = (
                CompensationState.SEARCH
            )

            self._search_state = (
                SearchState.START
            )