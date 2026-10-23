"""F9-R2 regression: isobaric (PH/UP) equilibrium of near-pure mixtures on a boiling plateau.

Independent reference: the exact pure feed, solved by the lever rule at the pure-component
saturation temperature (a different code path from the mixture search). As a trace vanishes,
the mixture state must approach that limit continuously; no tolerance is relaxed.

Before the fix, PH at P = 101325 Pa with an ethanol trace <= 1e-7 in water was rejected
("la búsqueda en T no converge ni es una meseta"): the two-phase band becomes narrower than
the floating-point resolution of T. Run from the repository root:
    python tests/test_near_pure_isobaric_flash.py
"""
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import mezclas as mz

P = 101325.0
ETHANOL, WATER = '64-17-5', '7732-18-5'
PACKAGES = ('unifac-original-public', 'unifac-dortmund-public')
TRACES = (1e-7, 1e-9, 1e-12, 1e-16, 1e-100, 1e-200, 1e-300)


def certified(test, state):
    for key, (residual, tolerance, _) in state.verificaciones.items():
        test.assertTrue(np.isfinite(residual) and residual <= tolerance, f'{key}: {residual} > {tolerance}')
    for phase in state.fases:
        test.assertTrue(np.all(np.isfinite(phase.x)) and np.all(phase.x >= 0) and phase.n > 0)


class NearPureIsobaricFlash(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {}
        for package in PACKAGES:
            system = mz.Sistema(package, [ETHANOL, WATER])
            lo, hi = system.T_rango
            liquid = system.equilibrio_TP(0.5 * (lo + hi), P, np.array([0.0, 1.0]))
            H = liquid.H + 0.05 * abs(liquid.H) + 50.0          # inside the water boiling plateau
            pure = system.equilibrio_PH(P, H, np.array([0.0, 1.0]))
            vapor = sum(f.n for f in pure.fases if f.tipo == 'vapor')
            cls.cases[package] = (system, H, pure, vapor)

    def test_reference_is_the_pure_plateau(self):
        for package, (system, H, pure, vapor) in self.cases.items():
            self.assertAlmostEqual(pure.T, system.T_saturacion(P, 1), delta=1e-9)
            self.assertTrue(0.0 < vapor < 1.0)
            self.assertLessEqual(abs(pure.H - H), 1e-10 * abs(H))

    def test_ph_trace_converges_to_the_pure_limit(self):
        for package, (system, H, pure, vapor0) in self.cases.items():
            for trace in TRACES:
                with self.subTest(package=package, trace=trace):
                    z = np.array([trace, 1.0])
                    state = system.equilibrio_PH(P, H, z)
                    certified(self, state)
                    self.assertLessEqual(abs(state.H - H), 1e-10 * max(abs(H), mz.R * state.T * z.sum()))
                    self.assertEqual(sorted(f.tipo for f in state.fases), ['liquido', 'vapor'])
                    # Boiling-range width and lever shift are first order in the trace.
                    self.assertLessEqual(abs(state.T - pure.T), 1e3 * trace + 1e-9)
                    vapor = sum(f.n for f in state.fases if f.tipo == 'vapor') / z.sum()
                    self.assertLessEqual(abs(vapor - vapor0), 10 * trace + 1e-9)
                    np.testing.assert_allclose(state.n, z, rtol=0, atol=1e-12 * z.sum())

    def test_up_uses_the_same_isobaric_path(self):
        system, H, pure, vapor0 = self.cases[PACKAGES[0]]
        U = pure.U
        state = system.equilibrio_UP(P, U, np.array([1e-12, 1.0]))
        certified(self, state)
        self.assertLessEqual(abs(state.T - pure.T), 1e-8)
        self.assertLessEqual(abs(state.U - U), 1e-10 * abs(U))

    def test_seeded_dynamic_flash_with_vanishing_trace(self):
        # The dynamic coordinator seeds from the previous state; the old seed scaling underflowed (p*nz).
        system, H, pure, vapor0 = self.cases[PACKAGES[0]]
        lo, hi = system.T_rango
        z = np.array([1e-300, 1.0])
        seed = system.equilibrio_TP(0.5 * (lo + hi), P, z)
        state = system.flash_rapido('PH', P, H, z, seed)
        certified(self, state)
        self.assertLessEqual(abs(state.T - pure.T), 1e-9)

    def test_binary_stability_reports_an_edge_minimum(self):
        # A near-pure liquid has its tangent-plane minimum beyond the logit grid (|u| = 34).
        system = self.cases[PACKAGES[0]][0]
        T = system.T_saturacion(P, 1) - 1.0
        x = np.array([1e-20, 1.0]) / (1.0 + 1e-20)
        mu_ref = system.mu('liquido', T, P, x, [0, 1])
        liquids = [p for p in system.prueba_estabilidad(T, P, mu_ref, [0, 1], incluir_vapor=False) if p[0] == 'liquido']
        self.assertTrue(liquids, 'the liquid trial set must not be empty')
        best = min(liquids, key=lambda p: p[2])
        self.assertTrue(np.all(best[1] > 0) and abs(best[1].sum() - 1.0) < 1e-12)
        # The grid alone stops at w1 ~ 2e-15; the refined minimum must resolve the 1e-20 trace scale.
        self.assertLess(best[1][0], 1e-18)
        self.assertGreaterEqual(best[2], -mz.TOL_TM)          # the feed liquid itself is stable

    def test_certification_tolerances_are_not_relaxed(self):
        self.assertEqual((mz.TOL_TM, mz.TOL_MU), (1e-9, 1e-10))


if __name__ == '__main__':
    unittest.main()
