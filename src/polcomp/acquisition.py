import typing

from .polcomp import BB84DetectionResult


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