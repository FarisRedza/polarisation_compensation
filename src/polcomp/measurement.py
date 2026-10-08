import dataclasses
import typing

import qtoolkit


@dataclasses.dataclass(frozen=True)
class AggregatedBB84Measurement:
    """BB84 error metrics calculated from combined coincidences."""

    qber: float
    qx: float


def aggregate_bb84_measurements(
        *,
        results: typing.Sequence[typing.Any],
        z_pairs: typing.Any,
        x_pairs: typing.Any,
) -> AggregatedBB84Measurement:
    """Aggregate coincidences and calculate BB84 error metrics."""

    coincidences: dict[tuple[int, int], int] = {}

    for result in results:
        for pair, count in result.coincidences.items():
            coincidences[pair] = (
                coincidences.get(pair, 0) + count
            )

    zz = qtoolkit.qkd.BasisMetrics.from_coincidences(
        coincidences=coincidences,
        pairs=z_pairs,
    )

    xx = qtoolkit.qkd.BasisMetrics.from_coincidences(
        coincidences=coincidences,
        pairs=x_pairs,
    )

    return AggregatedBB84Measurement(
        qber=zz.qber,
        qx=xx.qber,
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