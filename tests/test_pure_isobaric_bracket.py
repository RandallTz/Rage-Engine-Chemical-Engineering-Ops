"""F9-R7 regression: isobaric (PH/UP) closure of a single present species next to its boiling plateau.

Before the fix, `Sistema.equilibrio_isobaro` bracketed the one-phase side at Ts(1 -+ 1e-9), so every
one-phase state between that point and Ts (a target within about 1e-9 |H| of the plateau ends) raised
FueraDeAlcance. The common compiler's event probes land in that band, so heating pure liquid toluene to
boiling aborted. The bracket now ends at Ts itself, evaluated with the phase of its side.

Independent reference: the one-phase state at a target y = y_end + dy next to a plateau end is
T = Ts + dy / c, with Ts from `T_saturacion` and the heat capacity c of that phase from a central
difference of TP evaluations 1e-3 K away (a different code path from the isobaric search; the
linearization error is below 1e-12 K for these dy). A species declared with an exact zero amount must
give the same state as the pure system. Run from the repository root:
    python tests/test_pure_isobaric_bracket.py
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
CASES = (('mezcla-ideal', '108-88-3'), ('mezcla-ideal', '71-43-2'), ('nrtl-chemsep', '64-17-5'),
         ('unifac-dortmund-public', '7732-18-5'))
RELATIVE = (1e-9, 1e-11, 1e-13)           # |dy| / |y_end|: all inside the band the old bracket excluded


def phase_property(system, T, side, prop):
    state = system._puro_TP(T, P, np.array([1.0]), [0], 'TP', lado=side)
    return state.H if prop == 'h' else state.U


class PureIsobaricBracket(unittest.TestCase):
    def check_side(self, system, n, side, prop):
        Ts = system.T_saturacion(P, 0)
        end = phase_property(system, Ts, side, prop)
        c = (phase_property(system, Ts + 1e-3, side, prop) - phase_property(system, Ts - 1e-3, side, prop)) / 2e-3
        sign = -1.0 if side == 'liquido' else 1.0
        for rel in RELATIVE:
            dy = sign * rel * abs(end)
            target = end + dy
            solve = system.equilibrio_PH if prop == 'h' else system.equilibrio_UP
            state = solve(P, target * n.sum(), n)
            with self.subTest(side=side, prop=prop, rel=rel):
                self.assertEqual([f.tipo for f in state.fases], [side])
                self.assertAlmostEqual(state.T, Ts + dy / c, delta=1e-9 + 1e-12 * Ts)
                self.assertTrue(state.T <= Ts if side == 'liquido' else state.T >= Ts)
                value = state.H if prop == 'h' else state.U
                self.assertLessEqual(abs(value - target * n.sum()), 1e-10 * abs(target * n.sum()))

    def test_one_phase_states_next_to_the_plateau(self):
        for package, cas in CASES:
            system = mz.Sistema(package, [cas])
            for side in ('liquido', 'vapor'):
                for prop in ('h', 'u'):
                    with self.subTest(package=package, cas=cas):
                        self.check_side(system, np.array([1.0]), side, prop)

    def test_plateau_follows_the_lever_rule(self):
        system = mz.Sistema('mezcla-ideal', ['108-88-3'])
        Ts = system.T_saturacion(P, 0)
        hL, hV = (phase_property(system, Ts, side, 'h') for side in ('liquido', 'vapor'))
        for beta in (1e-12, 1e-6, 0.052126623960, 0.5, 1 - 1e-6):
            state = system.equilibrio_PH(P, 0.92 * ((1 - beta) * hL + beta * hV), np.array([0.92]))
            vapor = sum(f.n for f in state.fases if f.tipo == 'vapor')
            with self.subTest(beta=beta):
                self.assertEqual(state.T, Ts)
                self.assertAlmostEqual(vapor / 0.92, beta, delta=1e-12)

    def test_declared_zero_species_matches_the_pure_system(self):
        pure = mz.Sistema('mezcla-ideal', ['108-88-3'])
        binary = mz.Sistema('mezcla-ideal', ['71-43-2', '108-88-3'])
        Ts = pure.T_saturacion(P, 0)
        hL = phase_property(pure, Ts, 'liquido', 'h')
        for rel in (1e-9, 1e-12, 0.0, -1e-6):        # below, at and above (plateau) the saturated liquid
            H = 0.92 * hL * (1 + rel)
            a = pure.equilibrio_PH(P, H, np.array([0.92]))
            b = binary.equilibrio_PH(P, H, np.array([0.0, 0.92]))
            with self.subTest(rel=rel):
                self.assertEqual(sorted(f.tipo for f in a.fases), sorted(f.tipo for f in b.fases))
                self.assertAlmostEqual(a.T, b.T, delta=1e-12 * a.T)


if __name__ == '__main__':
    unittest.main(verbosity=2)
