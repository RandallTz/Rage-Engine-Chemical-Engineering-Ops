"""Cooling jacket service volume and jacketed reactor: deduction, execution and independent references (F4).

JacketService (minutes): the jacket alone against a prescribed process temperature. Compared with
a DOP853 integration that calls the package directly, with the steady enthalpy balance solved by
brentq, and with the published steady state of arXiv:2110.00618 (Debnath, Sahoo, Decardi-Nelson
and Liu, 2021, Section "Application to a CSTR", Eq. 19 and Table 1) evaluated on the deduced
jacket energy row with that source's constant-cp caloric closure.

JacketedReactor (slow: authoring 11-27 min, two 60000 s BDF runs): the accepted Demo 0.2 continuous
reactor coupled to the jacket through one shared-wall relation. Compared with an independent
LSODA integration, with the stationary balances of both volumes solved together, and with the
prescribed-jacket limit (large coolant flow) of the accepted single-reactor reference.
"""
import copy
import json
import os
import sys
import unittest
from pathlib import Path

import numpy as np
import sympy as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jacketed_reactor_inputs import (SERVICE, JACKETED, JACKET, COOLANT_IN, COOLANT_OUT, author_jacket_service, author_jacketed_reactor, jacketed_data,
                                     reference_jacket_service, steady_jacket_service, reference_jacketed, steady_jacketed, water_enthalpy_functions, T)
from core.compilador.derived import DerivedSystem, resolve_system
from core.modelo.equation_workbench import build
import demo02_cstr

# arXiv:2110.00618 (v1, 1 October 2021), Table 1 "Nominal values of parameters of the CSTR" (p. 30) and the
# steady state stated on p. 18: [CA, CB, T, Tj] = [1.205 mol/l, 1.295 mol/l, 302.3 K, 302.6 K] for
# [FA, Fh] = [2.0 l/s, 0.1 l/s]. Jacket: cph = 8.0 J/(g K), rho_h = 800 g/l, Vh = 0.0494 l, Th = 330 K,
# epsilon = rho cp / UA = 0.1 s/l (so UA = 64000 W/K). Eq. 19: dTj/dt = Fh/Vh (Th - Tj) - UA/(rho_h cph Vh) (Tj - T).
ARXIV_2110_00618 = {'cp': 8000.0, 'rho': 800.0, 'Fh': 1e-4, 'Th': 330.0, 'UA': 64000.0, 'T': 302.3, 'Tj': 302.6, 'rounding': 0.05}


def _series(result):
    return {row['id']: np.array(row['valores']) for row in result['series']}


def _closure_T(system, result, owner):
    closure = next(c for c in system.closures if c.owner == owner)
    return _series(result)['closure.' + owner + '.' + system.ids[closure.T]]


class JacketService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.out = author_jacket_service()
        cls.replayed = build(cls.model)
        cls.system = DerivedSystem(cls.model)
        cls.result = resolve_system(cls.system)
        cls.times = np.array(cls.result['ejes'][0]['valores'])

    def test_deduction_is_recorded_from_the_fundamental_laws(self):
        graph = self.replayed.graph
        energy = graph.nodes[self.out['jacket.energy']].equation
        # The state equation keeps the inventory rate on the left and only closure outputs, declared data and the port variable on the right.
        self.assertEqual(energy.lhs, sp.Derivative(sp.Function('H__' + JACKET)(T), T))
        names = {str(a.func) if isinstance(a, sp.core.function.AppliedUndef) else str(a) for a in energy.rhs.atoms(sp.Symbol, sp.core.function.AppliedUndef)}
        self.assertTrue({'coolantFlow', 'wallConductance', 'processTemperature', 'T__jacket', 'phase_h__jacket__L',
                         'inlet_specific_enthalpy__coolantIn'} <= names, names)
        self.assertNotIn('wallHeat', names)
        self.assertNotIn('ambientHeat', names)
        # Every operation is pinned to its inputs; the family journals start at the fundamental laws.
        operations = self.model['motores']['equationWorkbench']['operations']
        self.assertTrue(all(op.get('sourceSignatures') for op in operations if op.get('sources') or op.get('relation')))
        for key in ('materialDerivation', 'energyDerivation', 'thermodynamicDerivation', 'momentumDerivation'):
            entry = self.model['motores'][key]['volumes'][JACKET]
            self.assertEqual(entry['origin'], 'reviewed_rebuild')   # the journal starts at the fundamental law
            self.assertTrue(entry['operations'])
        # Boundary heat partition rows are typed premises, not balances.
        kinds = {graph.nodes[k].kind for k in (self.out['wallLaw'],)}
        self.assertEqual(kinds, {'constitutive'})

    def test_trajectory_against_direct_package_integration(self):
        self.assertEqual(self.result['estado'], 'resuelto')
        Tj = _closure_T(self.system, self.result, JACKET)
        _, reference = reference_jacket_service(self.times)
        self.assertLess(np.max(abs(Tj - reference)), 1e-5)   # K
        ids = [row['quantityId'] for row in self.model['motores']['derivedExecution']['states']]
        mass = _series(self.result)['campo.' + ids[0]]
        self.assertEqual(np.max(abs(mass - SERVICE['mj0'])), 0.0)   # kg: the return equals the supply by construction
        checks = {row['id']: row for row in self.result['verificaciones']}
        self.assertLess(checks['conservation.matter.' + JACKET + '.total']['valor'], 1e-9)
        self.assertLessEqual(checks['thermodynamics.closure.' + JACKET]['valor'], checks['thermodynamics.closure.' + JACKET]['tolerancia'])

    def test_steady_limit_of_the_enthalpy_balance(self):
        Tj = _closure_T(self.system, self.result, JACKET)
        steady = steady_jacket_service()
        # tau = m/(F + UA/cp) is about 14 s; at 600 s the transient is below the integration tolerance.
        self.assertLess(abs(Tj[-1] - steady), 1e-6)   # K

    def test_published_steady_state_arxiv_2110_00618(self):
        """The deduced jacket energy row, closed with the source's constant-cp caloric relation, gives its published Tj."""
        p = ARXIV_2110_00618
        graph = self.replayed.graph
        equation = graph.nodes[self.out['jacket.energy']].equation
        f = lambda name: sp.Function(name)(T)
        Tj, Tref = f('T__' + JACKET), 298.15
        M = sp.Symbol('molar_mass_1__' + JACKET, real=True)
        intro = self.replayed.introduced
        substitution = {sp.Derivative(f('H__' + JACKET), T): 0, sp.Derivative(f('P__' + JACKET), T): 0,
                        intro['coolantFlow']: p['rho'] * p['Fh'], intro['wallConductance']: p['UA'], intro['processTemperature']: p['T'],
                        f('inlet_specific_enthalpy__' + COOLANT_IN): p['cp'] * (p['Th'] - Tref),
                        f('phase_h__' + JACKET + '__L'): M * p['cp'] * (Tj - Tref), f('phase_x_1__' + JACKET + '__L'): 1, f('phase_M__' + JACKET + '__L'): M}
        residual = sp.simplify((equation.lhs - equation.rhs).subs(substitution))
        roots = sp.solve(residual, Tj)
        self.assertEqual(len(roots), 1)
        value = float(roots[0])
        # Closed form of the same balance: Tj = (UA T + rho Fh cp Th)/(UA + rho Fh cp) = 302.574 K; the source prints 302.6 K.
        self.assertAlmostEqual(value, (p['UA'] * p['T'] + p['rho'] * p['Fh'] * p['cp'] * p['Th']) / (p['UA'] + p['rho'] * p['Fh'] * p['cp']), places=9)
        self.assertLess(abs(value - p['Tj']), p['rounding'])   # K, within the source's printed rounding


class JacketedReactor(unittest.TestCase):
    """Authoring takes about 11 minutes; set RAGE_JACKETED_MODEL to a saved model JSON to reuse it."""

    @classmethod
    def setUpClass(cls):
        saved = os.environ.get('RAGE_JACKETED_MODEL')
        if saved and os.path.exists(saved):
            cls.model = json.load(open(saved, encoding='utf-8'))
            cls.out = json.load(open(saved.replace('.model.json', '.out.json'), encoding='utf-8'))
        else:
            cls.model, cls.out = author_jacketed_reactor()
        cls.replayed = build(cls.model)
        cls.system = DerivedSystem(cls.model)
        cls.result = resolve_system(cls.system)
        cls.times = np.array(cls.result['ejes'][0]['valores'])
        cls.reference, cls.reference_T, cls.reference_Tj = reference_jacketed(cls.times)

    def test_shared_wall_heat_enters_both_balances_once_with_opposite_signs(self):
        graph = self.replayed.graph
        wall = sp.Function('wallHeat')(T)
        reactor = graph.nodes[self.out['reactor.heat']].equation
        jacket = graph.nodes[self.out['jacket.heat']].equation
        self.assertEqual(sp.diff(reactor.rhs, wall), -1)
        self.assertEqual(sp.diff(jacket.rhs, wall), 1)
        total = graph.nodes[self.out['totalEnergy']].equation
        self.assertFalse(sp.expand(total.lhs - total.rhs).has(wall))
        # The coupled state equations contain both closure temperatures and no residual heat quantity.
        for key in ('energy', 'jacket.energy'):
            rhs = graph.nodes[self.out[key]].equation.rhs
            names = {str(a.func) for a in rhs.atoms(sp.core.function.AppliedUndef)}
            self.assertTrue({'T__cell', 'T__jacket'} <= names, names)
            self.assertNotIn('wallHeat', names)

    def test_trajectory_against_independent_lsoda_integration(self):
        self.assertEqual(self.result['estado'], 'resuelto')
        T_cell = _closure_T(self.system, self.result, 'cell')
        T_jacket = _closure_T(self.system, self.result, JACKET)
        self.assertLess(np.max(abs(T_cell - self.reference_T)), 2e-5)      # K
        self.assertLess(np.max(abs(T_jacket - self.reference_Tj)), 2e-5)   # K
        values = _series(self.result)
        ids = [row['quantityId'] for row in self.model['motores']['derivedExecution']['states']]
        masses = demo02_cstr.reference_functions()[1]
        for k in range(4):
            self.assertLess(np.max(abs(values['campo.' + ids[k]] / masses[k] - self.reference.y[k])), 2e-6)   # mol
        self.assertLess(np.max(abs(values['campo.' + ids[4]] - self.reference.y[4])) / abs(self.reference.y[4][0]), 5e-8)   # 0.084 J on 3.8e6 J
        self.assertLess(np.max(abs(values['campo.' + ids[5]] - self.reference.y[5])), 1e-9)   # kg/s
        self.assertEqual(np.max(abs(values['campo.' + ids[6]] - JACKETED['mj0'])), 0.0)      # kg
        self.assertEqual(float(self.model['datos']['service.UA']['declaracion']['texto']), JACKETED['UA'])   # the record describes the run (JR-2)
        self.assertEqual(float(self.model['datos']['solve.tf']['declaracion']['texto']), JACKETED['tf'])
        self.assertLess(np.max(abs(values['campo.' + ids[7]] - self.reference.y[7])) / abs(self.reference.y[7][0]), 1e-8)
        checks = {row['id']: row for row in self.result['verificaciones']}
        self.assertLess(checks['conservation.matter.cell.total']['valor'], 1e-9)
        if 'conservation.matter.' + JACKET + '.total' in checks:   # absent in a model saved before the jacket check was added
            self.assertLess(checks['conservation.matter.' + JACKET + '.total']['valor'], 1e-9)
        for owner in ('cell', JACKET):
            self.assertLessEqual(checks['thermodynamics.closure.' + owner]['valor'], checks['thermodynamics.closure.' + owner]['tolerancia'])

    def test_approach_to_the_coupled_steady_state(self):
        steady = steady_jacketed()
        T_cell = _closure_T(self.system, self.result, 'cell')
        T_jacket = _closure_T(self.system, self.result, JACKET)
        # At 60000 s (about a hundred holdup times) the pair is at its steady state: the engine's final sample, the
        # reference's final sample and the joint root must agree.
        self.assertLess(abs(T_cell[-1] - self.reference_T[-1]), 2e-5)
        self.assertLess(abs(T_cell[-1] - steady['temperature']), 1e-6)         # K
        self.assertLess(abs(T_jacket[-1] - steady['jacketTemperature']), 1e-6)
        self.assertLess(steady['residual'], 1e-8)   # scaled hybr residual
        sol, T_long, Tj_long = reference_jacketed(np.linspace(0, 60000, 7))
        self.assertLess(abs(T_long[-1] - steady['temperature']), 1e-3)      # K
        self.assertLess(abs(Tj_long[-1] - steady['jacketTemperature']), 1e-3)
        self.assertLess(T_jacket[-1], T_cell[-1])
        self.assertGreater(T_jacket[-1], JACKETED['Tin'])

    def test_prescribed_jacket_temperature_is_the_large_flow_limit(self):
        """With a large coolant flow the jacket stays at its inlet temperature and the reactor steady state is the accepted single-reactor reference with Tj = Tin."""
        data = dict(jacketed_data(), coolantFlow=5.0)
        model = copy.deepcopy(self.model)
        model['datos']['service.flow']['declaracion']['texto'] = repr(5.0)
        model['datos']['solve.tf']['declaracion']['texto'] = repr(60000.0)
        system = DerivedSystem(model)
        result = resolve_system(system)
        self.assertEqual(result['estado'], 'resuelto')
        T_cell = _closure_T(system, result, 'cell')
        T_jacket = _closure_T(system, result, JACKET)
        # The limit is isenthalpic: the coolant enters at 2 bar and leaves at the jacket pressure, so with a large flow the
        # jacket sits at T* with h(T*, P_j) = h(T_in, P_in), 0.024 K above T_in (the P v term of the liquid, 100 J/kg).
        enthalpy, temperature, _ = water_enthalpy_functions(data['Pj'])
        limit = temperature(enthalpy(data['Tin'], data['Pin']))
        self.assertAlmostEqual(limit - data['Tin'], 0.024, delta=0.005)
        cp = (enthalpy(limit + 0.5) - enthalpy(limit - 0.5))   # package liquid heat capacity of the coolant, J/(kg K)
        bound = data['UA'] * (T_cell.max() - limit) / (5.0 * cp)
        self.assertLess(abs(T_jacket[-1] - limit), bound + 1e-5)   # K
        row = demo02_cstr.sequential_steady_reference(1, dict(data, Tj=limit))[0]
        self.assertLess(abs(T_cell[-1] - row['temperature']), 2 * bound + 1e-3)   # K
        coupled = steady_jacketed(data)
        self.assertLess(abs(T_cell[-1] - coupled['temperature']), 1e-3)
        self.assertLess(abs(coupled['temperature'] - row['temperature']), bound + 1e-6)


if __name__ == '__main__':
    unittest.main()
