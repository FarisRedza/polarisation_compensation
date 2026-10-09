import dataclasses
import typing

import qtoolkit

from .polcomp import BB84DetectionResult
from .measurement import measurement_counts_from_result


@typing.runtime_checkable
class TimetagSource(typing.Protocol):
    """Source of timetag data for a requested acquisition duration."""

    def read(
        self,
        duration_s: float,
    ) -> qtoolkit.timetags.TimetagData:
        ...


@typing.runtime_checkable
class BB84MeasurementSource(typing.Protocol):
    """Interface for acquiring BB84 detection measurements.

    Implementations may acquire data from simulation, recorded
    timetags, or physical timetagging hardware.

    Each measurement must return a BB84DetectionResult
    containing the calculated basis metrics and detector counts.
    """

    def measure(
        self,
        duration_s: float,
        coincidence_window_ps: int,
    ) -> BB84DetectionResult:
        ...


class BB84TimetagAcquisition(BB84MeasurementSource):
    """Convert timetags from any TimetagSource into BB84 measurements."""

    def __init__(
        self,
        source: TimetagSource,
        measurements: qtoolkit.polarisation.BB84MeasurementPair,
    ) -> None:
        self._source = source
        self.measurements = measurements

    @property
    def channels(self) -> tuple[int, ...]:
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
        return self._source.read(duration_s)

    def measure(
        self,
        duration_s: float,
        coincidence_window_ps: int,
    ) -> BB84DetectionResult:
        data = self.read(duration_s)

        singles = {
            channel: data.count(channel)
            for channel in self.channels
        }

        pairs = (
            *self.measurements.z_pairs,
            *self.measurements.x_pairs,
        )

        coincidences = qtoolkit.timetags.count_coincidences(
            data=data,
            pairs=[
                pair.as_tuple()
                for pair in pairs
            ],
            coincidence_window=coincidence_window_ps,
        )

        zz = qtoolkit.qkd.BasisMetrics.from_coincidences(
            coincidences=coincidences,
            pairs=self.measurements.z_pairs,
        )

        xx = qtoolkit.qkd.BasisMetrics.from_coincidences(
            coincidences=coincidences,
            pairs=self.measurements.x_pairs,
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