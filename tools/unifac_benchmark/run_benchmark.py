"""F9-R6 timing benchmark for UNIFAC state closures (measurement only).

Measures how the cost of the common thermodynamic closures in core/mezclas.py
scales with the number of species, the phase regime, trace feeds and the number
of seeded samples of a dynamic run. Production code is not modified: the
benchmark only wraps instance methods of one Sistema to count calls, so it can
tell a seeded Newton flash from its fallback to the complete certified search.

Usage, from the repository root:
    python tools/unifac_benchmark/run_benchmark.py                 all cases
    python tools/unifac_benchmark/run_benchmark.py --only species  case ids containing a text
    python tools/unifac_benchmark/run_benchmark.py --profile ID    cProfile of one case
Options: --timeout SECONDS (per case, default 300), --repeats N (default 3),
--out DIRECTORY (default .tmp/claude-r6-benchmark).

Each case runs in its own process with a wall-clock cap, so one slow closure
cannot hide the others. Every published state is checked with the same validity
rule as the F9-R2 adversarial matrix; a timing is reported only with its outcome.
"""
import argparse
import cProfile
import hashlib
import io
import json
import math
import multiprocessing as mp
import platform
import pstats
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

W, E, BZ, TO, B, EA, ME, AC = ('7732-18-5', '64-17-5', '71-43-2', '108-88-3',
                               '71-36-3', '141-78-6', '67-56-1', '67-64-1')
NAMES = {W: 'water', E: 'ethanol', BZ: 'benzene', TO: 'toluene', B: '1-butanol',
         EA: 'ethyl acetate', ME: 'methanol', AC: 'acetone'}
LADDER = [W, E, BZ, TO, ME, AC, EA, B]          # species added one at a time
ORIGINAL, DORTMUND = 'unifac-original-public', 'unifac-dortmund-public'
P = 101325.0


def uniform(k):
    return [1.0 / k] * k


def cases():
    """(id, group, package, species, T, feed, operations, samples)."""
    out = []
    for package, sizes in ((ORIGINAL, range(2, 9)), (DORTMUND, (2, 3, 5, 8))):
        tag = 'orig' if package == ORIGINAL else 'dort'
        for k in sizes:
            out.append((f'species/{tag}/k{k}', 'species', package, LADDER[:k], 350.0, uniform(k),
                        ('TP', 'PH', 'UV', 'fastPH'), 0))
    regimes = [
        ('regime/liquid', [W, E], 300.0, [0.5, 0.5]),
        ('regime/vapor', [W, E], 420.0, [0.5, 0.5]),
        ('regime/vle', [W, E], 355.0, [0.5, 0.5]),
        ('regime/lle', [W, B], 300.0, [0.7, 0.3]),
        ('regime/vlle-near', [W, B], 365.5, [0.7, 0.3]),
        ('regime/lle-ternary', [BZ, W, E], 300.0, [0.45, 0.45, 0.10]),
    ]
    for cid, species, T, z in regimes:
        out.append((cid, 'regime', ORIGINAL, species, T, z, ('TP', 'PH', 'UV', 'fastPH'), 0))
    for k, species in ((2, [E, W]), (3, [BZ, W, E])):
        for exponent in (6, 12, 300):
            # Binary: an ethanol trace in water. Ternary: a water trace in 1:1
            # benzene-ethanol, as in the F0 and R2 reproducers.
            z = [10.0 ** -exponent, 1.0] if k == 2 else [0.5, 10.0 ** -exponent, 0.5]
            out.append((f'trace/k{k}/1e-{exponent}', 'trace', ORIGINAL, species, 345.0, z,
                        ('TP', 'PH', 'fastPH'), 0))
    for k in (2, 3, 5):
        for samples in (10, 40):
            out.append((f'samples/k{k}/n{samples}', 'samples', ORIGINAL, LADDER[:k], 350.0, uniform(k),
                        (), samples))
    return out


def valid(state):
    import numpy as np
    problems = []
    for phase in state.fases:
        if not (math.isfinite(phase.n) and phase.n >= 0):
            problems.append('amount')
        x = np.asarray(phase.x)
        if not np.all(np.isfinite(x)) or abs(x.sum() - 1) > 1e-9 or np.any(x < 0):
            problems.append('composition')
    for key, (residual, tolerance, _) in state.verificaciones.items():
        if not (math.isfinite(residual) and residual <= tolerance):
            problems.append(key)
    return problems


class Counters:
    """Counts calls of instance methods without changing their behavior."""

    WATCHED = ('equilibrio_TP', 'equilibrio_PH', 'equilibrio_UV', 'prueba_estabilidad', 'mu')

    def __init__(self, system):
        self.calls = dict.fromkeys(self.WATCHED, 0)
        for name in self.WATCHED:
            original = getattr(system, name)

            def wrapped(*args, _name=name, _original=original, **kwargs):
                self.calls[_name] += 1
                return _original(*args, **kwargs)
            setattr(system, name, wrapped)

    def take(self):
        snapshot, self.calls = self.calls, dict.fromkeys(self.WATCHED, 0)
        return snapshot


def timed(fn):
    start = time.perf_counter()
    try:
        state = fn()
        return time.perf_counter() - start, state, None
    except Exception as error:                 # structured rejections are outcomes too
        return time.perf_counter() - start, None, f'{type(error).__name__}: {str(error)[:160]}'


def run_case(case, repeats):
    import numpy as np
    from core import mezclas as mz
    cid, group, package, species, T, feed, operations, samples = case
    record = {'id': cid, 'group': group, 'package': package, 'species': [NAMES[c] for c in species],
              'k': len(species), 'T': T, 'P': P, 'feed': feed, 'operations': {}}
    start = time.perf_counter()
    system = mz.Sistema(package, species)
    record['constructSeconds'] = round(time.perf_counter() - start, 4)
    counters = Counters(system)
    z = np.asarray(feed, float)

    def measure(name, fn):
        runs = []
        for attempt in range(repeats):
            seconds, state, error = timed(fn)
            calls = counters.take()
            runs.append({'seconds': seconds, 'calls': calls})
            if error or attempt == 0 and seconds > 30:
                break                          # a rejection or a slow closure is not repeated
        first = runs[0]
        entry = {'cold': round(first['seconds'], 4),
                 'warmMedian': round(statistics.median(r['seconds'] for r in runs[1:]), 4) if len(runs) > 1 else None,
                 'calls': first['calls'],
                 'outcome': 'rejected' if error else ('invalid' if valid(state) else 'valid'),
                 'phases': [f.tipo for f in state.fases] if state is not None else None}
        if error:
            entry['error'] = error
        record['operations'][name] = entry
        return state

    seed = measure('TP', lambda: system.equilibrio_TP(T, P, z)) if 'TP' in operations or samples else None
    if seed is not None:
        H, V, U = seed.H, seed.V, seed.U
        if 'PH' in operations:
            measure('PH', lambda: system.equilibrio_PH(P, H, z, semilla=seed))
        if 'UV' in operations:
            measure('UV', lambda: system.equilibrio_UV(U, V, z))
        if 'fastPH' in operations:
            # The dynamic step: a small energy change from a certified seed.
            target = H + 0.01 * max(abs(H), 8.314 * T * z.sum())
            entry_state = measure('fastPH', lambda: system.flash_rapido('PH', P, target, z, seed))
            fast = record['operations']['fastPH']
            fast['fallback'] = any(fast['calls'][key] for key in ('equilibrio_TP', 'equilibrio_PH', 'equilibrio_UV'))
    if samples and seed is not None:
        # A heating trajectory: each sample seeds the next, as dynamics does.
        H0 = seed.H
        step = 0.002 * max(abs(H0), 8.314 * T * z.sum())
        per_sample, fallbacks, outcomes = [], 0, []
        state = seed
        for index in range(samples):
            seconds, new_state, error = timed(lambda: system.flash_rapido('PH', P, H0 + (index + 1) * step, z, state))
            calls = counters.take()
            per_sample.append(seconds)
            fallbacks += any(calls[key] for key in ('equilibrio_TP', 'equilibrio_PH', 'equilibrio_UV'))
            if error:
                outcomes.append(error)
                break
            outcomes.append('invalid' if valid(new_state) else 'valid')
            state = new_state
        record['samples'] = {'requested': samples, 'completed': len(per_sample),
                             'totalSeconds': round(sum(per_sample), 4),
                             'medianSeconds': round(statistics.median(per_sample), 4),
                             'maxSeconds': round(max(per_sample), 4), 'fallbacks': fallbacks,
                             'invalid': outcomes.count('invalid'),
                             'finalT': round(state.T, 4), 'finalPhases': [f.tipo for f in state.fases],
                             'error': next((o for o in outcomes if o not in ('valid', 'invalid')), None)}
    return record


def worker(case, repeats, queue):
    import warnings
    warnings.simplefilter('ignore')            # timing only; R2 traced floating-point events separately
    try:
        queue.put(run_case(case, repeats))
    except Exception as error:
        queue.put({'id': case[0], 'group': case[1], 'crash': f'{type(error).__name__}: {str(error)[:200]}'})


def environment():
    import numpy
    import scipy
    def digest(path):
        return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()[:16]
    try:
        head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        head = None
    return {'python': platform.python_version(), 'numpy': numpy.__version__, 'scipy': scipy.__version__,
            'platform': platform.platform(), 'processor': platform.processor(), 'cpus': mp.cpu_count(),
            'gitHead': head, 'workingTreeDigests': {p: digest(p) for p in
                ('core/mezclas.py', 'core/mezclas_datos.py', 'core/unifac.py')}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', default='')
    parser.add_argument('--profile', default='')
    parser.add_argument('--timeout', type=float, default=300.0)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--out', default=str(ROOT / '.tmp/claude-r6-benchmark'))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    selected = [c for c in cases() if args.only in c[0]]
    if args.profile:
        import warnings
        warnings.simplefilter('ignore')
        case = next(c for c in cases() if c[0] == args.profile)
        profiler = cProfile.Profile()
        profiler.enable()
        record = run_case(case, 1)
        profiler.disable()
        text = io.StringIO()
        pstats.Stats(profiler, stream=text).sort_stats('cumulative').print_stats(35)
        name = args.profile.replace('/', '_')
        (out / f'profile_{name}.txt').write_text(json.dumps(record, indent=1) + '\n' + text.getvalue(), encoding='utf8')
        print(text.getvalue()[:6000])
        return
    results = {'format': 'rage.unifac-benchmark', 'version': 1, 'environment': environment(),
               'timeoutSeconds': args.timeout, 'repeats': args.repeats, 'cases': []}
    target = out / ('benchmark.json' if not args.only else f'benchmark_{args.only.replace("/", "_")}.json')
    for case in selected:
        queue = mp.Queue()
        process = mp.Process(target=worker, args=(case, args.repeats, queue))
        start = time.perf_counter()
        process.start()
        process.join(args.timeout)
        if process.is_alive():
            process.terminate()
            process.join()
            record = {'id': case[0], 'group': case[1], 'timeout': args.timeout}
        else:
            record = queue.get() if not queue.empty() else {'id': case[0], 'group': case[1], 'crash': 'no result'}
        record['wallSeconds'] = round(time.perf_counter() - start, 3)
        results['cases'].append(record)
        ops = record.get('operations', {})
        summary = ' '.join(f"{k}={v['cold']}s/{v['outcome']}" + ('/fallback' if v.get('fallback') else '')
                           for k, v in ops.items())
        extra = f" samples={record['samples']['totalSeconds']}s fb={record['samples']['fallbacks']}" if 'samples' in record else ''
        print(f"{case[0]:24s} {summary}{extra} {record.get('timeout') and 'TIMEOUT' or record.get('crash', '')}", flush=True)
        target.write_text(json.dumps(results, indent=1), encoding='utf8')
    print('written', target)


if __name__ == '__main__':
    main()
