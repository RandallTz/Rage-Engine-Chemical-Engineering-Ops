"""f8b: three-liquid (L-L-L) ternary regions (core/termodinamica/three_liquid.py).

The catalog has no ternary that forms three liquids (its organics are mutually miscible), so the exact
references use a test liquid on the catalog's ideal-vapor data, g^E/RT = sum_{i<j} (a_ij / T) x_i x_j
(three-suffix-free ternary Margules), and the real package is checked where the literature says there is no
three-liquid region. References, each reached by another path than the triangle solver:
1. Symmetric a_ij = a: the triangle is (p, q, q) and permutations with q = (1 - p) / 2 and
   ln(p / q) = (a / T)(p - q) (scalar brentq). Its four-liquid invariant (the triangle and the centroid liquid on
   one tangent plane) is p = 2/3, a / T = 4 ln 2, and its L-L-L-V point is where the bubble pressure of a
   vertex, sum x_i gamma_i K_i^ideal, reaches P (nested brentq, species data only).
2. The package's certified TP flash: three liquids equal to the vertices at interior feeds, amounts equal to
   the lever rule (mass balance), two liquids at feeds just outside each side ending at that side's vertices.
3. The Gibbs phase rule: at fixed T and P the triangle is invariant (every seed gives the same triangle); at
   fixed P the four-phase points are invariant in T.
4. The binary-edge two-liquid branches of the ternary tracer end on the triangle sides.
5. UNIFAC-LLE water/benzene/toluene at 25 C: one miscibility gap and no three liquids (literature).
Run: python -m pytest tests/test_three_liquid_ternary.py (about 2 min).
"""
import math
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import mezclas as mz
from core.termodinamica import three_liquid as tl

warnings.filterwarnings('ignore')
BZ, TO, E, W = '71-43-2', '108-88-3', '64-17-5', '7732-18-5'
P_ATM = 101325.0


class Margules3:
    """Test liquid: g^E/RT = 1/2 x^T (a / T) x, a symmetric with zero diagonal."""
    nombre = 'ternary Margules (test)'

    def __init__(self, a, idx=(0, 1, 2)):
        self.a, self.idx = np.asarray(a, float), list(idx)

    def _A(self, T):
        return self.a[np.ix_(self.idx, self.idx)] / T

    def gE_RT(self, T, x):
        x = np.asarray(x, float)
        return 0.5 * x @ self._A(T) @ x

    def lngamma(self, T, x):
        return self.lngamma_lote(T, np.asarray(x, float)[None, :])[0]

    def lngamma_lote(self, T, X):
        A = self._A(T)
        return X @ A - 0.5 * np.einsum('ni,ij,nj->n', X, A, X)[:, None]

    def subconjunto(self, idx):
        return Margules3(self.a, [self.idx[i] for i in idx])


def system(a01, a02, a12):
    sis = mz.Sistema('mezcla-ideal', [BZ, TO, E])
    sis.liq = Margules3([[0, a01, a02], [a01, 0, a12], [a02, a12, 0]])
    sis.__dict__.pop('_subs', None)
    return sis


def symmetric_vertex(A):
    """p of the symmetric triangle (p, q, q) for A = a / T: the root of ln(p/q) = A (p - q) above 1/3."""
    f = lambda p: math.log(2 * p / (1 - p)) - A * (3 * p - 1) / 2
    return brentq(f, 0.5, 1 - 1e-12, xtol=1e-15)


def liquids_of(state):
    return [np.asarray(f.x, float) for f in state.fases if f.tipo == 'liquido'], \
        [f.n for f in state.fases if f.tipo == 'liquido']


def match(xs, ys):
    """max over vertices of the distance to the nearest other vertex (order-free)."""
    return max(min(float(np.max(np.abs(x - y))) for y in ys) for x in xs)


class SymmetricTriangle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.T, cls.a = 300.0, 2.8 * 300.0
        cls.sis = system(cls.a, cls.a, cls.a)
        cls.r = tl.region(cls.sis, cls.T, P_ATM)

    def test_triangle_against_the_analytic_root(self):
        self.assertEqual(len(self.r['triangles']), 1)
        tri = self.r['triangles'][0]
        p = symmetric_vertex(self.a / self.T)
        q = (1 - p) / 2
        ref = [np.array(v) for v in ((p, q, q), (q, p, q), (q, q, p))]
        err = match(tri['liquids'], ref)
        self.assertLess(err, 1e-10)
        self.assertEqual(tri['certificate']['estado'], 'cumple')
        print(f"\nsymmetric triangle: p = {p:.10f}, worst vertex error {err:.1e}")

    def test_phase_rule_flash_and_lever_rule_inside(self):
        tri = self.r['triangles'][0]
        rng = np.random.default_rng(7)
        worst_x = worst_n = 0.0
        for _ in range(5):
            w = rng.dirichlet([2, 2, 2])
            z = w @ np.array(tri['liquids'])                     # a feed inside the triangle
            xs, ns = liquids_of(self.sis.equilibrio_TP(self.T, P_ATM, z))
            self.assertEqual(len(xs), 3)
            worst_x = max(worst_x, match(xs, tri['liquids']))
            amounts = tl.phase_amounts(tri, z)
            self.assertTrue(np.all(amounts > 0))
            for x, n in zip(xs, ns):
                k = int(np.argmin([np.max(np.abs(x - v)) for v in tri['liquids']]))
                worst_n = max(worst_n, abs(n - amounts[k]))
        self.assertLess(worst_x, 1e-7)
        self.assertLess(worst_n, 1e-7)
        print(f"\nTP flash inside: worst vertex {worst_x:.1e}, worst amount vs lever rule {worst_n:.1e} mol")

    def test_edges_flash_and_branches(self):
        tri = self.r['triangles'][0]
        xs = tri['liquids']
        worst = 0.0
        for i, j in ((0, 1), (0, 2), (1, 2)):
            k = 3 - i - j
            mid = 0.5 * (xs[i] + xs[j])
            z = mid + 2e-3 * (mid - xs[k]) / np.linalg.norm(mid - xs[k])  # just outside the side
            self.assertTrue(np.any(tl.phase_amounts(tri, z) < 0))
            ls, _ = liquids_of(self.sis.equilibrio_TP(self.T, P_ATM, z))
            self.assertEqual(len(ls), 2)
            worst = max(worst, match(ls, [xs[i], xs[j]]))
        self.assertLess(worst, 2e-2)
        for side in tri['sides']:
            self.assertLess(side['nearestBranchEnd']['distance'], 1e-5)
            self.assertEqual(side['nearestBranchEnd']['end'], 'inestable')
        print(f"\nTP flash just outside the sides: two liquids within {worst:.1e} of the side vertices; "
              f"branch ends on sides within {max(s['nearestBranchEnd']['distance'] for s in tri['sides']):.1e}")

    def test_four_liquid_invariant_against_the_analytic_point(self):
        out, end = tl.sweep_temperature(self.sis, P_ATM, self.r['triangles'][0], 400.0)
        self.assertEqual(end['kind'], 'four_phase_point')
        pt = end['point']
        T_ref = self.a / (4 * math.log(2))
        self.assertLess(abs(pt['T'] - T_ref), 1e-8)
        self.assertEqual(pt['fourthPhase']['kind'], 'liquido')
        self.assertLess(float(np.max(np.abs(pt['fourthPhase']['composition'] - 1 / 3))), 1e-8)
        ref = [np.array(v) for v in ((2 / 3, 1 / 6, 1 / 6), (1 / 6, 2 / 3, 1 / 6), (1 / 6, 1 / 6, 2 / 3))]
        self.assertLess(match(pt['liquids'], ref), 1e-8)
        self.assertEqual(pt['certificate']['estado'], 'cumple')
        print(f"\nL-L-L-L invariant: T {pt['T']:.10f} K vs a / (4 ln 2) = {T_ref:.10f} K")


class SymmetricFourPhaseWithVapor(unittest.TestCase):
    def test_lllv_point_against_the_bubble_pressure_of_a_vertex(self):
        a = 3.6 * 300.0
        sis = system(a, a, a)
        e = sis.equilibrio_TP(300.0, P_ATM, np.array([1 / 3, 1 / 3, 1 / 3]))
        tri = tl.triangle(sis, 300.0, P_ATM, *liquids_of(e)[0])
        out, end = tl.sweep_temperature(sis, P_ATM, tri, 450.0)
        self.assertEqual(end['kind'], 'four_phase_point')
        pt = end['point']
        self.assertEqual(pt['fourthPhase']['kind'], 'vapor')

        # the first vertex to boil: the lowest T at which any permutation of (p, q, q) reaches P
        T_ref = brentq(lambda T: max(bubble_perm(sis, a, T)) - 1.0, 320.0, 340.0, xtol=1e-12)
        self.assertLess(abs(pt['T'] - T_ref), 1e-7)
        y_ref = None
        for perm in range(3):
            if abs(bubble_perm(sis, a, T_ref)[perm] - 1.0) < 1e-9:
                y_ref = bubble_perm(sis, a, T_ref, vapor=perm)
        self.assertLess(float(np.max(np.abs(pt['fourthPhase']['composition'] - y_ref))), 1e-7)
        self.assertEqual(pt['certificate']['estado'], 'cumple')
        print(f"\nL-L-L-V point: T {pt['T']:.8f} K vs vertex bubble {T_ref:.8f} K")


def bubble_perm(sis, a, T, vapor=None):
    """Bubble sums sum x_i gamma_i K_i of the three permuted vertices (or the vapor of one of them)."""
    p = symmetric_vertex(a / T)
    q = (1 - p) / 2
    K = np.array([s.Psat(T) * math.exp(s.vL * (P_ATM - s.Psat(T)) / (mz.R * T)) / P_ATM for s in sis.esp])
    sums = []
    for k in range(3):
        x = np.full(3, q)
        x[k] = p
        yk = x * np.exp(sis.liq.lngamma(T, x)) * K
        if vapor == k:
            return yk / yk.sum()
        sums.append(float(yk.sum()))
    return sums


class AsymmetricTriangle(unittest.TestCase):
    def test_invariance_flash_and_critical_end(self):
        T = 300.0
        sis = system(2.6 * T, 3.0 * T, 3.2 * T)
        r = tl.region(sis, T, P_ATM)
        self.assertEqual(len(r['triangles']), 1)              # every seed gave the same triangle
        tri = r['triangles'][0]
        for side in tri['sides']:
            self.assertLess(side['nearestBranchEnd']['distance'], 1e-5)
        worst = 0.0
        for w in ([0.2, 0.3, 0.5], [0.6, 0.2, 0.2], [0.1, 0.8, 0.1]):
            z = np.array(w) @ np.array(tri['liquids'])
            xs, ns = liquids_of(sis.equilibrio_TP(T, P_ATM, z))
            self.assertEqual(len(xs), 3)
            worst = max(worst, match(xs, tri['liquids']))
            self.assertLess(abs(sum(ns) - 1.0), 1e-12)
            back = sum(n * x for n, x in zip(ns, xs))
            self.assertLess(float(np.max(np.abs(back - z))), 1e-12)          # mass balance
        self.assertLess(worst, 1e-7)
        out, end = tl.sweep_temperature(sis, P_ATM, tri, 450.0, min_dT=1e-9)
        self.assertEqual(end['kind'], 'critical_end_point_bracket')
        last = out[-1]
        i, j = end['mergingLiquids']
        k = 3 - i - j
        xs, _ = liquids_of(sis.equilibrio_TP(last['T'] + 1e-2, P_ATM, 0.5 * (last['liquids'][i] + last['liquids'][k])))
        self.assertEqual(len(xs), 2)                                             # above it: two liquids
        print(f"\nasymmetric: flash inside within {worst:.1e}; critical end point bracket at "
              f"{last['T']:.6f} K, gap {end['gap']:.1e}")


class UnifacNoThreeLiquids(unittest.TestCase):
    def test_water_benzene_toluene(self):
        sis = mz.Sistema('unifac-original-lle-public', [W, BZ, TO])
        r = tl.region(sis, 298.15, P_ATM)
        self.assertEqual(r['triangles'], [])
        self.assertEqual(r['uncertified'], [])
        self.assertGreater(len(r['branches']), 0)



class ReviewRegressions(unittest.TestCase):
    """Codex's three-liquid review of 30 October (.tmp/codex-f8b-review/three-liquid-probe.py): both cases
    failed on the first delivery."""

    @classmethod
    def setUpClass(cls):
        cls.a, cls.T, cls.P = 900.0, 310.0, 120000.0
        cls.sis = system(cls.a, cls.a, cls.a)
        p = symmetric_vertex(cls.a / cls.T)
        q = (1 - p) / 2
        cls.tri = tl.triangle(cls.sis, cls.T, cls.P, *[np.array(v) for v in ((p, q, q), (q, p, q), (q, q, p))])
        assert cls.tri['certificate']['estado'] == 'cumple'

    def test_sweep_recertifies_the_seed(self):
        import copy
        for defect in ('mu', 'normalization', 'phase_distinction'):
            bad = copy.deepcopy(self.tri)                  # still carries the seed's cached 'cumple'
            if defect == 'mu':
                bad['liquids'][0] = bad['liquids'][0] + np.array([0.01, -0.005, -0.005])
            elif defect == 'normalization':
                bad['liquids'][0] = bad['liquids'][0] * 1.01
            else:
                bad['liquids'][1] = bad['liquids'][0].copy()
            for T_end in (self.T, self.T + 0.1):
                out, end = tl.sweep_temperature(self.sis, self.P, bad, T_end, dT=0.1)
                self.assertEqual(end['kind'], 'seed_not_certified')
                self.assertEqual(len(out), 1)
                self.assertIsNot(out[0], bad)
                self.assertEqual(out[0]['certificate']['estado'], 'no_cumple')
        out, end = tl.sweep_temperature(self.sis, self.P, self.tri, self.T)    # a valid seed is recertified too
        self.assertEqual(out[0]['certificate']['estado'], 'cumple')
        self.assertIsNot(out[0]['certificate'], self.tri['certificate'])

    def test_triangle_rejects_pressures_outside_the_domain(self):
        with self.assertRaises(mz.FueraDeAlcance):
            tl.triangle(self.sis, self.T, 1e6, *self.tri['liquids'])
        out, end = tl.sweep_temperature(self.sis, 1e6, self.tri, self.T + 1.0)
        self.assertEqual((out, end['kind']), ([], 'domain_limit'))


if __name__ == '__main__':
    unittest.main()
