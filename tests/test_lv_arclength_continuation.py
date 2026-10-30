"""f8b: liquid-vapor branches by pseudo-arclength continuation (core/termodinamica/lv_continuation.py).

References, each reached by another path than the continuation:
1. Ideal solution + ideal vapor (package 'mezcla-ideal'): the analytic K_i = Psat_i exp(vL_i (P - Psat_i) / RT) / P
   from the species data, solved with brentq for the bubble T of each traced x (T-xy) and for the bubble and dew
   P of each traced T (ternary envelopes).
2. UNIFAC (original, public parameters): the existing binary bubble solver (core/coexistencia_lv.resolver_punto)
   seeded by the package's certified TP flash, the existing azeotrope solver (x = y), the pure saturation
   temperatures, the package's TP flash on both sides of a traced ternary bubble and dew point, the existing
   L-L-V three-phase point (core/coexistencia_ll.three_phase_point) and the literature ethanol-water azeotrope
   (Gmehling et al., Azeotropic Data: 78.15 C, x = 0.894; UNIFAC is a prediction, so the band is wider).
3. Turning points: natural-parameter stepping in T (or P), the plain method, stops at the azeotrope fold; the
   continuation passes it and reaches the other pure end.
Run: python -m pytest tests/test_lv_arclength_continuation.py (about 1 min).
"""
import math
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import coexistencia_ll as ll
from core import coexistencia_lv as co
from core import mezclas as mz
from core.termodinamica import lv_continuation as lc

warnings.filterwarnings('ignore')
BZ, TO, E, W, ME, AC, BU = '71-43-2', '108-88-3', '64-17-5', '7732-18-5', '67-56-1', '67-64-1', '71-36-3'
P_ATM = 101325.0
UNIFAC = 'unifac-original-public'


def ideal_K(sis, T, P):
    return np.array([e.Psat(T) * math.exp(e.vL * (P - e.Psat(T)) / (mz.R * T)) / P for e in sis.esp])


def natural_parameter_T(sis, P, x0_start, T_start, y0_start, dT, minimum=1e-6):
    """Plain stepping in T on the T-xy branch: Newton in (logit x0, logit y0) at each fixed T from the previous
    point, halving the step on failure. Returns the last converged (T, x0)."""
    T, x, y = T_start, x0_start, y0_start
    while abs(dT) >= minimum:
        Tn = T + dT

        def F(v):
            a, b = co._sig(v[0]), co._sig(v[1])
            return co.residuo(sis, 'Txy', P, Tn, (a, 1 - a), (b, 1 - b))
        try:
            v, f = co._newton(F, [co._logit(x), co._logit(y)])
            ok = np.max(np.abs(f)) < 1e-11 and abs(co._sig(v[0]) - x) < 0.2
        except (mz.FueraDeAlcance, ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError):
            ok = False
        if ok:
            T, x, y = Tn, co._sig(v[0]), co._sig(v[1])
        else:
            dT *= 0.5
    return T, x


def interior(r):
    return [p for p in r['points'] if 1e-9 < p['x'][0] < 1 - 1e-9]


class IdealReference(unittest.TestCase):
    def test_binary_txy_against_the_analytic_curve(self):
        sis = mz.Sistema('mezcla-ideal', [BZ, TO])
        r = lc.trace(sis, 'isobaric', P_ATM)
        self.assertEqual(r['end']['kind'], 'pure_component')
        self.assertEqual(r['turningPoints'], [])
        worst_T = worst_y = 0.0
        for p in r['points']:
            x = np.array(p['x'])
            T_ref = brentq(lambda T: (x * ideal_K(sis, T, P_ATM)).sum() - 1, 300, 420, xtol=1e-13)
            y_ref = x * ideal_K(sis, T_ref, P_ATM)
            worst_T = max(worst_T, abs(p['T'] - T_ref))
            worst_y = max(worst_y, float(np.max(np.abs(np.array(p['y']) - y_ref))))
            self.assertEqual(p['certificate']['state'], 'certified')
        self.assertLess(worst_T, 1e-8)
        self.assertLess(worst_y, 1e-10)
        ends = (r['points'][0], r['points'][-1])
        self.assertAlmostEqual(ends[0]['T'], sis.T_saturacion(P_ATM, 0), delta=1e-8)
        self.assertAlmostEqual(ends[1]['T'], sis.T_saturacion(P_ATM, 1), delta=1e-8)
        print(f"\nideal T-xy: {len(r['points'])} points, worst |dT| {worst_T:.1e} K, |dy| {worst_y:.1e}")

    def test_ternary_envelopes_against_the_analytic_pressures(self):
        sis = mz.Sistema('mezcla-ideal', [E, W, ME])
        z = np.array([0.3, 0.4, 0.3])
        for kind in ('bubble', 'dew'):
            r = lc.trace(sis, kind, z=z)
            self.assertEqual(r['end']['kind'], 'domain_limit')
            worst = 0.0
            for p in r['points']:
                T = p['T']
                g = (lambda P: (z * ideal_K(sis, T, P)).sum() - 1) if kind == 'bubble' else \
                    (lambda P: (z / ideal_K(sis, T, P)).sum() - 1)
                P_ref = brentq(g, 10.0, 1e7, xtol=1e-12, rtol=1e-15)
                worst = max(worst, abs(p['P'] / P_ref - 1))
                fixed = p['x'] if kind == 'bubble' else p['y']
                self.assertLess(max(abs(a - b) for a, b in zip(fixed, z)), 1e-12)
            self.assertLess(worst, 1e-10)
            print(f"\nideal ternary {kind}: {len(r['points'])} points, worst relative |dP| {worst:.1e}")


class UnifacAzeotrope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sis = mz.Sistema(UNIFAC, [E, W])
        cls.r = lc.trace(cls.sis, 'isobaric', P_ATM)

    def test_branch_passes_the_azeotrope_to_the_other_pure_end(self):
        r = self.r
        self.assertEqual(r['end']['kind'], 'pure_component')
        self.assertAlmostEqual(r['points'][0]['T'], self.sis.T_saturacion(P_ATM, 0), delta=1e-8)
        self.assertAlmostEqual(r['points'][-1]['T'], self.sis.T_saturacion(P_ATM, 1), delta=1e-8)
        self.assertLess(r['points'][-1]['x'][0], 1e-15)
        self.assertTrue(all(p['certificate']['state'] == 'certified' for p in r['points']))
        tps = r['turningPoints']
        self.assertEqual(len(tps), 1)
        self.assertEqual(tps[0]['turningPoint'], {'variable': 'temperature', 'kind': 'minimum', 'located': True})

    def test_turning_point_against_the_azeotrope_solver_and_literature(self):
        tp = self.r['turningPoints'][0]
        T_az, x_az = co.resolver_azeotropo(self.sis, 'Txy', P_ATM, (351.3, 0.894))
        self.assertLess(abs(tp['T'] - T_az), 1e-9)
        self.assertLess(abs(tp['x'][0] - x_az), 1e-7)
        self.assertLess(abs(tp['x'][0] - tp['y'][0]), 1e-7)
        self.assertLess(abs(tp['T'] - (78.15 + 273.15)), 0.5)
        self.assertLess(abs(tp['x'][0] - 0.894), 0.01)
        print(f"\nUNIFAC ethanol-water azeotrope: |dT| {abs(tp['T'] - T_az):.1e} K, |dx| {abs(tp['x'][0] - x_az):.1e} "
              f"against the x = y solver; {tp['T'] - 273.15:.3f} C, x {tp['x'][0]:.4f} (lit. 78.15 C, 0.894)")

    def test_sampled_points_against_the_existing_bubble_solver(self):
        pts = interior(self.r)
        worst_T = worst_y = 0.0
        for p in pts[::max(1, len(pts) // 8)]:
            x0 = p['x'][0]
            seed = co.semilla_por_flash(self.sis, 'Txy', P_ATM, x0)     # independent seed: the TP flash
            T, y0 = co.resolver_punto(self.sis, 'Txy', P_ATM, x0, seed)
            worst_T = max(worst_T, abs(p['T'] - T))
            worst_y = max(worst_y, abs(p['y'][0] - y0))
        self.assertLess(worst_T, 1e-8)
        self.assertLess(worst_y, 1e-9)
        print(f"\nUNIFAC ethanol-water vs resolver_punto: worst |dT| {worst_T:.1e} K, |dy| {worst_y:.1e}")

    def test_natural_parameter_stepping_stops_at_the_fold(self):
        T0 = self.sis.T_saturacion(P_ATM, 1)
        T_end, x_end = natural_parameter_T(self.sis, P_ATM, 1e-6, T0 - 1e-6, 1e-5, dT=-0.5)
        x_az = self.r['turningPoints'][0]['x'][0]
        self.assertLess(x_end, x_az + 1e-3)
        self.assertLess(abs(T_end - self.r['turningPoints'][0]['T']), 1e-3)
        self.assertGreater(max(p['x'][0] for p in self.r['points']), 1 - 1e-12)
        print(f"\nplain stepping in T stops at x = {x_end:.6f}, T = {T_end:.6f} K (fold at x = {x_az:.6f}); "
              "continuation reaches x = 1")


class UnifacTurningInPressure(unittest.TestCase):
    def test_pxy_maximum_pressure_azeotrope(self):
        sis = mz.Sistema(UNIFAC, [E, BZ])
        r = lc.trace(sis, 'isothermal', 340.0)
        self.assertEqual(r['end']['kind'], 'pure_component')
        tps = r['turningPoints']
        self.assertEqual([t['turningPoint'] for t in tps], [{'variable': 'pressure', 'kind': 'maximum', 'located': True}])
        P_az, x_az = co.resolver_azeotropo(sis, 'Pxy', 340.0, (tps[0]['P'] * 1.01, 0.5))
        self.assertLess(abs(tps[0]['P'] / P_az - 1), 1e-10)
        self.assertLess(abs(tps[0]['x'][0] - x_az), 1e-7)
        self.assertAlmostEqual(r['points'][0]['P'] / sis.P_saturacion(340.0, 0), 1.0, delta=1e-10)
        self.assertAlmostEqual(r['points'][-1]['P'] / sis.P_saturacion(340.0, 1), 1.0, delta=1e-10)
        self.assertTrue(all(p['certificate']['state'] == 'certified' for p in r['points']))


class UnifacHeterogeneous(unittest.TestCase):
    def test_stability_changes_at_the_three_phase_point(self):
        sis = mz.Sistema(UNIFAC, [W, BU])
        r = lc.trace(sis, 'isobaric', P_ATM)
        self.assertEqual(r['end']['kind'], 'pure_component')
        ch = r['stabilityChanges']
        self.assertEqual(len(ch), 2)
        good = [c['certifiedSide'] for c in ch]
        self.assertTrue(all(g['certificate']['state'] == 'certified' for g in good))
        self.assertTrue(all(c['uncertifiedSide']['certificate']['state'] == 'unstable' for c in ch))
        xa, xb = sorted(g['x'][0] for g in good)
        q, a, b, y = ll.three_phase_point(sis, 'Txy', P_ATM, ll.q_of('Txy', good[0]['T'], P_ATM), xb, xa, good[0]['y'][0])
        T3 = ll.TP('Txy', P_ATM, q)[0]
        for g in good:
            self.assertLess(abs(g['T'] - T3), 1e-5)
        self.assertLess(abs(max(a, b) - xb), 1e-5)
        self.assertLess(abs(min(a, b) - xa), 1e-5)
        print(f"\nUNIFAC water-1-butanol L-L-V: continuation T {good[0]['T']:.6f}/{good[1]['T']:.6f} K vs "
              f"three_phase_point {T3:.6f} K")


class UnifacTernaryEnvelope(unittest.TestCase):
    def test_bubble_and_dew_against_the_package_flash(self):
        sis = mz.Sistema(UNIFAC, [AC, ME, W])
        z = np.array([0.3, 0.3, 0.4])
        for kind in ('bubble', 'dew'):
            r = lc.trace(sis, kind, z=z)
            self.assertEqual(r['end']['kind'], 'domain_limit')
            self.assertTrue(all(p['certificate']['state'] == 'certified' for p in r['points']))
            pts = r['points']
            for p in pts[1:-1:max(1, len(pts) // 6)]:
                T, P = p['T'], p['P']
                above = sis.equilibrio_TP(T, P * (1 + 1e-4), z)
                below = sis.equilibrio_TP(T, P * (1 - 1e-4), z)
                kinds_above = sorted(f.tipo for f in above.fases)
                kinds_below = sorted(f.tipo for f in below.fases)
                self.assertEqual(kinds_above, ['liquido', 'vapor'] if kind == 'dew' else ['liquido'])
                self.assertEqual(kinds_below, ['vapor'] if kind == 'dew' else ['liquido', 'vapor'])
                # the incipient phase of the flash approaches the traced one
                two = below if kind == 'bubble' else above
                inc = next(f for f in two.fases if f.tipo == ('vapor' if kind == 'bubble' else 'liquido'))
                ref = np.array(p['y'] if kind == 'bubble' else p['x'])
                self.assertLess(float(np.max(np.abs(np.asarray(inc.x) - ref))), 5e-4)   # 1e-4 off the point in P



class EndpointFold:
    """Numerical adapter from Codex's f8b review (not a physical example): the exact branch is
    T = 350 + (x0 - 0.001)^2, y0 = x0 (1 + 0.1 (1 - x0)), so a minimum in T sits just before the pure end x0 = 0."""
    esp = [None, None]
    cas = ['a', 'b']
    T_rango = (300.0, 400.0)

    def dominio(self, T, P):
        if not 300 <= T <= 400:
            raise ValueError('domain')

    def T_saturacion(self, P, i):
        return 350.0 + (float(i == 0) - 0.001) ** 2

    def lv_ln_k(self, T, P, x, idx):
        a = float(x[0])
        return np.log([1 + 0.1 * (1 - a), 1 - 0.1 * a]) + (T - (350.0 + (a - 0.001) ** 2))


class ReviewRegressions(unittest.TestCase):
    """Codex's review of 30 October (.tmp/codex-f8b-review): both cases failed on the first delivery."""

    def test_fold_on_the_closing_step_is_detected(self):
        from unittest.mock import patch
        with patch.object(lc, 'certify', return_value={'state': 'certified'}):   # algorithm-only control
            r = lc.trace(EndpointFold(), 'isobaric', P_ATM)
        self.assertEqual(r['end']['kind'], 'pure_component')
        self.assertEqual(len(r['turningPoints']), 1)
        tp = r['turningPoints'][0]
        self.assertEqual(tp['turningPoint']['kind'], 'minimum')
        self.assertTrue(tp['turningPoint']['located'])
        self.assertLess(abs(tp['x'][0] - 0.001), 1e-6)
        self.assertLess(abs(tp['T'] - 350.0), 1e-9)

    def test_mismatched_support_is_rejected(self):
        sis = mz.Sistema('mezcla-ideal', [BZ, TO])
        T = sis.T_saturacion(P_ATM, 0)
        c = lc.certify(sis, T, P_ATM, [1.0, 0.0], [0.5, 0.5])     # actual mu gap of species 0: ln 2 RT
        self.assertEqual(c['state'], 'failed')
        self.assertFalse(c['residuals'][0]['passes'])
        self.assertEqual(c['residuals'][0]['species'], [1])
        c = lc.certify(sis, T, P_ATM, [0.5, 0.5], [1.0, 0.0])
        self.assertEqual(c['state'], 'failed')
        c = lc.certify(sis, T, P_ATM, [1.0, 0.0], [1.0, 0.0])     # the true pure end: same support
        self.assertEqual(c['state'], 'certified')


if __name__ == '__main__':
    unittest.main()
