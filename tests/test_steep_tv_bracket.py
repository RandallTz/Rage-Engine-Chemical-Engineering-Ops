"""F9-R7 regression: TV and cold UV closures where V(P) is steep, just below a bubble point.

Before the fix, `Sistema.equilibrio_TV` with the loose tolerance used inside the cold `equilibrio_UV` search
(rtol 1e-7 in ln P) left a volume error above its acceptance threshold when little vapor is present
(d ln V / d ln P of order 1e2 to 1e5), took it for an invariant coexistence, found none and raised
FueraDeAlcance. The common compiler certifies published samples with that cold UV, so every rigid two-phase
mixture volume near its bubble point aborted. The loose bracket is now narrowed before testing for a jump.

Independent reference, written here: the ideal package is Raoult's law with the Poynting factor,
K_i = Psat_i(T) exp(vL_i (P - Psat_i) / (R T)) / P, an incompressible liquid and an ideal-gas vapor. For a chosen
P below the bubble pressure, Rachford-Rice gives the vapor fraction and V = sum(x_i vL_i) nL + nV R T / P.
TV(T, V) must return that P, and cold UV(U, V) must return T. Run from the repository root:
    python tests/test_steep_tv_bracket.py
"""
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import mezclas as mz

warnings.filterwarnings('ignore')
BENZENE, TOLUENE = '71-43-2', '108-88-3'


def raoult_state(system, T, P, n):
    """(vapor amount, V) of the ideal package at T, P from Raoult-Poynting and Rachford-Rice."""
    Psat = np.array([e.Psat(T) for e in system.esp])
    K = Psat * np.exp(system.vL * (P - Psat) / (mz.R * T)) / P
    z = n / n.sum()
    rr = lambda b: float(np.sum(z * (K - 1) / (1 + b * (K - 1))))
    beta = brentq(rr, 0.0, 1.0, xtol=1e-300, rtol=1e-15) if rr(0.0) > 0 > rr(1.0) else (0.0 if rr(0.0) <= 0 else 1.0)
    x = z / (1 + beta * (K - 1))
    nL, nV = (1 - beta) * n.sum(), beta * n.sum()
    return nV, nL * float(x @ system.vL) + nV * mz.R * T / P


def bubble_pressure(system, T, n):
    z = n / n.sum()
    g = lambda P: float(np.sum(z * np.array([e.Psat(T) for e in system.esp]) *
                               np.exp(system.vL * (P - np.array([e.Psat(T) for e in system.esp])) / (mz.R * T)) / P)) - 1
    return brentq(g, 100.0, 5e5, xtol=1e-300, rtol=1e-15)


class SteepTVBracket(unittest.TestCase):
    def test_tv_and_cold_uv_just_below_the_bubble_point(self):
        system = mz.Sistema('mezcla-ideal', [BENZENE, TOLUENE])
        for n in (np.array([0.2, 0.8]), np.array([0.5, 0.5])):
            for T in (300.0, 313.357789992, 340.0):
                Pb = bubble_pressure(system, T, n)
                for gap in (1e-2, 1e-3, 4e-3 * 1e-1, 1e-4):          # (Pb - P) / Pb: vapor fraction ~ gap
                    P = Pb * (1 - gap)
                    nV, V = raoult_state(system, T, P, n)
                    with self.subTest(n=n.tolist(), T=T, gap=gap):
                        self.assertGreater(nV, 0.0)
                        for rtol in (1e-7, 1e-15):
                            e = system.equilibrio_TV(T, V, n, rtol=rtol)
                            self.assertAlmostEqual(e.P / P, 1.0, delta=max(1e-9, 10 * rtol))
                        exact = system.equilibrio_TV(T, V, n)
                        vapor = sum(f.n for f in exact.fases if f.tipo == 'vapor')
                        self.assertAlmostEqual(vapor / nV, 1.0, delta=1e-7)
                        cold = system.equilibrio_UV(exact.U, V, n)
                        self.assertAlmostEqual(cold.T, T, delta=1e-7)
                        self.assertAlmostEqual(cold.P / P, 1.0, delta=1e-7)


if __name__ == '__main__':
    unittest.main(verbosity=2)
