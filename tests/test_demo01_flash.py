"""Demo 0.1 flash drum fixture (frontend/testing/demo01/flashDrum.ts).

The frozen fixture must equal a fresh authoring through the shared tools and solve through derived execution
in agreement with an independent DOP853 integration that calls core.mezclas directly (no bridge, no graph):
states, temperature, level and the located vapour-appearance event.
"""
import unittest

import numpy as np

from demo01_flash import DEMO, FIXTURE, author_demo_flash, frozen_model, publication
from derived_closure_inputs import OWNER, reference_drum
from core.compilador.derived import DerivedSystem, resolve_system


class DemoFlashDrum(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = frozen_model()
        cls.system = DerivedSystem(cls.model)
        cls.result = resolve_system(cls.system)
        cls.times = np.array(cls.result['ejes'][0]['valores'])
        cls.reference, cls.reference_T = reference_drum(cls.times, DEMO)
        cls.values = {row['id']: np.array(row['valores']) for row in cls.result['series']}

    def _closure(self, quantity):
        return self.values['closure.' + OWNER + '.' + self.system.ids[quantity]]

    def test_fixture_is_the_shared_authoring(self):
        self.assertEqual(FIXTURE.read_text(encoding='utf-8'), publication(author_demo_flash()))

    def test_states_temperature_and_level_against_direct_package_integration(self):
        from core import mezclas
        self.assertEqual(self.result['estado'], 'resuelto')
        package = mezclas.Sistema('unifac-dortmund-public', ['64-17-5', '7732-18-5'])
        M = np.asarray(package.M)
        level = []
        for y in self.reference.y.T:
            state = package.equilibrio_PH(DEMO['P'], y[2], np.asarray(y[:2]) / M)
            level.append(sum(f.n * f.v for f in state.fases if f.tipo != 'vapor') / DEMO['area'])
        execution = self.model['motores']['derivedExecution']
        ids = [row['quantityId'] for row in execution['states']]
        for index in range(2):
            self.assertLess(np.max(abs(self.values['campo.' + ids[index]] - self.reference.y[index])), 2e-6)
        self.assertLess(np.max(abs(self.values['campo.' + ids[2]] - self.reference.y[2])) / abs(self.reference.y[2][0]), 1e-8)
        T = self._closure(self.system.closures[0].T)
        self.assertLess(np.max(abs(T - self.reference_T)), 2e-5)
        level_id = next(row['quantityId'] for row in execution['reconstructions']
                        if str(self.system._quantity(row['quantityId'])) == 'level(t)')
        self.assertLess(np.max(abs(self.values['observable.' + level_id] - np.asarray(level))), 1e-7)
        # Subcooled start, two-phase steady state near the mixture bubble point at 1 atm, rising level.
        self.assertAlmostEqual(T[0], DEMO['T0'], delta=1e-8)
        self.assertAlmostEqual(T[-1], 362.54, delta=0.05)
        self.assertGreater(level[-1], level[0])
        checks = {row['id']: row for row in self.result['verificaciones']}
        self.assertLessEqual(checks['thermodynamics.closure.' + OWNER]['valor'], checks['thermodynamics.closure.' + OWNER]['tolerancia'])
        self.assertLess(checks['conservation.matter.' + OWNER + '.total']['valor'], 1e-9)

    def test_vapour_appears_once_at_the_independent_bubble_point(self):
        from core import mezclas
        events = [e for e in self.result['eventos'] if e['codigo'] == 'aparicion_fase']
        self.assertEqual(len(events), 1)
        self.assertIn('vapor-1', events[0]['descripcion'])
        package = mezclas.Sistema('unifac-dortmund-public', ['64-17-5', '7732-18-5'])
        M = np.asarray(package.M)

        def vapour(index):
            y = self.reference.y[:, index]
            return any(f.tipo == 'vapor' and f.n > 0 for f in package.equilibrio_PH(DEMO['P'], y[2], np.asarray(y[:2]) / M).fases)
        first = next(i for i in range(len(self.times)) if vapour(i))
        self.assertLess(self.times[first - 1], events[0]['valor'])
        self.assertLessEqual(events[0]['valor'], self.times[first])
        # RD-3: the output grid brackets only to 37.5 s; refine the reference to 0.05 s inside that interval.
        fine = np.linspace(self.times[first - 1], self.times[first], 751)
        refined, _ = reference_drum(np.concatenate([[0.0], fine]), DEMO)
        crossing = next(i for i in range(1, refined.y.shape[1]) if any(
            f.tipo == 'vapor' and f.n > 0 for f in package.equilibrio_PH(DEMO['P'], refined.y[2, i], refined.y[:2, i] / M).fases))
        self.assertGreater(crossing, 1)
        self.assertLess(abs(events[0]['valor'] - refined.t[crossing]), 0.5)
        closure = self.system.closures[0]
        present = self._closure(closure.output_map[next(i for i, (_, key) in enumerate(closure.output_map) if key == ('present', 'V'))][0])
        self.assertEqual((present[0], present[-1]), (0., 1.))
        # The vent draws a vapour richer in ethanol than the liquid it leaves.
        vapour_x = self._closure(closure.output_map[next(i for i, (_, key) in enumerate(closure.output_map) if key == ('x', 'V', 0))][0])
        liquid_x = self._closure(closure.output_map[next(i for i, (_, key) in enumerate(closure.output_map) if key == ('x', 'L', 0))][0])
        self.assertGreater(vapour_x[-1], 5 * liquid_x[-1])


if __name__ == '__main__':
    unittest.main()
