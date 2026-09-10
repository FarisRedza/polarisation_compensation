import dataclasses
import typing

import numpy as np
import numpy.typing as npt

import qtoolkit
from qtoolkit.polarisation import WavePlate

from .polcomp import (
    BB84DetectionResult,
)
from motor.dummy_motor import DummyMotor


class SimulatedMotor(DummyMotor):
    def __init__(
            self,
            waveplate: WavePlate
    ) -> None:
        super().__init__()
        self.waveplate = waveplate

    @property
    def matrix(self) -> np.ndarray:
        self.waveplate.angle_deg = self.position
        return self.waveplate.matrix


@dataclasses.dataclass
class SimulatedEPS:
    """
    Simulated two-photon polarisation source.
    """
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
    """
    Simulated polarisation compensation experiment

    - entangled photon source
    - compensation waveplates
    - propagation of the quantum state
    - BB84 detector probabilities
    - simulated singles
    - simulated coincidence events

    The output is ordinary TimetagData, so the timetagger does not need
    to know how the data was generated.
    """

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

        self.waveplates = tuple(
            waveplates
        )

        self.measurements = measurements

        self.compensation_subsystem = (
            compensation_subsystem
        )

        self.coincidence_delay_ps = (
            coincidence_delay_ps
        )

        self.coincidence_jitter_ps = (
            coincidence_jitter_ps
        )

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
        """
        Current Jones matrix of the compensation waveplates.
        """
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
        """
        Current two-photon state after compensation.
        """
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
        """
        Current BB84 joint detector probabilities.
        """
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
        """
        Generate a block of simulated timetags.
        """
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
    """
    Something capable of providing timetag data.

    SimulatedBB84System satisfies this protocol, but another
    implementation could read from a file, network connection, etc.
    """

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
        """
        Channels belonging to the configured BB84 measurements.
        """
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
        """
        Acquire one block of timetags.
        """
        return self._source.read(
            duration_s
        )

    def measure(
        self,
        duration_s: float,
        coincidence_window_ps: int,
    ) -> BB84DetectionResult:
        """
        Acquire timetags and calculate BB84 measurement statistics.
        """
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

        return BB84DetectionResult(
            data=data,
            singles=singles,
            coincidences=coincidences,
            qber=zz.qber,
            qx=xx.qber,
        )