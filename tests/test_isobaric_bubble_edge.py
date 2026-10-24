"""A PH target just past a bubble point is solved, not rejected.

Found while retiring the legacy v1 assembly (dec-r5-legacy-v1): after R5 the common solver probes events with cold
certified PH closures, and validar_capa_unifac failed on water/ethanol/ethyl acetate/methanol (original UNIFAC,
0.25 mol each, 101325 Pa, H = -35494.16088 J). There the certified TP states on either side of the bubble point
differ by about 2.6e-5 J (the TM_INTENTO/N_AUSENTE band), the target lies inside that gap and neither side meets the
1e-10 relative tolerance; the phase-amount Newton fallback started from an equal split (0.5 mol of vapor) and
failed. Seeded with the two-phase side's own amounts, and with its energy residual on the PH acceptance scale
(max(|H|, RT n); for Dortmund the RT n scale lies below the rounding of H), it finds about 1e-10 mol of vapor.
Run: python tests/test_isobaric_bubble_edge.py
"""
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import mezclas as mz

warnings.filterwarnings('ignore')
CAS = ['7732-18-5', '64-17-5', '141-78-6', '67-56-1']
P = 101325.0


class BubbleEdge(unittest.TestCase):
    def test_target_inside_the_bubble_point_band(self):
        for package, H in (('unifac-original-public', -35494.16088295461), ('unifac-dortmund-public', -34511.1586094273)):
            with self.subTest(package=package):
                self.check_edge(mz.Sistema(package, CAS), H)

    def check_edge(self, system, H):
        n = np.full(4, 0.25)
        state = system.equilibrio_PH(P, H, n)
        self.assertLessEqual(abs(state.H - H), 1e-10 * abs(H))
        for key, (residual, tolerance, _) in state.verificaciones.items():
            self.assertLessEqual(residual, tolerance, key)
        self.assertEqual(sorted(f.tipo for f in state.fases), ['liquido', 'vapor'])
        vapor = next(f.n for f in state.fases if f.tipo == 'vapor')
        self.assertLess(vapor, 1e-8)
        # the TP flash at the published T reproduces the state (independent of the PH search)
        tp = system.equilibrio_TP(state.T, P, n)
        self.assertLessEqual(abs(tp.H - state.H), 1e-4)

    def test_neighbouring_targets_still_solve(self):
        system = mz.Sistema('unifac-original-public', CAS)
        n = np.full(4, 0.25)
        for H in (-35600.0, -35494.16088295461 - 1e-3, -35494.16088295461 + 1e-3, -30000.0):
            with self.subTest(H=H):
                state = system.equilibrio_PH(P, H, n)
                self.assertLessEqual(abs(state.H - H), 1e-10 * max(abs(H), mz.R * state.T))


if __name__ == '__main__':
    unittest.main()
