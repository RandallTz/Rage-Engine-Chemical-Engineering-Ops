"""R5 common compiler: water/butanol window vs independent PH boundaries."""
import copy
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_transient_phase_window import request, NARROW, reference_window
from core.modelo import desde_ensamblaje_v2
from core.compilador import resolver, compilar
from core.mezclas import FueraDeAlcance


class UnifacEventProbeTests(unittest.TestCase):
    def system(self):
        path = Path(__file__).resolve().parents[1] / 'docs/ejemplos/motor-unifac/motor-ensamblaje-v2-resolver-unifac-dortmund-calentamiento-4-peticion.json'
        system = compilar(desde_ensamblaje_v2(json.loads(path.read_text(encoding='utf8'))))
        return system, system.inicial()

    def test_dortmund_bubble_edge_probe_uses_valid_seeded_state(self):
        # Four species, 0.25 mol each, 101325 Pa. This exact H failed cold PH
        # after R5: TP enthalpy noise exceeded PH's 1e-10*abs(H) tolerance.
        system, state = self.system()
        volume = system.vols[0]
        seed = volume.cierre.semilla
        state[volume.i_E] = -34511.158609610495
        signature, margins = system.event_state(0., state)
        self.assertIs(volume.cierre.semilla, seed)
        expected = system._estados(0., state, rapido=True)[volume.id]
        self.assertEqual(signature, ((volume.id, expected.firma),))
        self.assertEqual(expected.firma, ('liquido-1', 'vapor-1'))
        self.assertAlmostEqual(expected.H, state[volume.i_E], delta=1e-10*abs(expected.H))
        self.assertTrue(all(value is None or np.isfinite(value) and value >= 0 for value in margins))

    def test_failed_cold_probe_restores_seeds_before_retry_and_afterwards(self):
        system, state = self.system()
        seeds = [volume.cierre.semilla for volume in system.vols]
        expected = system.event_state(0., state)
        evaluate = system._estados

        def fail_cold(t, y, rapido=True):
            if not rapido:
                for volume in system.vols:
                    volume.cierre.semilla = object()
                raise FueraDeAlcance('no_convergente', 'Cold event probe unavailable')
            self.assertTrue(all(volume.cierre.semilla is seed for volume, seed in zip(system.vols, seeds)))
            return evaluate(t, y, rapido=True)

        with patch.object(system, '_estados', side_effect=fail_cold) as probe:
            actual = system.event_state(0., state)
        self.assertEqual([call.kwargs['rapido'] for call in probe.call_args_list], [False, True])
        self.assertEqual(actual[0], expected[0], 'A failed certificate is not a changed phase identity.')
        self.assertTrue(all(volume.cierre.semilla is seed for volume, seed in zip(system.vols, seeds)))


class CommonPhaseWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = reference_window(NARROW)

    def test_common_rk45_and_bdf_locate_the_window_with_coarse_and_finer_sampling(self):
        records = []
        for method in ('rk45', 'bdf'):
            for samples in (2, 11):
                with self.subTest(method=method, samples=samples):
                    model = desde_ensamblaje_v2(request(NARROW, samples))
                    model['estudio']['metodoSolicitado'] = method
                    start = time.perf_counter()
                    result = resolver(model)
                    self.assertEqual(result['estado'], 'resuelto', result['procedencia'])
                    self.assertIn(method.upper(), result['procedencia']['metodo'])
                    events = result['eventos']
                    self.assertEqual([row['codigo'] for row in events], ['aparicion_fase', 'desaparicion_fase', 'aparicion_fase'])
                    self.assertAlmostEqual(events[0]['valor'], self.reference[0], delta=1e-3)
                    self.assertAlmostEqual(events[1]['valor'], self.reference[1], delta=1e-3)
                    self.assertTrue(all(row['valor'] <= row['tolerancia'] for row in result['verificaciones']))
                    record = {'method': method, 'samples': samples, 'seconds': round(time.perf_counter()-start, 3),
                              'events': events, 'verification': result['verificaciones']}
                    print(json.dumps(record), flush=True)
                    records.append(record)
        path = Path('.tmp/f9-r5-evidence.json')
        evidence = json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
        evidence['repaired'] = {'independentWindow': self.reference, 'runs': records}
        path.write_text(json.dumps(evidence, indent=2), encoding='utf8')

    def test_certified_event_probes_preserve_rhs_seed_context(self):
        system = compilar(desde_ensamblaje_v2(request(NARROW, 2)))
        state = system.inicial()
        seeds = [volume.cierre.semilla for volume in system.vols]
        first = system.event_state(0., state)
        system.event_state(0., copy.deepcopy(state))
        self.assertEqual(first, system.event_state(0., state))
        self.assertTrue(all(volume.cierre.semilla is seed for volume, seed in zip(system.vols, seeds)))


if __name__ == '__main__':
    unittest.main()
