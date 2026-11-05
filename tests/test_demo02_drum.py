"""Demo 0.2 equipment template fixture (frontend/testing/demo02/flashDrum.ts).

The frozen fixture must equal a fresh authoring through the shared tools; it carries the equipment template
record with typed ports; it solves through derived execution in agreement with an independent DOP853
integration that calls core.mezclas directly; and its steady state, solved through the version-5 steady
path from the same deduced rows, is the long-time limit of the dynamic run.
"""
import copy
import unittest

import numpy as np

from demo02_drum import DEMO, FIXTURE, author_demo_drum, frozen_model, publication
from derived_closure_inputs import OWNER
from derived_momentum_inputs import PIPE, reference_outlet
from test_steady_package_closure import reference_drum_steady, steady_selection
from core.compilador.derived import DerivedSystem, resolve_system
from core.compilador.steady import SteadySystem, read_result
from core.modelo import leer_modelo_comun


class DemoDrumTemplate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = frozen_model()
        cls.system = DerivedSystem(cls.model)
        cls.result = resolve_system(cls.system)
        cls.times = np.array(cls.result['ejes'][0]['valores'])
        cls.reference, cls.reference_T = reference_outlet(cls.times, DEMO)
        cls.values = {row['id']: np.array(row['valores']) for row in cls.result['series']}
        cls.ids = [row['quantityId'] for row in cls.model['motores']['derivedExecution']['states']]

    def test_fixture_is_the_shared_authoring(self):
        self.assertEqual(FIXTURE.read_text(encoding='utf-8'), publication(author_demo_drum()[0]))

    def test_equipment_record_and_typed_ports(self):
        model = leer_modelo_comun(copy.deepcopy(self.model))
        template = model['template']
        self.assertTrue(template['equipment'])
        self.assertEqual(set(template['recipe']['journals']) >= {'materialDerivation', 'energyDerivation', 'momentumDerivation', 'thermodynamicDerivation'}, True)
        ports = {port['id']: port for port in template['ports']}
        self.assertEqual(set(ports), {'feed', 'vapour', 'liquid', 'heat'})
        self.assertEqual((ports['feed']['direction'], ports['feed']['exteriorState']), ('inlet', 'estadoExterior'))
        self.assertEqual((ports['vapour']['direction'], ports['vapour']['donorPhase']), ('outlet', 'vapor'))
        self.assertEqual((ports['liquid']['volumeId'], ports['liquid']['direction']), (PIPE, 'outlet'))
        self.assertEqual(ports['heat']['boundary'], {'type': 'term', 'id': 'calor'})
        # Every active balance of the drum, including momentum, is in the recorded recipe.
        drum = next(v for v in model['volumenes'] if v['id'] == OWNER)
        self.assertEqual(drum['balances'], {'materia': True, 'energia': True, 'momento': True})
        # No assumption text names a piece of equipment (decision 4 of dec-demo02-dynamic-first).
        reasons = ' '.join(op.get('reason', '') for op in model['motores']['equationWorkbench']['operations']).lower()
        for word in ('drum', 'valve', 'vent', 'orifice', 'pump', 'tray', 'distillation column'):
            self.assertNotIn(word, reasons)

    def test_dynamic_run_against_direct_package_integration(self):
        self.assertEqual(self.result['estado'], 'resuelto')
        for index, tolerance in [(0, 2e-6), (1, 2e-6), (3, 1e-7)]:
            self.assertLess(np.max(abs(self.values['campo.' + self.ids[index]] - self.reference.y[index])), tolerance)
        self.assertLess(np.max(abs(self.values['campo.' + self.ids[2]] - self.reference.y[2])) / abs(self.reference.y[2][0]), 1e-8)
        T = self.values['closure.' + OWNER + '.' + self.system.ids[self.system.closures[0].T]]
        self.assertLess(np.max(abs(T - self.reference_T)), 2e-5)
        events = [e for e in self.result['eventos'] if e['codigo'] == 'aparicion_fase']
        self.assertEqual(len(events), 1)
        # The published level is the free-surface elevation: V_L / A above the floor at 0 m.
        level_row = self.model['motores']['derivedExecution']['reconstructions'][-1]
        from core import mezclas
        package = mezclas.Sistema('unifac-dortmund-public', ['64-17-5', '7732-18-5'])
        M = np.asarray(package.M)
        level = [sum(f.n * f.v for f in package.equilibrio_PH(DEMO['P'], y[2], np.asarray(y[:2]) / M).fases if f.tipo != 'vapor') / DEMO['area']
                 for y in self.reference.y.T]
        self.assertLess(np.max(abs(self.values['observable.' + level_row['quantityId']] - np.asarray(level))), 1e-7)

    def test_steady_state_is_the_long_time_limit(self):
        seeds = {self.ids[0]: (8.0, 0.0, 200.0, 10.0, 'kg'), self.ids[1]: (90.0, 1.0, 2000.0, 100.0, 'kg'),
                 self.ids[2]: (-1.6e8, -5e9, -1e6, 1e8, 'J'), self.ids[3]: (0.45, 1e-3, 5.0, 0.1, 'kg/s')}
        model = steady_selection(self.model, seeds, [(0.01, 'kg/s'), (0.01, 'kg/s'), (1000.0, 'W'), (1e-4, 'kg/s2')])
        result = SteadySystem(model).solve()
        read_result(copy.deepcopy(result))
        values = {row['id']: row['valores'] for row in result['series']}
        root = np.array([values['steady.' + qid] for qid in self.ids])
        reference, _ = reference_drum_steady(DEMO, momentum=True, guess=root * np.array([1.05, 0.97, 1.01, 1.02]))
        np.testing.assert_allclose(root[[0, 1, 3]], reference[[0, 1, 3]], rtol=1e-7, atol=1e-9)
        self.assertLess(abs(root[2] - reference[2]) / abs(reference[2]), 1e-9)
        # The same deduced model integrated long enough to settle (the 1200 s fixture run is still approaching it).
        settled = copy.deepcopy(self.model)
        settled['datos'][settled['estudio']['tiempoId']]['declaracion']['texto'] = '6000'
        long_run = resolve_system(DerivedSystem(settled))
        values = {row['id']: np.array(row['valores']) for row in long_run['series']}
        final = np.array([values['campo.' + qid][-1] for qid in self.ids])
        np.testing.assert_allclose(final[[0, 1, 3]], root[[0, 1, 3]], rtol=2e-4)
        self.assertLess(abs(final[2] - root[2]) / abs(root[2]), 2e-5)


if __name__ == '__main__':
    unittest.main()
