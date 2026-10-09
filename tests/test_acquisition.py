"""Tests for the BB84 acquisition interface and simulated backend."""

import numpy as np
import pytest
import qtoolkit

from polcomp.acquisition import BB84MeasurementSource
from polcomp.measurement import aggregate_bb84_measurements
from polcomp.polcomp import BB84DetectionResult
from polcomp.simulation import SimulatedTimetagger
from polcomp.acquisition import (
    BB84MeasurementSource,
    BB84TimetagAcquisition,
    TimetagSource,
)


def test_simulated_timetagger_implements_protocol():
    assert issubclass(SimulatedTimetagger, BB84MeasurementSource)


def test_protocol_accepts_compatible_source():
    class CompatibleSource:
        def measure(self, duration_s: float, coincidence_window_ps: int):
            return None

    # Runtime protocols check attribute presence, not type signatures.
    assert isinstance(CompatibleSource(), BB84MeasurementSource)


def test_protocol_rejects_missing_measure_method():
    class InvalidSource:
        pass

    assert not isinstance(InvalidSource(), BB84MeasurementSource)


@pytest.fixture
def measurements():
    first = qtoolkit.polarisation.BB84Measurement(
        channels=qtoolkit.polarisation.PolarisationChannelMap(
            h=1, v=2, d=3, a=4,
        ),
    )
    second = qtoolkit.polarisation.BB84Measurement(
        channels=qtoolkit.polarisation.PolarisationChannelMap(
            h=5, v=6, d=7, a=8,
        ),
    )
    return qtoolkit.polarisation.BB84MeasurementPair(
        first=first, second=second,
    )


@pytest.fixture
def deterministic_timetag_source():
    data = qtoolkit.timetags.TimetagData(
        timetags=np.array([100, 110, 1000, 1010], dtype=np.int64),
        channels=np.array([1, 5, 3, 7], dtype=np.int8),
        start_ps=0,
        stop_ps=1_000_000_000_000,
    )

    class FixedSource:
        def read(self, duration_s: float):
            assert duration_s == 1.0
            return data

    return FixedSource()


def test_simulated_acquisition_aggregates(
    measurements,
    deterministic_timetag_source,
):
    timetagger = SimulatedTimetagger(
        source=deterministic_timetag_source,
        measurements=measurements,
    )
    result = timetagger.measure(
        duration_s=1.0,
        coincidence_window_ps=100,
    )

    assert isinstance(result, BB84DetectionResult)
    assert result.counts is not None
    assert result.counts.duration_s == pytest.approx(result.data.duration_s)
    assert result.counts.coincidence_window_ps == 100

    aggregated = aggregate_bb84_measurements(
        results=[result],
        z_pairs=measurements.z_pairs,
        x_pairs=measurements.x_pairs,
    )
    assert aggregated.counts is not None
    assert aggregated.qber == pytest.approx(result.qber)
    assert aggregated.qx == pytest.approx(result.qx)
    assert dict(aggregated.counts.singles) == result.singles
    assert dict(aggregated.counts.coincidences) == result.coincidences

def test_generic_acquisition_implements_protocol():
    assert issubclass(
        BB84TimetagAcquisition,
        BB84MeasurementSource,
    )

def test_simulated_timetagger_uses_generic_acquisition():
    assert issubclass(
        SimulatedTimetagger,
        BB84TimetagAcquisition,
    )

def test_generic_acquisition(
    measurements,
    deterministic_timetag_source,
):
    acquisition = BB84TimetagAcquisition(
        source=deterministic_timetag_source,
        measurements=measurements,
    )

    result = acquisition.measure(
        duration_s=1.0,
        coincidence_window_ps=100,
    )

    assert isinstance(result, BB84DetectionResult)
    assert result.counts is not None

    assert dict(result.counts.singles) == result.singles
    assert dict(result.counts.coincidences) == result.coincidences

    assert result.counts.duration_s == pytest.approx(1.0)
    assert result.counts.coincidence_window_ps == 100

    assert (
        result.counts.get_basis_metrics(
            measurements.z_pairs,
        ).qber
        == result.qber
    )

    assert (
        result.counts.get_basis_metrics(
            measurements.x_pairs,
        ).qber
        == result.qx
    )

def test_generic_and_simulated_acquisition_agree(
    measurements,
    deterministic_timetag_source,
):
    generic = BB84TimetagAcquisition(
        source=deterministic_timetag_source,
        measurements=measurements,
    )

    simulated = SimulatedTimetagger(
        source=deterministic_timetag_source,
        measurements=measurements,
    )

    generic_result = generic.measure(
        duration_s=1.0,
        coincidence_window_ps=100,
    )

    simulated_result = simulated.measure(
        duration_s=1.0,
        coincidence_window_ps=100,
    )

    assert generic_result.qber == simulated_result.qber
    assert generic_result.qx == simulated_result.qx

    assert generic_result.singles == simulated_result.singles
    assert (
        generic_result.coincidences
        == simulated_result.coincidences
    )

    assert (
        generic_result.counts
        is not None
        and simulated_result.counts is not None
    )

    assert (
        dict(generic_result.counts.coincidences)
        == dict(simulated_result.counts.coincidences)
    )