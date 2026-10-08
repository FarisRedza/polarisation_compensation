import dataclasses
import typing
import enum

import motor
import qtoolkit

from .config import PolCompConfig
from .jacobian_search import JacobianSearch


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

    # Empirical Jacobian SEARCH.
    JACOBIAN_PROBE_MOVE = enum.auto()
    JACOBIAN_PROBE_MEASURE = enum.auto()
    JACOBIAN_PROBE_RETURN = enum.auto()
    JACOBIAN_APPLY = enum.auto()

    # Existing rolling-jog SEARCH, retained as a fallback.
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

    # Rolling-jog fallback diagnostics.
    search_cycle: int
    search_cycle_start_score: typing.Optional[float]
    search_cycle_best_score: typing.Optional[float]
    search_cycle_improvement: typing.Optional[float]

    # Empirical Jacobian diagnostics.
    jacobian_probe_index: int
    jacobian_iteration: int
    jacobian_condition: typing.Optional[float]
    jacobian_predicted_score: typing.Optional[float]
    jacobian_step_qwp1: typing.Optional[float]
    jacobian_step_hwp: typing.Optional[float]
    jacobian_step_qwp2: typing.Optional[float]
    jacobian_fallback_count: int

    # Compatibility fields retained for the existing tools.
    search_step_deg: typing.Optional[float]
    search_retained_improvement: typing.Optional[float]
    search_stagnant: bool
    search_escape_count: int
    search_low_improvement_cycles: int

    best_score: typing.Optional[float]
    best_position: typing.Optional[float]

    measurement_position: typing.Optional[float]
    measurement_start_position: typing.Optional[float]
    measurement_end_position: typing.Optional[float]

    is_moving: bool



class PolCompController:
    """Control a QWP-HWP-QWP stack using BB84 error feedback.

    SEARCH is led by an empirical 2x3 Jacobian.  A stationary baseline is
    measured, then QWP1, HWP and QWP2 are each displaced by a small known
    probe angle.  The measured changes in normalised QBER and Qx form the
    columns of a local Jacobian::

        [d e_Z / d QWP1   d e_Z / d HWP   d e_Z / d QWP2]
        [d e_X / d QWP1   d e_X / d HWP   d e_X / d QWP2]

    A damped least-squares pseudoinverse then chooses a combined
    three-waveplate correction.  This allows SEARCH to move along a useful
    coupled direction even when no individual coordinate gives a strong
    scalar-objective improvement.

    The previous rolling-jog QWP1 -> HWP -> QWP2 line search is retained as
    a fallback.  It is used when the measured Jacobian is too weak,
    ill-conditioned, or predicts insufficient improvement.

    SEARCH uses the smooth RMS of the two normalised errors for guidance.
    The max(QBER/target_QBER, Qx/target_Qx) objective remains authoritative
    for candidate acceptance, LOCK verification and COMPLETE.

    TRACK and RECOVER remain reserved for later closed-loop behaviour.
    """

    def __init__(
        self,
        *,
        qwp1: motor.Motor,
        hwp: motor.Motor,
        qwp2: motor.Motor,
        measurements: qtoolkit.polarisation.BB84MeasurementPair,
        config: typing.Optional[PolCompConfig] = None,
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
        self.config = (
            config
            if config is not None
            else PolCompConfig()
        )
        self._jacobian_search = JacobianSearch(
            config=self.config.jacobian,
        )

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

        # Rolling-jog fallback diagnostics.
        self._search_cycle = 0
        self._search_cycle_start_score: typing.Optional[float] = None
        self._search_cycle_best_score: typing.Optional[float] = None
        self._search_cycle_improvement: typing.Optional[float] = None

        self._using_jog_fallback = False

        # Rolling moving-measurement window. Each entry stores the BB84
        # result together with the angular interval traversed while it was
        # measured.
        self._search_jog_results: list[
            tuple[BB84DetectionResult, float, float]
        ] = []

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
    def search_measurements(self) -> int:
        return self.config.jog.reference_measurements

    @property
    def search_jog_measurements(self) -> int:
        return self.config.jog.jog_measurements

    @property
    def search_worsening_measurements(self) -> int:
        return self.config.jog.worsening_measurements

    @property
    def search_jog_velocity(self) -> float:
        return self.config.jog.jog_velocity

    @property
    def search_candidate_score(self) -> float:
        return self.config.jog.candidate_score

    @property
    def jacobian_probe_deg(self) -> float:
        return self.config.jacobian.probe_deg

    @property
    def jacobian_measurements(self) -> int:
        return self.config.jacobian.measurements

    @property
    def jacobian_damping(self) -> float:
        return self.config.jacobian.damping    
    
    @property
    def jacobian_max_step_deg(self) -> float:
        return self.config.jacobian.max_step_deg

    @property
    def jacobian_max_total_step_deg(self) -> float:
        return self.config.jacobian.max_total_step_deg

    @property
    def jacobian_min_determinant(self) -> float:
        return self.config.jacobian.min_determinant

    @property
    def jacobian_min_predicted_improvement(self) -> float:
        return self.config.jacobian.min_predicted_improvement

    @property
    def target_qber(self) -> float:
        return self.config.target_qber

    @property
    def target_qx(self) -> float:
        return self.config.target_qx

    @property
    def lock_measurements(self) -> int:
        return self.config.lock.measurements


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

        self._search_cycle = 0
        self._search_cycle_start_score = None
        self._search_cycle_best_score = None
        self._search_cycle_improvement = None

        self._jacobian_search.reset()
        self._using_jog_fallback = False

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
        step = self._jacobian_search.state.step

        return PolCompStatus(
            state=self.state,
            search_state=(
                self._search_state
                if self.state is CompensationState.SEARCH
                else None
            ),
            score=self._score,
            search_waveplate_index=self._search_waveplate_index,
            search_measurement_count=len(self._search_results),
            search_worsening_count=self._search_worsening_count,
            search_cycle=self._search_cycle,
            search_cycle_start_score=self._search_cycle_start_score,
            search_cycle_best_score=self._search_cycle_best_score,
            search_cycle_improvement=self._search_cycle_improvement,
            jacobian_probe_index=self._jacobian_search.state.probe_index,
            jacobian_iteration=self._jacobian_search.state.iteration,
            jacobian_condition=self._jacobian_search.state.condition,
            jacobian_predicted_score=self._jacobian_search.state.predicted_score,
            jacobian_step_qwp1=(step[0] if step is not None else None),
            jacobian_step_hwp=(step[1] if step is not None else None),
            jacobian_step_qwp2=(step[2] if step is not None else None),
            jacobian_fallback_count=self._jacobian_search.state.fallback_count,
            search_step_deg=None,
            search_retained_improvement=None,
            search_stagnant=False,
            search_escape_count=0,
            search_low_improvement_cycles=0,
            best_score=self._search_best_score,
            best_position=self._search_best_position,
            measurement_position=self._search_measurement_position,
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

    def search_objective(
        self,
        qber: float,
        qx: float,
    ) -> float:
        """Return the smooth objective used to guide SEARCH.

        The RMS of the two normalised BB84 errors rewards reductions in
        either basis while still weighting the larger error more strongly
        than a simple arithmetic mean. Unlike ``objective()``, it does not
        develop a hard ridge when QBER and Qx exchange which is larger.

        This value is only used to choose SEARCH directions and positions.
        Candidate acceptance and LOCK continue to use ``objective()`` so
        both QBER and Qx must satisfy their individual targets.
        """
        qber_normalised = (
            qber / self.target_qber
        )
        qx_normalised = (
            qx / self.target_qx
        )

        return (
            (
                qber_normalised ** 2
                + qx_normalised ** 2
            )
            / 2
        ) ** 0.5

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
        # Existing rolling-jog fallback consumes measurements during motion.
        if self._search_state in (
            SearchState.JOG_POSITIVE,
            SearchState.JOG_NEGATIVE,
        ):
            self._update_jog_measurement(
                result=result,
            )
            return

        # Measurements acquired while move_to() is active are discarded.
        if self.is_moving:
            return

        # The first result delivered after a probe move/return/application
        # may overlap the tail of that motion.  Use it only to advance the
        # state, then start collecting fresh stationary measurements.
        if self._search_state is SearchState.JACOBIAN_PROBE_MOVE:
            self._search_results.clear()
            self._search_state = SearchState.JACOBIAN_PROBE_MEASURE
            return

        if self._search_state is SearchState.JACOBIAN_PROBE_RETURN:
            self._search_results.clear()
            self._advance_jacobian_probe()
            return

        if self._search_state is SearchState.JACOBIAN_APPLY:
            self._search_results.clear()
            self._search_state = SearchState.START
            self._reset_search_line()
            return

        # Rolling-jog fallback return states.
        if self._search_state is SearchState.RETURN_FROM_POSITIVE:
            self._start_jog(
                direction=motor.MotorDirection.BACKWARD,
                state=SearchState.JOG_NEGATIVE,
            )
            return

        if self._search_state is SearchState.RETURN_TO_BEST:
            self._next_search_waveplate()
            return

        if self._search_state is SearchState.RETURN_TO_LOCK:
            self._lock_results.clear()
            self.state = CompensationState.LOCK
            self._update_lock(
                result=result,
            )
            return

        if self._search_state is SearchState.JACOBIAN_PROBE_MEASURE:
            self._search_results.append(result)

            if len(self._search_results) < self.jacobian_measurements:
                return

            qber, qx = self._aggregate_results(self._search_results)
            self._search_results.clear()

            assert self._jacobian_search.state.baseline_errors is not None
            base_z, base_x = self._jacobian_search.state.baseline_errors

            probe_z = qber / self.target_qber
            probe_x = qx / self.target_qx

            self._jacobian_search.state.columns.append(
                (
                    (probe_z - base_z) / self.jacobian_probe_deg,
                    (probe_x - base_x) / self.jacobian_probe_deg,
                )
            )

            assert self._jacobian_search.state.baseline_positions is not None
            motor_index = self._jacobian_search.state.probe_index
            self.waveplates[motor_index].move_to(
                self._jacobian_search.state.baseline_positions[motor_index]
            )
            self._search_state = SearchState.JACOBIAN_PROBE_RETURN
            return

        # START during the one-cycle rolling-jog fallback uses the old
        # stationary reference and then launches a line search.
        if self._using_jog_fallback:
            self._search_results.append(result)

            if len(self._search_results) < self.search_measurements:
                return

            qber, qx = self._aggregate_results(self._search_results)
            self._search_results.clear()

            score = self.search_objective(qber=qber, qx=qx)
            self._score = score

            if self.target_reached(qber=qber, qx=qx):
                self._lock_results.clear()
                self.state = CompensationState.LOCK
                return

            if self._search_waveplate_index == 0:
                self._search_cycle_start_score = score
                self._search_cycle_best_score = score
                self._search_cycle_improvement = None
            elif (
                self._search_cycle_best_score is None
                or score < self._search_cycle_best_score
            ):
                self._search_cycle_best_score = score

            position = self.search_waveplate.position
            self._search_reference_score = score
            self._search_reference_position = position
            self._search_best_score = score
            self._search_best_position = position
            self._search_worsening_count = 0

            self._start_jog(
                direction=motor.MotorDirection.FORWARD,
                state=SearchState.JOG_POSITIVE,
            )
            return

        # START: collect the stationary baseline for a Jacobian iteration.
        self._search_results.append(result)

        if len(self._search_results) < self.search_measurements:
            return

        qber, qx = self._aggregate_results(self._search_results)
        self._search_results.clear()

        score = self.search_objective(qber=qber, qx=qx)
        self._score = score

        if self.target_reached(qber=qber, qx=qx):
            self._lock_results.clear()
            self.state = CompensationState.LOCK
            return

        self._jacobian_search.state.baseline_errors = (
            qber / self.target_qber,
            qx / self.target_qx,
        )
        self._jacobian_search.state.baseline_score = score
        self._jacobian_search.state.baseline_positions = tuple(
            waveplate.position
            for waveplate in self.waveplates
        )
        self._jacobian_search.state.columns.clear()
        self._jacobian_search.state.probe_index = 0
        self._jacobian_search.state.condition = None
        self._jacobian_search.state.predicted_score = None
        self._jacobian_search.state.step = None

        self._start_jacobian_probe()


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
        self._search_previous_position = current_position

        self._search_jog_results.append(
            (result, start_position, end_position)
        )

        if (
            len(self._search_jog_results)
            > self.search_jog_measurements
        ):
            self._search_jog_results.pop(0)

        # Do not make a SEARCH decision until the moving window contains
        # the same number of measurements as the stationary reference.
        if (
            len(self._search_jog_results)
            < self.search_jog_measurements
        ):
            return

        window_results = [
            item[0]
            for item in self._search_jog_results
        ]

        qber, qx = self._aggregate_results(
            window_results
        )

        window_start_position = (
            self._search_jog_results[0][1]
        )
        window_end_position = (
            self._search_jog_results[-1][2]
        )
        measurement_position = (
            window_start_position
            + window_end_position
        ) / 2

        self._search_measurement_start_position = (
            window_start_position
        )
        self._search_measurement_end_position = (
            window_end_position
        )
        self._search_measurement_position = (
            measurement_position
        )

        score = self.search_objective(
            qber=qber,
            qx=qx,
        )
        acceptance_score = self.objective(
            qber=qber,
            qx=qx,
        )
        self._score = score

        if (
            self._search_cycle_best_score is None
            or score < self._search_cycle_best_score
        ):
            self._search_cycle_best_score = score

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

        # A moving result is only a candidate. Candidate acceptance uses
        # the authoritative max objective rather than the smoother SEARCH
        # objective, so both bases must be comfortably inside their targets
        # before SEARCH is interrupted for LOCK.
        if acceptance_score <= self.search_candidate_score:
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

    def _start_jacobian_probe(
        self,
    ) -> None:
        assert self._jacobian_search.state.baseline_positions is not None

        index = self._jacobian_search.state.probe_index
        target = (
            self._jacobian_search.state.baseline_positions[index]
            + self.jacobian_probe_deg
        )

        self.waveplates[index].move_to(target)
        self._search_state = SearchState.JACOBIAN_PROBE_MOVE

    def _advance_jacobian_probe(
        self,
    ) -> None:
        self._jacobian_search.state.probe_index += 1

        if self._jacobian_search.state.probe_index < len(self.waveplates):
            self._start_jacobian_probe()
            return

        self._finish_jacobian_iteration()

    def _finish_jacobian_iteration(self) -> None:
        state = self._jacobian_search.state

        assert state.baseline_errors is not None
        assert state.baseline_score is not None

        if len(state.columns) != 3:
            self._start_jog_fallback()
            return

        solution = self._jacobian_search.solver.solve(
            columns=state.columns,
            baseline_errors=state.baseline_errors,
            baseline_score=state.baseline_score,
        )

        state.condition = solution.condition
        state.predicted_score = solution.predicted_score
        state.step = solution.step

        if not solution.accepted:
            self._start_jog_fallback()
            return

        assert solution.step is not None

        for waveplate, delta in zip(
            self.waveplates,
            solution.step,
        ):
            waveplate.move_to(
                waveplate.position + delta
            )

        state.iteration += 1
        self._search_state = SearchState.JACOBIAN_APPLY

    def _start_jog_fallback(
        self,
    ) -> None:
        # Run one complete QWP1 -> HWP -> QWP2 rolling-jog cycle, then
        # return to a fresh empirical Jacobian measurement.
        self._jacobian_search.state.fallback_count += 1
        self._using_jog_fallback = True

        self._search_waveplate_index = 0
        self._search_cycle_start_score = None
        self._search_cycle_best_score = None
        self._search_cycle_improvement = None

        self._search_state = SearchState.START
        self._reset_search_line()
        self._search_results.clear()

        # Mark START as fallback by retaining this flag.  The next
        # stationary aggregate is handled by the fallback starter below.
        self._start_fallback_reference()

    def _start_fallback_reference(
        self,
    ) -> None:
        # START itself is shared with Jacobian baseline collection.  Set a
        # sentinel reference score so the dispatcher can distinguish the
        # fallback path on subsequent stationary samples.
        self._search_reference_score = float('nan')


    def _start_jog(
        self,
        *,
        direction: motor.MotorDirection,
        state: SearchState,
    ) -> None:
        self._search_worsening_count = 0
        self._search_jog_results.clear()

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
        self._search_jog_results.clear()
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

            if (
                self._search_cycle_start_score is not None
                and self._search_cycle_best_score is not None
            ):
                if self._search_cycle_start_score > 0:
                    self._search_cycle_improvement = (
                        self._search_cycle_start_score
                        - self._search_cycle_best_score
                    ) / self._search_cycle_start_score
                else:
                    self._search_cycle_improvement = 0.0

            self._search_cycle += 1

            if self._using_jog_fallback:
                self._using_jog_fallback = False

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
        self._search_jog_results.clear()

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
            self._using_jog_fallback = False
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