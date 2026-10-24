"""F8: ternary liquid-liquid equilibrium at fixed T and P (core/ternary_liquid_liquid.py): binodal and tie lines
by pseudo-arclength continuation, plait point, binary-edge ends and the liquid-liquid-vapor triangle.

References, each reached by another path than the continuation:
1. A Margules liquid g^E/RT = A x0 x1 with species 2 ideal (A = 900 K / T): by the 0-1 symmetry its plait point is
   x0 = x1 = 1/A exactly, and on the edge x2 = 0 the pair is the binary Margules binodal ln((1-x)/x) = A(1-2x).
2. The package's certified TP flash (Gibbs minimization) at feeds on traced tie lines and inside the triangle.
3. The binary branch of core/coexistencia_ll.py (a Pxy slice of the edge pair, whose compositions do not depend
   on P) at the binary-edge end.
Run: python tests/test_ternary_liquid_liquid.py (about 1 min).
"""
import math
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import coexistencia_ll as ll
from core import mezclas as mz
from core import ternary_liquid_liquid as tl

warnings.filterwarnings('ignore')
BZ, TO, AC, W, E = '71-43-2', '108-88-3', '67-64-1', '7732-18-5', '64-17-5'
P = 101325.0
UNIFAC = 'unifac-original-public'


def _margules_lngamma(A, F):
    return np.column_stack([A * F[:, 1] * (1 - F[:, 0]), A * F[:, 0] * (1 - F[:, 1]), -A * F[:, 0] * F[:, 1]])


class Margules3:
    """Test liquid: g^E/RT = (a/T) x0 x1; subsets keep the same g^E."""
    nombre = 'Margules ternary (test)'

    def __init__(self, a, idx=(0, 1, 2)):
        self.a, self.idx = a, list(idx)

    def _full(self, X):
        F = np.zeros((X.shape[0], 3))
        F[:, self.idx] = X
        return F

    def gE_RT(self, T, x):
        F = self._full(np.asarray(x)[None, :])[0]
        return self.a / T * F[0] * F[1]

    def lngamma_lote(self, T, X):
        return _margules_lngamma(self.a / T, self._full(np.asarray(X, dtype=float)))[:, self.idx]

    def lngamma(self, T, x):
        return self.lngamma_lote(T, np.asarray(x, dtype=float)[None, :])[0]

    def subconjunto(self, idx):
        return Margules3(self.a, [self.idx[i] for i in idx])


def margules_system(a):
    system = mz.Sistema('mezcla-ideal', [BZ, TO, AC])
    system.liq = Margules3(a)
    system.__dict__.pop('_subs', None)
    return system


def ends(branch, kind):
    return [e for e in branch.ends if e['tipo'] == kind]


class MargulesReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.T, cls.A = 300.0, 3.0
        cls.branches = tl.trace(margules_system(cls.A * 300.0), cls.T, P, tl.PROFILES['exploratoria'])

    def test_plait_point_and_binary_edge(self):
        self.assertEqual(len(self.branches), 1)
        b = self.branches[0]
        self.assertTrue(all(p['cert']['estado'] == 'cumple' for p in b.points))
        plait = ends(b, 'pliegue')
        self.assertEqual(len(plait), 1)
        self.assertLessEqual(float(np.max(np.abs(plait[0]['x'] - [1 / self.A, 1 / self.A, 1 - 2 / self.A]))), 1e-6)
        self.assertTrue(plait[0]['estable'])
        edge = ends(b, 'borde_binario')
        self.assertEqual(len(edge), 1)
        self.assertEqual(edge[0]['especieAusente'], 2)
        x = min(edge[0]['xa'][0], edge[0]['xb'][0])
        self.assertLessEqual(abs(math.log((1 - x) / x) - self.A * (1 - 2 * x)), 1e-10)
        self.assertEqual(edge[0]['cert']['estado'], 'cumple')

    def test_tie_lines_are_mirror_images(self):
        # swapping species 0 and 1 maps one liquid of a tie line onto the other
        for p in self.branches[0].points:
            self.assertLessEqual(float(np.max(np.abs(p['xa'][[1, 0, 2]] - p['xb']))), 1e-8)


class BenzeneWaterEthanol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system = mz.Sistema(UNIFAC, [BZ, W, E])
        cls.branches = tl.trace(cls.system, 300.0, P, tl.PROFILES['exploratoria'])

    def test_tie_lines_match_the_tp_flash(self):
        self.assertEqual(len(self.branches), 1)
        b = self.branches[0]
        self.assertTrue(all(p['cert']['estado'] == 'cumple' for p in b.points))
        # Within about 0.004 of the plait point the flash may publish one liquid inside its certification band
        # (tm of order -1e-11 > -TOL_TM); the comparison uses tie lines whose liquids differ by more than 0.02.
        wide = [p for p in b.points if float(np.max(np.abs(p['xa'] - p['xb']))) > 0.02]
        for p in wide[::max(1, len(wide) // 8)]:
            z = 0.5 * (p['xa'] + p['xb'])
            state = self.system.equilibrio_TP(300.0, P, z)
            liquids = [f.x for f in state.fases if f.tipo == 'liquido']
            self.assertEqual(len(state.fases), 2)
            self.assertEqual(len(liquids), 2)
            for x in (p['xa'], p['xb']):
                self.assertLessEqual(min(float(np.max(np.abs(x - q))) for q in liquids), 1e-7)

    def test_ends_plait_point_and_binary_edge(self):
        b = self.branches[0]
        plait = ends(b, 'pliegue')
        self.assertEqual(len(plait), 1)
        self.assertLessEqual(plait[0]['residuo'], 1e-6)
        self.assertTrue(plait[0]['estable'])
        last = min(b.points, key=lambda p: float(np.max(np.abs(p['xa'] - p['xb']))))
        self.assertLessEqual(float(np.max(np.abs(0.5 * (last['xa'] + last['xb']) - plait[0]['x']))), 0.02)
        edge = ends(b, 'borde_binario')
        self.assertEqual(len(edge), 1)
        self.assertEqual(edge[0]['especieAusente'], 2)
        binary = ll.trace(mz.Sistema(UNIFAC, [BZ, W]), 'Pxy', 300.0, ll.PROFILES['exploratoria'])
        self.assertEqual(len(binary), 1)
        pair = binary[0].points[-1]
        got = sorted([edge[0]['xa'][0], edge[0]['xb'][0]])
        self.assertLessEqual(abs(got[0] - pair['xa']), 1e-8)
        self.assertLessEqual(abs(got[1] - pair['xb']), 1e-8)

    def test_three_phase_triangle_matches_the_tp_flash(self):
        b = tl.trace(self.system, 340.0, P, tl.PROFILES['exploratoria'])
        tri = [e for br in b for e in ends(br, 'tres_fases')]
        self.assertEqual(len(tri), 1)
        self.assertEqual(tri[0]['cert']['estado'], 'cumple')
        z = (tri[0]['xa'] + tri[0]['xb'] + tri[0]['y']) / 3
        state = self.system.equilibrio_TP(340.0, P, z)
        self.assertEqual(sorted(f.tipo for f in state.fases), ['liquido', 'liquido', 'vapor'])
        for x in (tri[0]['xa'], tri[0]['xb'], tri[0]['y']):
            self.assertLessEqual(min(float(np.max(np.abs(x - f.x))) for f in state.fases), 1e-7)


if __name__ == '__main__':
    unittest.main()
