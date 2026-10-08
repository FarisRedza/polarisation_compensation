"""Tests for coincidence aggregation without motors or acquisition hardware."""

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from polcomp import measurement


Z_PAIRS = object()
X_PAIRS = object()


@dataclass(frozen=True)
class Sample:
    coincidences: dict[tuple[int, int], int]


@pytest.fixture
def basis_metrics_stub(monkeypatch):
    """Record the exact counts passed to each qtoolkit basis calculation."""
    calls = []

    class FakeBasisMetrics:
        @staticmethod
        def from_coincidences(*, coincidences, pairs):
            calls.append((dict(coincidences), pairs))
            # An intentionally count-weighted metric, with distinct Z/X pairs.
            if pairs is Z_PAIRS:
                correct, error = (0, 0), (0, 1)
            elif pairs is X_PAIRS:
                correct, error = (1, 0), (1, 1)
            else:
                raise AssertionError("Unexpected basis pairs")
            total = coincidences.get(correct, 0) + coincidences.get(error, 0)
            return SimpleNamespace(qber=coincidences.get(error, 0) / total if total else float("nan"))

    monkeypatch.setattr(measurement.qtoolkit.qkd, "BasisMetrics", FakeBasisMetrics)
    return calls


def aggregate(*samples):
    return measurement.aggregate_bb84_measurements(
        results=samples, z_pairs=Z_PAIRS, x_pairs=X_PAIRS
    )


def test_single_measurement(basis_metrics_stub):
    counts = {(0, 0): 90, (0, 1): 10, (1, 0): 80, (1, 1): 20}
    result = aggregate(Sample(counts))

    assert result.qber == pytest.approx(0.1)
    assert result.qx == pytest.approx(0.2)
    assert basis_metrics_stub == [(counts, Z_PAIRS), (counts, X_PAIRS)]


def test_multiple_measurements_sum_coincidences(basis_metrics_stub):
    first = Sample({(0, 0): 8, (0, 1): 2, (1, 0): 7})
    second = Sample({(0, 0): 12, (1, 0): 9, (1, 1): 4})

    result = aggregate(first, second)
    expected = {(0, 0): 20, (0, 1): 2, (1, 0): 16, (1, 1): 4}

    assert basis_metrics_stub == [(expected, Z_PAIRS), (expected, X_PAIRS)]
    assert result.qber == pytest.approx(2 / 22)
    assert result.qx == pytest.approx(4 / 20)


def test_unequal_sample_sizes_are_count_weighted(basis_metrics_stub):
    # The per-acquisition Z error rates are 1.0 and 0.0.
    # Averaging them would incorrectly give 0.5 instead of 0.01.
    small = Sample({(0, 1): 1, (1, 1): 1})
    large = Sample({(0, 0): 99, (1, 0): 99})

    result = aggregate(small, large)

    assert result.qber == pytest.approx(0.01)
    assert result.qx == pytest.approx(0.01)


def test_zero_counts_are_forwarded_unchanged(basis_metrics_stub):
    # Do not impose new zero-count semantics; leave those to qtoolkit.
    result = aggregate(Sample({(0, 0): 0}), Sample({}))

    assert basis_metrics_stub == [({(0, 0): 0}, Z_PAIRS), ({(0, 0): 0}, X_PAIRS)]
    assert result.qber != result.qber  # NaN from this test stub
    assert result.qx != result.qx


def test_inputs_are_not_modified(basis_metrics_stub):
    first = Sample({(0, 0): 3, (0, 1): 1})
    second = Sample({(0, 0): 5, (1, 1): 2})
    before_first = first.coincidences.copy()
    before_second = second.coincidences.copy()

    aggregate(first, second)

    assert first.coincidences == before_first
    assert second.coincidences == before_second
    assert first.coincidences is not second.coincidences

"""
Tests for the optional qtoolkit MeasurementCounts integration.
Will eventually be integrated properly.
"""

from types import SimpleNamespace

import pytest

from polcomp.measurement import measurement_counts_from_result
from polcomp.polcomp import BB84DetectionResult


def make_result(*, singles=None, coincidences=None, duration_s=0.25, file_path=None):
    if singles is None:
        singles = {1: 12, 2: 8}
    if coincidences is None:
        coincidences = {(1, 2): 3, (2, 1): 0}

    # Only duration_s and file_path are used by the conversion helper.
    # A full TimetagData instance is unnecessary for this unit test.
    data = SimpleNamespace(duration_s=duration_s, file_path=file_path)
    return BB84DetectionResult(
        data=data,
        qber=0.1,
        qx=0.2,
        singles=singles,
        coincidences=coincidences,
    )


def test_counts_field_is_optional():
    result = make_result()
    assert result.counts is None


def test_conversion_preserves_counts():
    result = make_result()
    counts = measurement_counts_from_result(
        result=result,
        coincidence_window_ps=500,
    )

    assert dict(counts.singles) == result.singles
    assert dict(counts.coincidences) == result.coincidences


def test_conversion_preserves_acquisition_metadata(tmp_path):
    path = tmp_path / "measurement.ttbin"
    result = make_result(duration_s=0.75, file_path=path)

    counts = measurement_counts_from_result(
        result=result,
        coincidence_window_ps=250,
    )

    assert counts.duration_s == 0.75
    assert counts.coincidence_window_ps == 250
    assert counts.file_path == path
    assert counts.source_file_paths == (path,)


def test_conversion_preserves_unknown_duration():
    result = make_result(duration_s=None)
    counts = measurement_counts_from_result(
        result=result,
        coincidence_window_ps=500,
    )
    assert counts.duration_s is None


def test_conversion_copies_input_counts():
    result = make_result()
    counts = measurement_counts_from_result(
        result=result,
        coincidence_window_ps=500,
    )

    result.singles[1] = 999
    result.coincidences[(1, 2)] = 999

    assert counts.singles[1] == 12
    assert counts.coincidences[(1, 2)] == 3


def test_converted_counts_are_immutable():
    result = make_result()
    counts = measurement_counts_from_result(
        result=result,
        coincidence_window_ps=500,
    )

    with pytest.raises(TypeError):
        counts.singles[1] = 100

    with pytest.raises(TypeError):
        counts.coincidences[(1, 2)] = 100


def test_counts_can_be_attached_without_changing_legacy_fields():
    original = make_result()
    counts = measurement_counts_from_result(
        result=original,
        coincidence_window_ps=500,
    )

    with_counts = BB84DetectionResult(
        data=original.data,
        qber=original.qber,
        qx=original.qx,
        singles=original.singles,
        coincidences=original.coincidences,
        counts=counts,
    )

    assert with_counts.counts is counts
    assert with_counts.qber == original.qber
    assert with_counts.qx == original.qx
    assert with_counts.singles == original.singles
    assert with_counts.coincidences == original.coincidences


def test_invalid_coincidence_window_is_rejected():
    result = make_result()
    with pytest.raises(ValueError):
        measurement_counts_from_result(
            result=result,
            coincidence_window_ps=-1,
        )
