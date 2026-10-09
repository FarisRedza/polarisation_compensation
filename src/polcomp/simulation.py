import dataclasses
import math
import time
import typing

import numpy as np
import numpy.typing as npt

import motor
import qtoolkit
from qtoolkit.polarisation import Waveplate

from .polcomp import BB84DetectionResult
from .measurement import measurement_counts_from_result


class Clock:
    """Clock interface used by deterministic simulated motors."""

    def time(self) -> float:
        ...

    def advance(self, seconds: float) -> None:
        ...


class RealTimeClock:
    """Clock whose advancement follows real wall-clock time."""

    def time(self) -> float:
        return time.monotonic()

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError('seconds must be non-negative')

        time.sleep(seconds)


class SimulationClock:
    """A manually advanced monotonic clock for deterministic simulations."""

    def __init__(self) -> None:
        self._time = 0.0

    def time(self) -> float:
        return self._time

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError('seconds must be non-negative')

        self._time += seconds


class SimulatedMotor(motor.Motor):
    """Motor model driven by an injectable clock.

    The motion profile mirrors DummyMotor: finite moves use triangular or
    trapezoidal acceleration profiles and jogs accelerate to a constant
    velocity.  No background tracking thread is required; position and
    motion state are updated whenever they are read.

    The default clock is real time, so standalone motors progress naturally.
    Accelerated experiments must explicitly supply and advance a shared
    SimulationClock for all participating motors.
    """

    def __init__(
        self,
        waveplate: Waveplate,
        *,
        clock: typing.Optional[Clock] = None,
    ) -> None:
        super().__init__(
            serial_number='simulated_motor'
        )
        self.waveplate = waveplate
        self.clock = (
            clock
            if clock is not None
            else RealTimeClock()
        )

        self.acceleration = 20.0
        self.max_velocity = 25.0

        self._position = 0.0
        self._is_moving = False
        self._tracking_error: typing.Optional[Exception] = None

        self._motion_mode: typing.Optional[str] = None
        self._jog_direction = 0.0

        self._move_start_time = 0.0
        self._move_start_position = 0.0
        self._move_distance = 0.0
        self._move_acceleration = 0.0
        self._move_peak_velocity = 0.0
        self._move_accel_time = 0.0
        self._move_cruise_time = 0.0
        self._move_total_time = 0.0

        self.device_info = motor.DeviceInfo(
            device_name='Simulated Device',
            model='Simulated Motor',
            serial_number='simulated_motor',
            firmware_version='0.0.0',
        )

    @property
    def position(self) -> float:
        self._update_motion()
        return self._position

    @position.setter
    def position(self, value: float) -> None:
        # Motor.__init__ assigns this attribute.  Keeping a setter makes the
        # subclass compatible with that initialisation while all later state
        # is stored in _position.
        self._position = value

    @property
    def is_moving(self) -> bool:
        self._update_motion()
        return self._is_moving

    @is_moving.setter
    def is_moving(self, value: bool) -> None:
        self._is_moving = value

    @property
    def tracking_error(self) -> typing.Optional[Exception]:
        return self._tracking_error

    @property
    def matrix(self) -> np.ndarray:
        self.waveplate.angle_deg = self.position
        return self.waveplate.matrix

    def move_by(
        self,
        angle: float,
        acceleration: typing.Optional[float] = None,
        max_velocity: typing.Optional[float] = None,
    ) -> None:
        requested_acceleration = (
            self.acceleration
            if acceleration is None
            else acceleration
        )
        requested_max_velocity = (
            self.max_velocity
            if max_velocity is None
            else max_velocity
        )

        if acceleration is not None or max_velocity is not None:
            self.update_settings(
                acceleration=requested_acceleration,
                max_velocity=requested_max_velocity,
            )

        if angle == 0:
            return

        self._update_motion()

        distance = abs(angle)
        accel_time = self.max_velocity / self.acceleration
        accel_distance = (
            0.5
            * self.acceleration
            * accel_time ** 2
        )

        if 2 * accel_distance >= distance:
            accel_time = math.sqrt(
                distance / self.acceleration
            )
            peak_velocity = (
                self.acceleration * accel_time
            )
            cruise_time = 0.0
            total_time = 2 * accel_time
        else:
            peak_velocity = self.max_velocity
            cruise_distance = (
                distance - 2 * accel_distance
            )
            cruise_time = (
                cruise_distance / peak_velocity
            )
            total_time = (
                2 * accel_time + cruise_time
            )

        self._motion_mode = 'move'
        self._jog_direction = 0.0
        self._move_start_time = self.clock.time()
        self._move_start_position = self._position
        self._move_distance = angle
        self._move_acceleration = self.acceleration
        self._move_peak_velocity = peak_velocity
        self._move_accel_time = accel_time
        self._move_cruise_time = cruise_time
        self._move_total_time = total_time
        self._is_moving = True

    def move_to(
        self,
        position: float,
        acceleration: typing.Optional[float] = None,
        max_velocity: typing.Optional[float] = None,
    ) -> None:
        self._update_motion()

        self.move_by(
            angle=position - self._position,
            acceleration=acceleration,
            max_velocity=max_velocity,
        )

    def jog(
        self,
        direction: motor.MotorDirection,
        acceleration: typing.Optional[float] = None,
        max_velocity: typing.Optional[float] = None,
    ) -> None:
        requested_acceleration = (
            self.acceleration
            if acceleration is None
            else acceleration
        )
        requested_max_velocity = (
            self.max_velocity
            if max_velocity is None
            else max_velocity
        )

        if acceleration is not None or max_velocity is not None:
            self.update_settings(
                acceleration=requested_acceleration,
                max_velocity=requested_max_velocity,
            )

        if direction is motor.MotorDirection.FORWARD:
            jog_direction = 1.0
        elif direction is motor.MotorDirection.BACKWARD:
            jog_direction = -1.0
        else:
            raise ValueError(
                f'Unsupported motor direction: {direction!r}'
            )

        self._update_motion()

        self._motion_mode = 'jog'
        self._jog_direction = jog_direction
        self._move_start_time = self.clock.time()
        self._move_start_position = self._position
        self._move_acceleration = self.acceleration
        self._move_peak_velocity = self.max_velocity
        self._move_accel_time = (
            self.max_velocity / self.acceleration
        )
        self._is_moving = True

    def stop(self) -> None:
        self._update_motion()

        self._is_moving = False
        self._motion_mode = None
        self._jog_direction = 0.0

    def disconnect(self) -> None:
        self.stop()

    def update_settings(
        self,
        acceleration: float,
        max_velocity: float,
    ) -> None:
        if acceleration <= 0:
            raise ValueError(
                'acceleration must be positive'
            )

        if max_velocity <= 0:
            raise ValueError(
                'max_velocity must be positive'
            )

        self.acceleration = acceleration
        self.max_velocity = max_velocity

    def _update_motion(self) -> None:
        if not self._is_moving:
            return

        elapsed = (
            self.clock.time()
            - self._move_start_time
        )

        if self._motion_mode == 'jog':
            acceleration = self._move_acceleration
            max_velocity = self._move_peak_velocity
            accel_time = self._move_accel_time

            if elapsed < accel_time:
                distance = (
                    0.5
                    * acceleration
                    * elapsed ** 2
                )
            else:
                accel_distance = (
                    0.5
                    * acceleration
                    * accel_time ** 2
                )
                cruise_elapsed = (
                    elapsed - accel_time
                )
                distance = (
                    accel_distance
                    + max_velocity * cruise_elapsed
                )

            self._position = (
                self._move_start_position
                + self._jog_direction * distance
            )
            return

        if self._motion_mode != 'move':
            self._is_moving = False
            return

        total_distance = abs(
            self._move_distance
        )
        direction = (
            1.0
            if self._move_distance >= 0
            else -1.0
        )

        acceleration = self._move_acceleration
        peak_velocity = self._move_peak_velocity
        accel_time = self._move_accel_time
        cruise_time = self._move_cruise_time

        if elapsed >= self._move_total_time:
            self._position = (
                self._move_start_position
                + self._move_distance
            )
            self._is_moving = False
            self._motion_mode = None
            return

        if elapsed < accel_time:
            distance = (
                0.5
                * acceleration
                * elapsed ** 2
            )
        elif elapsed < accel_time + cruise_time:
            accel_distance = (
                0.5
                * acceleration
                * accel_time ** 2
            )
            cruise_elapsed = (
                elapsed - accel_time
            )
            distance = (
                accel_distance
                + peak_velocity * cruise_elapsed
            )
        else:
            remaining_time = (
                self._move_total_time
                - elapsed
            )
            remaining_distance = (
                0.5
                * acceleration
                * remaining_time ** 2
            )
            distance = (
                total_distance
                - remaining_distance
            )

        self._position = (
            self._move_start_position
            + direction * distance
        )


@dataclasses.dataclass
class SimulatedEPS:
    """Simulated two-photon polarisation source."""

    state: npt.NDArray[np.complex128]
    pair_rate_hz: float

    def __post_init__(self) -> None:
        self.state = np.asarray(
            self.state,
            dtype=np.complex128,
        )

        if self.state.shape != (4,):
            raise ValueError(
                'Two-photon state must have shape (4,).'
            )

        if self.pair_rate_hz < 0:
            raise ValueError(
                'pair_rate_hz must be non-negative.'
            )


class SimulatedPolCompSystem:
    """Simulated polarisation compensation experiment."""

    def __init__(
        self,
        source: SimulatedEPS,
        waveplates: typing.Sequence[SimulatedMotor],
        measurements: qtoolkit.polarisation.BB84MeasurementPair,
        channel_rates: typing.Mapping[int, float],
        *,
        compensation_subsystem: int = 0,
        coincidence_delay_ps: int = 0,
        coincidence_jitter_ps: float = 0.0,
        rng: typing.Optional[np.random.Generator] = None,
    ) -> None:
        self.source = source
        self.waveplates = tuple(waveplates)
        self.measurements = measurements
        self.compensation_subsystem = compensation_subsystem
        self.coincidence_delay_ps = coincidence_delay_ps
        self.coincidence_jitter_ps = coincidence_jitter_ps

        self._simulator = (
            qtoolkit.timetags.LiveTimetagSimulator(
                channel_rates=channel_rates,
                coincidence_pairs=(),
                rng=rng,
            )
        )

    @property
    def compensation_matrix(
        self,
    ) -> npt.NDArray[np.complex128]:
        result = np.eye(
            2,
            dtype=np.complex128,
        )

        for waveplate in self.waveplates:
            result = (
                waveplate.matrix
                @ result
            )

        return result

    @property
    def state(
        self,
    ) -> npt.NDArray[np.complex128]:
        return (
            qtoolkit.polarisation
            .apply_local_jones_matrix(
                state=self.source.state,
                matrix=self.compensation_matrix,
                subsystem=self.compensation_subsystem,
            )
        )

    @property
    def joint_probabilities(
        self,
    ) -> dict[tuple[int, int], float]:
        return (
            self.measurements
            .joint_probabilities(
                self.state
            )
        )

    def read(
        self,
        duration_s: float,
    ) -> qtoolkit.timetags.TimetagData:
        coincidence_processes = (
            qtoolkit.timetags
            .coincidence_processes_from_probabilities(
                probabilities=self.joint_probabilities,
                pair_rate_hz=self.source.pair_rate_hz,
                delay_ps=self.coincidence_delay_ps,
                jitter_ps=self.coincidence_jitter_ps,
            )
        )

        self._simulator.set_coincidence_processes(
            coincidence_processes
        )

        return self._simulator.read(
            duration_s
        )


class TimetagSource(typing.Protocol):
    def read(
        self,
        duration_s: float,
    ) -> qtoolkit.timetags.TimetagData:
        ...


class SimulatedTimetagger:
    def __init__(
        self,
        source: TimetagSource,
        measurements: qtoolkit.polarisation.BB84MeasurementPair,
    ) -> None:
        self._source = source
        self.measurements = measurements

    @property
    def channels(
        self,
    ) -> tuple[int, ...]:
        pairs = (
            *self.measurements.z_pairs,
            *self.measurements.x_pairs,
        )

        return tuple(
            sorted({
                channel
                for pair in pairs
                for channel in pair.as_tuple()
            })
        )

    def read(
        self,
        duration_s: float,
    ) -> qtoolkit.timetags.TimetagData:
        return self._source.read(
            duration_s
        )

    def measure(
        self,
        duration_s: float,
        coincidence_window_ps: int,
    ) -> BB84DetectionResult:
        data = self.read(
            duration_s
        )

        singles = {
            channel: data.count(channel)
            for channel in self.channels
        }

        pairs = (
            *self.measurements.z_pairs,
            *self.measurements.x_pairs,
        )

        coincidences = (
            qtoolkit.timetags.count_coincidences(
                data=data,
                pairs=[
                    pair.as_tuple()
                    for pair in pairs
                ],
                coincidence_window=(
                    coincidence_window_ps
                ),
            )
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

        result = BB84DetectionResult(
            data=data,
            singles=singles,
            coincidences=coincidences,
            qber=zz.qber,
            qx=xx.qber,
        )

        counts = measurement_counts_from_result(
            result=result,
            coincidence_window_ps=coincidence_window_ps,
        )

        return dataclasses.replace(
            result,
            counts=counts,
        )
