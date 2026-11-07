"""F3H-3: inverse specifications reject package-closure models up front, by name.

The forward v5 steady path solves package-closure volumes (demo-02-steady), but the inverse adapter
rebuilds its augmented block without the closure symbols. Until inverse specifications are lowered over
package closures, the Demo 0.1 flash drum (free solve.Q, specify the first holdup) must be rejected with
its own located code, never with the misleading arithmetic diagnostic about the closure outputs.
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))
from demo01_flash import frozen_model
from test_f3_inverse_specifications import specification
from test_steady_package_closure import steady_selection
from core.compilador.steady import LoweringError, SteadySystem
from core.solvers import inverse_spec
from core.solvers.inverse_steady import InverseSteadySystem


class PackageClosureInverseRejection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dynamic = frozen_model()
        cls.ids = [row['quantityId'] for row in dynamic['motores']['derivedExecution']['states']]
        seeds = {cls.ids[0]: (8.0, 0.0, 200.0, 10.0, 'kg'), cls.ids[1]: (150.0, 1.0, 2000.0, 100.0, 'kg'),
                 cls.ids[2]: (-2.4e8, -5e9, -1e6, 1e8, 'J')}
        cls.model = steady_selection(dynamic, seeds, [(0.01, 'kg/s'), (0.01, 'kg/s'), (1000.0, 'W')])
        cls.heat = next(k for k, v in cls.model['motores']['derivedExecution']['parameters'].items() if v == 'solve.Q')

    def record(self):
        return specification(self.model, [('holdup', self.ids[0], 9.0, 'kg', 1.0)], [(self.heat, 1000.0, 0.0, 1e5, 1000.0, 'W')])

    def test_forward_selection_is_a_package_closure_model(self):
        system = SteadySystem(self.model)
        self.assertEqual(sorted({c.owner for c in system.closures.closures}), ['drum'])

    def test_drum_inverse_is_rejected_with_its_own_located_code(self):
        record = self.record()
        # Admission must stop before Newton or any symbolic rebuild of the augmented block.
        with patch.object(SteadySystem, 'solve', side_effect=AssertionError('solve called')), \
             patch.object(inverse_spec, 'check_structure', side_effect=AssertionError('augmented block built')):
            with self.assertRaises(LoweringError) as caught:
                InverseSteadySystem(self.model, record)
        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic['code'], 'inverse_package_closure_unsupported')
        self.assertEqual(diagnostic['terminationReason'], 'inverse_package_closure_unsupported')
        self.assertEqual(diagnostic['volumeIds'], ['drum'])
        self.assertEqual(diagnostic['stage'], 'admission')
        self.assertEqual(diagnostic['path'], 'motores.derivedExecution')
        self.assertEqual(diagnostic['modelId'], self.model.get('id'))
        message = str(caught.exception)
        self.assertIn('package thermodynamic closures', message)
        self.assertIn('drum', message)
        self.assertNotIn('rational arithmetic', message)
        self.assertNotIn('phase_amount', message)

    def test_malformed_record_keeps_its_own_code(self):
        record = self.record(); record['freedInputs'] = []
        with self.assertRaises(LoweringError) as caught:
            InverseSteadySystem(self.model, record)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'inverse_not_square')


if __name__ == '__main__':
    unittest.main()
