import dataclasses
import time
import typing

import numpy as np

from qtoolkit.polarisation import (
    QuarterWaveplate,
    HalfWaveplate,
    PHI_PLUS,
    PolarisationChannelMap,
    BB84Measurement,
    BB84MeasurementPair,
)

from polcomp import (
    SimulatedEPS,
    SimulatedPolCompSystem,
    SimulatedTimetagger,
    SimulatedMotor,
    PolCompController,
)
from polcomp.simulation import (
    Clock,
    RealTimeClock,
    SimulationClock
)


INTERVAL_S = 0.1
PAIR_RATE_HZ = 40_000
MEASUREMENT_TIME_S = 0.1
COINCIDENCE_WINDOW_PS = 1_000


@dataclasses.dataclass(frozen=True)
class BenchmarkSample:
    elapsed_s: float
    controller_state: str
    search_state: typing.Optional[str]
    qber: float
    qx: float
    search_score: float
    acceptance_score: float
    jacobian_iteration: int
    jacobian_condition: typing.Optional[float]
    jacobian_fallback_count: int
    compensation_positions: tuple[float, float, float]


@dataclasses.dataclass(frozen=True)
class BenchmarkResult:
    disturbance: tuple[float, float, float]
    seed: int
    timeout_s: float
    simulated_time: bool
    completed: bool
    elapsed_s: float
    wall_clock_runtime_s: float

    initial_qber: float
    initial_qx: float
    initial_search_score: float

    final_qber: float
    final_qx: float
    final_search_score: float
    final_acceptance_score: float

    jacobian_iterations: int
    jacobian_fallback_count: int
    max_jacobian_condition: typing.Optional[float]

    final_positions: tuple[float, float, float]
    total_motor_travel_deg: float

    samples: tuple[BenchmarkSample, ...]

    def summary(self) -> str:
        condition = (
            f'{self.max_jacobian_condition:.3f}'
            if self.max_jacobian_condition is not None
            else '-'
        )

        return '\n'.join(
            (
                'Polarisation compensation benchmark',
                '-----------------------------------',
                (
                    'Disturbance:          '
                    f'({self.disturbance[0]:.1f}, '
                    f'{self.disturbance[1]:.1f}, '
                    f'{self.disturbance[2]:.1f}) deg'
                ),
                f'RNG seed:             {self.seed}',
                (
                    'Clock:                '
                    f'{"simulated" if self.simulated_time else "real-time"}'
                ),
                (
                    'Result:               '
                    f'{"COMPLETE" if self.completed else "TIMEOUT"}'
                ),
                f'Elapsed model time:   {self.elapsed_s:.2f} s',
                f'Wall-clock runtime:    {self.wall_clock_runtime_s:.2f} s',
                (
                    'Simulation speedup:   '
                    f'{self.elapsed_s / self.wall_clock_runtime_s:.1f}x'
                    if self.wall_clock_runtime_s > 0
                    else 'Simulation speedup:   -'
                ),
                f'Timeout:              {self.timeout_s:.2f} s',
                (
                    'Initial QBER / Qx:    '
                    f'{self.initial_qber:.4f} / '
                    f'{self.initial_qx:.4f}'
                ),
                (
                    'Initial search RMS:   '
                    f'{self.initial_search_score:.3f}'
                ),
                (
                    'Final QBER / Qx:      '
                    f'{self.final_qber:.4f} / '
                    f'{self.final_qx:.4f}'
                ),
                (
                    'Final search RMS:     '
                    f'{self.final_search_score:.3f}'
                ),
                (
                    'Final acceptance:     '
                    f'{self.final_acceptance_score:.3f}'
                ),
                (
                    'Jacobian iterations:  '
                    f'{self.jacobian_iterations}'
                ),
                (
                    'Jog fallbacks:        '
                    f'{self.jacobian_fallback_count}'
                ),
                f'Max Jacobian cond.:    {condition}',
                (
                    'Final compensation:   '
                    f'({self.final_positions[0]:.2f}, '
                    f'{self.final_positions[1]:.2f}, '
                    f'{self.final_positions[2]:.2f}) deg'
                ),
                (
                    'Total motor travel:   '
                    f'{self.total_motor_travel_deg:.2f} deg'
                ),
            )
        )

    def failure_details(
        self,
        *,
        last_samples: int = 10,
    ) -> str:
        lines = [
            self.summary(),
            '',
            f'Last {min(last_samples, len(self.samples))} samples:',
        ]

        for sample in self.samples[-last_samples:]:
            search_state = (
                sample.search_state
                if sample.search_state is not None
                else '-'
            )
            condition = (
                f'{sample.jacobian_condition:.2f}'
                if sample.jacobian_condition is not None
                else '-'
            )

            lines.append(
                (
                    f'  t={sample.elapsed_s:7.2f}s '
                    f'{sample.controller_state:8s} '
                    f'{search_state:24s} '
                    f'QBER={sample.qber:.4f} '
                    f'Qx={sample.qx:.4f} '
                    f'RMS={sample.search_score:.3f} '
                    f'accept={sample.acceptance_score:.3f} '
                    f'J={sample.jacobian_iteration} '
                    f'cond={condition}'
                )
            )

        return '\n'.join(lines)


def _set_initial_disturbance(
    motors: tuple[SimulatedMotor, SimulatedMotor, SimulatedMotor],
    disturbance: tuple[float, float, float],
    clock: Clock,
) -> None:
    """Position disturbance plates before benchmark timing begins."""

    for motor, position in zip(
        motors,
        disturbance,
    ):
        motor.move_to(
            position=position,
            acceleration=100_000.0,
            max_velocity=100_000.0,
        )

    while any(
        motor.is_moving
        for motor in motors
    ):
        clock.advance(0.001)


def run_compensation_benchmark(
    *,
    disturbance: tuple[float, float, float],
    seed: int = 42,
    timeout_s: float = 120.0,
    interval_s: float = INTERVAL_S,
    measurement_time_s: float = MEASUREMENT_TIME_S,
    coincidence_window_ps: int = COINCIDENCE_WINDOW_PS,
    simulated_time: bool = True,
) -> BenchmarkResult:
    """Run one accelerated end-to-end compensation benchmark.

    The controller and optical simulation use their normal public
    interfaces.  Motor dynamics are driven by a manually advanced
    SimulationClock, so a long simulated acquisition can run without
    wall-clock sleeps.

    ``elapsed_s`` and ``timeout_s`` are simulated time.
    """

    if timeout_s <= 0:
        raise ValueError(
            'timeout_s must be positive'
        )

    if interval_s <= 0:
        raise ValueError(
            'interval_s must be positive'
        )

    if measurement_time_s <= 0:
        raise ValueError(
            'measurement_time_s must be positive'
        )

    clock = (
        SimulationClock()
        if simulated_time
        else RealTimeClock()
    )
    wall_clock_start = time.monotonic()

    source = SimulatedEPS(
        state=PHI_PLUS,
        pair_rate_hz=PAIR_RATE_HZ,
    )

    disturbance_motors = (
        SimulatedMotor(
            waveplate=QuarterWaveplate(),
            clock=clock,
        ),
        SimulatedMotor(
            waveplate=HalfWaveplate(),
            clock=clock,
        ),
        SimulatedMotor(
            waveplate=QuarterWaveplate(),
            clock=clock,
        ),
    )

    compensation_motors = (
        SimulatedMotor(
            waveplate=QuarterWaveplate(),
            clock=clock,
        ),
        SimulatedMotor(
            waveplate=HalfWaveplate(),
            clock=clock,
        ),
        SimulatedMotor(
            waveplate=QuarterWaveplate(),
            clock=clock,
        ),
    )

    all_motors = (
        *disturbance_motors,
        *compensation_motors,
    )

    try:
        _set_initial_disturbance(
            disturbance_motors,
            disturbance,
            clock,
        )

        first_channels = PolarisationChannelMap(
            h=0,
            v=1,
            d=2,
            a=3,
        )
        second_channels = PolarisationChannelMap(
            h=4,
            v=5,
            d=6,
            a=7,
        )

        measurements = BB84MeasurementPair(
            first=BB84Measurement(
                channels=first_channels,
            ),
            second=BB84Measurement(
                channels=second_channels,
            ),
        )

        channel_rates = {
            channel: 25_000
            for channel in range(8)
        }

        system = SimulatedPolCompSystem(
            source=source,
            waveplates=all_motors,
            measurements=measurements,
            channel_rates=channel_rates,
            coincidence_delay_ps=300,
            coincidence_jitter_ps=50,
            rng=np.random.default_rng(seed),
        )

        timetagger = SimulatedTimetagger(
            source=system,
            measurements=measurements,
        )

        controller = PolCompController(
            qwp1=compensation_motors[0],
            hwp=compensation_motors[1],
            qwp2=compensation_motors[2],
            measurements=measurements,
            target_qber=0.05,
            target_qx=0.05,
            lock_measurements=5,
        )

        samples: list[BenchmarkSample] = []
        max_jacobian_condition: typing.Optional[
            float
        ] = None
        total_motor_travel_deg = 0.0

        previous_positions = tuple(
            motor.position
            for motor in compensation_motors
        )

        controller.start()
        start_time = clock.time()

        initial_qber: typing.Optional[float] = None
        initial_qx: typing.Optional[float] = None
        initial_search_score: typing.Optional[float] = None
        last_result = None

        while (
            clock.time() - start_time
            < timeout_s
        ):
            elapsed_s = (
                clock.time() - start_time
            )

            result = timetagger.measure(
                duration_s=measurement_time_s,
                coincidence_window_ps=(
                    coincidence_window_ps
                ),
            )

            if initial_qber is None:
                initial_qber = result.qber
                initial_qx = result.qx
                initial_search_score = (
                    controller.search_objective(
                        result.qber,
                        result.qx,
                    )
                )

            controller.update(
                result=result,
            )
            last_result = result

            status = controller.status
            positions = tuple(
                motor.position
                for motor in compensation_motors
            )

            total_motor_travel_deg += sum(
                abs(current - previous)
                for current, previous in zip(
                    positions,
                    previous_positions,
                )
            )
            previous_positions = positions

            if (
                status.jacobian_condition
                is not None
            ):
                if max_jacobian_condition is None:
                    max_jacobian_condition = (
                        status.jacobian_condition
                    )
                else:
                    max_jacobian_condition = max(
                        max_jacobian_condition,
                        status.jacobian_condition,
                    )

            samples.append(
                BenchmarkSample(
                    elapsed_s=elapsed_s,
                    controller_state=(
                        status.state.name
                    ),
                    search_state=(
                        status.search_state.name
                        if status.search_state is not None
                        else None
                    ),
                    qber=result.qber,
                    qx=result.qx,
                    search_score=(
                        controller.search_objective(
                            result.qber,
                            result.qx,
                        )
                    ),
                    acceptance_score=(
                        controller.objective(
                            result.qber,
                            result.qx,
                        )
                    ),
                    jacobian_iteration=(
                        status.jacobian_iteration
                    ),
                    jacobian_condition=(
                        status.jacobian_condition
                    ),
                    jacobian_fallback_count=(
                        status.jacobian_fallback_count
                    ),
                    compensation_positions=positions,
                )
            )

            if status.state.name == 'COMPLETE':
                break

            # On the next loop, every motor reports the position it would
            # have reached after this amount of simulated time.
            clock.advance(
                interval_s
            )

        if last_result is None:
            raise RuntimeError(
                'Benchmark ended before a measurement was acquired.'
            )

        assert initial_qber is not None
        assert initial_qx is not None
        assert initial_search_score is not None

        final_status = controller.status
        final_positions = tuple(
            motor.position
            for motor in compensation_motors
        )
        final_elapsed_s = (
            clock.time() - start_time
        )

        total_motor_travel_deg += sum(
            abs(current - previous)
            for current, previous in zip(
                final_positions,
                previous_positions,
            )
        )

        return BenchmarkResult(
            disturbance=disturbance,
            seed=seed,
            timeout_s=timeout_s,
            simulated_time=simulated_time,
            completed=(
                final_status.state.name
                == 'COMPLETE'
            ),
            elapsed_s=final_elapsed_s,
            wall_clock_runtime_s=(
                time.monotonic()
                - wall_clock_start
            ),
            initial_qber=initial_qber,
            initial_qx=initial_qx,
            initial_search_score=(
                initial_search_score
            ),
            final_qber=last_result.qber,
            final_qx=last_result.qx,
            final_search_score=(
                controller.search_objective(
                    last_result.qber,
                    last_result.qx,
                )
            ),
            final_acceptance_score=(
                controller.objective(
                    last_result.qber,
                    last_result.qx,
                )
            ),
            jacobian_iterations=(
                final_status.jacobian_iteration
            ),
            jacobian_fallback_count=(
                final_status.jacobian_fallback_count
            ),
            max_jacobian_condition=(
                max_jacobian_condition
            ),
            final_positions=final_positions,
            total_motor_travel_deg=(
                total_motor_travel_deg
            ),
            samples=tuple(samples),
        )

    finally:
        for motor in all_motors:
            motor.disconnect()
