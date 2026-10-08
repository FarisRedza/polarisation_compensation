import argparse
import csv
import dataclasses
import math
import pathlib
import statistics
import typing

import numpy as np

from benchmark import (
    BenchmarkResult,
    run_compensation_benchmark,
)


DEFAULT_CASES = 100
DEFAULT_SEED = 42
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_OUTPUT = 'compensation_characterisation.csv'

QWP_RANGE_DEG = (0.0, 180.0)
HWP_RANGE_DEG = (0.0, 90.0)


@dataclasses.dataclass(frozen=True)
class CharacterisationSummary:
    cases: int
    successes: int
    failures: int
    success_rate: float

    median_time_s: typing.Optional[float]
    p90_time_s: typing.Optional[float]
    p95_time_s: typing.Optional[float]
    worst_time_s: typing.Optional[float]

    median_jacobian_iterations: typing.Optional[float]
    p95_jacobian_iterations: typing.Optional[float]
    worst_jacobian_iterations: typing.Optional[int]

    fallback_cases: int
    fallback_case_rate: float
    total_fallbacks: int

    median_motor_travel_deg: typing.Optional[float]
    p95_motor_travel_deg: typing.Optional[float]
    worst_motor_travel_deg: typing.Optional[float]

    max_jacobian_condition: typing.Optional[float]

    wall_clock_runtime_s: float

    def format(self) -> str:
        def value(
            number: typing.Optional[float],
            suffix: str = '',
            decimals: int = 2,
        ) -> str:
            if number is None:
                return '-'

            return f'{number:.{decimals}f}{suffix}'

        return '\n'.join(
            (
                '',
                'Randomised compensation characterisation',
                '-----------------------------------------',
                f'Cases:                       {self.cases}',
                (
                    'Successes:                   '
                    f'{self.successes}'
                ),
                (
                    'Failures:                    '
                    f'{self.failures}'
                ),
                (
                    'Success rate:                '
                    f'{100.0 * self.success_rate:.1f}%'
                ),
                '',
                'Successful-case convergence',
                (
                    '  Median time:               '
                    f'{value(self.median_time_s, " s")}'
                ),
                (
                    '  p90 time:                  '
                    f'{value(self.p90_time_s, " s")}'
                ),
                (
                    '  p95 time:                  '
                    f'{value(self.p95_time_s, " s")}'
                ),
                (
                    '  Worst time:                '
                    f'{value(self.worst_time_s, " s")}'
                ),
                '',
                'Jacobian behaviour',
                (
                    '  Median iterations:         '
                    f'{value(self.median_jacobian_iterations, decimals=1)}'
                ),
                (
                    '  p95 iterations:            '
                    f'{value(self.p95_jacobian_iterations, decimals=1)}'
                ),
                (
                    '  Worst iterations:          '
                    f'{self.worst_jacobian_iterations if self.worst_jacobian_iterations is not None else "-"}'
                ),
                (
                    '  Cases using fallback:      '
                    f'{self.fallback_cases} '
                    f'({100.0 * self.fallback_case_rate:.1f}%)'
                ),
                (
                    '  Total fallbacks:           '
                    f'{self.total_fallbacks}'
                ),
                (
                    '  Max condition observed:    '
                    f'{value(self.max_jacobian_condition)}'
                ),
                '',
                'Motor travel',
                (
                    '  Median:                    '
                    f'{value(self.median_motor_travel_deg, " deg")}'
                ),
                (
                    '  p95:                       '
                    f'{value(self.p95_motor_travel_deg, " deg")}'
                ),
                (
                    '  Worst:                     '
                    f'{value(self.worst_motor_travel_deg, " deg")}'
                ),
                '',
                (
                    'Wall-clock runtime:           '
                    f'{self.wall_clock_runtime_s:.2f} s'
                ),
            )
        )


def percentile(
    values: typing.Sequence[float],
    q: float,
) -> typing.Optional[float]:
    if not values:
        return None

    return float(
        np.percentile(
            np.asarray(values, dtype=float),
            q,
        )
    )


def finite_max(
    values: typing.Iterable[typing.Optional[float]],
) -> typing.Optional[float]:
    finite = [
        value
        for value in values
        if value is not None
        and math.isfinite(value)
    ]

    if not finite:
        return None

    return max(finite)


def generate_disturbances(
    *,
    cases: int,
    seed: int,
) -> list[tuple[float, float, float]]:
    """Generate reproducible random QWP-HWP-QWP disturbances.

    One complete optical period is sampled for each plate:
    QWP1/QWP2 in [0, 180) degrees and HWP in [0, 90) degrees.
    """

    if cases <= 0:
        raise ValueError(
            'cases must be positive'
        )

    rng = np.random.default_rng(seed)

    qwp1 = rng.uniform(
        *QWP_RANGE_DEG,
        size=cases,
    )
    hwp = rng.uniform(
        *HWP_RANGE_DEG,
        size=cases,
    )
    qwp2 = rng.uniform(
        *QWP_RANGE_DEG,
        size=cases,
    )

    return [
        (
            float(qwp1[index]),
            float(hwp[index]),
            float(qwp2[index]),
        )
        for index in range(cases)
    ]


def result_to_row(
    *,
    case: int,
    measurement_seed: int,
    result: BenchmarkResult,
) -> dict[str, typing.Any]:
    return {
        'case': case,
        'measurement_seed': measurement_seed,
        'dist_qwp1_deg': result.disturbance[0],
        'dist_hwp_deg': result.disturbance[1],
        'dist_qwp2_deg': result.disturbance[2],
        'success': result.completed,
        'elapsed_s': result.elapsed_s,
        'wall_clock_runtime_s': (
            result.wall_clock_runtime_s
        ),
        'initial_qber': result.initial_qber,
        'initial_qx': result.initial_qx,
        'initial_search_rms': (
            result.initial_search_score
        ),
        'final_qber': result.final_qber,
        'final_qx': result.final_qx,
        'final_search_rms': (
            result.final_search_score
        ),
        'final_acceptance_score': (
            result.final_acceptance_score
        ),
        'jacobian_iterations': (
            result.jacobian_iterations
        ),
        'jacobian_fallback_count': (
            result.jacobian_fallback_count
        ),
        'max_jacobian_condition': (
            result.max_jacobian_condition
        ),
        'final_qwp1_deg': (
            result.final_positions[0]
        ),
        'final_hwp_deg': (
            result.final_positions[1]
        ),
        'final_qwp2_deg': (
            result.final_positions[2]
        ),
        'total_motor_travel_deg': (
            result.total_motor_travel_deg
        ),
    }


def write_csv(
    *,
    path: pathlib.Path,
    rows: typing.Sequence[
        dict[str, typing.Any]
    ],
) -> None:
    if not rows:
        return

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        'w',
        newline='',
        encoding='utf-8',
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)


def summarise(
    results: typing.Sequence[BenchmarkResult],
) -> CharacterisationSummary:
    successful = [
        result
        for result in results
        if result.completed
    ]

    successful_times = [
        result.elapsed_s
        for result in successful
    ]
    successful_iterations = [
        result.jacobian_iterations
        for result in successful
    ]
    successful_travel = [
        result.total_motor_travel_deg
        for result in successful
    ]

    fallback_cases = sum(
        result.jacobian_fallback_count > 0
        for result in results
    )
    total_fallbacks = sum(
        result.jacobian_fallback_count
        for result in results
    )

    cases = len(results)
    successes = len(successful)

    return CharacterisationSummary(
        cases=cases,
        successes=successes,
        failures=cases - successes,
        success_rate=(
            successes / cases
            if cases
            else 0.0
        ),
        median_time_s=(
            statistics.median(successful_times)
            if successful_times
            else None
        ),
        p90_time_s=percentile(
            successful_times,
            90,
        ),
        p95_time_s=percentile(
            successful_times,
            95,
        ),
        worst_time_s=(
            max(successful_times)
            if successful_times
            else None
        ),
        median_jacobian_iterations=(
            statistics.median(
                successful_iterations
            )
            if successful_iterations
            else None
        ),
        p95_jacobian_iterations=percentile(
            successful_iterations,
            95,
        ),
        worst_jacobian_iterations=(
            max(successful_iterations)
            if successful_iterations
            else None
        ),
        fallback_cases=fallback_cases,
        fallback_case_rate=(
            fallback_cases / cases
            if cases
            else 0.0
        ),
        total_fallbacks=total_fallbacks,
        median_motor_travel_deg=(
            statistics.median(
                successful_travel
            )
            if successful_travel
            else None
        ),
        p95_motor_travel_deg=percentile(
            successful_travel,
            95,
        ),
        worst_motor_travel_deg=(
            max(successful_travel)
            if successful_travel
            else None
        ),
        max_jacobian_condition=finite_max(
            result.max_jacobian_condition
            for result in results
        ),
        wall_clock_runtime_s=sum(
            result.wall_clock_runtime_s
            for result in results
        ),
    )


def run_characterisation(
    *,
    cases: int,
    seed: int,
    timeout_s: float,
    output: pathlib.Path,
) -> CharacterisationSummary:
    disturbances = generate_disturbances(
        cases=cases,
        seed=seed,
    )

    # Give every case its own deterministic measurement RNG stream.  This
    # avoids every disturbance seeing exactly the same random photon sequence
    # while keeping the complete suite reproducible from one master seed.
    seed_sequence = np.random.SeedSequence(
        seed
    )
    child_sequences = seed_sequence.spawn(
        cases
    )
    measurement_seeds = [
        int(
            child.generate_state(
                1,
                dtype=np.uint32,
            )[0]
        )
        for child in child_sequences
    ]

    results: list[BenchmarkResult] = []
    rows: list[dict[str, typing.Any]] = []

    print(
        'Running '
        f'{cases} randomised compensation cases '
        f'(seed={seed})'
    )

    for index, (
        disturbance,
        measurement_seed,
    ) in enumerate(
        zip(
            disturbances,
            measurement_seeds,
        ),
        start=1,
    ):
        result = run_compensation_benchmark(
            disturbance=disturbance,
            seed=measurement_seed,
            timeout_s=timeout_s,
            simulated_time=True,
        )

        results.append(
            result
        )
        rows.append(
            result_to_row(
                case=index,
                measurement_seed=measurement_seed,
                result=result,
            )
        )

        outcome = (
            'PASS'
            if result.completed
            else 'TIMEOUT'
        )

        print(
            f'[{index:3d}/{cases}] '
            f'{outcome:7s} '
            f't={result.elapsed_s:6.1f}s '
            f'J={result.jacobian_iterations:2d} '
            f'fallbacks={result.jacobian_fallback_count:2d} '
            'dist=('
            f'{disturbance[0]:7.2f}, '
            f'{disturbance[1]:7.2f}, '
            f'{disturbance[2]:7.2f}'
            ')'
        )

    write_csv(
        path=output,
        rows=rows,
    )

    summary = summarise(
        results
    )

    print(
        summary.format()
    )
    print(
        f'\nCSV written to: {output}'
    )

    failures = [
        (index, result)
        for index, result in enumerate(
            results,
            start=1,
        )
        if not result.completed
    ]

    if failures:
        print(
            '\nFailed / timed-out cases'
        )
        print(
            '------------------------'
        )

        for index, result in failures:
            print(
                f'Case {index}: '
                'disturbance=('
                f'{result.disturbance[0]:.6f}, '
                f'{result.disturbance[1]:.6f}, '
                f'{result.disturbance[2]:.6f}'
                '), '
                f'seed={measurement_seeds[index - 1]}, '
                f'RMS={result.final_search_score:.3f}, '
                'acceptance='
                f'{result.final_acceptance_score:.3f}, '
                'J='
                f'{result.jacobian_iterations}, '
                'fallbacks='
                f'{result.jacobian_fallback_count}'
            )

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Characterise the polarisation compensation '
            'controller over reproducible random disturbances.'
        )
    )

    parser.add_argument(
        '--cases',
        type=int,
        default=DEFAULT_CASES,
        help=(
            'Number of random disturbances '
            f'(default: {DEFAULT_CASES}).'
        ),
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=DEFAULT_SEED,
        help=(
            'Master RNG seed '
            f'(default: {DEFAULT_SEED}).'
        ),
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help=(
            'Simulated timeout per case in seconds '
            f'(default: {DEFAULT_TIMEOUT_S:g}).'
        ),
    )
    parser.add_argument(
        '--output',
        type=pathlib.Path,
        default=pathlib.Path(
            DEFAULT_OUTPUT
        ),
        help=(
            'CSV output path '
            f'(default: {DEFAULT_OUTPUT}).'
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_characterisation(
        cases=args.cases,
        seed=args.seed,
        timeout_s=args.timeout,
        output=args.output,
    )


if __name__ == '__main__':
    main()
