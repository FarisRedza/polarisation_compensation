from unittest.mock import Mock

from polcomp.acquisition import BB84MeasurementSource
from polcomp.simulation import SimulatedTimetagger


def test_simulated_timetagger_satisfies_protocol():
    timetagger = SimulatedTimetagger(
        source=Mock(),
        measurements=Mock(),
    )

    assert isinstance(
        timetagger,
        BB84MeasurementSource,
    )


def test_protocol_accepts_compatible_source():
    class DummySource:
        def measure(
            self,
            duration_s: float,
            coincidence_window_ps: int,
        ):
            return None

    assert isinstance(
        DummySource(),
        BB84MeasurementSource,
    )


def test_protocol_rejects_missing_measure_method():
    class InvalidSource:
        pass

    assert not isinstance(
        InvalidSource(),
        BB84MeasurementSource,
    )

def test_simulated_timetagger_explicitly_implements_protocol():
    assert issubclass(
        SimulatedTimetagger,
        BB84MeasurementSource,
    )