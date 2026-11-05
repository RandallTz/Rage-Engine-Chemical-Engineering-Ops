"""Outlet flow of a package-closure drum from the momentum balance (demo-02-momentum; F6 + F4).

Fresh shared-law author (tests/derived_momentum_inputs.py). The reference is an
independent DOP853 integration that calls core.mezclas directly.
"""
import copy
import unittest

import numpy as np
import sympy as sp

from derived_momentum_inputs import OUTLET, OWNER, PIPE, author_outlet, reference_outlet, select_outlet
from core.compilador.derived import DerivedSystem, LoweringError, resolve_system


def _series(result):
    return {row['id']: np.array(row['valores']) for row in result['series']}


class MomentumOutlet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.author, cls.out = author_outlet()
        cls.runs = {}
        for method in ('rk45', 'bdf'):
            model = select_outlet(cls.author, cls.out, method=method)
            system = DerivedSystem(model)
            cls.runs[method] = (model, system, resolve_system(system))
        cls.times = np.array(cls.runs['rk45'][2]['ejes'][0]['valores'])
        cls.reference, cls.reference_T = reference_outlet(cls.times)

    def test_deduced_path_balance_retains_inertia_head_and_loss(self):
        t = sp.Symbol('t', real=True)
        f = lambda name: sp.Function(name)(t)
        s = lambda name: sp.Symbol(name, real=True)
        equation = self.author.result.graph.nodes[self.out['flow']].equation
        F, ML, vL, VL, P = f('liquidMassFlow'), f(f'phase_M__{OWNER}__L'), f(f'phase_v__{OWNER}__L'), f(f'liquid_volume__{OWNER}'), f(f'P__{OWNER}')
        A, L, K, g, Ad, Pout = s(f'A__{PIPE}'), s(f'L__{PIPE}'), s('lossCoefficient'), s(f'g__{OWNER}'), s('crossSectionArea'), s('outletPressure')
        rho = ML / vL
        # The journal's signed Darcy-Weisbach/local-loss law with zero distributed friction (review RM-1).
        expected = A / L * (P + rho * g * VL / Ad - Pout - K * F * sp.sqrt(F**2) / (2 * rho * A**2))
        self.assertEqual(equation.lhs, sp.diff(F, t))
        self.assertEqual(sp.simplify(equation.rhs - expected), 0)
        total = self.author.result.graph.nodes[self.out['donorTotal']].equation
        self.assertEqual(sp.simplify(total.lhs - f('q__liquid__1') - f('q__liquid__2')), 0)
        self.assertEqual(total.rhs, F)

    def test_states_and_floor_pressure_against_direct_package_integration(self):
        from core import mezclas
        package = mezclas.Sistema('unifac-dortmund-public', ['64-17-5', '7732-18-5'])
        M = np.asarray(package.M)
        floor = []
        for y in self.reference.y.T:
            liquid = next(p for p in package.equilibrio_PH(OUTLET['P'], y[2], np.asarray(y[:2]) / M).fases if p.tipo != 'vapor')
            floor.append(OUTLET['P'] + liquid.M / liquid.v * OUTLET['g'] * liquid.n * liquid.v / OUTLET['area'])
        floor = np.asarray(floor)
        for method, (model, system, result) in self.runs.items():
            with self.subTest(method=method):
                self.assertEqual(result['estado'], 'resuelto')
                values = _series(result)
                ids = [row['quantityId'] for row in model['motores']['derivedExecution']['states']]
                for index, tolerance in [(0, 1e-7), (1, 1e-7), (3, 1e-7)]:
                    self.assertLess(np.max(abs(values['campo.' + ids[index]] - self.reference.y[index])), tolerance)
                self.assertLess(np.max(abs(values['campo.' + ids[2]] - self.reference.y[2])) / abs(self.reference.y[2][0]), 1e-8)
                T = values['closure.' + OWNER + '.' + system.ids[system.closures[0].T]]
                self.assertLess(np.max(abs(T - self.reference_T)), 1e-5)
                pressure = next(row for row in model['motores']['derivedExecution']['reconstructions'] if row['equationId'] == self.out['floorPressure'])
                np.testing.assert_allclose(values['observable.' + pressure['quantityId']], floor, rtol=1e-9)
                checks = {row['id']: row for row in result['verificaciones']}
                self.assertLessEqual(checks['thermodynamics.closure.' + OWNER]['valor'], 1.)
                self.assertLess(checks['conservation.matter.' + OWNER + '.total']['valor'], 1e-9)
        # The deduced flow is not constant: it follows the liquid head and density.
        flow = self.reference.y[3]
        self.assertGreater(flow.max() - flow.min(), 0.02)
        # Review RM-3: monitor the quasi-constant-density premise A L |d rho/dt| / F of the path reduction.
        from core import mezclas
        package = mezclas.Sistema('unifac-dortmund-public', ['64-17-5', '7732-18-5'])
        M = np.asarray(package.M)
        rho = np.array([next(p.M / p.v for p in package.equilibrio_PH(OUTLET['P'], y[2], np.asarray(y[:2]) / M).fases if p.tipo != 'vapor')
                        for y in self.reference.y.T])
        storage = OUTLET['pipeArea'] * OUTLET['length'] * np.abs(np.gradient(rho, self.times)) / flow
        self.assertLess(storage.max(), 1e-3)

    def test_vapour_appearance_is_still_a_located_phase_event(self):
        rk45 = [e['valor'] for e in self.runs['rk45'][2]['eventos'] if e['codigo'] == 'aparicion_fase']
        bdf = [e['valor'] for e in self.runs['bdf'][2]['eventos'] if e['codigo'] == 'aparicion_fase']
        self.assertEqual((len(rk45), len(bdf)), (1, 1))
        self.assertAlmostEqual(rk45[0], bdf[0], delta=1e-4)

    def test_path_flow_must_be_integrated_and_forward(self):
        model = select_outlet(self.author, self.out)
        selection = model['motores']['derivedExecution']
        flow = next(row for row in selection['states'] if row['equationId'] == self.out['flow'])
        selection['states'].remove(flow)
        selection['initialValues'].pop(flow['quantityId'])
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(model)
        diagnostic = caught.exception.diagnostics[0]
        if diagnostic['code'] == 'unsupported_condition':
            # Isolating discharge enthalpy introduces the recorded nonzero
            # flow condition; removing the flow state leaves it unbound.
            self.assertEqual(diagnostic['equationId'], self.out['enthalpy.discharge'])
        else:
            self.assertIn(diagnostic['code'], ('unsupported_momentum_regime', 'unsupported_operation', 'closure_input_unresolved', 'unsupported_expression', 'uncovered_balance', 'unsupported_rate'))
        model = select_outlet(self.author, self.out)
        model['datos']['solve.F0']['declaracion']['texto'] = '-0.1'
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'invalid_initial_domain')


if __name__ == '__main__':
    unittest.main()
