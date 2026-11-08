"""Declared long-digit data must reach numpy evaluation as floats (post-solve defect).

A declared 0.0007000000000000001 became an exact rational whose integers exceed int64 inside sqrt;
lambdify printed Python ints and numpy rejected the object array. The rounded 0.0007 solved.
"""
import copy
import unittest

import numpy as np
import sympy as sp

from core.compilador.steady import SteadySystem
from core.mathematics.numeric_lowering import float_constants, lambdify_numeric
from test_steady_package_closure import steady_selection


class FloatConstants(unittest.TestCase):
    def test_big_exact_numbers_become_floats_and_small_ones_stay_exact(self):
        x = sp.Symbol('x')
        big = sp.Integer(21991148575128554141592653589793)
        expression = sp.sqrt(big) * x + sp.Rational(1, 3) * x
        lowered = float_constants(expression)
        self.assertFalse(any(abs(n.p) > 2 ** 62 for n in lowered.atoms(sp.Rational)))
        self.assertAlmostEqual(lambdify_numeric([x], expression, modules='numpy')(2.0),
                               float(expression.subs(x, 2)), delta=1e-9 * float(expression.subs(x, 2)))
        with self.assertRaises(TypeError):
            sp.lambdify([x], expression, modules='numpy')(np.float64(2.0))


class LongDigitDatumOnShippedFixture(unittest.TestCase):
    def test_long_digit_pipe_area_agrees_with_rounded_datum(self):
        from derived_momentum_inputs import author_outlet, select_outlet
        author, out = author_outlet()
        dynamic = select_outlet(author, out)
        ids = [row['quantityId'] for row in dynamic['motores']['derivedExecution']['states']]
        seeds = {ids[0]: (8.0, 0.0, 200.0, 10.0, 'kg'), ids[1]: (90.0, 1.0, 2000.0, 100.0, 'kg'),
                 ids[2]: (-1.6e8, -5e9, -1e6, 1e8, 'J'), ids[3]: (0.45, 1e-3, 5.0, 0.1, 'kg/s')}
        base = steady_selection(dynamic, seeds, [(0.01, 'kg/s'), (0.01, 'kg/s'), (1000.0, 'W'), (1e-4, 'kg/s2')])
        roots = {}
        for text in ('0.0007', '0.0007000000000000001'):
            model = copy.deepcopy(base)
            model['datos']['solve.pipeArea']['declaracion']['texto'] = text
            result = SteadySystem(model).solve()
            self.assertEqual(result['estado'], 'resuelto')
            values = {row['id']: row['valores'] for row in result['series']}
            roots[text] = np.array([values['steady.' + q] for q in ids])
        np.testing.assert_allclose(roots['0.0007000000000000001'], roots['0.0007'], rtol=1e-7, atol=1e-9)


if __name__ == '__main__':
    unittest.main()
