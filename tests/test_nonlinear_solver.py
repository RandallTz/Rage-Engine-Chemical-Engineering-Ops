"""Generic Newton tests, independent of physical families and the compiler."""
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.solvers.nonlinear import solve, NonlinearError


class NewtonTests(unittest.TestCase):
    def run_problem(self, residual, jacobian, seed=(1.,), bounds=((0.1, 4.),), **kwargs):
        return solve(residual, jacobian, seed, bounds, np.ones(len(seed)),
                     np.ones(len(seed)), **kwargs)

    def rejection(self, code, *args, **kwargs):
        with self.assertRaises(NonlinearError) as caught:
            self.run_problem(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.diagnostic['terminationReason'], code)
        return caught.exception.diagnostic

    def test_polynomial_reference_and_order_independence(self):
        f = lambda z: np.array([z[0]**2+z[1]-6, z[0]-z[1]])
        j = lambda z: np.array([[2*z[0], 1], [1, -1]])
        args = (f, j, (1., 1.), ((0.1, 4.), (0.1, 4.)))
        z, evidence = self.run_problem(*args)
        np.testing.assert_allclose(z, [2., 2.], atol=1e-10)
        self.assertLessEqual(evidence['residualNorm'], 1e-10)
        again, _ = self.run_problem(*args)
        np.testing.assert_array_equal(z, again)

    def test_dimensioned_rows_and_variables_use_separate_scales(self):
        # x is length [m], y is time [s]. Coefficients 1 m^2/s and
        # 1 s/m make the rows [m^2] and [s]; the hand roots are (2 m,2 s).
        f=lambda z: [z[0]**2+z[1]-6, z[0]-z[1]]
        j=lambda z: [[2*z[0],1],[1,-1]]
        root,detail=solve(f,j,[1,1],[[.1,4],[.1,4]],[2,3],[6,2])
        np.testing.assert_allclose(root,[2,2],atol=1e-10)
        self.assertLessEqual(detail['residualNorm'],1e-10)

    def test_singular_root_is_not_convergence(self):
        self.rejection('nonlinear_singular_jacobian', lambda z: [z[0]**2], lambda z: [[2*z[0]]],
                       seed=(0.,), bounds=((-1., 1.),))

    def test_review_double_root_is_not_regular_convergence(self):
        # Claude's reproducer: cond(J) == 1 even as the scalar Jacobian vanishes.
        # A near-root seed also prevents a correction-only gate from hiding it.
        for seed in (2., 1.+1e-13):
            with self.subTest(seed=seed):
                detail = self.rejection('nonlinear_ill_conditioned',
                    lambda z: [(z[0]-1)**2], lambda z: [[2*(z[0]-1)]],
                    seed=(seed,), bounds=((1., 3.),))
                self.assertEqual(detail['conditionInfinity'], 1.)

    def test_small_residual_still_requires_small_final_correction(self):
        root, detail = self.run_problem(lambda z: [z[0]**2-2], lambda z: [[2*z[0]]],
                                       seed=(np.sqrt(2.)+1e-11,))
        self.assertLess(abs(root[0]-np.sqrt(2.)), 1e-14)
        self.assertLessEqual(detail['stepNorm'], 1e-12)
        self.assertGreaterEqual(detail['iterations'], 1)

    def test_uniformly_small_scaled_jacobian_rejects(self):
        self.rejection('nonlinear_ill_conditioned',
            lambda z: [1e-12*z[0], 1e-12*z[1]],
            lambda z: [[1e-12, 0], [0, 1e-12]],
            seed=(0., 0.), bounds=((-1., 1.), (-1., 1.)))

    def test_weak_raw_slope_with_consistent_row_scale_is_admitted(self):
        root, detail = solve(lambda z: [1e-12*(z[0]-2)], lambda z: [[1e-12]],
                             [1.], [[0., 3.]], [1.], [1e-12])
        np.testing.assert_allclose(root, [2.], atol=1e-14, rtol=0)
        self.assertLessEqual(detail['stepNorm'], 1e-12)

    def test_ill_conditioning(self):
        self.rejection('nonlinear_ill_conditioned', lambda z: [z[0], 1e-12*z[1]],
                       lambda z: [[1, 0], [0, 1e-12]], seed=(1.,1.), bounds=((-2.,2.),(-2.,2.)))

    def test_multiple_roots(self):
        self.rejection('nonlinear_multiple_roots', lambda z: [z[0]**2-1], lambda z: [[2*z[0]]],
                       seed=(1.,), bounds=((-2.,2.),))

    def test_initial_domain(self):
        self.rejection('nonlinear_invalid_seed', lambda z: [z[0]-2], lambda z: [[1]], seed=(-1.,))

    def test_leaving_domain(self):
        self.rejection('nonlinear_domain', lambda z: [z[0]-5], lambda z: [[1]], seed=(4.,))

    def test_nonfinite(self):
        self.rejection('nonlinear_nonfinite', lambda z: [float('nan')], lambda z: [[1]])

    def test_iteration_limit(self):
        self.rejection('nonlinear_iteration_limit', lambda z: [z[0]**2-2], lambda z: [[2*z[0]]], max_iterations=1)

    def test_stagnation(self):
        self.rejection('nonlinear_stagnation', lambda z: [z[0]**2-2], lambda z: [[2*z[0]]], step_tolerance=1.)

    def test_jacobian_domain_error_rejects_the_trial_step(self):
        # The full Newton step from 0.5 lands at 4.25, where the Jacobian is not
        # evaluable; that trial is backtracked like a residual-domain error.
        def j(z):
            if z[0] > 3.:
                raise ValueError('outside the Jacobian domain')
            return np.array([[2*z[0]]])
        z, evidence = self.run_problem(lambda z: np.array([z[0]**2-4]), j, seed=(0.5,), bounds=((0.1, 10.),))
        np.testing.assert_allclose(z, [2.], atol=1e-10)
        self.assertGreater(evidence['backtracks'], 0)

    def test_line_search_limit(self):
        self.rejection('nonlinear_line_search', lambda z: [z[0]**3-2*z[0]+2],
                       lambda z: [[3*z[0]**2-2]], seed=(1.,), bounds=((-3.,3.),), max_backtracks=1)

    def test_unsupported_graph_expressions(self):
        import sympy as sp
        from core.compilador.nonlinear_block import NonlinearBlock
        block=NonlinearBlock.__new__(NonlinearBlock)
        x=sp.Symbol('x');block.arguments=[x]
        for expression in (sp.sin(x),sp.sqrt(x),sp.Derivative(sp.Function('f')(x),x)):
            with self.assertRaises(NonlinearError) as caught:block.validate(expression)
            self.assertEqual(caught.exception.code,'nonlinear_unsupported_expression')

    def test_invalid_scale(self):
        with self.assertRaises(NonlinearError) as caught:
            solve(lambda z: z, lambda z: [[1]], [1], [[0,2]], [0], [1])
        self.assertEqual(caught.exception.code, 'nonlinear_invalid_settings')


if __name__ == '__main__':
    unittest.main()
