import dataclasses
import typing

import qtoolkit


@dataclasses.dataclass(frozen=True)
class AggregatedBB84Measurement:
    """BB84 error metrics calculated from combined coincidences."""

    qber: float
    qx: float

    counts: typing.Optional[
        qtoolkit.timetags.MeasurementCounts
    ] = None


@dataclasses.dataclass(frozen=True)
class Observation:
    """BB84 metrics observed during a compensation measurement."""

    qber: float
    qx: float
    score: float

    counts: typing.Optional[
        qtoolkit.timetags.MeasurementCounts
    ] = None


def make_observation(
    *,
    qber: float,
    qx: float,
    score: float,
    counts: typing.Optional[
        qtoolkit.timetags.MeasurementCounts
    ] = None,
) -> Observation:
    """Construct an immutable compensation observation."""

    return Observation(
        qber=qber,
        qx=qx,
        score=score,
        counts=counts,
    )

def aggregate_bb84_measurements(
    *,
    results: typing.Sequence[typing.Any],
    z_pairs: typing.Any,
    x_pairs: typing.Any,
) -> AggregatedBB84Measurement:
    """Aggregate compatible BB84 measurements using qtoolkit."""

    if not results:
        raise ValueError(
            'Cannot aggregate an empty collection of measurements.'
        )

    counts = []

    for index, result in enumerate(results):
        if result.counts is None:
            raise ValueError(
                f'Measurement {index} has no MeasurementCounts.'
            )

        counts.append(result.counts)

    combined = qtoolkit.timetags.aggregate_measurements(
        counts
    )

    zz = combined.get_basis_metrics(z_pairs)
    xx = combined.get_basis_metrics(x_pairs)

    return AggregatedBB84Measurement(
        qber=zz.qber,
        qx=xx.qber,
        counts=combined,
    )

def measurement_counts_from_result(
        *,
        result: typing.Any,
        coincidence_window_ps: int,
) -> qtoolkit.timetags.MeasurementCounts:
    """Construct immutable qtoolkit counts from detection result."""
    return qtoolkit.timetags.MeasurementCounts(
        singles=result.singles,
        coincidences=result.coincidences,
        duration_s=result.data.duration_s,
        coincidence_window_ps=coincidence_window_ps,
        file_path=result.data.file_path,
    )