"""Tests for BB84 count aggregation, metadata, and simulated acquisition."""

from types import SimpleNamespace

import numpy as np
import pytest
import qtoolkit

from polcomp import measurement, simulation
from polcomp.polcomp import BB84DetectionResult


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
        first=first,
        second=second,
    )


@pytest.fixture
def pairs(measurements):
    return tuple(
        pair.as_tuple()
        for pair in (*measurements.z_pairs, *measurements.x_pairs)
    )


def make_result(*, singles=None, coincidences=None, duration_s=0.25,
                file_path=None, coincidence_window_ps=None):
    """Create a legacy result, optionally attaching immutable qtoolkit counts."""
    if singles is None:
        singles = {1: 12, 2: 8}
    if coincidences is None:
        coincidences = {(1, 2): 3, (2, 1): 0}

    result = BB84DetectionResult(
        data=SimpleNamespace(duration_s=duration_s, file_path=file_path),
        qber=0.1,
        qx=0.2,
        singles=singles,
        coincidences=coincidences,
    )
    if coincidence_window_ps is None:
        return result

    from dataclasses import replace
    return replace(
        result,
        counts=measurement.measurement_counts_from_result(
            result=result,
            coincidence_window_ps=coincidence_window_ps,
        ),
    )


def counted_result(pairs, values=None, *, singles=None, window=500):
    """Use identical pair keys in every acquisition, including zero counts."""
    if values is None:
        values = {}
    coincidences = {pair: values.get(pair, 0) for pair in pairs}
    if singles is None:
        singles = {channel: 100 for pair in pairs for channel in pair}
    return make_result(
        singles=singles,
        coincidences=coincidences,
        coincidence_window_ps=window,
    )


def aggregate(measurements, *results):
    return measurement.aggregate_bb84_measurements(
        results=results,
        z_pairs=measurements.z_pairs,
        x_pairs=measurements.x_pairs,
    )


def test_single_measurement(measurements, pairs):
    values = {pair: i + 1 for i, pair in enumerate(pairs)}
    result = counted_result(pairs, values)
    actual = aggregate(measurements, result)
    assert actual.qber == pytest.approx(
        qtoolkit.qkd.BasisMetrics.from_coincidences(
            values, measurements.z_pairs,
        ).qber
    )
    assert actual.qx == pytest.approx(
        qtoolkit.qkd.BasisMetrics.from_coincidences(
            values, measurements.x_pairs,
        ).qber
    )


def test_multiple_measurements_sum_counts(measurements, pairs):
    first_values = {pair: i + 1 for i, pair in enumerate(pairs)}
    second_values = {pair: 2 * i + 3 for i, pair in enumerate(pairs)}
    first = counted_result(pairs, first_values)
    second = counted_result(pairs, second_values)
    expected = {pair: first_values[pair] + second_values[pair] for pair in pairs}

    actual = aggregate(measurements, first, second)
    assert actual.qber == pytest.approx(
        qtoolkit.qkd.BasisMetrics.from_coincidences(
            expected, measurements.z_pairs,
        ).qber
    )
    assert actual.qx == pytest.approx(
        qtoolkit.qkd.BasisMetrics.from_coincidences(
            expected, measurements.x_pairs,
        ).qber
    )


def test_unequal_sample_sizes_are_count_weighted(measurements, pairs):
    # In both bases, the first acquisition is entirely erroneous and the
    # second entirely correct. Averaging per-acquisition QBER gives 0.5.
    small = {}
    large = {}
    for basis in (measurements.z_pairs, measurements.x_pairs):
        basis_pairs = [pair.as_tuple() for pair in basis]
        small[basis_pairs[1]] = 1
        large[basis_pairs[0]] = 99

    actual = aggregate(
        measurements,
        counted_result(pairs, small),
        counted_result(pairs, large),
    )
    assert actual.qber == pytest.approx(0.01)
    assert actual.qx == pytest.approx(0.01)


def test_zero_counts_use_qtoolkit_semantics(measurements, pairs):
    actual = aggregate(measurements, counted_result(pairs), counted_result(pairs))
    expected = {pair: 0 for pair in pairs}
    assert actual.qber == qtoolkit.qkd.BasisMetrics.from_coincidences(
        expected, measurements.z_pairs,
    ).qber
    assert actual.qx == qtoolkit.qkd.BasisMetrics.from_coincidences(
        expected, measurements.x_pairs,
    ).qber


def test_aggregation_does_not_modify_inputs(measurements, pairs):
    first = counted_result(pairs, {pairs[0]: 3})
    second = counted_result(pairs, {pairs[1]: 2})
    original_first = dict(first.counts.coincidences)
    original_second = dict(second.counts.coincidences)

    aggregate(measurements, first, second)

    assert dict(first.counts.coincidences) == original_first
    assert dict(second.counts.coincidences) == original_second
    assert first.counts is not second.counts


def test_rejects_different_coincidence_windows(measurements, pairs):
    with pytest.raises(ValueError):
        aggregate(
            measurements,
            counted_result(pairs, window=500),
            counted_result(pairs, window=1000),
        )


def test_rejects_different_singles_channels(measurements, pairs):
    first = counted_result(pairs)
    second = counted_result(pairs, singles={1: 100})
    with pytest.raises(ValueError):
        aggregate(measurements, first, second)


def test_rejects_different_coincidence_pair_keys(measurements, pairs):
    first = counted_result(pairs)
    second = make_result(
        singles=dict(first.singles),
        coincidences={pair: 0 for pair in pairs[:-1]},
        coincidence_window_ps=500,
    )
    with pytest.raises(ValueError):
        aggregate(measurements, first, second)


def test_rejects_missing_counts(measurements, pairs):
    with pytest.raises(ValueError, match="no MeasurementCounts"):
        aggregate(measurements, counted_result(pairs), make_result())


def test_rejects_empty_input(measurements):
    with pytest.raises(ValueError):
        aggregate(measurements)


def test_simulated_timetagger_populates_measurement_counts(measurements):
    data = qtoolkit.timetags.TimetagData(
        timetags=np.array([100, 110, 1000, 1010], dtype=np.int64),
        channels=np.array([1, 5, 3, 7], dtype=np.int8),
        start_ps=0,
        stop_ps=1_000_000_000_000,
    )

    class FakeSource:
        def read(self, duration_s):
            assert duration_s == 1.0
            return data

    timetagger = simulation.SimulatedTimetagger(
        source=FakeSource(), measurements=measurements,
    )
    result = timetagger.measure(duration_s=1.0, coincidence_window_ps=100)

    assert result.counts is not None
    assert dict(result.counts.singles) == result.singles
    assert dict(result.counts.coincidences) == result.coincidences
    assert result.counts.duration_s == pytest.approx(1.0)
    assert result.counts.coincidence_window_ps == 100
    assert result.counts.get_basis_metrics(measurements.z_pairs).qber == result.qber
    assert result.counts.get_basis_metrics(measurements.x_pairs).qber == result.qx


def test_counts_field_is_optional():
    assert make_result().counts is None


def test_conversion_preserves_counts():
    result = make_result()
    counts = measurement.measurement_counts_from_result(
        result=result, coincidence_window_ps=500,
    )
    assert dict(counts.singles) == result.singles
    assert dict(counts.coincidences) == result.coincidences


def test_conversion_preserves_acquisition_metadata(tmp_path):
    path = tmp_path / "measurement.ttbin"
    result = make_result(duration_s=0.75, file_path=path)
    counts = measurement.measurement_counts_from_result(
        result=result, coincidence_window_ps=250,
    )
    assert counts.duration_s == 0.75
    assert counts.coincidence_window_ps == 250
    assert counts.file_path == path
    assert counts.source_file_paths == (path,)


def test_conversion_preserves_unknown_duration():
    result = make_result(duration_s=None)
    counts = measurement.measurement_counts_from_result(
        result=result, coincidence_window_ps=500,
    )
    assert counts.duration_s is None


def test_conversion_copies_input_counts():
    result = make_result()
    counts = measurement.measurement_counts_from_result(
        result=result, coincidence_window_ps=500,
    )
    result.singles[1] = 999
    result.coincidences[(1, 2)] = 999
    assert counts.singles[1] == 12
    assert counts.coincidences[(1, 2)] == 3


def test_converted_counts_are_immutable():
    result = make_result()
    counts = measurement.measurement_counts_from_result(
        result=result, coincidence_window_ps=500,
    )
    with pytest.raises(TypeError):
        counts.singles[1] = 100
    with pytest.raises(TypeError):
        counts.coincidences[(1, 2)] = 100


def test_counts_can_be_attached_without_changing_legacy_fields():
    original = make_result()
    counts = measurement.measurement_counts_from_result(
        result=original, coincidence_window_ps=500,
    )
    from dataclasses import replace
    with_counts = replace(original, counts=counts)
    assert with_counts.counts is counts
    assert with_counts.qber == original.qber
    assert with_counts.qx == original.qx
    assert with_counts.singles == original.singles
    assert with_counts.coincidences == original.coincidences


def test_invalid_coincidence_window_is_rejected():
    with pytest.raises(ValueError):
        measurement.measurement_counts_from_result(
            result=make_result(), coincidence_window_ps=-1,
        )
