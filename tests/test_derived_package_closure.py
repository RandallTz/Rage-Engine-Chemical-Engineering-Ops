"""Package thermodynamic closures in derived execution (FD-1 to FD-4).

Fresh shared-law authors only (tests/derived_closure_inputs.py). References
call core.mezclas directly, never the bridge or the lowered graph.
"""
import copy
import math
import unittest

import numpy as np
import sympy as sp

from derived_closure_inputs import (DRUM, OWNER, VESSEL, author_drum, author_vessel, reference_drum,
                                    reference_vessel, select_drum, select_vessel)
from core.compilador.derived import DerivedSystem, LoweringError, resolve_system
from core.termodinamica import derived_bridge as bridge


def _series(result):
    return {row['id']: np.array(row['valores']) for row in result['series']}


def _closure_series(system, result, quantity):
    return _series(result)['closure.' + OWNER + '.' + system.ids[quantity]]


class TwoPhaseDrum(unittest.TestCase):
    """Feed, vent and orifice drum at prescribed pressure; the vapour appears during the run."""

    @classmethod
    def setUpClass(cls):
        cls.author, cls.out = author_drum()
        cls.runs = {}
        for method in ('rk45', 'bdf'):
            model = select_drum(cls.author, cls.out, method=method)
            system = DerivedSystem(model)
            cls.runs[method] = (model, system, resolve_system(system))
        times = np.array(cls.runs['rk45'][2]['ejes'][0]['valores'])
        cls.times = times
        cls.reference, cls.reference_T = reference_drum(times)

    def test_states_temperature_and_level_against_direct_package_integration(self):
        from core import mezclas
        package = mezclas.Sistema('unifac-dortmund-public', ['64-17-5', '7732-18-5'])
        M = np.asarray(package.M)
        liquid_volume = []
        for y in self.reference.y.T:
            state = package.equilibrio_PH(DRUM['P'], y[2], np.asarray(y[:2]) / M)
            liquid_volume.append(sum(f.n * f.v for f in state.fases if f.tipo != 'vapor'))
        level = np.asarray(liquid_volume) / DRUM['area']
        for method, (model, system, result) in self.runs.items():
            with self.subTest(method=method):
                self.assertEqual(result['estado'], 'resuelto')
                self.assertEqual(np.array(result['ejes'][0]['valores']).tolist(), self.times.tolist())
                values = _series(result)
                ids = [row['quantityId'] for row in model['motores']['derivedExecution']['states']]
                self.assertLess(np.max(abs(values['campo.' + ids[0]] - self.reference.y[0])), 2e-6)
                self.assertLess(np.max(abs(values['campo.' + ids[1]] - self.reference.y[1])), 2e-6)
                self.assertLess(np.max(abs(values['campo.' + ids[2]] - self.reference.y[2])) / abs(self.reference.y[2][0]), 1e-8)
                closure = system.closures[0]
                self.assertLess(np.max(abs(_closure_series(system, result, closure.T) - self.reference_T)), 2e-5)
                level_id = next(row['quantityId'] for row in model['motores']['derivedExecution']['reconstructions']
                                if str(system._quantity(row['quantityId'])) == 'level(t)')
                self.assertLess(np.max(abs(values['observable.' + level_id] - level)), 1e-7)
                checks = {row['id']: row for row in result['verificaciones']}
                certificate = checks['thermodynamics.closure.' + OWNER]
                self.assertLessEqual(certificate['valor'], certificate['tolerancia'])
                self.assertLess(checks['conservation.matter.' + OWNER + '.total']['valor'], 1e-9)

    def test_vapour_appearance_is_a_located_phase_event(self):
        rk45 = [e for e in self.runs['rk45'][2]['eventos'] if e['codigo'] == 'aparicion_fase']
        bdf = [e for e in self.runs['bdf'][2]['eventos'] if e['codigo'] == 'aparicion_fase']
        self.assertEqual(len(rk45), 1)
        self.assertEqual(len(bdf), 1)
        self.assertIn('vapor-1', rk45[0]['descripcion'] if 'descripcion' in rk45[0] else str(rk45[0]))
        self.assertAlmostEqual(rk45[0]['valor'], bdf[0]['valor'], delta=1e-4)
        # Independent bubble point of the drum inventory along the reference trajectory.
        from core import mezclas
        package = mezclas.Sistema('unifac-dortmund-public', ['64-17-5', '7732-18-5'])
        M = np.asarray(package.M)
        def vapour(t_index):
            y = self.reference.y[:, t_index]
            return any(f.tipo == 'vapor' and f.n > 0 for f in package.equilibrio_PH(DRUM['P'], y[2], np.asarray(y[:2]) / M).fases)
        first = next(i for i in range(len(self.times)) if vapour(i))
        self.assertLess(self.times[first - 1], rk45[0]['valor'])
        self.assertLessEqual(rk45[0]['valor'], self.times[first])
        _, system, result = self.runs['rk45']
        present = _closure_series(system, result, system.closures[0].output_map[next(
            i for i, (_, key) in enumerate(system.closures[0].output_map) if key == ('present', 'V'))][0])
        self.assertEqual(present[0], 0.)
        self.assertEqual(present[-1], 1.)

    def test_lowered_phase_donors_equal_the_bridge_phase_draw(self):
        model, system, result = self.runs['rk45']
        closure = system.closures[0]
        times = np.array(result['ejes'][0]['valores'])
        values = _series(result)
        ids = [row['quantityId'] for row in model['motores']['derivedExecution']['states']]
        y = np.array([values['campo.' + i][-1] for i in ids] + [values['budget.matter.' + OWNER + '.total'][-1]])
        rate = system.rhs(times[-1], y)
        M = np.asarray(closure.molar_masses)
        n = y[:2] / M
        state = bridge.close_state('unifac-dortmund-public', closure.species, n, 'PH', DRUM['P'], y[2])
        vapour = next(p for p in state.phases if p.kind == 'vapor')
        liquid = next(p for p in state.phases if p.kind == 'liquid')
        vent = bridge.phase_draw(state, 'vapor', DRUM['vent'] * vapour.amount)
        level = state.liquid_volume / DRUM['area']
        orifice = bridge.phase_draw(state, 'liquid', DRUM['Cd'] * DRUM['orifice'] * math.sqrt(2 * DRUM['g'] * level) / liquid.v)
        zF = np.asarray(DRUM['zF'])
        feed = bridge.phase_caloric('unifac-dortmund-public', closure.species, DRUM['TF'], DRUM['PF'], list(zF))
        wF = zF * M / (zF @ M)
        expected = DRUM['feed'] * wF - np.asarray(vent['component_mass_flows']) - np.asarray(orifice['component_mass_flows'])
        np.testing.assert_allclose(rate[:2], expected, rtol=1e-9, atol=1e-12)
        energy = DRUM['feed'] * feed['H'] / (zF @ M) - vent['enthalpy_flow'] - orifice['enthalpy_flow'] + DRUM['Q']
        self.assertAlmostEqual(rate[2], energy, delta=1e-7 * abs(energy) + 1e-6)

    def test_report_pins_the_package_closure(self):
        _, system, result = self.runs['rk45']
        report = result['procedencia']['compilation']
        self.assertEqual(report['closureStrategy'], 'package_closure')
        row = report['derivedExecution']['thermodynamicClosures'][0]
        self.assertEqual((row['volumeId'], row['specification'], row['mode']), (OWNER, 'PH', 'equilibrium'))
        self.assertTrue(row['fingerprint'].startswith('sha256:'))
        self.assertEqual(row['inlets']['feed']['phase'], 'liquid')
        packaged = [p for p in report['parameters'] if p.get('source') == 'package']
        self.assertEqual(len(packaged), 2 + 3 + 2)   # molar masses and the inlet h, M, h/M and mass fractions
        changed = select_drum(self.author, self.out)
        changed['termodinamica']['paquetes'][0]['modelo']['id'] = 'unifac-original-public'
        from core.termodinamica import derivation as thermodynamics
        journal = {'format': thermodynamics.FORMAT, 'version': 1, 'volumes': {}}
        journal = thermodynamics.edit_journal(journal, OWNER, {'kind': 'start'})
        changed['motores']['thermodynamicDerivation'] = thermodynamics.edit_journal(
            journal, OWNER, {'kind': 'select_closure'}, thermodynamics.expected_closure(changed, changed['volumenes'][0]))
        other = DerivedSystem(changed)
        # The replayed mathematics is the same; the package fingerprint pins the result signature.
        self.assertNotEqual(other.report['derivedExecution']['thermodynamicClosures'][0]['fingerprint'], row['fingerprint'])
        self.assertNotEqual(other.report['signature'], report['signature'])

    def test_competing_and_unresolved_closures_reject(self):
        model = select_drum(self.author, self.out)
        selection = model['motores']['derivedExecution']
        selection['reconstructions'] = [row for row in selection['reconstructions'] if not row['equationId'].endswith('component-amount-1')]
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'closure_input_unresolved')
        model = select_drum(self.author, self.out)
        system = self.runs['rk45'][1]
        temperature = next(k for k, q in system.quantities.items() if q == system.closures[0].T)
        model['motores']['derivedExecution']['parameters'][temperature] = OWNER + '.temperature'
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(model)
        self.assertIn(caught.exception.diagnostics[0]['code'], ('competing_closure', 'closure_specification'))


class SingleLiquidPolicy(unittest.TestCase):
    def test_declared_single_liquid_stops_when_vapour_would_form(self):
        policy = {'cantidad': 'monofasico', 'cambioInterno': 'prohibido', 'evaluacion': 'equilibrio_estable', 'tiposPermitidos': ['liquido']}
        author, out = author_drum(vapour=False, policy=policy)
        system = DerivedSystem(select_drum(author, out))
        self.assertEqual(system.closures[0].describe()['mode'], 'single_phase')
        result = resolve_system(system)
        self.assertEqual(result['estado'], 'parcial')
        stops = [e for e in result['eventos'] if e['codigo'] == 'politica_incumplida']
        self.assertEqual(len(stops), 1)
        # The liquid stays stable before the stop and the reconstruction is certified.
        times = np.array(result['ejes'][0]['valores'])
        self.assertGreater(times[-1], 30.)
        self.assertLess(times[-1], 120.)
        check = next(v for v in result['verificaciones'] if v['id'] == 'thermodynamics.closure.' + OWNER)
        self.assertLessEqual(check['valor'], check['tolerancia'])


class RigidVessel(unittest.TestCase):
    """Closed rigid vessel heated at constant duty: the UV closure gives T and the vapour pressure."""

    def test_vapour_controlled_pressure_against_direct_uv_closure(self):
        author, out = author_vessel()
        for method in ('rk45', 'bdf'):
            with self.subTest(method=method):
                model = select_vessel(author, out, method=method)
                system = DerivedSystem(model)
                self.assertEqual(system.closures[0].spec, 'UV')
                result = resolve_system(system)
                self.assertEqual(result['estado'], 'resuelto')
                times = np.array(result['ejes'][0]['valores'])
                U0, states = reference_vessel(times)
                values = _series(result)
                ids = [row['quantityId'] for row in model['motores']['derivedExecution']['states']]
                self.assertLess(np.max(abs(values['campo.' + ids[2]] - (U0 + VESSEL['Q'] * times))), 1e-4)
                closure = system.closures[0]
                T = _closure_series(system, result, closure.T)
                P = _closure_series(system, result, closure.P)
                np.testing.assert_allclose(T, [s.T for s in states], rtol=0, atol=1e-7)
                np.testing.assert_allclose(P, [s.P for s in states], rtol=1e-9)
                self.assertGreater(P[-1], 6 * P[0])

    def test_leaving_the_package_domain_is_a_structured_stop(self):
        author, out = author_vessel()
        data = dict(VESSEL, tf=300.)
        result = resolve_system(DerivedSystem(select_vessel(author, out, data)))
        self.assertEqual(result['estado'], 'parcial')
        self.assertTrue(any(e['codigo'] == 'closure_out_of_domain' for e in result['eventos']))


if __name__ == '__main__':
    unittest.main()
