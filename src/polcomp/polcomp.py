import dataclasses
import typing
import enum

import motor
import qtoolkit

from .config import PolCompConfig
from .jacobian_search import (
    JacobianCorrection,
    JacobianSearch,
    JacobianAction,
    JacobianActionType,
)
from .jog_search import (
    JogSearch,
    JogActionType,
    JogDirection,
)
from .measurement import (
    Observation,
    make_observation,
    aggregate_bb84_measurements,
)
from .motor_execution import MotorExecutor
from .objectives import (
    acceptance_score,
    search_score,
    targets_satisfied,
)
from .lock import LockDecision, evaluate_lock


@dataclasses.dataclass(frozen=True)
class BB84DetectionResult:
    data: qtoolkit.timetags.TimetagData
    qber: float
    qx: float
    singles: dict[int, int]
    coincidences: dict[tuple[int, int], int]

    counts: typing.Optional[
        qtoolkit.timetags.MeasurementCounts
    ] = None


@dataclasses.dataclass(frozen=True)
class JacobianLineSearchTrial:
    alpha: float
    score: float


@dataclasses.dataclass(frozen=True)
class JacobianLineSearchResult:
    iteration: int

    baseline_score: float
    full_score: float
    trial_score: float

    trial_alpha: float
    accepted_alpha: float
    extra_travel_deg: float

    trials: tuple[JacobianLineSearchTrial, ...] = ()

    @property
    def trial_improvement(self) -> float:
        return self.full_score - self.trial_score

    @property
    def accepted_score(self) -> float:
        if self.accepted_alpha == 0.0:
            return self.baseline_score

        if self.accepted_alpha == 1.0:
            return self.full_score

        if self.trials:
            for trial in self.trials:
                if trial.alpha == self.accepted_alpha:
                    return trial.score

        if self.accepted_alpha == self.trial_alpha:
            return self.trial_score

        raise ValueError(
            f"No score recorded for accepted alpha "
            f"{self.accepted_alpha}"
        )


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
    JACOBIAN_LINE_MOVE = enum.auto()
    JACOBIAN_LINE_MEASURE = enum.auto()
    JACOBIAN_LINE_RETURN = enum.auto()

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
    jacobian_max_total_step_deg: float

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

    last_jacobian_correction: JacobianCorrection | None
    last_line_search: JacobianLineSearchResult | None


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
        self._motor_executor = MotorExecutor(
            self.waveplates
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
        self._jog_search = JogSearch(
            config=self.config.jog,
        )

        self.active = False
        self.state = CompensationState.IDLE

        self._score: typing.Optional[float] = None

        self._search_state = SearchState.START

        self._search_results: list[
            BB84DetectionResult
        ] = []

        self._using_jog_fallback = False

        # Rolling moving-measurement window. Each entry stores the BB84
        # result together with the angular interval traversed while it was
        # measured.
        self._search_jog_results: list[
            tuple[BB84DetectionResult, float, float]
        ] = []

        self._lock_results: list[
            BB84DetectionResult
        ] = []

        self._pending_jacobian_correction: (
            tuple[int, float, float, tuple[float, float, float], float | None]
            | None
        ) = None

        self._last_jacobian_correction: JacobianCorrection | None = None
        # Experimental one-trial line search; the pending correction is
        # finalised only after returning to the selected stationary point.
        self._line_trial: tuple[float, tuple[float, float, float]] | None = None
        self._line_trial_completed = False
        self._last_line_search: JacobianLineSearchResult | None = None
        self._line_alpha = 0.0
        self._line_best_alpha = 0.0
        self._line_best_score = float("inf")
        self._line_best_positions = None
        self._line_trials: list[JacobianLineSearchTrial] = []
        self._line_extra_travel = 0.0
        self._line_previous_positions = None


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
            self._jog_search.state.waveplate_index
        ]

    @property
    def search_waveplate_position(self) -> float:
        return self._motor_executor.position(
            self._jog_search.state.waveplate_index
        )

    def start(self) -> None:
        self.active = True
        self.state = CompensationState.SEARCH

        self._search_state = SearchState.START

        self._jacobian_search.reset()
        self._pending_jacobian_correction = None
        self._last_jacobian_correction = None
        self._line_trial = None
        self._line_trial_completed = False
        self._last_line_search = None
        self._line_alpha = 0.0
        self._line_best_alpha = 0.0
        self._line_best_score = float('inf')
        self._line_best_positions = None
        self._line_trials = []
        self._line_extra_travel = 0.0
        self._line_previous_positions = None
        self._using_jog_fallback = False

        self._jog_search.reset()

        self._reset_search_line()

        self._search_results.clear()
        self._lock_results.clear()

    def stop(self) -> None:
        self._motor_executor.stop_moving()

        self.active = False
        self.state = CompensationState.IDLE

    @property
    def is_moving(self) -> bool:
        return self._motor_executor.is_moving

    @property
    def line_search_mode(self) -> str:
        mode = self.config.jacobian.line_search_mode

        if mode is None:
            return (
                'capped'
                if self.config.jacobian.experimental_line_search
                else 'disabled'
            )

        if mode not in ('disabled', 'single', 'extended', 'capped'):
            raise ValueError(
                f'Unknown line-search mode: {mode!r}'
            )

        return mode

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
            search_waveplate_index=self._jog_search.state.waveplate_index,
            search_measurement_count=len(self._search_results),
            search_worsening_count=self._jog_search.state.worsening_count,
            search_cycle=self._jog_search.state.cycle,
            search_cycle_start_score=self._jog_search.state.cycle_start_score,
            search_cycle_best_score=self._jog_search.state.cycle_best_score,
            search_cycle_improvement=self._jog_search.state.cycle_improvement,
            jacobian_probe_index=self._jacobian_search.state.probe_index,
            jacobian_iteration=self._jacobian_search.state.iteration,
            jacobian_condition=self._jacobian_search.state.condition,
            jacobian_predicted_score=self._jacobian_search.state.predicted_score,
            jacobian_step_qwp1=(step[0] if step is not None else None),
            jacobian_step_hwp=(step[1] if step is not None else None),
            jacobian_step_qwp2=(step[2] if step is not None else None),
            jacobian_fallback_count=self._jacobian_search.state.fallback_count,
            jacobian_max_total_step_deg=(
                self._jacobian_search.max_total_step_deg
            ),
            search_step_deg=None,
            search_retained_improvement=None,
            search_stagnant=False,
            search_escape_count=0,
            search_low_improvement_cycles=0,
            best_score=self._jog_search.state.best_score,
            best_position=self._jog_search.state.best_position,
            measurement_position=self._jog_search.state.measurement_position,
            measurement_start_position=(
                self._jog_search.state.measurement_start_position
            ),
            measurement_end_position=(
                self._jog_search.state.measurement_end_position
            ),
            is_moving=self.is_moving,
            last_jacobian_correction=self._last_jacobian_correction,
            last_line_search=self._last_line_search,
        )

    def objective(
        self,
        qber: float,
        qx: float,
    ) -> float:
        return acceptance_score(
            qber=qber,
            qx=qx,
            target_qber=self.target_qber,
            target_qx=self.target_qx,
        )

    def search_objective(
        self,
        qber: float,
        qx: float,
    ) -> float:
        return search_score(
            qber=qber,
            qx=qx,
            target_qber=self.target_qber,
            target_qx=self.target_qx,
        )

    def target_reached(
        self,
        qber: float,
        qx: float,
    ) -> bool:
        return targets_satisfied(
            qber=qber,
            qx=qx,
            target_qber=self.target_qber,
            target_qx=self.target_qx,
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

        if self._search_state is SearchState.JACOBIAN_LINE_MOVE:
            self._search_results.clear()
            self._search_state = SearchState.JACOBIAN_LINE_MEASURE
            return

        if self._search_state is SearchState.JACOBIAN_LINE_RETURN:
            self._search_results.clear()
            self._search_state = SearchState.START
            return

        if self._search_state is SearchState.JACOBIAN_LINE_MEASURE:
            self._search_results.append(result)

            if len(self._search_results) < self.search_measurements:
                return

            observation = self._observe_results(
                self._search_results,
                search=True,
            )
            self._search_results.clear()

            assert self._line_trial is not None
            assert self._pending_jacobian_correction is not None
            assert self._line_best_positions is not None

            full_score, full_positions = self._line_trial

            (
                iteration,
                baseline_score,
                _,
                step,
                _,
            ) = self._pending_jacobian_correction

            baseline_positions = (
                self._jacobian_search.state.baseline_positions
            )
            assert baseline_positions is not None

            trial_positions = self._motor_executor.positions()
            trial_score = observation.score
            trial_alpha = self._line_alpha

            self._line_trials.append(
                JacobianLineSearchTrial(
                    alpha=trial_alpha,
                    score=trial_score,
                )
            )

            mode = self.line_search_mode

            # For forward exploration, compare against the previous
            # explored position, even if that position cannot be accepted.
            if len(self._line_trials) == 1:
                previous_explored_score = full_score
            else:
                previous_explored_score = self._line_trials[-2].score

            improved = trial_score < previous_explored_score

            # Capped mode may explore beyond alpha=1.5, but cannot
            # accept those positions.
            max_accepted_alpha = (
                1.5 if mode == 'capped' else 2.5
            )

            if (
                trial_alpha <= max_accepted_alpha
                and trial_score < self._line_best_score
            ):
                self._line_best_score = trial_score
                self._line_best_alpha = trial_alpha
                self._line_best_positions = trial_positions

            # The single-trial mode never extends beyond its first trial.
            max_trial_alpha = (
                1.5 if mode == 'single' else 2.5
            )

            continue_forward = (
                mode in ('extended', 'capped')
                and trial_alpha >= 1.5
                and improved
                and trial_alpha < max_trial_alpha
                and not self.target_reached(
                    qber=observation.qber,
                    qx=observation.qx,
                )
            )

            if continue_forward:
                next_alpha = min(trial_alpha + 0.5, 2.5)

                next_positions = tuple(
                    base + next_alpha * delta
                    for base, delta in zip(
                        baseline_positions,
                        step,
                    )
                )

                self._line_extra_travel += sum(
                    abs(new - old)
                    for new, old in zip(
                        next_positions,
                        trial_positions,
                    )
                )

                self._line_alpha = next_alpha

                self._motor_executor.move_positions(next_positions)
                self._search_state = SearchState.JACOBIAN_LINE_MOVE
                return

            # The line search is finished.
            # Return to the best measured position if necessary.
            selected = self._line_best_positions

            self._line_extra_travel += sum(
                abs(chosen - current)
                for chosen, current in zip(
                    selected,
                    trial_positions,
                )
            )

            self._last_line_search = JacobianLineSearchResult(
                iteration=iteration,
                baseline_score=baseline_score,
                full_score=full_score,
                trial_score=trial_score,
                trial_alpha=trial_alpha,
                accepted_alpha=self._line_best_alpha,
                extra_travel_deg=self._line_extra_travel,
                trials=tuple(self._line_trials),
            )

            self._line_trial = None
            self._line_trial_completed = True

            if selected != trial_positions:
                self._motor_executor.move_positions(selected)
                self._search_state = SearchState.JACOBIAN_LINE_RETURN
            else:
                self._search_state = SearchState.START

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

            observation = self._observe_results(
                self._search_results,
                search=True,
            )
            self._search_results.clear()

            assert self._jacobian_search.state.baseline_errors is not None

            action = self._jacobian_search.record_probe(
                observation=observation,
                target_qber=self.target_qber,
                target_qx=self.target_qx,
            )

            self._execute_jacobian_action(action)
            self._search_state = SearchState.JACOBIAN_PROBE_RETURN
            return

        # START during the one-cycle rolling-jog fallback uses the old
        # stationary reference and then launches a line search.
        if self._using_jog_fallback:
            self._search_results.append(result)

            if len(self._search_results) < self.search_measurements:
                return

            observation = self._observe_results(
                self._search_results,
                search=True,
            )
            self._search_results.clear()

            self._score = observation.score

            if self.target_reached(
                qber=observation.qber,
                qx=observation.qx
            ):
                self._lock_results.clear()
                self.state = CompensationState.LOCK
                return

            self._jog_search.begin_line(
                observation=observation,
                position=self.search_waveplate_position,
            )

            self._start_jog(
                direction=motor.MotorDirection.FORWARD,
                state=SearchState.JOG_POSITIVE,
            )
            return

        # START: collect the stationary baseline for a Jacobian iteration.
        self._search_results.append(result)

        if len(self._search_results) < self.search_measurements:
            return

        observation = self._observe_results(
            self._search_results,
            search=True,
        )
        self._search_results.clear()

        self._score = observation.score
        if (
            self.line_search_mode != 'disabled'
            and self._pending_jacobian_correction is not None
            and not self._line_trial_completed
            and self._line_trial is None
            and not self.target_reached(
                qber=observation.qber,
                qx=observation.qx,
            )
        ):
            _, baseline_score, _, step, _ = (
                self._pending_jacobian_correction
            )

            baseline_positions = (
                self._jacobian_search.state.baseline_positions
            )
            assert baseline_positions is not None

            full_positions = tuple(
                base + delta
                for base, delta in zip(baseline_positions, step)
            )

            full_score = observation.score

            if full_score < baseline_score:
                self._line_best_alpha = 1.0
                self._line_best_score = full_score
                self._line_best_positions = full_positions
                self._line_alpha = 1.5
            else:
                self._line_best_alpha = 0.0
                self._line_best_score = baseline_score
                self._line_best_positions = baseline_positions
                self._line_alpha = 0.5

            self._line_trials = []
            self._line_extra_travel = 0.0
            self._line_previous_positions = full_positions

            trial_positions = tuple(
                base + self._line_alpha * delta
                for base, delta in zip(baseline_positions, step)
            )

            self._line_trial = (full_score, full_positions)

            self._line_extra_travel += sum(
                abs(new - old)
                for new, old in zip(
                    trial_positions,
                    full_positions,
                )
            )

            self._motor_executor.move_positions(trial_positions)
            self._search_state = SearchState.JACOBIAN_LINE_MOVE
            return

        if self._pending_jacobian_correction is not None:
            (
                iteration,
                baseline_score,
                predicted_score,
                step,
                condition,
            ) = self._pending_jacobian_correction

            self._last_jacobian_correction = JacobianCorrection(
                iteration=iteration,
                baseline_score=baseline_score,
                predicted_score=predicted_score,
                measured_score=observation.score,
                step=step,
                condition=condition,
            )

            self._pending_jacobian_correction = None
            self._line_trial_completed = False

            self._jacobian_search.record_correction(
                self._last_jacobian_correction
            )

        if self.target_reached(
            qber=observation.qber, 
            qx=observation.qx
        ):
            self._lock_results.clear()
            self.state = CompensationState.LOCK
            return

        action = self._jacobian_search.begin_iteration(
            observation=observation,
            target_qber=self.target_qber,
            target_qx=self.target_qx,
            baseline_positions=self._motor_executor.positions(),
        )

        self._execute_jacobian_action(action)
        self._search_state = SearchState.JACOBIAN_PROBE_MOVE


    def _update_jog_measurement(
        self,
        *,
        result: BB84DetectionResult,
    ) -> None:
        current_position = self.search_waveplate.position

        interval = self._jog_search.record_motor_position(
            position=current_position,
        )

        if interval is None:
            return

        start_position, end_position = interval

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

        observation = self._observe_results(
            window_results,
            search=True,
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

        self._jog_search.record_measurement_position(
            start_position=window_start_position,
            end_position=window_end_position,
        )

        self._score = observation.score

        if self._search_state is SearchState.JOG_POSITIVE:
            direction = JogDirection.POSITIVE
        elif self._search_state is SearchState.JOG_NEGATIVE:
            direction = JogDirection.NEGATIVE
        else:
            raise ValueError(
                f'Unexpected jog state: {self._search_state}'
            )

        action = self._jog_search.record_measurement(
            observation=observation,
            target_qber=self.target_qber,
            target_qx=self.target_qx,
            position=measurement_position,
            direction=direction,
        )

        if action.type is JogActionType.CONTINUE:
            return

        assert action.position is not None

        if action.type is JogActionType.RETURN_TO_LOCK:
            self._return_to_position(
                position=action.position,
                state=SearchState.RETURN_TO_LOCK,
            )
            return

        if action.type is JogActionType.RETURN_FROM_POSITIVE:
            self._return_to_position(
                position=action.position,
                state=SearchState.RETURN_FROM_POSITIVE,
            )
            return

        if action.type is JogActionType.RETURN_TO_BEST:
            self._return_to_position(
                position=action.position,
                state=SearchState.RETURN_TO_BEST,
            )
            return

        raise ValueError(f'Unexpected jog action: {action.type}')

    def _advance_jacobian_probe(self) -> None:
        action = self._jacobian_search.advance_probe()

        self._execute_jacobian_action(action)

        if (
            action.type is JacobianActionType.MOVE_TO
        ):
            self._search_state = SearchState.JACOBIAN_PROBE_MOVE

    def _start_jog_fallback(self) -> None:
        self._jacobian_search.state.fallback_count += 1
        self._using_jog_fallback = True

        self._jog_search.begin_fallback_cycle()

        self._search_state = SearchState.START
        self._reset_search_line()
        self._search_results.clear()

    def _start_jog(
        self,
        *,
        direction: motor.MotorDirection,
        state: SearchState,
    ) -> None:
        self._search_jog_results.clear()

        self._jog_search.begin_jog(
            position=self.search_waveplate_position,
        )

        self._motor_executor.jog(
            index=self._jog_search.state.waveplate_index,
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
        self._motor_executor.stop_and_move_to(
            index=self._jog_search.state.waveplate_index,
            position=position,
        )

        self._search_state = state
        self._jog_search.begin_return()
        self._search_jog_results.clear()

    def _next_search_waveplate(self) -> None:
        cycle_complete = self._jog_search.advance_waveplate(
            waveplate_count=len(self.waveplates),
        )

        if cycle_complete and self._using_jog_fallback:
            self._using_jog_fallback = False

        self._search_state = SearchState.START
        self._reset_search_line()
        self._search_results.clear()

    def _reset_search_line(self) -> None:
        self._jog_search.reset_line()
        self._search_jog_results.clear()


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

        observation = self._observe_results(
            self._lock_results,
            search=False,
        )
        self._lock_results.clear()

        self._score = observation.score

        decision = evaluate_lock(
            observation=observation,
            target_qber=self.target_qber,
            target_qx=self.target_qx,
        )

        if decision is LockDecision.COMPLETE:
            self.state = CompensationState.COMPLETE

        elif decision is LockDecision.RETRY_SEARCH:
            # A failed LOCK returns to a fresh line search from the
            # current, stationary position.
            self._using_jog_fallback = False
            self._search_state = SearchState.START
            self._reset_search_line()
            self._search_results.clear()
            self.state = CompensationState.SEARCH

        else:
            raise ValueError(
                f'Unexpected LOCK decision: {decision}'
            )

    def _aggregate_results(
        self,
        results: typing.Sequence[BB84DetectionResult],
    ) -> tuple[float, float]:
        measurement = aggregate_bb84_measurements(
            results=results,
            z_pairs=self.measurements.z_pairs,
            x_pairs=self.measurements.x_pairs,
        )

        return measurement.qber, measurement.qx

    def _observe_results(
        self,
        results: typing.Sequence[BB84DetectionResult],
        *,
        search: bool,
    ) -> Observation:
        """Create an observation from an aggregated measurement window."""

        measurement = aggregate_bb84_measurements(
            results=results,
            z_pairs=self.measurements.z_pairs,
            x_pairs=self.measurements.x_pairs,
        )

        if search:
            score = self.search_objective(
                qber=measurement.qber,
                qx=measurement.qx,
            )
        else:
            score = self.objective(
                qber=measurement.qber,
                qx=measurement.qx,
            )

        return make_observation(
            qber=measurement.qber,
            qx=measurement.qx,
            score=score,
            counts=measurement.counts,
        )

    def _execute_jacobian_action(
        self,
        action: JacobianAction,
    ) -> None:
        if action.type is JacobianActionType.MOVE_TO:
            assert action.motor_index is not None
            assert action.position is not None

            self._motor_executor.move_to(
                index=action.motor_index,
                position=action.position,
            )

            return

        if action.type is JacobianActionType.APPLY_STEP:
            assert action.step is not None

            jacobian_state = self._jacobian_search.state

            if (
                jacobian_state.baseline_score is not None
                and jacobian_state.predicted_score is not None
            ):
                self._pending_jacobian_correction = (
                    jacobian_state.iteration + 1,
                    jacobian_state.baseline_score,
                    jacobian_state.predicted_score,
                    action.step,
                    jacobian_state.condition,
                )
            else:
                self._pending_jacobian_correction = None

            self._motor_executor.apply_step(action.step)

            jacobian_state.iteration += 1
            self._search_state = SearchState.JACOBIAN_APPLY
            return

        if action.type is JacobianActionType.FALLBACK:
            self._start_jog_fallback()
            return

        raise ValueError(
            f'Unknown Jacobian action: {action.type}'
        )