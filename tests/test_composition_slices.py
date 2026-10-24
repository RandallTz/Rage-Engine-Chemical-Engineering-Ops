"""F8: multicomponent composition-line slices at fixed T and P (core/composition_slices.py).

References:
1. A feed line along a tie line traced by core/ternary_liquid_liquid.py (another path: pseudo-arclength on mu
   equality) crosses the binodal exactly at the tie line's ends, where the incipient phase is the other end.
2. A binary line across the water-1-butanol gap: its boundaries are the binary pair of core/coexistencia_ll.py.
3. Every species is kept: a species absent from both ends is rejected, never dropped.
Run: python tests/test_composition_slices.py (about 30 s).
"""
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import coexistencia_ll as ll
from core import composition_slices as cs
from core import mezclas as mz
from core import ternary_liquid_liquid as tl

warnings.filterwarnings('ignore')
BZ, W, E, B = '71-43-2', '7732-18-5', '64-17-5', '71-36-3'
P = 101325.0
UNIFAC = 'unifac-original-public'


class TieLineSlice(unittest.TestCase):
    def test_boundaries_are_the_tie_line_ends(self):
        system = mz.Sistema(UNIFAC, [BZ, W, E])
        branch = tl.trace(system, 300.0, P, tl.PROFILES['exploratoria'])[0]
        p = branch.points[len(branch.points) // 2]
        xa, xb = p['xa'], p['xb']
        d = xa - xb
        f = 0.5 * min(min(xa[i] / -d[i] for i in range(3) if d[i] < 0), min(xb[i] / d[i] for i in range(3) if d[i] > 0))
        zA, zB = xa + f * d, xb - f * d
        r = cs.trace(system, 300.0, P, zA, zB, cs.PROFILES['exploratoria'])
        self.assertEqual(r['fallos'], [])
        self.assertTrue(all(row['certificado'] for row in r['filas']))
        expected = [f / (1 + 2 * f), (1 + f) / (1 + 2 * f)]
        self.assertEqual(len(r['fronteras']), 2)
        for bd, l_star in zip(r['fronteras'], expected):
            self.assertLessEqual(abs(0.5 * sum(bd['l']) - l_star), 1e-8)
            two = bd['antes'] if len(bd['antes']['fases']) == 2 else bd['despues']
            for x in (xa, xb):
                self.assertLessEqual(min(float(np.max(np.abs(np.asarray(ph['x']) - x))) for ph in two['fases']), 1e-6)


class BinarySlice(unittest.TestCase):
    def test_boundaries_are_the_binary_pair(self):
        system = mz.Sistema('nrtl-lle-agua-butanol', [W, B])
        r = cs.trace(system, 330.0, P, [0.995, 0.005], [0.40, 0.60], cs.PROFILES['exploratoria'])
        pair = ll.trace(system, 'Pxy', 330.0, ll.PROFILES['exploratoria'])[0].points[-1]
        self.assertEqual(len(r['fronteras']), 2)
        found = sorted(row['z'][0] for bd in r['fronteras'] for row in (bd['antes'], bd['despues'])
                       if len(row['fases']) == 1)
        self.assertLessEqual(abs(found[0] - pair['xa']), 1e-6)
        self.assertLessEqual(abs(found[1] - pair['xb']), 1e-6)


class Rejections(unittest.TestCase):
    def test_absent_species_is_not_dropped(self):
        system = mz.Sistema(UNIFAC, [BZ, W, E])
        with self.assertRaises(cs.SliceRejected) as raised:
            cs.trace(system, 300.0, P, [0.5, 0.5, 0.0], [0.2, 0.8, 0.0], cs.PROFILES['exploratoria'])
        self.assertEqual(raised.exception.motivo, 'no_soportado')

    def test_invalid_feed(self):
        system = mz.Sistema(UNIFAC, [BZ, W, E])
        with self.assertRaises(cs.SliceRejected):
            cs.trace(system, 300.0, P, [0.6, 0.6, -0.2], [0.2, 0.7, 0.1], cs.PROFILES['exploratoria'])


if __name__ == '__main__':
    unittest.main()
