"""Outlet flow of a package-closure drum from the momentum balance (demo-02-momentum; F6 + F4).

Fresh shared-law author (tests/derived_momentum_inputs.py). The reference is an
independent DOP853 integration that calls core.mezclas directly.
"""
import copy
import math
import re
import unittest

import numpy as np
import sympy as sp

from derived_momentum_inputs import OUTLET, OWNER, PIPE, author_outlet, reference_outlet, select_outlet
from test_demo02_drum import recorded_texts
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
            # Study tolerances tighter than the shared fixture's (rtol 1e-9, atol 1e-9 mol, 1e-3 J). Masses are about
            # 100 kg, so at rtol 1e-9 the engine's own truncation error is about 1e-7 kg: BDF measured 1.06e-7 to
            # 1.09e-7 kg against the DOP853 reference on six kernels, within a factor 1.9 of the 2e-7 kg bound, and
            # 3.31e-7 kg on a CI runner (group-9, 11 Nov 2026), whose step sequence differs. The comparison is meant to
            # test the engine's physics, not how many of its allowed rtol-sized steps fell on one side of the bound.
            # At rtol 1e-10 the same runs measure at most 3e-8 kg on three kernels (BDF 6e-9 to 2.6e-8), so the bounds
            # below are unchanged and keep a margin of 7 to 30.
            model['estudio'].update({'rtol': 1e-10, 'atol': {'cantidad': 1e-10, 'energia': 1e-4}})
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
        A, L, K, g, Ad, Pout = s(f'A__{PIPE}'), s(f'L__{PIPE}'), s(f'K__{PIPE}'), s(f'g__{OWNER}'), s('crossSectionArea'), s('outletPressure')
        rho = ML / vL
        # The journal's own signed Darcy-Weisbach/local-loss node, with the recorded constant Darcy factor and the
        # circular-section hydraulic diameter (reviews RM-1, PR-2, CR-1).
        # The relation parser reads pi as the binary64 literal 3.141592653589793 (no exact pi symbol).
        K = K + s('darcyFriction') * L / sp.sqrt(4 * A / sp.Rational(repr(math.pi)))
        expected = A / L * (P + rho * g * VL / Ad - Pout - K * F * sp.Abs(F) / (2 * rho * A**2))
        self.assertEqual(equation.lhs, sp.diff(F, t))
        self.assertEqual(sp.simplify(equation.rhs - expected), 0)
        total = self.author.result.graph.nodes[self.out['donorTotal']].equation
        self.assertEqual(sp.simplify(total.lhs - f('q__liquid__1') - f('q__liquid__2')), 0)
        self.assertEqual(total.rhs, F)
        # PR-2: the loss is the journal's published constitutive node, reached by recorded substitutions.
        graph = self.author.result.graph
        ancestry, stack = set(), [self.out['loss']]
        while stack:
            key = stack.pop()
            if key not in ancestry:
                ancestry.add(key)
                stack.extend(graph.nodes[key].inputs)
        self.assertIn(f'momentum.{PIPE}.path.darcy-weisbach', ancestry)
        self.assertEqual(graph.nodes[f'momentum.{PIPE}.path.darcy-weisbach'].kind, 'constitutive')
        # The friction coefficient relation carries its recorded validity range.
        operations = self.author.definition['operations']
        friction = [op for op in operations if op['kind'] == 'declare_relation' and op['left'] == self.author.quantity(s(f'f__{PIPE}'))]
        self.assertEqual(len(friction), 1)
        self.assertEqual(friction[0]['source'], OUTLET['friction']['source'])
        # PR-4: donor assumptions and basis definitions are separate recorded relations.
        kinds = {op['reason']: op.get('relationKind') for op in operations if op['kind'] == 'declare_relation'}
        self.assertEqual(kinds['Phase donor: the stream has the liquid phase composition of this volume'], 'constitutive')
        self.assertEqual(kinds['Definition of mass fraction from mole fraction, component molar mass and the phase mean molar mass'], 'definition')
        self.assertEqual(kinds['Definition of component mass flow from component molar flow and molar mass'], 'definition')
        self.assertEqual(kinds['The outgoing material draws the donor vapour phase at its thermodynamic state'], 'constitutive')
        # PR-1: no recorded text names a piece of equipment.
        text = recorded_texts(select_outlet(self.author, self.out))
        for word in ('drum', 'valve', 'vent', 'orifice', 'pump', 'tray', 'distillation column'):
            self.assertIsNone(re.search(r'\b' + word + r'\b', text), word)

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
                # Masses about 100 kg: 2e-7 kg is 2e-9 relative, 20 times the study rtol of 1e-10 set in setUpClass.
                for index, tolerance in [(0, 2e-7), (1, 2e-7), (3, 1e-7)]:
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

    def test_momentum_admission_gate_reports_its_own_diagnostic(self):
        # PR-3: the selection above is now rejected earlier (discharge-enthalpy condition), so exercise the
        # admission gate itself on an admitted system with the path row removed from the selection.
        system = DerivedSystem(select_outlet(self.author, self.out))
        selection = system.selection
        system.selection = {**selection, 'states': [row for row in selection['states'] if row['equationId'] != self.out['flow']]}
        with self.assertRaises(LoweringError) as caught:
            system._reduced_momentum_admission()
        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic['code'], 'unsupported_momentum_regime')
        self.assertEqual(diagnostic['equationId'], f'momentum.{PIPE}.path.pressure-form')
        system.selection = selection
        system.model = copy.deepcopy(system.model)
        system.model['motores']['momentumDerivation']['volumes'].pop(PIPE)
        with self.assertRaises(LoweringError) as caught:
            system._reduced_momentum_admission()
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'unsupported_momentum_regime')
        self.assertIn('Record the momentum journal of ' + PIPE, caught.exception.diagnostics[0]['message'])

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
