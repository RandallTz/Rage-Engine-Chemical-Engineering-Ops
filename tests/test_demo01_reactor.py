"""Demo 0.1 batch reactor fixture (frontend/testing/demo01/batchReactor.ts).

The frozen fixture must equal a fresh authoring through the shared tools, solve through derived execution,
match an independent DOP853 integration whose caloric inventory is Gibbs-Helmholtz on the package potentials,
and end at the certified equilibrium (its rates are in detailed balance with K(T) at the jacket temperature).
"""
import unittest

import numpy as np

from demo01_reactor import DEMO, FIXTURE, author_demo_reactor, demo_data, detailed_balance, frozen_model, publication
from derived_reactor_inputs import OWNER, reference_reactor
from core.compilador.derived import DerivedSystem, resolve_system


class DemoBatchReactor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = frozen_model()
        cls.system = DerivedSystem(cls.model)
        cls.result = resolve_system(cls.system)
        cls.times = np.array(cls.result['ejes'][0]['valores'])
        cls.reference, cls.reference_T = reference_reactor(cls.times, demo_data())

    def test_fixture_is_the_shared_authoring(self):
        self.assertEqual(FIXTURE.read_text(encoding='utf-8'), publication(author_demo_reactor()))

    def test_rates_in_detailed_balance_with_the_package(self):
        balance = detailed_balance()
        self.assertAlmostEqual(balance['K'], 3.6710, delta=1e-3)
        self.assertAlmostEqual(balance['kr'] * balance['K'], DEMO['kf'], delta=1e-20)
        self.assertAlmostEqual(balance['Er'] - DEMO['E'], -balance['dH'], delta=1e-9)
        self.assertTrue(-4000 < balance['dH'] < -2000, balance['dH'])

    def test_fixture_reverse_data_follow_from_its_own_forward_data(self):
        # RD-1: kr and Er are bare data in the common model; recompute them from the fixture's kf, Ef, Tref, charge and P.
        datum = lambda key: float(self.model['datos'][key]['declaracion']['texto'])
        own = {'n0': tuple(datum('initial%d' % i) for i in (1, 2, 3, 4)), 'P': datum(OWNER + '.pressure'),
               'Tref': datum('rateTemperature'), 'kf': datum('forwardRate'), 'E': datum('activation')}
        balance = detailed_balance(own)
        self.assertAlmostEqual(datum('reverseRate'), balance['kr'], delta=1e-12 * balance['kr'])
        self.assertAlmostEqual(datum('reverseActivation'), balance['Er'], delta=1e-6)

    def test_trajectory_against_independent_reference(self):
        self.assertEqual(self.result['estado'], 'resuelto')
        values = {row['id']: np.array(row['valores']) for row in self.result['series']}
        ids = [row['quantityId'] for row in self.model['motores']['derivedExecution']['states']]
        for index in range(4):
            self.assertLess(np.max(abs(values['campo.' + ids[index]] - self.reference.y[index])), 1e-7)
        self.assertLess(np.max(abs(values['campo.' + ids[4]] - self.reference.y[4])) / abs(self.reference.y[4][0]), 1e-8)
        closure = self.system.closures[0]
        T = values['closure.' + OWNER + '.' + self.system.ids[closure.T]]
        self.assertLess(np.max(abs(T - self.reference_T)), 1e-5)
        # Jacket heating from 320 K, a small reaction-heat overshoot above the jacket, then the jacket temperature.
        self.assertAlmostEqual(T[0], DEMO['T0'], delta=1e-8)
        self.assertAlmostEqual(T.max(), 341.154, delta=0.01)
        self.assertAlmostEqual(T[-1], DEMO['Tj'], delta=1e-2)
        # Inside the tabulated acetic acid cp_L range (Perry 2-153, 289.81-391.05 K).
        self.assertTrue(289.81 <= T.min() and T.max() <= 391.05)

    def test_ends_at_the_certified_equilibrium(self):
        checks = {row['id']: row for row in self.result['verificaciones']}
        row = checks['reactions.equilibrium_limit.' + OWNER]
        self.assertLess(row['valor'], row['tolerancia'])
        detail = self.result['procedencia']['reactionEquilibrium'][0]
        np.testing.assert_allclose(detail['finalAmounts'], detailed_balance()['equilibrium'], rtol=0, atol=1e-3)
        self.assertLessEqual(checks['thermodynamics.closure.' + OWNER]['valor'], checks['thermodynamics.closure.' + OWNER]['tolerancia'])
        self.assertLess(checks['conservation.matter.' + OWNER + '.total']['valor'], 1e-9)


if __name__ == '__main__':
    unittest.main()
