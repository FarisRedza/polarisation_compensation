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
