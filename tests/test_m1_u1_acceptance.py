"""Fixed-reference U1 accuracy/refinement evidence; no product gate inference."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from derived_execution_inputs import fixture
from test_derived_execution import numerical_reference
from core.compilador.derived import DerivedSystem, LoweringError, resolve_system


class U1Acceptance(unittest.TestCase):
    def test_fixed_references_with_tenfold_refinement(self):
        start = time.perf_counter()
        frozen = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (ROOT / 'tests/reference_data').glob('m1-*.json')}
        metrics, publications, diagnostics = [], {}, []
        for name in 'abc':
            model, document, _ = fixture(name)
            for refinement in (1, 10):
                candidate = copy.deepcopy(model)
                candidate['estudio']['rtol'] /= refinement
                candidate['estudio']['atol'] = {key: value / refinement for key, value in candidate['estudio']['atol'].items()}
                system = DerivedSystem(candidate)
                for method in ('RK45', 'BDF'):
                    system.method = method
                    system.model['estudio']['metodoSolicitado'] = method.lower()
                    system.report = system._report()
                    result = resolve_system(system)
                    self.assertEqual(result['estado'], 'resuelto')
                    expected, scales = numerical_reference(name, document['reference'], np.array(result['ejes'][0]['valores']))
                    quantities = {key: str(q) for key, q in system.quantities.items()}
                    error = max(float(np.max(np.abs(np.array(row['valores']) - expected[quantities[row['id'].split('.', 1)[1]]])) /
                                      scales[quantities[row['id'].split('.', 1)[1]]]) for row in result['series']
                                if row['id'].startswith(('campo.', 'observable.')))
                    conservation = max(row['valor'] for row in result['verificaciones'])
                    self.assertLessEqual(error, 1e-5)
                    self.assertLessEqual(conservation, 1e-6)
                    metric = {'case': name.upper(), 'method': method, 'refinement': refinement,
                              'scaledError': error, 'conservationResidual': conservation}
                    print(json.dumps(metric), flush=True)
                    metrics.append(metric)
                    publications[f'{name}.{method}.{refinement}'] = copy.deepcopy({'model': system.model, 'report': system.report, 'result': result})
            if name == 'b':
                for datum, premise in [('drive', 'operation.14'), ('outletElevation', 'operation.16')]:
                    changed = copy.deepcopy(model)
                    changed['datos'][datum]['declaracion']['texto'] = '1'
                    with self.assertRaises(LoweringError) as caught:
                        DerivedSystem(changed)
                    diagnostic = caught.exception.diagnostics[0]
                    self.assertEqual(diagnostic['code'], 'inconsistent_parameter_premise')
                    self.assertEqual(diagnostic['equationId'], premise)
                    diagnostics.append(diagnostic)
        for metric in metrics:
            if metric['refinement'] == 10:
                previous = next(row for row in metrics if row['case'] == metric['case'] and row['method'] == metric['method'] and row['refinement'] == 1)
                self.assertTrue(metric['scaledError'] <= previous['scaledError'] or metric['scaledError'] <= 1e-5)
        for path, digest in frozen.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)
        (ROOT / '.tmp/m1-u1-publications.json').write_text(json.dumps({'publications': publications}, indent=2), encoding='utf8')
        (ROOT / '.tmp/m1-u1-evidence.json').write_text(json.dumps({'metrics': metrics, 'diagnostics': diagnostics,
            'seconds': round(time.perf_counter() - start, 3), 'frozenUnchanged': True}, indent=2), encoding='utf8')


if __name__ == '__main__':
    unittest.main()
