"""Domain guards compared with analytic and independent integrations."""
import unittest
from unittest.mock import patch

import numpy as np
from scipy.integrate import solve_ivp

from core.solvers.integrador import integrar, DomainViolation, _dense
import core.solvers.integrador as integrator


class Reaction:
    def __init__(self):
        self.evaluations = []

    def dominio(self, t, y):
        return [y[0], y[1]]

    def describir_dominio(self, index):
        return ['A', 'B'][index]

    def rhs(self, t, y):
        assert min(y) >= 0
        self.evaluations.append((t, y.copy()))
        return np.array([-y[0], y[0]])

    def firma(self, t, y):
        assert min(y) >= 0
        return None


class Stiff(Reaction):
    def rhs(self, t, y):
        assert min(y) >= 0
        self.evaluations.append((t, y.copy()))
        return np.array([-1000 * (y[0] - .001), 0.])


class DomainTests(unittest.TestCase):
    def test_first_order_reaction(self):
        for method in ('RK45', 'BDF'):
            with self.subTest(method=method):
                system = Reaction()
                result = integrar(system, [1., 0.], 8., metodo=method, rtol=1e-9, atol=1e-12)
                self.assertIsNone(result.detenida)
                self.assertAlmostEqual(result.y_fin[0], np.exp(-8), delta=2e-9)
                self.assertAlmostEqual(sum(result.y_fin), 1., delta=2e-9)
                self.assertTrue(all(np.all(y >= 0) for _, y in system.evaluations))

    def test_stiff_relaxation(self):
        reference = solve_ivp(lambda t, y: [-1000 * (y[0]-.001)], (0, .02), [1.],
                              method='DOP853', rtol=1e-13, atol=1e-15).y[0, -1]
        self.assertLess(1. + .01 * -999., 0.)
        for method in ('RK45', 'BDF'):
            with self.subTest(method=method):
                system = Stiff()
                result = integrar(system, [1., 0.], .02, metodo=method, rtol=1e-9, atol=1e-12, max_step=.01)
                self.assertIsNone(result.detenida)
                self.assertAlmostEqual(result.y_fin[0], reference, delta=2e-9)
                self.assertTrue(all(np.all(y >= 0) for _, y in system.evaluations))

    def test_valid_domain_does_not_change_trajectory_bits(self):
        class Unconstrained:
            def rhs(self, t, y): return np.array([-y[0], y[0]])
            def firma(self, t, y): return None
        for method in ('RK45', 'BDF'):
            protected = integrar(Reaction(), [1., 0.], 2., metodo=method)
            original = integrar(Unconstrained(), [1., 0.], 2., metodo=method)
            self.assertEqual(protected.pasos, original.pasos)
            np.testing.assert_array_equal(protected.y_fin, original.y_fin)
            for t in np.linspace(0, 2, 101):
                np.testing.assert_array_equal(protected.y(t), original.y(t))

    def test_bad_dense_sample_rebuilds_suffix(self):
        system = Reaction()
        result = integrar(system, [1., 0.], 2., max_step=.2)
        index = len(result.tramos)//2
        start, end, original = result.tramos[index]
        def defective(t):
            if start < t < end:
                return np.array([-1., 2.])
            return original(t)
        result.tramos[index] = (start, end, _dense(system, defective))
        sample = result.y((start+end)/2)
        self.assertGreaterEqual(min(sample), 0)
        self.assertGreater(result.rechazos, 0)
        self.assertAlmostEqual(result.y(2.)[0], np.exp(-2), delta=1e-7)

    def test_bad_dense_sample_at_minimum_step_is_localized(self):
        system = Reaction()
        result = integrar(system, [1., 0.], 1., h_min=.1, max_step=.1)
        start, end, original = result.tramos[0]
        def defective(t):
            return np.array([-1., 2.]) if start < t < end else original(t)
        result.tramos[0] = (start, end, _dense(system, defective))
        with self.assertRaises(DomainViolation) as caught:
            result.y((start+end)/2)
        self.assertEqual(caught.exception.variable, 'A')
        self.assertEqual(caught.exception.time, start)
        self.assertGreater(caught.exception.step, 0)

    def test_outward_boundary_and_located_failure(self):
        class Drain(Reaction):
            def rhs(self, t, y):
                assert y[0] >= 0
                return np.array([-1., 0.])
        result = integrar(Drain(), [.3, 0.], 1., max_step=.2, h_min=1e-9)
        self.assertIsNotNone(result.detenida)
        self.assertEqual(result.detenida.codigo, 'agotamiento')
        self.assertAlmostEqual(result.t_fin, .3, delta=2e-8)
        self.assertGreaterEqual(result.y_fin[0], 0)
        if isinstance(result.detenida, DomainViolation):
            self.assertEqual(result.detenida.variable, 'A')
            self.assertGreater(result.detenida.step, 0)

    def test_finite_boundary_against_analytic_time(self):
        class Drain(Reaction):
            def rhs(self, t, y):
                assert y[0] >= 0
                return np.array([-1., 0.])
        for method in ('RK45', 'BDF'):
            result = integrar(Drain(), [.3, 0.], 1., max_step=.2, h_min=1e-12, metodo=method)
            self.assertIsNotNone(result.detenida)
            self.assertAlmostEqual(result.t_fin, .3, delta=1e-11)
            self.assertGreaterEqual(result.y_fin[0], 0.)

    def test_bdf_jacobian_at_upper_boundary(self):
        class Stationary:
            def rhs(self, t, y):
                assert 0 <= y[0] <= 1
                return np.array([0.])
            def dominio(self, t, y): return [y[0], 1-y[0]]
            def describir_dominio(self, k): return ['lower', 'upper'][k]
            def firma(self, t, y): return None
        result = integrar(Stationary(), [1.], 1., metodo='BDF')
        self.assertIsNone(result.detenida)
        self.assertEqual(result.y_fin[0], 1.)

    def test_no_admissible_jacobian_probe_is_localized(self):
        class Fixed:
            def rhs(self, t, y):
                assert y[0] == 0
                return np.array([0.])
            def dominio(self, t, y): return [y[0], -y[0]]
            def describir_dominio(self, k): return ['lower', 'upper'][k]
            def firma(self, t, y): return None
        result = integrar(Fixed(), [0.], 1., metodo='BDF')
        self.assertIsInstance(result.detenida, DomainViolation)
        self.assertEqual(result.t_fin, 0.)
        self.assertEqual(result.detenida.step, 0.)

    def test_exact_boundary_is_an_event(self):
        class Deadline:
            def rhs(self, t, y): return np.array([0.])
            def dominio(self, t, y): return [.5-t]
            def describir_dominio(self, k): return 'time limit'
            def firma(self, t, y): return None
        result = integrar(Deadline(), [0.], .5, max_step=.5)
        self.assertEqual(result.t_fin, .5)
        self.assertEqual(result.detenida.codigo, 'agotamiento')
        self.assertEqual(result.eventos[-1][0], 'agotamiento')

    def test_event_reintegration_retries_domain_failure(self):
        class Switching:
            def rhs(self, t, y): return np.array([0.])
            def dominio(self, t, y): return [y[0]]
            def describir_dominio(self, k): return 'A'
            def event_state(self, t, y): return (t >= .5, ())
        system = Switching()
        real_rk = integrator._rk
        failures = []
        def injected(*args, **kwargs):
            if args[3] < 1. and not failures:
                failures.append(args[3])
                raise DomainViolation(system, 0, args[1])
            return real_rk(*args, **kwargs)
        with patch.object(integrator, '_rk', side_effect=injected):
            result = integrar(system, [1.], 1., max_step=.2)
        self.assertEqual(len(failures), 1)
        self.assertIsNone(result.detenida)
        self.assertGreater(result.rechazos, 0)
        self.assertTrue(any(event[0] == 'cambio_firma' for event in result.eventos))

    def test_event_reintegration_minimum_step_is_localized(self):
        class Switching:
            def rhs(self, t, y): return np.array([0.])
            def dominio(self, t, y): return [y[0]]
            def describir_dominio(self, k): return 'A'
            def event_state(self, t, y): return (t >= .5, ())
        system = Switching()
        real_rk = integrator._rk
        def injected(*args, **kwargs):
            if args[3] < 1.:
                raise DomainViolation(system, 0, args[1])
            return real_rk(*args, **kwargs)
        with patch.object(integrator, '_rk', side_effect=injected):
            result = integrar(system, [1.], 1., max_step=.2, h_min=.001)
        self.assertIsInstance(result.detenida, DomainViolation)
        self.assertEqual(result.detenida.variable, 'A')
        self.assertEqual(result.detenida.bound, 'declared margin >= 0')
        self.assertGreater(result.detenida.step, 0.)
        self.assertLessEqual(result.t_fin, .5)


if __name__ == '__main__':
    unittest.main()
