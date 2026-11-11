"""Attainable-resolution tolerances of the Newton solver (F5 item 1).

The residual and step tolerances are requests; the solver may not demand more
than floating point can deliver at the current iterate. Problems that have no
solution and runs that stall for a real reason must still be rejected.
"""
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.solvers.nonlinear import solve, NonlinearError


class AttainableResolutionTests(unittest.TestCase):
    def test_badly_scaled_root_is_not_rejected_as_stagnation(self):
        # u^2 = 2e16 with declared scales of 1 (a root of 1.4e8 in unit scales):
        # the residual carries rounding noise of ~eps*2e16 = 4, so a fixed
        # 1e-10 residual tolerance can never be met although z is exact to
        # the last bit.
        c = 2e16
        z, detail = solve(lambda z: [z[0]**2 - c], lambda z: [[2*z[0]]], [1e8], [[1e7, 1e9]], [1.], [1.])
        self.assertAlmostEqual(z[0] / np.sqrt(c), 1., delta=4*np.finfo(float).eps)
        self.assertEqual(detail['terminationReason'], 'converged')

    def test_badly_scaled_large_offset_step_floor(self):
        # z - c with c = 1e9 and unit scales: the step resolution eps*|z| = 2e-7
        # is far above a 1e-12 step tolerance.
        z, detail = solve(lambda z: [z[0] - 1e9], lambda z: [[1.]], [5e8], [[1e8, 2e9]], [1.], [1.])
        self.assertEqual(z[0], 1e9)
        self.assertEqual(detail['terminationReason'], 'converged')

    def test_no_solution_is_still_not_converged(self):
        # u^2 + 1e16 = 0 has no real root; the floor must not hide it.
        with self.assertRaises(NonlinearError) as caught:
            solve(lambda z: [z[0]**2 + 1e16], lambda z: [[2*z[0]]], [1e8], [[1e7, 1e9]], [1.], [1.])
        self.assertNotEqual(caught.exception.diagnostic['terminationReason'], 'converged')

    def test_no_solution_well_scaled_is_not_converged(self):
        with self.assertRaises(NonlinearError):
            solve(lambda z: [z[0]**2 + 1.], lambda z: [[2*z[0]]], [1.], [[.1, 4.]], [1.], [1.])

    def test_small_step_with_real_residual_is_stagnation_not_convergence(self):
        # Residual 1e-6 of unit-order terms is 1e10 eps above the floor; a huge
        # step tolerance must still report stagnation, never convergence.
        with self.assertRaises(NonlinearError) as caught:
            solve(lambda z: [z[0]**2 - 2.], lambda z: [[2*z[0]]], [1.], [[.1, 4.]], [1.], [1.],
                  step_tolerance=1.)
        self.assertEqual(caught.exception.code, 'nonlinear_stagnation')

    def test_well_scaled_result_unchanged_bit_for_bit(self):
        z, detail = solve(lambda z: [z[0]**2 - 2.], lambda z: [[2*z[0]]], [1.], [[.1, 4.]], [1.], [1.])
        self.assertLessEqual(abs(z[0] - np.sqrt(2.)), 4*np.finfo(float).eps)


if __name__ == '__main__':
    unittest.main()
