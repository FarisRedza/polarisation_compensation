"""Offline optical landscape study; no controller or motor changes."""
import argparse
import csv
import gzip
import itertools
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from qtoolkit.polarisation import QuarterWaveplate, HalfWaveplate, PHI_PLUS
from polcomp.config import PolCompConfig
from polcomp.simulation.jacobian_reference import OpticalJacobianReference, error_probabilities
from polcomp.states.search.jacobian import JacobianSolver
from diagnose_compensation import generate_cases

GRID = (.5, 1., 2., 3.75, 7.5, 15.)
PERIODS = np.array([180., 90., 180.])


def optical_model(disturbance, targets):
    plates = [QuarterWaveplate(), HalfWaveplate(), QuarterWaveplate()] * 1
    plates += [QuarterWaveplate(), HalfWaveplate(), QuarterWaveplate()]
    for p, a in zip(plates, (*disturbance, 0., 0., 0.)):
        p.angle_deg = a
    system = SimpleNamespace(waveplates=[SimpleNamespace(matrix=p.matrix.copy(), waveplate=p) for p in plates],
                             source=SimpleNamespace(state=np.asarray(PHI_PLUS)), compensation_subsystem=0)
    ref = OpticalJacobianReference(system, 'analytical')
    fd = OpticalJacobianReference(system, 'ideal_fd')
    fixed = plates[2].matrix @ plates[1].matrix @ plates[0].matrix @ np.asarray(PHI_PLUS).reshape(2, 2)
    # Cache harmonic coefficients of the exact fixed-retardance plate matrices.
    coefficients = []
    for p in plates[3:]:
        ms = []
        for a in (0., 45., 90.):
            p.angle_deg = a
            ms.append(p.matrix.copy())
        A = (ms[0] + ms[2]) / 2
        coefficients.append((A, ms[0]-A, ms[1]-A))
    def errors(x):
        state = fixed
        for a, (A, B, C) in zip(np.deg2rad(x), coefficients):
            state = (A+B*np.cos(2*a)+C*np.sin(2*a)) @ state
        return error_probabilities(state) / targets
    def jac(x, h=2., ideal=False):
        return np.asarray((fd if ideal else ref)(x, h, *targets)).T
    return errors, jac


def score(e):
    return np.linalg.norm(e)/np.sqrt(2)


def hessian(jac, errors, x, h=.05):
    H = np.column_stack([(jac(x+d).T @ errors(x+d)-jac(x-d).T @ errors(x-d))/(2*h)
                         for d in np.eye(3)*h])
    return (H+H.T)/2


def normalized(v):
    n = np.linalg.norm(v)
    return v/n if n > 1e-12 else None


def directions(J, e, H, cfg, rng):
    g = J.T @ e
    raw = -J.T @ np.linalg.solve(J @ J.T + cfg.damping**2*np.eye(2), e)
    clipped = np.clip(raw, -cfg.max_step_deg, cfg.max_step_deg)
    out = [('clipped_dls', clipped), ('scaled_dls', raw), ('gradient', -g)]
    _, _, vh = np.linalg.svd(J, full_matrices=True)
    out += [('null_plus', vh[-1]), ('null_minus', -vh[-1])]
    eigenvalues, vectors = np.linalg.eigh(H)
    if eigenvalues[0] < 0:
        out += [('curvature_plus', vectors[:,0]), ('curvature_minus', -vectors[:,0])]
    for i, v in enumerate(np.eye(3)):
        out += [(f'axis_{i}_plus', v), (f'axis_{i}_minus', -v)]
    for i,j in itertools.combinations(range(3),2):
        for a,b in itertools.product((-1,1), repeat=2):
            out.append((f'coupled_{i}{j}_{a}_{b}', a*np.eye(3)[i]+b*np.eye(3)[j]))
    out.append(('random', rng.normal(size=3)))
    return out, raw, g


def diagnostic_positions(archives):
    seen = set()
    for archive in archives:
        with tarfile.open(archive, 'r:*') as tar:
            for member in sorted(tar.getmembers(), key=lambda m:m.name):
                if not member.isfile() or not member.name.endswith('.json.gz'):
                    continue
                with gzip.GzipFile(fileobj=tar.extractfile(member)) as f:
                    data = json.load(f)
                for row in data['jacobians']:
                    x = np.remainder(row['positions'], PERIODS)
                    key = (data['case'], *np.round(x, 8))
                    if key not in seen:
                        seen.add(key)
                        yield data['case'], x, f'{archive.name}:{member.name}:{row["attempt"]}'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('results/optical_landscape'))
    p.add_argument('--random-per-case', type=int, default=20)
    p.add_argument('--case-limit', type=int, default=100)
    p.add_argument('--sample-seed', type=int, default=20261119)
    p.add_argument('--diagnostics', type=Path, nargs='*', default=[])
    args = p.parse_args()
    if not 1 <= args.case_limit <= 100 or args.random_per_case < 0:
        p.error('Invalid sample counts')
    args.output.mkdir(parents=True, exist_ok=True)
    cfg = PolCompConfig()
    jc = cfg.jacobian
    targets = np.array([cfg.target_qber, cfg.target_qx])
    cases = generate_cases(cases=100, seed=42)
    rng = np.random.default_rng(args.sample_seed)
    direction_rng = np.random.default_rng(args.sample_seed+1)
    samples = []
    for case in range(1, args.case_limit+1):
        samples.append((case, np.zeros(3), 'initial', ''))
        samples.extend((case, x, 'random', '') for x in rng.uniform(0, 1, (args.random_per_case,3))*PERIODS)
    samples.extend((case,x,'trajectory',origin) for case,x,origin in diagnostic_positions(args.diagnostics) if case <= args.case_limit)
    manifest = dict(case_seed=42, sample_seed=args.sample_seed, case_limit=args.case_limit,
                    random_per_case=args.random_per_case, samples=len(samples), grid=GRID,
                    targets=targets.tolist(), max_axis_deg=jc.max_step_deg, max_total_deg=jc.max_total_step_deg,
                    damping=jc.damping, hessian_step_deg=.05, diagnostics=[str(a) for a in args.diagnostics])
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    models = {c: optical_model(cases[c-1][0], targets) for c in range(1,args.case_limit+1)}
    with gzip.open(args.output/'samples.csv.gz','wt',newline='') as fs, gzip.open(args.output/'trials.csv.gz','wt',newline='') as ft:
        sw, tw = csv.writer(fs), csv.writer(ft)
        sw.writerow(['sample','population','case','origin','qwp1','hwp','qwp2','qber','qx','score','gradient_norm','sigma_max','sigma_min','hessian_min','hessian_mid','hessian_max','fd_error_norm','solver_accepted'])
        tw.writerow(['sample','method','trial_type','requested_deg','actual_deg','dqwp1','dhwp','dqwp2','predicted_score','actual_score','qber','qx','relative_improvement','improvement_per_deg','target_reached'])
        for sid,(case,x,pop,origin) in enumerate(samples):
            errors,jac = models[case]
            e = errors(x); F = score(e); J = jac(x); H = hessian(jac,errors,x)
            dirs,raw,g = directions(J,e,H,jc,direction_rng)
            sv = np.linalg.svd(J,compute_uv=False)
            sol = JacobianSolver(jc).solve(columns=J.T,baseline_errors=e,baseline_score=F) if F>1e-12 else None
            sw.writerow([sid,pop,case,origin,*x,*(e*targets),F,np.linalg.norm(g),*sv,*np.linalg.eigvalsh(H),np.linalg.norm(jac(x,ideal=True)-J),bool(sol and sol.accepted)])
            def trial(name,kind,requested,step):
                dist = np.linalg.norm(step)
                if dist <= 1e-12: return
                actual = errors(x+step); val = score(actual)
                improvement = (F-val)/F if F>1e-12 else float('nan')
                tw.writerow([sid,name,kind,requested,dist,*step,score(e+J@step),val,*(actual*targets),improvement,improvement/dist,bool(np.all(actual<=1))])
            def constrain(v):
                return v*min(1.,jc.max_step_deg/max(np.max(np.abs(v)),1e-30),jc.max_total_step_deg/max(np.linalg.norm(v),1e-30))
            for name,v in dirs:
                d = normalized(v)
                if d is None: continue
                for radius in GRID:
                    # Skip infeasible radii rather than silently comparing unequal distances.
                    if radius*np.max(np.abs(d)) <= jc.max_step_deg+1e-10 and radius<=jc.max_total_step_deg:
                        trial(name,'grid',radius,radius*d)
            if sol and sol.step is not None:
                trial('clipped_dls','native',np.linalg.norm(sol.step),np.asarray(sol.step))
            trial('scaled_dls','native',np.linalg.norm(raw),constrain(raw))
            denom = np.linalg.norm(J@g)**2
            if denom>1e-24:
                cauchy = -np.dot(g,g)/denom*g
                trial('cauchy','native',np.linalg.norm(cauchy),constrain(cauchy))
            if (sid+1)%100==0 or sid+1==len(samples):
                print(f'{sid+1}/{len(samples)} samples',flush=True)


if __name__ == '__main__':
    main()
