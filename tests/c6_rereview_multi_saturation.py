"""Demo 0.3 C6 re-review probe (not collected by pytest): several saturations in one run against a hand-written piecewise reference.

m c dT/dt = P v, v = min(max(u_c, u_min), u_max), u_c = K_c (r - T + I/tau_I), dI/dt = r - T.
Reference: DOP853 at rtol 1e-13 on each branch, with the switching surfaces as root events.
Engine: every published `cambio_firma` against the reference event, measured in units of the
literal DR-6 bound 10 rtol |u_c| / |du_c/dt| (|u_c| = |limit| at the event).
Also: each event against the run's own crossing (bisected on its dense output), which separates
location error from the trajectory's own state error.
usage: python tests/c6_rereview_multi_saturation.py <u_max> <u_min> <tf> [rtol ...]   (e.g. 0.2 -0.02 600)
"""
import copy, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
import numpy as np
from scipy.integrate import solve_ivp
from test_control_kernel import author_pid, lowered_model
from core.compilador.derived import DerivedSystem
from core.solvers import integrar

UMAX, UMIN, TF = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
RTOLS = [float(x) for x in sys.argv[4:]] or [1e-6, 1e-8, 1e-10]
K, TAU, P, MC, T0, R = 0.05, 50., 1000., 1000., 320., 330.
uc = lambda y: K * (R - y[0] + y[1] / TAU)


def reference():
    y, t, events = np.array([T0, 0.]), 0., []
    branch = 'max' if uc(y) > UMAX else 'min' if uc(y) < UMIN else 'free'
    while t < TF:
        v = {'max': lambda y: UMAX, 'min': lambda y: UMIN, 'free': uc}[branch]
        rhs = lambda t, y: [P / MC * v(y), R - y[0]]
        if branch == 'free':
            fs = [lambda t, y: uc(y) - UMAX, lambda t, y: uc(y) - UMIN]
            fs[0].direction, fs[1].direction = 1, -1
        else:
            lim = UMAX if branch == 'max' else UMIN
            fs = [lambda t, y, lim=lim: uc(y) - lim]
            fs[0].direction = -1 if branch == 'max' else 1
        for f in fs: f.terminal = True
        sol = solve_ivp(rhs, (t, TF), y, method='DOP853', rtol=1e-13, atol=1e-12, events=fs, first_step=1e-3)
        hits = [(te[0], i) for i, te in enumerate(sol.t_events) if len(te)]
        if not hits:
            break
        t, i = min(hits)
        y = sol.y_events[i][0]
        if branch == 'free':
            branch = 'max' if i == 0 else 'min'
        else:
            branch = 'free'
        lim = UMAX if abs(uc(y) - UMAX) < abs(uc(y) - UMIN) else UMIN
        duc = K * (-P / MC * lim + (R - y[0]) / TAU)
        events.append((t, branch, abs(lim), abs(duc)))
    return events


ref = reference()
print(f'u_max {UMAX} u_min {UMIN} tf {TF}: reference events', [(round(t, 6), b) for t, b, *_ in ref], flush=True)
author, rows = author_pid()
data = {'commandMax': (UMAX, '1'), 'commandMin': (UMIN, '1')}
for rtol in RTOLS:
    for method in ('RK45', 'BDF'):
        model = lowered_model(author, rows, data); model['estudio']['rtol'] = rtol
        s = DerivedSystem(copy.deepcopy(model))
        tr = integrar(s, s.initial(), TF, rtol=rtol, atol=s.numeric.atol, max_step=s.tf / 120, metodo=method)
        ev = [t for c, t, *_ in tr.eventos if c == 'cambio_firma']
        iU = next(i for i, q in enumerate(s.states) if str(q).startswith('U__')); iI = s.states.index(s.quantities['integral'])
        ucr = lambda t: K * (R - (300 + tr.y(t)[iU] / 1000) + tr.y(t)[iI] / TAU)
        ratios, loc, glob = [], [], []
        for (t_r, _, ulim, duc), t_e in zip(ref, ev):
            lim = UMAX if abs(ucr(t_e) - UMAX) < abs(ucr(t_e) - UMIN) else UMIN
            g = lambda t: ucr(t) - lim
            a, b = t_e - 0.5, t_e + 0.5
            for _ in range(200):
                m = 0.5 * (a + b)
                if np.sign(g(m)) == np.sign(g(a)): a = m
                else: b = m
            own = 0.5 * (a + b)
            bound = 10 * rtol * ulim / duc
            ratios.append(abs(t_e - t_r) / bound); loc.append(abs(t_e - own) / bound); glob.append(abs(own - t_r) / bound)
        print(f'  {method} rtol {rtol:g}: events {len(ev)} (ref {len(ref)}), steps {tr.pasos}, rejections {tr.rechazos}, '
              f'detenida {tr.detenida}; |dt|/bound {["%.3f" % r for r in ratios]}; event-own crossing /bound {["%.3f" % r for r in loc]}; own crossing-ref /bound {["%.3f" % r for r in glob]}', flush=True)
