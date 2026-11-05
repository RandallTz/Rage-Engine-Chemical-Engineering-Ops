"""Steady state of package-closure volumes as a Transform of the dynamic deduction (demo-02-steady).

The version-5 selections reuse the same deduced derivative rows of the dynamic models (the Demo 0.1
flash drum and the momentum-outlet drum) at zero rate. Independent references solve the same physics
with direct core.mezclas calls and scipy.optimize.root.
"""
import copy
import math
import unittest

import numpy as np
from scipy.optimize import root

from demo01_flash import DEMO, frozen_model
from core.compilador.steady import SteadySystem
from core.compilador.derived_graph import LoweringError

ETHANOL, WATER = '64-17-5', '7732-18-5'


def _datum(model, key, value, unit):
    model['datos'][key] = {'magnitud': key, 'funcion': 'parametro', 'declaracion': {'texto': repr(float(value)), 'unidad': unit},
                           'origen': {'propietarioId': 'estudio', 'ruta': key}}
    return key


def steady_selection(model, seeds, residual_scales):
    """Version-5 selection over the same deduced rows as the dynamic version-1 selection."""
    model = copy.deepcopy(model)
    dynamic = model['motores']['derivedExecution']
    states = dynamic['states']
    variables = {}
    for row in states:
        qid = row['quantityId']
        seed, lower, upper, scale, unit = seeds[qid] if qid in seeds else seeds[len(variables)]
        variables[qid] = {key: _datum(model, 'steady.' + qid + '.' + key, value, unit) for key, value in
                          [('seedDataId', seed), ('lowerDataId', lower), ('upperDataId', upper), ('scaleDataId', scale)]}
    scales = {row['equationId']: _datum(model, 'steady.residual.' + row['equationId'], value, unit)
              for row, (value, unit) in zip(states, residual_scales)}
    model['motores']['derivedExecution'] = {
        'format': 'rage.derived-execution', 'version': 5, 'sourceSignature': dynamic['sourceSignature'], 'timeId': dynamic['timeId'],
        'states': states, 'algebraic': [], 'unknowns': [row['quantityId'] for row in states], 'parameters': dynamic['parameters'],
        'invariants': {}, 'reconstructions': dynamic['reconstructions'],
        # A steady check scales the specialized balance rate, not the dynamic inventory.
        'checks': [{'equationId': row['equationId'], 'scaleDataId': _datum(model, 'steady.check.' + row['equationId'], 0.01, 'kg/s')}
                   for row in dynamic['checks']],
        'nonlinear': {'variables': variables, 'residualScales': scales, 'residualTolerance': 1e-9, 'stepTolerance': 1e-12,
                      'maxIterations': 30, 'maxBacktracks': 20}}
    model['estudio'] = {'tipo': 'steady', 'version': 1, 'metodoSolicitado': 'damped_newton'}
    return model


def reference_drum_steady(data, momentum=False, guess=None):
    """Steady state of the same drum physics from direct core.mezclas calls and scipy root (no bridge, no graph)."""
    from core import mezclas
    s = mezclas.Sistema('unifac-dortmund-public', [ETHANOL, WATER])
    M = np.asarray(s.M, dtype=float)
    zF = np.asarray(data['zF'])
    hF_mass = s.equilibrio_TP(data['TF'], data['PF'], zF).H / float(zF @ M)
    wF = zF * M / float(zF @ M)

    def rates(y):
        e = s.equilibrio_PH(data['P'], y[2], np.asarray(y[:2]) / M)
        q = np.zeros(2); Hs = 0.0; dF = None
        for phase in e.fases:
            x = np.asarray(phase.x)
            if phase.tipo == 'vapor':
                F = data['vent'] * phase.n
                q += F * x * M; Hs += F * phase.h
            else:
                level = phase.n * phase.v / data['area']
                rho = phase.M / phase.v
                if momentum:
                    F = y[3]
                    dF = data['pipeArea'] / data['length'] * (data['P'] + rho * data['g'] * level - data['Pout']
                                                             - data['loss'] * F**2 / (2 * rho * data['pipeArea']**2))
                    q += F * x * M / phase.M; Hs += F * phase.h / phase.M
                else:
                    F = data['Cd'] * data['orifice'] * math.sqrt(2 * data['g'] * level) / phase.v
                    q += F * x * M; Hs += F * phase.h
        out = [*(data['feed'] * wF - q), data['feed'] * hF_mass - Hs + data['Q']]
        return (out + [dF] if momentum else out), e

    scales = np.array([0.1, 0.1, 1e4] + ([1.0] if momentum else []))
    solution = root(lambda y: np.asarray(rates(y)[0]) / scales, guess, method='hybr', options={'xtol': 1e-13})
    assert solution.success, solution.message
    return solution.x, rates(solution.x)[1]


class FlashDrumSteady(unittest.TestCase):
    """The Demo 0.1 flash drum: its deduced rows at zero rate, closure evaluated through the package."""

    @classmethod
    def setUpClass(cls):
        cls.dynamic = frozen_model()
        ids = [row['quantityId'] for row in cls.dynamic['motores']['derivedExecution']['states']]
        seeds = {ids[0]: (8.0, 0.0, 200.0, 10.0, 'kg'), ids[1]: (150.0, 1.0, 2000.0, 100.0, 'kg'),
                 ids[2]: (-2.4e8, -5e9, -1e6, 1e8, 'J')}
        cls.model = steady_selection(cls.dynamic, seeds, [(0.01, 'kg/s'), (0.01, 'kg/s'), (1000.0, 'W')])
        cls.system = SteadySystem(cls.model)
        cls.result = cls.system.solve()
        cls.ids = ids
        values = {row['id']: row['valores'] for row in cls.result['series']}
        cls.root = np.array([values['steady.' + qid] for qid in ids])
        cls.reference, cls.reference_state = reference_drum_steady(DEMO, guess=cls.root * np.array([1.05, 0.97, 1.01]))

    def test_steady_root_against_direct_package_solution(self):
        self.assertEqual(self.result['estado'], 'resuelto')
        np.testing.assert_allclose(self.root[:2], self.reference[:2], rtol=1e-7, atol=1e-8)
        self.assertLess(abs(self.root[2] - self.reference[2]) / abs(self.reference[2]), 1e-9)
        closure = self.system.closures.closures[0]
        values = {row['id']: row['valores'] for row in self.result['series']}
        temperature = values['closure.' + next(k for k, q in self.system.quantities.items() if q == closure.T)]
        self.assertAlmostEqual(temperature, self.reference_state.T, delta=1e-6)
        checks = {row['id']: row for row in self.result['verificaciones']}
        self.assertLessEqual(checks['thermodynamics.closure.drum']['valor'], 1.)
        self.assertLessEqual(checks['steady.scaled_residual']['valor'], 1e-9)

    def test_phase_presence_comes_from_the_certified_flash(self):
        details = self.result['procedencia']['steadyDiagnostics']['thermodynamicClosures'][0]
        expected = sorted(f.id for f in self.reference_state.fases if f.n > 0)
        self.assertEqual(sorted(details['phaseSet']), expected)
        self.assertIn('vapor-1', details['phaseSet'])

    def test_steady_state_is_the_long_time_limit_of_the_dynamic_run(self):
        # The same deduced model integrated in time (common RK45 with its located phase events)
        # settles on the steady root; 6000 s is many holdup times of the drum.
        from core.compilador.derived import DerivedSystem, resolve_system
        model = copy.deepcopy(self.dynamic)
        model['datos'][model['estudio']['tiempoId']]['declaracion']['texto'] = '6000'
        result = resolve_system(DerivedSystem(model))
        self.assertEqual(result['estado'], 'resuelto')
        values = {row['id']: np.array(row['valores']) for row in result['series']}
        final = np.array([values['campo.' + qid][-1] for qid in self.ids])
        rate = np.array([values['campo.' + qid][-1] - values['campo.' + qid][-2] for qid in self.ids])
        np.testing.assert_allclose(final[:2], self.root[:2], rtol=2e-4)
        self.assertLess(abs(final[2] - self.root[2]) / abs(self.root[2]), 2e-5)
        self.assertLess(np.max(np.abs(rate[:2])), 1e-2)

    def test_publication_passes_the_strict_steady_readers(self):
        from core.compilador.steady import read_result
        read_result(copy.deepcopy(self.result))
        tampered = copy.deepcopy(self.result)
        tampered['procedencia']['steadyDiagnostics']['thermodynamicClosures'][0]['volumeId'] = 'other'
        with self.assertRaises(ValueError):
            read_result(tampered)

    def test_rows_are_the_dynamic_rows_at_zero_rate(self):
        report = self.result['procedencia']['compilation']
        dynamic_rows = [row['equationId'] for row in self.dynamic['motores']['derivedExecution']['states']]
        self.assertEqual([row['id'] for row in report['rows']], dynamic_rows)
        self.assertEqual(self.model['motores']['derivedExecution']['sourceSignature'],
                         self.dynamic['motores']['derivedExecution']['sourceSignature'])


class MomentumDrumSteady(unittest.TestCase):
    """The momentum-outlet drum: the path momentum row at zero rate balances the head against the loss."""

    @classmethod
    def setUpClass(cls):
        from derived_momentum_inputs import OUTLET, author_outlet, select_outlet
        author, out = author_outlet()
        cls.data = OUTLET
        dynamic = select_outlet(author, out)
        cls.out = out
        ids = [row['quantityId'] for row in dynamic['motores']['derivedExecution']['states']]
        seeds = {ids[0]: (8.0, 0.0, 200.0, 10.0, 'kg'), ids[1]: (90.0, 1.0, 2000.0, 100.0, 'kg'),
                 ids[2]: (-1.6e8, -5e9, -1e6, 1e8, 'J'), ids[3]: (0.45, 1e-3, 5.0, 0.1, 'kg/s')}
        cls.model = steady_selection(dynamic, seeds, [(0.01, 'kg/s'), (0.01, 'kg/s'), (1000.0, 'W'), (1e-4, 'kg/s2')])
        cls.system = SteadySystem(cls.model)
        cls.result = cls.system.solve()
        values = {row['id']: row['valores'] for row in cls.result['series']}
        cls.root = np.array([values['steady.' + qid] for qid in ids])
        cls.reference, cls.reference_state = reference_drum_steady(OUTLET, momentum=True, guess=cls.root * np.array([1.05, 0.97, 1.01, 1.02]))

    def test_steady_root_and_outlet_flow_against_direct_package_solution(self):
        self.assertEqual(self.result['estado'], 'resuelto')
        np.testing.assert_allclose(self.root[[0, 1, 3]], self.reference[[0, 1, 3]], rtol=1e-7, atol=1e-9)
        self.assertLess(abs(self.root[2] - self.reference[2]) / abs(self.reference[2]), 1e-9)
        # The steady outlet flow balances the liquid head against the declared loss.
        liquid = next(f for f in self.reference_state.fases if f.tipo != 'vapor')
        rho = liquid.M / liquid.v
        head = rho * self.data['g'] * liquid.n * liquid.v / self.data['area']
        F = self.root[3]
        self.assertAlmostEqual(head, self.data['loss'] * F**2 / (2 * rho * self.data['pipeArea']**2), delta=1e-6 * head)

    def test_momentum_row_is_specialized_not_replaced(self):
        report = self.result['procedencia']['compilation']
        flow = next(row for row in report['rows'] if row['id'] == self.out['flow'])
        self.assertFalse(flow['identity'])
        self.assertIn('liquidMassFlow', str(self.model['motores']['derivedExecution']['unknowns']) + str(self.system.unknowns))


class Rejections(unittest.TestCase):
    def test_unresolved_closure_input_is_rejected(self):
        dynamic = frozen_model()
        ids = [row['quantityId'] for row in dynamic['motores']['derivedExecution']['states']]
        seeds = {ids[0]: (8.0, 0.0, 200.0, 10.0, 'kg'), ids[1]: (150.0, 1.0, 2000.0, 100.0, 'kg'), ids[2]: (-2.4e8, -5e9, -1e6, 1e8, 'J')}
        model = steady_selection(dynamic, seeds, [(0.01, 'kg/s'), (0.01, 'kg/s'), (1000.0, 'W')])
        selection = model['motores']['derivedExecution']
        selection['reconstructions'] = [row for row in selection['reconstructions'] if not row['equationId'].endswith('component-amount-1')]
        with self.assertRaises(LoweringError) as caught:
            SteadySystem(model)
        self.assertIn(caught.exception.diagnostics[0]['code'], ('closure_input_unresolved', 'steady_time_dependent', 'steady_unsupported_structure'))


if __name__ == '__main__':
    unittest.main()
