"""Demo 0.3 C6 review, finding C6-R1 reproducer (run: python tests/c6_review_exit_location.py): event time vs the published trajectory's own crossing vs t* = sqrt(3000).

Also the lower-limit entry of the unsaturated PI loop (u_min = 0, u_max = 1) against the matrix
exponential: x = T - r, I; x' = a(-x + I/tau_I), I' = -x, a = P K_c/(m c); u_c = K_c (-x + I/tau_I) = 0.
"""
import copy, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
import numpy as np
from scipy.linalg import expm
from scipy.optimize import brentq
from test_control_kernel import author_pid, lowered_model
from core.compilador.derived import DerivedSystem
from core.solvers import integrar

author, rows = author_pid()
T_STAR = math.sqrt(3000.); SLOPE = 2e-4 * T_STAR


def run(data, rtol, method):
    model = lowered_model(author, rows, data); model['estudio']['rtol'] = rtol
    s = DerivedSystem(copy.deepcopy(model))
    return s, integrar(s, s.initial(), s.tf, rtol=rtol, atol=s.numeric.atol, max_step=s.tf / 120, metodo=method)


def crossing(g, a, b):
    for _ in range(200):
        m = 0.5 * (a + b)
        if np.sign(g(m)) == np.sign(g(a)): a = m
        else: b = m
    return 0.5 * (a + b)


SAT = {'commandMax': (0.2, '1'), 'commandMin': (-0.1, '1')}
for rtol in (1e-6, 1e-8, 1e-10):
    for method in ('RK45', 'BDF'):
        s, tr = run(SAT, rtol, method)
        t_e = next(t for c, t, *_ in tr.eventos if c == 'cambio_firma')
        f = s.regimes[0]['evaluate']
        own = crossing(lambda t: f[0](t, tr.y(t)) - f[1](t, tr.y(t)), t_e - 1, t_e + 1)
        literal = 10 * rtol * 0.2 / SLOPE
        print(f'{method} rtol {rtol:g}: event - t* {t_e - T_STAR:+.3e}; own crossing - t* {own - T_STAR:+.3e}; '
              f'literal bound {literal:.3e}; event/literal {abs(t_e - T_STAR)/literal:.2f}; crossing/literal {abs(own - T_STAR)/literal:.3f}', flush=True)

a, tau, Kc = 1000 * 0.05 / 1000, 50., 0.05
M = np.array([[-a, a / tau], [-1., 0.]]); z0 = np.array([320 - 330., 0.])
uc = lambda t: Kc * np.array([-1., 1 / tau]) @ (expm(M * t) @ z0)
t_ref = brentq(uc, 1., 200.)
for method in ('RK45', 'BDF'):
    s, tr = run({'commandMax': (1, '1'), 'commandMin': (0, '1')}, 1e-10, method)
    t_e = next(t for c, t, *_ in tr.eventos if c == 'cambio_firma')
    slope = abs((uc(t_ref + 1e-4) - uc(t_ref - 1e-4)) / 2e-4)
    print(f'lower-limit entry {method} rtol 1e-10: event {t_e:.10f}, reference {t_ref:.10f}, diff {t_e - t_ref:+.3e}, '
          f'literal 10 rtol |u_c|/|du_c/dt| with |u_c| = max(|u_c|,|u_min|) = 0 -> 0 (degenerate)', flush=True)
