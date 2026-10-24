"""F9-R9: the TP flash resolves a phase of order 1e-12..1e-10 mol at a bubble point.

Before the repair, Dortmund UNIFAC water/ethanol/ethyl acetate/methanol (0.25 each, 101325 Pa) gave, within 1e-10 K
above its bubble point, vapor amounts scattered by up to 9e-10 mol around the physical line n_V = (dn_V/dT)(T - T_b)
(H errors up to 3e-5 J, above the PH tolerance 1e-10|H|), with mu residuals of 1e-11..7e-11 accepted below TOL_MU.
Cause: in the phase-split Newton the own-phase Jacobian blocks, computed by differences, carried rounding noise along
the total-amount direction, where the exact derivative is zero (mu is homogeneous of degree zero in the amounts of its
phase); for a tiny phase that noise exceeded the true coupling through the other phase. The identity is now imposed.

Reference (independent of the repair): the vapor amount must be linear in T near T_b, with the line through the states
2e-8 and 1e-7 K away, where the flash was already accurate (amount errors below 1e-12 mol) and the curvature is
negligible; the scatter about the line and the mu residual must be small.
Run: python tests/test_bubble_edge_h_noise.py (about 1 min).
"""
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import mezclas as mz

warnings.filterwarnings('ignore')
P = 101325.0


def bubble(system, n, lo, hi):
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if len(system.equilibrio_TP(m, P, n).fases) > 1:
            hi = m
        else:
            lo = m
    return hi


def vapor(state):
    return sum(f.n for f in state.fases if f.tipo == 'vapor')


class BubbleEdgeNoise(unittest.TestCase):
    def check(self, package, cas, n, lo, hi):
        system = mz.Sistema(package, cas)
        Tb = bubble(system, n, lo, hi)
        a, b = system.equilibrio_TP(Tb + 2e-8, P, n), system.equilibrio_TP(Tb + 1e-7, P, n)
        slope = (vapor(b) - vapor(a)) / (b.T - a.T)
        offset = vapor(a) - slope * (a.T - Tb)
        for dT in np.linspace(1e-11, 2e-10, 12):
            state = system.equilibrio_TP(Tb + dT, P, n)
            self.assertEqual(sorted(f.tipo for f in state.fases), ['liquido', 'vapor'])
            self.assertLessEqual(abs(vapor(state) - (offset + slope * dT)), 5e-12)
            self.assertLessEqual(state.verificaciones['equilibrio'][0], 1e-13)
            # the H error of that amount is far below the PH tolerance 1e-10 |H|
            self.assertLessEqual(abs(vapor(state) - (offset + slope * dT)) * 5e4, 1e-10 * abs(state.H))

    def test_four_species_dortmund(self):
        self.check('unifac-dortmund-public', ['7732-18-5', '64-17-5', '141-78-6', '67-56-1'], np.full(4, .25),
                   341.0, 343.0)

    def test_four_species_original(self):
        self.check('unifac-original-public', ['7732-18-5', '64-17-5', '141-78-6', '67-56-1'], np.full(4, .25),
                   341.0, 343.0)

    def test_binary(self):
        self.check('unifac-original-public', ['64-17-5', '7732-18-5'], np.array([.5, .5]), 340.0, 360.0)


if __name__ == '__main__':
    unittest.main()
