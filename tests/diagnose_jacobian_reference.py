"""Collect full trajectories and Jacobian estimates for selected cases."""
import argparse
import dataclasses
import gzip
import json
from pathlib import Path

from benchmark import run_compensation_benchmark
from diagnose_compensation import generate_cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', nargs='+', type=int, default=[4, 9, 32])
    parser.add_argument('--modes', nargs='+', choices=['empirical', 'ideal_fd', 'analytical'], default=['empirical', 'ideal_fd', 'analytical'])
    parser.add_argument('--repetitions', type=int, default=5)
    parser.add_argument('--line-search-mode', choices=['extended', 'backtracking'], default='extended')
    parser.add_argument('--skip-probe-cost', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('results/jacobian_diagnostics'))
    parser.add_argument("--rejection-limit", type=int, default=0)
    parser.add_argument("--cauchy-recovery", action="store_true")
    args = parser.parse_args()
    if args.rejection_limit < 0:
        parser.error("--rejection-limit must be non-negative")
    if args.skip_probe_cost and 'empirical' in args.modes:
        parser.error('Empirical mode requires probes')
    if args.repetitions < 1 or any(not 1 <= c <= 100 for c in args.cases):
        parser.error('Invalid cases or repetitions')
    args.output.mkdir(parents=True, exist_ok=True)
    cases = generate_cases(cases=100, seed=42)
    for case in args.cases:
        disturbance, _ = cases[case - 1]
        for mode in args.modes:
            for seed in range(1000, 1000 + args.repetitions):
                diagnostics = []
                result = run_compensation_benchmark(
                    disturbance=disturbance, seed=seed, timeout_s=120,
                    simulated_time=True, line_search_mode=args.line_search_mode,
                    rejection_limit=args.rejection_limit,
                    cauchy_recovery=args.cauchy_recovery,
                    jacobian_mode=mode, retain_probe_cost=not args.skip_probe_cost,
                    jacobian_diagnostics=diagnostics,
                )
                suffix = '_no_probe' if args.skip_probe_cost else ''
                path = args.output / f'case{case}_{mode}{suffix}_{seed}.json.gz'
                temporary = path.with_suffix('.tmp')
                with gzip.open(temporary, 'wt') as file:
                    json.dump({'case': case, 'case_seed': 42, 'mode': mode,
                               'retain_probe_cost': not args.skip_probe_cost,
                               'line_search_mode': args.line_search_mode,
                               'rejection_limit': args.rejection_limit,
                               'cauchy_recovery': args.cauchy_recovery,
                               'jacobians': diagnostics,
                               'result': dataclasses.asdict(result)}, file,
                              default=lambda value: value.item() if hasattr(value, 'item') else value.tolist())
                temporary.replace(path)
                print(f'{path.name}: {result.completed}, {result.elapsed_s:.1f}s', flush=True)


if __name__ == '__main__':
    main()
