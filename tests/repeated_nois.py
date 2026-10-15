import argparse
import csv
import pathlib

import numpy as np

from benchmark import run_compensation_benchmark
from diagnose_compensation import generate_cases


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            'Repeat a compensation case with independent '
            'measurement-noise realizations.'
        )
    )

    parser.add_argument('case', type=int)
    parser.add_argument('--cases', type=int, default=100)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--repetitions', type=int, default=20)
    parser.add_argument('--noise-seed', type=int, default=1000)
    parser.add_argument('--timeout', type=float, default=120.0)
    parser.add_argument(
        '--experimental-line-search',
        action='store_true',
    )
    parser.add_argument(
        '--output',
        type=pathlib.Path,
        default=pathlib.Path('repeated_noise.csv'),
    )

    args = parser.parse_args()

    if not 1 <= args.case <= args.cases:
        parser.error('case must be between 1 and --cases')

    if args.repetitions <= 0:
        parser.error('--repetitions must be positive')

    disturbance, _ = generate_cases(
        cases=args.cases,
        seed=args.seed,
    )[args.case - 1]

    rows = []

    for repetition in range(args.repetitions):
        measurement_seed = args.noise_seed + repetition

        result = run_compensation_benchmark(
            disturbance=disturbance,
            seed=measurement_seed,
            timeout_s=args.timeout,
            simulated_time=True,
            experimental_line_search=(
                args.experimental_line_search
            ),
        )

        rows.append({
            'case_seed': args.seed,
            'case': args.case,
            'repetition': repetition,
            'measurement_seed': measurement_seed,
            'disturbance_qwp1': disturbance[0],
            'disturbance_hwp': disturbance[1],
            'disturbance_qwp2': disturbance[2],
            'completed': result.completed,
            'elapsed_s': result.elapsed_s,
            'final_qber': result.final_qber,
            'final_qx': result.final_qx,
            'jacobian_iterations': result.jacobian_iterations,
            'fallback_count': result.jacobian_fallback_count,
            'motor_travel_deg': result.total_motor_travel_deg,
        })

        print(
            f'{repetition + 1:3d}/{args.repetitions}: '
            f'seed={measurement_seed}, '
            f'completed={result.completed}, '
            f'elapsed={result.elapsed_s:.1f}s'
        )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.output.open(
        'w',
        newline='',
        encoding='utf-8',
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)

    successful = [
        row['elapsed_s']
        for row in rows
        if row['completed']
    ]

    print()
    print(
        f'Success rate: '
        f'{len(successful)}/{args.repetitions} '
        f'({len(successful) / args.repetitions:.1%})'
    )

    if successful:
        print(
            'Median successful time: '
            f'{np.median(successful):.1f}s'
        )

    print(f'Results: {args.output}')


if __name__ == '__main__':
    main()