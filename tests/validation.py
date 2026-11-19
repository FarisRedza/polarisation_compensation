#!/usr/bin/env python3

import argparse
import csv
import os
import subprocess
import sys
import time

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tests' / 'repeated_noise.py'

MODES = (
    'disabled',
    'single',
    'extended',
    'conditional',
)


@dataclass(frozen=True)
class BenchmarkJob:
    seed: int
    case: int
    mode: str

    @property
    def name(self) -> str:
        return f'seed{self.seed}_case{self.case}_{self.mode}'


def is_complete(
    path: Path,
    repetitions: int,
) -> bool:
    if not path.is_file():
        return False

    try:
        with path.open(newline='') as file:
            rows = list(csv.DictReader(file))

        return len(rows) == repetitions

    except (OSError, csv.Error):
        return False


def run_job(
    job: BenchmarkJob,
    output_dir: Path,
    repetitions: int,
    noise_seed: int,
    timeout: float,
    threshold: float,
) -> None:
    output = output_dir / f'{job.name}.csv'
    temporary = output_dir / f'{job.name}.tmp.csv'
    temporary.unlink(missing_ok=True)

    command = [
        sys.executable,
        str(SCRIPT),
        str(job.case),
        '--cases', '100',
        '--seed', str(job.seed),
        '--repetitions', str(repetitions),
        '--noise-seed', str(noise_seed),
        '--timeout', str(timeout),
        '--line-search-mode', job.mode,
        '--line-search-min-relative-improvement',
        str(threshold),
        '--output', str(temporary),
    ]

    # Avoid excessive nested CPU parallelism from NumPy/BLAS.
    env = os.environ.copy()

    for name in (
        'OMP_NUM_THREADS',
        'OPENBLAS_NUM_THREADS',
        'MKL_NUM_THREADS',
        'NUMEXPR_NUM_THREADS',
        'BLIS_NUM_THREADS',
    ):
        env[name] = '1'

    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f'{job.name} failed:\n'
            f'{result.stdout}\n'
            f'{result.stderr}'
        )

    if not is_complete(temporary, repetitions):
        raise RuntimeError(
            f'{job.name} produced incomplete results'
        )

    # Only publish the CSV once the job has completed.
    temporary.replace(output)


def format_duration(seconds: float) -> str:
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)

    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Parallel compensation validation'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=max(1, (os.cpu_count() or 2) // 2),
    )

    parser.add_argument(
        '--seeds',
        type=int,
        nargs='+',
        default=[10, 11, 12],
    )

    parser.add_argument(
        '--cases',
        type=int,
        default=100,
    )

    parser.add_argument(
        '--repetitions',
        type=int,
        default=5,
    )

    parser.add_argument(
        '--noise-seed',
        type=int,
        default=2000,
    )

    parser.add_argument(
        '--timeout',
        type=float,
        default=120.0,
    )

    parser.add_argument(
        '--threshold',
        type=float,
        default=0.2,
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=ROOT / 'results' / 'independent_validation',
    )

    args = parser.parse_args()

    if args.workers < 1:
        parser.error('--workers must be positive')

    if not 1 <= args.cases <= 100:
        parser.error('--cases must be between 1 and 100')

    if args.repetitions < 1:
        parser.error('--repetitions must be positive')

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    jobs = [
        BenchmarkJob(seed, case, mode)
        for seed in args.seeds
        for case in range(1, args.cases + 1)
        for mode in MODES
    ]

    pending = [
        job for job in jobs
        if not is_complete(
            output_dir / f'{job.name}.csv',
            args.repetitions,
        )
    ]

    skipped = len(jobs) - len(pending)

    print(f'Workers:        {args.workers}')
    print(f'Total jobs:     {len(jobs)}')
    print(f'Total runs:     {len(jobs) * args.repetitions}')
    print(f'Existing jobs:  {skipped}')
    print(f'Pending jobs:   {len(pending)}')
    print(f'Output:         {output_dir}')
    print()

    if not pending:
        print('All jobs already completed.')
        return

    start = time.monotonic()
    completed = 0
    failed = 0

    with ThreadPoolExecutor(
        max_workers=args.workers,
    ) as executor:

        futures = {
            executor.submit(
                run_job,
                job,
                output_dir,
                args.repetitions,
                args.noise_seed,
                args.timeout,
                args.threshold,
            ): job
            for job in pending
        }

        for future in as_completed(futures):
            job = futures[future]

            try:
                future.result()

            except Exception as error:
                failed += 1
                print(f'\nERROR: {error}', flush=True)

            completed += 1

            elapsed = time.monotonic() - start
            remaining = len(pending) - completed
            eta = elapsed / completed * remaining

            percentage = (
                100 * (completed + skipped) / len(jobs)
            )

            print(
                f'[{completed + skipped}/{len(jobs)}] '
                f'{percentage:5.1f}% | '
                f'{job.name:35s} | '
                f'Elapsed: {format_duration(elapsed)} | '
                f'ETA: {format_duration(eta)} | '
                f'Failed: {failed}',
                flush=True,
            )

    print()
    print(f'Successful jobs: {completed - failed + skipped}')
    print(f'Failed jobs:     {failed}')
    print(f'Total time:      {format_duration(time.monotonic() - start)}')

    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()