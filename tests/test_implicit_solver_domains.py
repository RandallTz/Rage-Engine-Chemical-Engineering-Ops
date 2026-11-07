"""Independent boundary references for the generic nonlinear solver."""
import unittest

import numpy as np

from core.solvers.nonlinear import NonlinearError, solve


class BoundedNewtonTests(unittest.TestCase):
    def test_trace_amount_uses_relative_domain_distance(self):
        reference = 1e-9
        evaluations = []

        def residual(z):
            self.assertGreater(z[0], 0)
            evaluations.append(z[0])
            return np.array([np.log(z[0] / reference)])

        def jacobian(z):
            self.assertGreater(z[0], 0)
            return np.array([[1 / z[0]]])

        result, _ = solve(residual, jacobian, [.9], [[0, 1]], [1], [1],
                          step_tolerance=1e-16, admissible=lambda z: z[0] > 0)
        self.assertAlmostEqual(result[0] / reference, 1, delta=1e-9)
        self.assertTrue(all(0 < value <= 1 for value in evaluations))

    def test_outward_step_at_boundary_is_rejected(self):
        with self.assertRaises(NonlinearError) as caught:
            solve(lambda z: np.array([z[0] + 1]), lambda z: np.ones((1, 1)),
                  [0], [[0, 1]], [1], [1])
        self.assertEqual(caught.exception.code, 'nonlinear_domain')

    def test_existing_interior_root(self):
        result, _ = solve(lambda z: np.array([z[0] ** 2 - .25]),
                          lambda z: np.array([[2 * z[0]]]),
                          [.8], [[.1, 1]], [1], [1])
        self.assertAlmostEqual(result[0], .5, delta=1e-10)


if __name__ == '__main__':
    unittest.main()
