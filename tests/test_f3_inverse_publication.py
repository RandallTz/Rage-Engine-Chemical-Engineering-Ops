"""F3 slice 5: the canonical steady readers accept the inverse publication and reject tampered evidence."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))
from test_f3_inverse_specifications import mixer, specification, series_value
from core.compilador.steady import SteadySystem, read_report, read_result, signature, steady_result_signature
from core.resultados.formato import leer_resultados
from core.solvers.inverse_steady import InverseSteadySystem


def publication(target=.6):
    model, named = mixer()
    record = specification(model, [('outlet-fraction', named('x3'), target, '1', .1)], [(named('F1'), 1, .01, 50, 1, 'mol/s')])
    return model, named, record, InverseSteadySystem(model, record).solve()


def resign(result):
    result['procedencia']['steadyDiagnostics']['resultSignature'] = steady_result_signature(result)
    return result


class InversePublication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, named, cls.record, cls.result = publication()
        cls.named = staticmethod(named)

    def tampered(self, change):
        result = copy.deepcopy(self.result)
        change(result, result['procedencia']['compilation'], result['procedencia']['steadyDiagnostics'])
        return resign(result)

    def rejects(self, change, pattern):
        result = self.tampered(change)
        with self.assertRaisesRegex(ValueError, pattern):
            read_result(result)
        with self.assertRaises(Exception):
            leer_resultados(result)

    def test_real_publication_round_trips_through_every_reader(self):
        F1 = series_value(self.result, self.named('F1'))
        self.assertLess(abs(F1-6)/6, 1e-12)  # analytic F2 (x3 - x2) / (x1 - x3) = 3 (0.4) / 0.2
        report = self.result['procedencia']['compilation']
        self.assertIs(read_report(report), report)
        self.assertIs(read_result(self.result), self.result)
        leer_resultados(self.result)
        forward = SteadySystem(mixer()[0]).report
        for key in ('selection', 'sourceSignature', 'formulationSignature', 'settingsSignature'):
            self.assertEqual(report[key], forward[key], key)
        self.assertEqual([v['id'] for v in report['variables']], [*forward['selection']['unknowns'], self.named('F1')])
        self.assertEqual(report['residualRows'][-1]['id'], 'specification.outlet-fraction')
        self.assertNotIn(self.named('F1'), {r['id'] for r in report['parameters']})

    def test_forward_publication_is_unchanged(self):
        result = SteadySystem(mixer()[0]).solve()
        self.assertNotIn('inverseSpecification', result['procedencia']['compilation'])
        self.assertNotIn('inverseSpecification', result['procedencia']['steadyDiagnostics'])
        read_result(result); leer_resultados(result)

    def test_unsigned_tampering_is_rejected(self):
        result = copy.deepcopy(self.result)
        result['procedencia']['compilation']['inverseSpecification']['rows'][0]['targetSI'] = .61
        with self.assertRaisesRegex(ValueError, 'signature'):
            read_result(result)

    def test_wrong_specification_residual(self):
        def change(result, report, evidence):
            row = next(s for s in result['series'] if s['id'] == 'steady.residual.specification.outlet-fraction')
            row['valores'] += 1e-9
        self.rejects(change, 'Specification residual differs')

    def test_target_mismatch(self):
        self.rejects(lambda r, report, e: report['inverseSpecification']['rows'][0].update(targetSI=.61), 'Specification residual differs')
        self.rejects(lambda r, report, e: report['inverseSpecification']['rows'][0].update(quantityId=self.named('F3')), 'Specification rows differ')

    def test_freed_input_mismatch(self):
        F2 = self.named('F2')
        self.rejects(lambda r, report, e: report['inverseSpecification']['freedInputs'][0].update(quantityId=F2), 'Freed-input evidence')
        def resigned_record(result, report, evidence):
            # A consistently re-signed record that frees F2 still disagrees with the augmented unknowns.
            block = report['inverseSpecification']
            row = block['record']['freedInputs'][0]; old = row['quantityId']; row['quantityId'] = F2
            block['freedInputs'][0]['quantityId'] = F2
            report['specificationSignature'] = evidence['inverseSpecification']['specificationSignature'] = signature([block['record'], block['data']])
            evidence['inverseSpecification']['freedInputs'] = [F2]
            self.assertNotEqual(old, F2)
        self.rejects(resigned_record, 'unknown ordering')
        def frees_unknown(result, report, evidence):
            report['inverseSpecification']['record']['freedInputs'][0]['quantityId'] = self.named('F3')
        self.rejects(frees_unknown, 'Stale inverse specification signature|Only constant parameters')

    def test_non_square_augmentation(self):
        def drop_row(result, report, evidence):
            report['residualRows'].pop()
            evidence['equationIds'].pop(); evidence['residualScales'].pop()
            result['series'] = [s for s in result['series'] if s['id'] != 'steady.residual.specification.outlet-fraction']
        self.rejects(drop_row, 'residual block')
        def extra_freed(result, report, evidence):
            record = report['inverseSpecification']['record']
            record['freedInputs'].append({**record['freedInputs'][0], 'quantityId': self.named('F2')})
        self.rejects(extra_freed, 'inverse_not_square')
        def stripped(result, report, evidence):
            # Without its augmentation evidence the augmented block is not the pinned forward selection.
            del report['inverseSpecification'], report['specificationSignature']
            del evidence['inverseSpecification']
        self.rejects(stripped, 'unknown ordering')

    def test_stale_signatures(self):
        self.rejects(lambda r, report, e: report.update(specificationSignature='0'*64), 'Stale inverse specification signature')
        self.rejects(lambda r, report, e: e['inverseSpecification'].update(specificationSignature='0'*64), 'Stale inverse specification diagnostics')
        def data(result, report, evidence):
            report['inverseSpecification']['data']['spec.outlet-fraction.target']['texto'] = '0.61'
        self.rejects(data, 'Stale inverse specification signature')
        def formulation(result, report, evidence):
            report['formulationSignature'] = evidence['formulationSignature'] = signature(report['selection'])[::-1]
        self.rejects(formulation, 'pinned selection')

    def test_resigned_data_must_reproduce_the_published_numbers(self):
        # Review RF-1: editing a carried declaration and re-signing it must not pass the readers.
        def resigned(field, text):
            def change(result, report, evidence):
                block = report['inverseSpecification']
                spec, freed = block['record']['specifications'][0], block['record']['freedInputs'][0]
                identity = {'target': spec['targetDataId'], 'scale': spec['residualScaleDataId'], 'upper': freed['upperDataId']}[field]
                block['data'][identity]['texto'] = text
                report['specificationSignature'] = evidence['inverseSpecification']['specificationSignature'] = signature([block['record'], block['data']])
            return change
        self.rejects(resigned('target', '0.61'), 'specification target differs')
        self.rejects(resigned('scale', '1000000'), 'residual scale differs')
        self.rejects(resigned('upper', '2'), 'freed-input seed, bound or scale differs')

    def test_new_target_changes_only_solve_signatures(self):
        other = publication(.75)[3]
        a, b = self.result['procedencia']['compilation'], other['procedencia']['compilation']
        for key in ('sourceSignature', 'formulationSignature', 'settingsSignature'):
            self.assertEqual(a[key], b[key], key)
        for key in ('specificationSignature', 'signature', 'dataSignature'):
            self.assertNotEqual(a[key], b[key], key)
        read_result(other)


if __name__ == '__main__':
    unittest.main()
