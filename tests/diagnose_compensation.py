import argparse
import csv
import pathlib
import sys
import typing

import numpy as np

sys.path.append(
    str(
        pathlib.Path(__file__).parent
    )
)

from benchmark import (
    BenchmarkResult,
    BenchmarkSample,
    run_compensation_benchmark,
)


DEFAULT_CASES = 100
DEFAULT_SEED = 42
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_TRACE_DIR = pathlib.Path(
    'compensation_traces'
)

QWP_RANGE_DEG = (0.0, 180.0)
HWP_RANGE_DEG = (0.0, 90.0)


def generate_cases(
    *,
    cases: int,
    seed: int,
) -> list[
    tuple[
        tuple[float, float, float],
        int,
    ]
]:
    """Recreate the exact cases used by the characterisation runner."""

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

    return [
        (
            (
                float(qwp1[index]),
                float(hwp[index]),
                float(qwp2[index]),
            ),
            measurement_seeds[index],
        )
        for index in range(cases)
    ]


def sample_to_row(
    sample: BenchmarkSample,
) -> dict[str, typing.Any]:
    return {
        'elapsed_s': sample.elapsed_s,
        'controller_state': (
            sample.controller_state
        ),
        'search_state': (
            sample.search_state
            if sample.search_state is not None
            else ''
        ),
        'qber': sample.qber,
        'qx': sample.qx,
        'search_rms': sample.search_score,
        'acceptance_score': (
            sample.acceptance_score
        ),
        'jacobian_iteration': (
            sample.jacobian_iteration
        ),
        'jacobian_condition': (
            sample.jacobian_condition
        ),
        'jacobian_fallback_count': (
            sample.jacobian_fallback_count
        ),
        'qwp1_deg': (
            sample.compensation_positions[0]
        ),
        'hwp_deg': (
            sample.compensation_positions[1]
        ),
        'qwp2_deg': (
            sample.compensation_positions[2]
        ),
    }


def write_trace(
    *,
    path: pathlib.Path,
    result: BenchmarkResult,
) -> None:
    rows = [
        sample_to_row(sample)
        for sample in result.samples
    ]

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
            fieldnames=list(
                rows[0].keys()
            ),
        )
        writer.writeheader()
        writer.writerows(rows)


def print_transitions(
    result: BenchmarkResult,
) -> None:
    """Print only meaningful state/Jacobian/fallback transitions."""

    print()
    print('Trajectory transitions')
    print('----------------------')

    previous_key = None

    for sample in result.samples:
        key = (
            sample.controller_state,
            sample.search_state,
            sample.jacobian_iteration,
            sample.jacobian_fallback_count,
        )

        if key == previous_key:
            continue

        condition = (
            f'{sample.jacobian_condition:.2f}'
            if sample.jacobian_condition is not None
            else '-'
        )

        print(
            f't={sample.elapsed_s:6.1f}s '
            f'{sample.controller_state:8s} '
            f'{(sample.search_state or "-"):24s} '
            f'RMS={sample.search_score:6.2f} '
            f'acc={sample.acceptance_score:6.2f} '
            f'J={sample.jacobian_iteration:2d} '
            f'cond={condition:>6s} '
            'fallbacks='
            f'{sample.jacobian_fallback_count:2d} '
            'pos=('
            f'{sample.compensation_positions[0]:7.2f}, '
            f'{sample.compensation_positions[1]:7.2f}, '
            f'{sample.compensation_positions[2]:7.2f}'
            ')'
        )

        previous_key = key


def replay_case(
    *,
    case_number: int,
    cases: int,
    seed: int,
    timeout_s: float,
    trace_dir: pathlib.Path,
) -> None:
    if not 1 <= case_number <= cases:
        raise ValueError(
            f'case must be between 1 and {cases}'
        )

    case_set = generate_cases(
        cases=cases,
        seed=seed,
    )

    disturbance, measurement_seed = (
        case_set[case_number - 1]
    )

    result = run_compensation_benchmark(
        disturbance=disturbance,
        seed=measurement_seed,
        timeout_s=timeout_s,
        simulated_time=True,
    )

    print(result.summary())

    print()
    print(
        'Reproduction parameters'
    )
    print(
        '-----------------------'
    )
    print(
        f'Case:             {case_number}'
    )
    print(
        f'Master seed:      {seed}'
    )
    print(
        'Disturbance:      '
        f'{disturbance}'
    )
    print(
        'Measurement seed: '
        f'{measurement_seed}'
    )

    print_transitions(
        result
    )

    trace_path = (
        trace_dir
        / f'case_{case_number:03d}.csv'
    )

    write_trace(
        path=trace_path,
        result=result,
    )

    print()
    print(
        f'Full trajectory written to: '
        f'{trace_path}'
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Reproduce and inspect one case from the '
            'randomised compensation characterisation.'
        )
    )

    parser.add_argument(
        'case',
        type=int,
        help=(
            '1-based case number from the '
            'characterisation run.'
        ),
    )
    parser.add_argument(
        '--cases',
        type=int,
        default=DEFAULT_CASES,
        help=(
            'Size of the original random suite '
            f'(default: {DEFAULT_CASES}).'
        ),
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=DEFAULT_SEED,
        help=(
            'Master seed used by the original suite '
            f'(default: {DEFAULT_SEED}).'
        ),
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help=(
            'Simulated timeout in seconds '
            f'(default: {DEFAULT_TIMEOUT_S:g}).'
        ),
    )
    parser.add_argument(
        '--trace-dir',
        type=pathlib.Path,
        default=DEFAULT_TRACE_DIR,
        help=(
            'Directory for trajectory CSV files '
            f'(default: {DEFAULT_TRACE_DIR}).'
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    replay_case(
        case_number=args.case,
        cases=args.cases,
        seed=args.seed,
        timeout_s=args.timeout,
        trace_dir=args.trace_dir,
    )


if __name__ == '__main__':
    main()
