"""Temporary CI diagnostic (branch diag/f9-steady-seed, never merged): run the tiny-seed case of
tests/test_steady_transform.py::test_missing_mass_budget... and print the Newton evidence."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
import numpy as np
from demo01_flash import frozen_model
from core.modelo.steady_transform import prepare_steady_transform
from core.compilador.steady import SteadySystem
from core.solvers import nonlinear

trace = []
original = nonlinear.solve
def solve(residual, jacobian, seed, *a, **k):
    def r(z):
        out = residual(z); return out
    try:
        return original(residual, jacobian, seed, *a, **k)
    except nonlinear.NonlinearError as error:
        print('NONLINEAR', json.dumps(error.diagnostic, default=str), flush=True); raise
nonlinear.solve = solve
import core.compilador.steady as steady
steady.nonlinear.solve = solve

def big(m, f=100):
    for k in ('drum.volume', 'solve.A', 'solve.Ao', 'solve.F', 'solve.Q', 'scale.mass'):
        d = m['datos'][k]['declaracion']; d['texto'] = str(float(d['texto'])*f)
for first, second in [('2000.0', '8000.0'), ('0.001', '0.004')]:
    m = frozen_model(); big(m)
    m['datos']['drum.mass']['declaracion']['texto'] = first
    m['datos']['drum.mass2']['declaracion']['texto'] = second
    m['motores']['derivedExecution']['checks'] = []
    response = prepare_steady_transform(m)
    system = SteadySystem(response['model'])
    print('CASE', first, second, 'config', json.dumps(system.config, default=str), flush=True)
    try:
        result = system.solve()
        d = result.get('motores', {}) if isinstance(result, dict) else {}
        print('RESULT', result.get('estado'), json.dumps(result.get('diagnosticos') or result.get('diagnostico') or '', default=str)[:2000], flush=True)
        for c in result.get('verificaciones', []):
            if 'residual' in c.get('id', ''): print('CHECK', json.dumps(c, default=str)[:400], flush=True)
    except Exception as error:
        print('ERROR', type(error).__name__, getattr(error, 'code', ''), str(error)[:300], flush=True)
