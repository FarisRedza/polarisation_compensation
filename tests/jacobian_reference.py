#!/usr/bin/env python3
"""Run the five Jacobian reference configurations from the project tests directory."""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tests' / 'repeated_noise.py'
CONFIGS = {
    'empirical': ('empirical', False),
    'ideal_fd': ('ideal_fd', False),
    'analytical': ('analytical', False),
    'ideal_fd_no_probe': ('ideal_fd', True),
    'analytical_no_probe': ('analytical', True),
}


def complete(path, case, seed, noise_seed, repetitions):
    try:
        with path.open(newline='') as f:
            rows = list(csv.DictReader(f))
        return (len(rows) == repetitions and
                {(int(r['case_seed']), int(r['case']), int(r['repetition']),
                  int(r['measurement_seed'])) for r in rows} ==
                {(seed, case, i, noise_seed + i) for i in range(repetitions)} and
                all(r['completed'] in ('True', 'False') and
                    all(r[k] not in (None, '') for k in (
                        'elapsed_s', 'final_qber', 'final_qx',
                        'motor_travel_deg', 'jacobian_iterations', 'fallback_count'))
                    for r in rows))
    except (OSError, csv.Error, KeyError, ValueError, TypeError):
        return False


def run_job(case, name, args, env):
    mode, skip = CONFIGS[name]
    output = args.output / f'seed{args.seed}_case{case:03d}_{name}.csv'
    temporary = output.with_suffix('.tmp.csv')
    temporary.unlink(missing_ok=True)
    cmd = [sys.executable, str(SCRIPT), str(case), '--cases', '100',
           '--seed', str(args.seed), '--repetitions', str(args.repetitions),
           '--noise-seed', str(args.noise_seed), '--timeout', str(args.timeout),
           '--line-search-mode', 'extended', '--jacobian-mode', mode,
           '--output', str(temporary)]
    if skip:
        cmd.append('--skip-probe-cost')
    result = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    if result.returncode or not complete(temporary, case, args.seed,
                                         args.noise_seed, args.repetitions):
        output.with_suffix('.error.log').write_text(result.stdout + '\n' + result.stderr)
        raise RuntimeError(f'{output.name}: failed or incomplete; see error log')
    temporary.replace(output)
    output.with_suffix('.error.log').unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--cases', type=int, default=100)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--noise-seed', type=int, default=1000)
    parser.add_argument('--repetitions', type=int, default=5)
    parser.add_argument('--timeout', type=float, default=120.0)
    parser.add_argument('--output', type=Path, default=ROOT / 'results/jacobian_reference')
    args = parser.parse_args()
    if not 1 <= args.cases <= 100 or min(args.workers, args.repetitions) < 1 or args.timeout <= 0:
        parser.error('invalid cases, workers, repetitions or timeout')
    if not SCRIPT.is_file():
        parser.error('place this script in the project tests directory')
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / 'benchmark.json'
    settings = dict(seed=args.seed, noise_seed=args.noise_seed, repetitions=args.repetitions,
                    timeout=args.timeout, disturbance_pool=100, line_search='extended',
                    configurations={k: list(v) for k, v in CONFIGS.items()})
    if manifest.exists():
        if json.loads(manifest.read_text()) != settings:
            parser.error('output directory contains different benchmark settings')
    else:
        if any(args.output.glob('*.csv')):
            parser.error('existing CSV files without manifest; use a fresh output directory')
        manifest.write_text(json.dumps(settings, indent=2) + '\n')
    jobs = [(c, n) for c in range(1, args.cases + 1) for n in CONFIGS]
    pending = [(c, n) for c, n in jobs if not complete(
        args.output / f'seed{args.seed}_case{c:03d}_{n}.csv', c, args.seed,
        args.noise_seed, args.repetitions)]
    skipped = len(jobs) - len(pending)
    print(f'{len(jobs)} jobs / {len(jobs)*args.repetitions} simulations; '
          f'{skipped} already complete; {args.workers} workers', flush=True)
    env = os.environ.copy()
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
        env[key] = '1'
    start = time.monotonic()
    failed = 0
    executor = ThreadPoolExecutor(max_workers=args.workers)
    try:
        futures = {executor.submit(run_job, c, n, args, env): (c, n) for c, n in pending}
        for i, future in enumerate(as_completed(futures), 1):
            c, n = futures[future]
            try:
                future.result()
            except Exception as exc:
                failed += 1
                print(f'ERROR: {exc}', flush=True)
            elapsed = time.monotonic() - start
            eta = elapsed / i * (len(pending) - i)
            print(f'[{skipped+i}/{len(jobs)}] case={c:03d} {n:24s} '
                  f'elapsed={elapsed/60:.1f} min ETA={eta/60:.1f} min failed={failed}', flush=True)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    print(f'Finished: {len(jobs)-failed} complete, {failed} failed')
    return int(failed > 0)


if __name__ == '__main__':
    sys.exit(main())
