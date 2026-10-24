"""F9-R6: the faster ternary stability refinement and the seeded UV path give the published answers of the
methods they replace.

1. Ternary liquid stability: each of the 12 lowest lattice seeds is refined by a Newton descent on tm*
   instead of Nelder-Mead. The reference here is the earlier Nelder-Mead refinement from the same seeds
   (the shared quantity is tm itself): same trial count, tm per seed within 1e-12, composition within 1e-6,
   for a single-liquid reference that splits, an equilibrium reference and a 1e-300 water trace.
2. UV: the seeded Newton UV path returns the certified state whose U and V come from a TP state, for the
   ternary vapor case that the nested search could not finish (F9-R6 benchmark) and an eight-species
   vapor-liquid case; a liquid that fills the volume is still rejected with the same reason.
Run: python tests/test_unifac_performance_paths.py (about 1 min).
"""
import math
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import mezclas as mz

warnings.filterwarnings('ignore')
ORIGINAL = 'unifac-original-public'
W, E, BZ, TO, ME, AC, EA, B = ('7732-18-5', '64-17-5', '71-43-2', '108-88-3', '67-56-1', '67-64-1',
                               '141-78-6', '71-36-3')
P = 101325.0


def nelder_mead_reference(system, T, mu_ref, idx):
    """The pre-R6 refinement: Nelder-Mead in softmax coordinates from the same 12 lattice seeds."""
    N = 60
    points = []
    for i in range(N + 1):
        for j in range(N + 1 - i):
            w = np.array([i, j, N - i - j], dtype=float) + 1e-6
            points.append(w / w.sum())
    tm = system._tm_liquido_lote(T, P, np.array(points), mu_ref, idx)
    seeds = [w for _, w in sorted(zip(tm.tolist(), points), key=lambda z: z[0])[:12]]

    def f(zz):
        w = mz._softmax3(zz)
        return math.inf if not np.all(w > 0) else system._tm_liquido(T, P, w, mu_ref, idx)
    out = []
    for w0 in seeds:
        r = minimize(f, np.log(w0[:2] / w0[2]), method='Nelder-Mead',
                     options={'xatol': 1e-11, 'fatol': 1e-15, 'maxiter': 4000})
        out.append((mz._softmax3(r.x), float(r.fun)))
    return out


class TernaryStability(unittest.TestCase):
    def compare(self, species, T, z, reference):
        system = mz.Sistema(ORIGINAL, species)
        idx = [0, 1, 2]
        z = np.asarray(z, dtype=float)
        if reference == 'feed':
            mu_ref = system.mu('liquido', T, P, z / z.sum(), idx)
        else:
            phase = system.equilibrio_TP(T, P, z).fases[0]
            mu_ref = system.mu(phase.tipo, T, P, phase.x[idx], idx)
        trials = [t for t in system.prueba_estabilidad(T, P, mu_ref, idx, incluir_vapor=False)]
        expected = nelder_mead_reference(system, T, mu_ref, idx)
        self.assertEqual(len(trials), len(expected))
        for (kind, w, tm), (w_ref, tm_ref) in zip(trials, expected):
            self.assertEqual(kind, 'liquido')
            self.assertLessEqual(abs(tm - tm_ref), 1e-12)
            self.assertLessEqual(float(np.max(np.abs(np.asarray(w) - w_ref))), 1e-6)
            self.assertTrue(np.all(np.asarray(w) > 0))

    def test_unstable_single_liquid(self):
        self.compare([W, E, BZ], 300.0, [0.45, 0.45, 0.10], 'feed')

    def test_equilibrium_reference(self):
        self.compare([BZ, W, E], 300.0, [0.45, 0.45, 0.10], 'state')

    def test_trace_reference(self):
        self.compare([BZ, W, E], 345.0, [0.5, 1e-300, 0.5], 'state')


class SeededUV(unittest.TestCase):
    def check(self, species, z):
        system = mz.Sistema(ORIGINAL, species)
        n = np.asarray(z, dtype=float)
        tp = system.equilibrio_TP(350.0, P, n)
        fast = mz._uv_acotado(system, tp.U, tp.V, n)
        self.assertIsNotNone(fast, 'the seeded Newton UV path must close this state')
        state = system.equilibrio_UV(tp.U, tp.V, n)
        self.assertEqual(state.especificacion, 'UV')
        self.assertAlmostEqual(state.T, 350.0, delta=1e-8)
        self.assertLessEqual(abs(state.P - P) / P, 1e-10)
        self.assertEqual(sorted(f.tipo for f in state.fases), sorted(f.tipo for f in tp.fases))
        for key, (residual, tolerance, _) in state.verificaciones.items():
            self.assertLessEqual(residual, tolerance, key)

    def test_ternary_vapor(self):
        self.check([W, E, BZ], [1 / 3] * 3)

    def test_eight_species_vapor_liquid(self):
        self.check([W, E, BZ, TO, ME, AC, EA, B], [1 / 8] * 8)

    def test_liquid_fills_volume_rejected(self):
        system = mz.Sistema(ORIGINAL, [W, E])
        n = np.array([0.5, 0.5])
        tp = system.equilibrio_TP(300.0, P, n)
        with self.assertRaises(mz.FueraDeAlcance) as raised:
            system.equilibrio_UV(tp.U, tp.V, n)
        self.assertEqual(raised.exception.motivo, 'no_soportado')


if __name__ == '__main__':
    unittest.main()
