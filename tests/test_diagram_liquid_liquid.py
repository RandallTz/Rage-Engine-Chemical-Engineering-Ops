"""F8: binary liquid-liquid branches, the liquid-liquid critical point (the binodal's fold) and the
liquid-liquid-vapor three-phase point (core/coexistencia_ll.py, published in liquidoLiquido).

References, each reached by another path than the continuation:
1. A two-suffix Margules liquid, g^E/RT = (a/T) x0 x1, on ideal-vapor benzene/toluene data: its binodal is
   symmetric and satisfies ln((1 - x)/x) = (a/T)(1 - 2x) exactly, and its critical point is T = a/2, x = 1/2.
2. The package's certified TP flash (Gibbs minimization and polish) at points of the traced branch.
3. The L-V tracer's meeting with the competing liquid (core/diagramas_equilibrio.py) at the three-phase T.
4. Slice consistency: a Pxy slice at T* gives the three-phase P*; the Txy slice at P* gives back T*.
Run: python tests/test_diagram_liquid_liquid.py (about 1 min).
"""
import math
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import motor_diagramas as service
from core import coexistencia_ll as ll
from core import diagramas_equilibrio as dg
from core import mezclas as mz

warnings.filterwarnings('ignore')
W, B, BZ, TO, E = '7732-18-5', '71-36-3', '71-43-2', '108-88-3', '64-17-5'
P = 101325.0
LLE = 'nrtl-lle-agua-butanol'


class Margules:
    """Test liquid: g^E/RT = (a/T) x0 x1."""
    nombre = 'Margules (test)'

    def __init__(self, a):
        self.a = a

    def gE_RT(self, T, x):
        return self.a / T * x[0] * x[1]

    def lngamma(self, T, x):
        return self.lngamma_lote(T, np.asarray(x, dtype=float)[None, :])[0]

    def lngamma_lote(self, T, X):
        A = self.a / T
        return np.column_stack([A * X[:, 1] ** 2, A * X[:, 0] ** 2])

    def subconjunto(self, idx):
        return self


def margules_system(a):
    system = mz.Sistema('mezcla-ideal', [BZ, TO])
    system.liq = Margules(a)
    system.__dict__.pop('_subs', None)
    return system


def trace(system, cut, fixed):
    return ll.trace(system, cut, fixed, ll.PROFILES['exploratoria'])


class MargulesReference(unittest.TestCase):
    def test_binodal_and_critical_point(self):
        a = 660.0
        branches = trace(margules_system(a), 'Txy', P)
        self.assertEqual(len(branches), 1)
        branch = branches[0]
        self.assertGreater(len(branch.points), 10)
        for p in branch.points:
            self.assertEqual(p['cert']['estado'], 'cumple')
            x = p['xa']
            self.assertLessEqual(abs(p['xa'] + p['xb'] - 1.0), 1e-10)
            self.assertLessEqual(abs(math.log((1 - x) / x) - a / p['T'] * (1 - 2 * x)), 1e-10)
        critical = [e for e in branch.ends if e['tipo'] == 'critico']
        self.assertEqual(len(critical), 1)
        self.assertAlmostEqual(critical[0]['T'], a / 2, delta=1e-6)
        self.assertAlmostEqual(critical[0]['x'], 0.5, delta=1e-6)
        self.assertEqual(critical[0]['estabilidad']['estado'], 'estable')
        # the fold: T rises to the critical point and the pair closes there
        top = max(branch.points, key=lambda p: p['T'])
        self.assertLess(top['T'], a / 2)
        self.assertLess(top['xb'] - top['xa'], 0.05)

    def test_no_branch_above_the_critical_temperature(self):
        # a / 2 = 260 K lies below the package's domain: the liquid is one phase everywhere in it
        self.assertEqual(trace(margules_system(520.0), 'Txy', P), [])


class WaterButanol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system = mz.Sistema(LLE, [W, B])
        cls.txy = trace(cls.system, 'Txy', P)

    def three_phase(self, branches):
        ends = [e for b in branches for e in b.ends if e['tipo'] == 'tres_fases']
        self.assertEqual(len(ends), 1)
        self.assertEqual(ends[0]['cert']['estado'], 'cumple')
        return ends[0]

    def test_branch_matches_the_tp_flash(self):
        self.assertEqual(len(self.txy), 1)
        points = self.txy[0].points
        self.assertTrue(all(p['cert']['estado'] == 'cumple' for p in points))
        for p in points[::max(1, len(points) // 6)]:
            z = 0.5 * (p['xa'] + p['xb'])
            state = self.system.equilibrio_TP(p['T'], p['P'], np.array([z, 1 - z]))
            liquids = sorted(float(f.x[0]) for f in state.fases if f.tipo == 'liquido')
            self.assertEqual(len(state.fases), 2)
            self.assertEqual(len(liquids), 2)
            self.assertLessEqual(abs(liquids[0] - p['xa']), 1e-7)
            self.assertLessEqual(abs(liquids[1] - p['xb']), 1e-7)

    def test_three_phase_point_against_the_lv_tracer(self):
        end = self.three_phase(self.txy)
        lv = dg.trazar(self.system, 'Txy', P, (0.0, 1.0), 'exploratoria')
        meetings = [b for kind, b, _ in lv['especiales'] if kind == 'encuentro_otra_fase']
        self.assertTrue(meetings)
        for b in meetings:
            self.assertLessEqual(abs(b.var - end['T']), 1e-4)
        # either side of T*: two liquids just below, liquid and vapor just above (the flash, not the tracer)
        z = np.array([0.5 * (end['xa'] + end['xb'])] * 1)
        n = np.array([z[0], 1 - z[0]])
        below = self.system.equilibrio_TP(end['T'] - 1e-3, P, n)
        above = self.system.equilibrio_TP(end['T'] + 1e-3, P, n)
        self.assertEqual(sorted(f.tipo for f in below.fases), ['liquido', 'liquido'])
        self.assertIn('vapor', [f.tipo for f in above.fases])

    def test_pxy_is_vertical_and_consistent_with_txy(self):
        T_star = 360.0
        branches = trace(self.system, 'Pxy', T_star)
        self.assertEqual(len(branches), 1)
        pts = branches[0].points
        # g^E does not depend on P and the pure-liquid Poynting terms cancel between two liquids
        self.assertLessEqual(max(abs(p['xa'] - pts[0]['xa']) for p in pts), 1e-9)
        end = self.three_phase(branches)
        back = self.three_phase(trace(self.system, 'Txy', end['P']))
        self.assertAlmostEqual(back['T'], T_star, delta=1e-6)
        self.assertLessEqual(abs(back['xa'] - end['xa']), 1e-7)
        self.assertLessEqual(abs(back['y'] - end['y']), 1e-7)


class Service(unittest.TestCase):
    def body(self, cas, model, axis=2):
        return {'revision': 1, 'solicitudId': 'f8', 'modelo': model, 'componenteEjeId': axis,
                'componentes': [{'id': 1, 'nombre': 'a', 'simbolo': 'a', 'identidadQuimica': {'cas': cas[0]}},
                                {'id': 2, 'nombre': 'b', 'simbolo': 'b', 'identidadQuimica': {'cas': cas[1]}}],
                'corte': {'tipo': 'Txy', 'P': {'valor': P, 'unidad': 'Pa'}}, 'intervaloComposicion': [0, 1],
                'resolucion': 'exploratoria'}

    def test_published_block_and_axis(self):
        model = {'id': LLE, 'version': mz.PAQUETES[LLE].version}
        r2 = service.trazar(self.body([W, B], model, axis=2))
        r1 = service.trazar(self.body([W, B], model, axis=1))
        block2, block1 = r2['liquidoLiquido'], r1['liquidoLiquido']
        self.assertEqual(block2['estado'], 'completo')
        self.assertEqual([e['tipo'] for e in block2['puntosEspeciales']].count('tres_fases'), 1)
        self.assertTrue(all(p['certificado']['estado'] == 'cumple' for p in block2['puntos']))
        for p2, p1 in zip(block2['puntos'], block1['puntos']):
            self.assertAlmostEqual(p2['xEje'][0], 1 - p1['xEje'][1], delta=1e-12)
            self.assertLess(p2['xEje'][0], p2['xEje'][1])
        # the L-V part of the response is not changed by the block
        self.assertIn('ramas', r2)
        self.assertTrue(all(r['tipo'] == 'LV' for r in r2['ramas']))

    def test_miscible_pair_has_no_branch(self):
        model = {'id': 'nrtl-chemsep', 'version': mz.PAQUETES['nrtl-chemsep'].version}
        block = service.trazar(self.body([E, W], model))['liquidoLiquido']
        self.assertEqual(block['ramas'], [])
        self.assertEqual(block['estado'], 'completo')


if __name__ == '__main__':
    unittest.main()
