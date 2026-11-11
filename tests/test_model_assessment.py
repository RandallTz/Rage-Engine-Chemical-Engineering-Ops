"""F0 staged verdicts: audit reproducers and independent physical controls."""
import copy
import asyncio
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from backend.api_modelo import describe_compilation, resolver_modelo, validar
from core.compilador import NoSoportado
from core.compilador.report import compilation_report
from core.modelo import ErrorModelo, leer_modelo_comun
from core.resultados import leer_resultados, ErrorResultados
from test_common_admission import model as network_model
from test_explicit_initialization import fixture


def assess(model, **options):
    from core.compilador.assessment import assess_model, read_assessment
    return read_assessment(assess_model(model, **options), model=model)


class AssessmentTests(unittest.TestCase):
    def test_generated_balance_structure_uses_the_same_laws_without_initial_data(self):
        path = Path(__file__).resolve().parents[1]/'docs/ejemplos/modelo-comun/balances-llenado-entrada-caliente.json'
        model = json.loads(path.read_text(encoding='utf-8'))['modelo']
        baseline = assess(model)
        del model['volumenes'][0]['inicial']
        pending = assess(model)
        self.assertEqual(pending['structure']['status'], 'complete')
        self.assertEqual(pending['initialization']['status'], 'pending')
        self.assertEqual(pending['inspection']['equations'], baseline['inspection']['equations'])
        self.assertEqual(len(pending['inspection']['variables']), 2)

    def test_transformed_negative_mass_is_also_initialization_rejection(self):
        from test_transformed_execution import fixture as transformed_fixture, select
        model = transformed_fixture(); select(model)
        model['datos']['matematico.m0']['declaracion'].update(texto='-1', unidad='kg')
        result = assess(model)
        self.assertEqual(result['structure']['status'], 'complete')
        self.assertEqual(result['initialization']['code'], 'INITIALIZATION_OUT_OF_DOMAIN')
        with self.assertRaises(NoSoportado): compilation_report(model)

    def test_initial_units_and_nonfinite_values_are_located_rejections(self):
        for text, unit in [('2', 's'), ('1/0', 'kg'), ('1e999', 'kg')]:
            model = fixture([(text, unit)])
            result = assess(model)
            self.assertEqual(result['structure']['status'], 'complete')
            self.assertEqual(result['initialization']['status'], 'incompatible')
            self.assertEqual(result['initialization']['diagnostics'][0]['path'], 'datos.matematico.initial_value_0')
            with self.assertRaises(HTTPException) as caught: resolver_modelo({'modelo': model, 'assessmentVersion': 1})
            self.assertEqual(caught.exception.status_code, 422)

    def test_http_assessment_preserves_typed_rejected_attempt(self):
        import httpx
        from fastapi import FastAPI
        from backend.api_modelo import router
        app = FastAPI(); app.include_router(router)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                model = fixture([('-1', 'kg')])
                response = await client.post('/modelo/assessment', json={
                    'format': 'rage.model-assessment.request', 'version': 1, 'model': model})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['initialization']['status'], 'incompatible')
                response = await client.post('/modelo/resolver', json={'modelo': model, 'assessmentVersion': 1})
                self.assertEqual(response.status_code, 422)
                detail = response.json()['detail']
                self.assertEqual(detail['codigo'], 'no_soportado')
                self.assertEqual(detail['assessment']['initialization']['code'], 'INITIALIZATION_OUT_OF_DOMAIN')
        asyncio.run(check())

    def test_negative_initial_mass_cannot_compile(self):
        model = fixture([('-1', 'kg')])
        with self.assertRaises(NoSoportado) as caught:
            compilation_report(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'INITIALIZATION_OUT_OF_DOMAIN')
        with self.assertRaises(HTTPException) as caught:
            describe_compilation({'modelo': model})
        self.assertEqual(caught.exception.status_code, 422)

    def test_missing_initialization_keeps_equilibrium_structure(self):
        for missing in ('energy', 'initial', 'amounts', 'datum', 'blank'):
            model = network_model(horizon='1')
            if missing == 'energy': del model['volumenes'][0]['inicial']['energia']
            if missing == 'initial': del model['volumenes'][0]['inicial']
            if missing == 'amounts': del model['volumenes'][0]['inicial']['cantidades']
            if missing == 'datum': del model['datos']['volumen.A.T0']
            if missing == 'blank': model['datos']['volumen.A.T0']['declaracion']['texto'] = ''
            original = copy.deepcopy(model)
            with self.subTest(missing=missing):
                result = assess(model)
                self.assertEqual(result['structure']['status'], 'complete')
                self.assertEqual(result['initialization']['code'], 'INITIALIZATION_MISSING_DATA')
                self.assertEqual(len(result['inspection']['variables']), 6)
                self.assertGreaterEqual(len(result['inspection']['equations']), 6)
                self.assertEqual(model, original)
                if missing != 'blank':
                    with self.assertRaises(ErrorModelo): leer_modelo_comun(model)
                    with self.assertRaises(HTTPException): validar({'modelo': model})

    def test_initialization_failure_does_not_hide_structure(self):
        hot = network_model(horizon='1')
        hot['datos']['volumen.A.T0']['declaracion']['texto'] = '1000'
        for model in (hot, fixture([('-1', 'kg')]), fixture([('2', 'kg'), ('3', 'kg')])):
            result = assess(model)
            self.assertEqual(result['structure']['status'], 'complete')
            self.assertEqual(result['initialization']['status'], 'incompatible')
            self.assertEqual(result['certification']['status'], 'not_evaluated')
            self.assertTrue(result['initialization']['diagnostics'][0]['path'])
            with self.assertRaises(NoSoportado): compilation_report(model)

    def test_missing_equation_and_missing_initial_condition_are_distinct(self):
        model = fixture([])
        result = assess(model)
        self.assertEqual(result['structure']['code'], 'STRUCTURE_COMPLETE')
        self.assertEqual(result['initialization']['code'], 'INITIALIZATION_MISSING_DATA')
        self.assertEqual(len(result['inspection']['variables']), 1)
        model['matematico']['ecuaciones'] = []
        result = assess(model)
        self.assertEqual(result['structure']['code'], 'STRUCTURE_MISSING_RELATION')
        self.assertEqual(result['initialization']['status'], 'not_evaluated')

    def test_missing_initial_only_parameter_is_pending(self):
        model = fixture([('2', 'kg')])
        del model['datos']['matematico.initial_value_0']
        result = assess(model)
        self.assertEqual(result['structure']['status'], 'complete')
        self.assertEqual(result['initialization']['status'], 'pending')

    def test_duplicate_rates_are_a_structural_conflict(self):
        model = fixture([('2', 'kg')])
        equation = copy.deepcopy(model['matematico']['ecuaciones'][0]); equation['id'] = 'second-rate'
        model['matematico']['ecuaciones'].append(equation)
        result = assess(model)
        self.assertEqual(result['structure']['code'], 'STRUCTURE_CONFLICT')
        self.assertEqual(result['initialization']['status'], 'not_evaluated')

    def test_failed_numerical_evidence_never_becomes_a_pass(self):
        from core.compilador.assessment import attach_result
        model = fixture([('2', 'kg')])
        result = resolver_modelo({'modelo': model})
        result['verificaciones'] = [{'id': 'injected-failed-check', 'valor': 1, 'tolerancia': 1e-7,
                                     'descripcion': 'Fault-injected evidence, not a new physical model.'}]
        attach_result(assess(model), result)
        self.assertEqual(result['estado'], 'resuelto')
        self.assertEqual(result['procedencia']['assessment']['certification']['status'], 'failed')
        leer_resultados(result)

    def test_equilibrium_limit_diagnostic_carries_no_verdict_but_real_failures_do(self):
        """RV-5: a kinetically limited CSTR sits away from equilibrium; that distance is information, not a failure."""
        from core.compilador.assessment import attach_result, certification
        model = fixture([('2', 'kg')])
        diagnostic = {'id': 'reactions.equilibrium_limit.reactor', 'valor': .154, 'tolerancia': 1e-3,
                      'descripcion': 'Distance to chemical equilibrium (diagnostic).'}
        result = resolver_modelo({'modelo': model})
        result['verificaciones'] = [diagnostic]
        attach_result(assess(model), result)
        self.assertEqual(result['procedencia']['assessment']['certification']['status'], 'not_evaluable')
        leer_resultados(result)
        # The same diagnostic beside a genuinely failed check still fails, and only the real check is cited.
        real = {'id': 'injected-failed-check', 'valor': 1, 'tolerancia': 1e-7, 'descripcion': 'Fault-injected evidence.'}
        result['verificaciones'] = [diagnostic, real]
        attach_result(assess(model), result)
        verdict = result['procedencia']['assessment']['certification']
        self.assertEqual(verdict['status'], 'failed')
        self.assertEqual([d['path'] for d in verdict['diagnostics'] if d['code'] == 'CERTIFICATION_FAILED'], ['verificaciones[1]'])
        # A result saved under the pre-RV-5 rule (diagnostic failed the verdict) still reads.
        result['verificaciones'] = [diagnostic]
        attach_result(assess(model), result)
        source = result['procedencia']['assessment']['sourceSignature']
        result['procedencia']['assessment']['certification'] = certification(result, source, legacy=True)
        self.assertEqual(result['procedencia']['assessment']['certification']['status'], 'failed')
        leer_resultados(result)

    def test_partial_certification_describes_only_published_prefix(self):
        from core.compilador.assessment import attach_result
        model = fixture([('2', 'kg')])
        result = resolver_modelo({'modelo': model})
        # A finite truncated trajectory is a publication control; no certificate
        # is invented from its successful initialization or numerical samples.
        result['estado'] = 'parcial'
        result['ejes'][0]['valores'] = result['ejes'][0]['valores'][:2]
        for series in result['series']: series['valores'] = series['valores'][:2]
        attach_result(assess(model), result)
        certificate = result['procedencia']['assessment']['certification']
        self.assertFalse(certificate['scope']['complete'])
        self.assertEqual(certificate['scope']['endSI'], .5)
        self.assertEqual(certificate['scope']['samples'], 2)
        self.assertEqual(certificate['status'], 'not_evaluable')
        leer_resultados(result)

    def test_malformed_initial_object_is_not_missing_data(self):
        model = network_model(horizon='1'); model['volumenes'][0]['inicial'] = []
        result = assess(model)
        self.assertEqual(result['structure']['code'], 'STRUCTURE_INVALID_DOCUMENT')
        self.assertEqual(result['initialization']['status'], 'not_evaluated')

    def test_structure_only_never_flashes_initial_state(self):
        with patch('core.compilador.compilador.SistemaCompilado.inicial', side_effect=AssertionError('Initial flash')):
            result = assess(network_model(horizon='1'), initialize=False)
        self.assertEqual(result['structure']['status'], 'complete')
        self.assertEqual(result['initialization']['status'], 'not_evaluated')

    def test_versioned_endpoint_and_rejected_attempt(self):
        from backend.api_modelo import model_assessment
        model = fixture([('-1', 'kg')])
        result = model_assessment({'format': 'rage.model-assessment.request', 'version': 1, 'model': model})
        self.assertEqual(result['initialization']['status'], 'incompatible')
        with self.assertRaises(HTTPException):
            model_assessment({'format': 'rage.model-assessment.request', 'version': 99, 'model': model})
        with self.assertRaises(HTTPException) as caught:
            resolver_modelo({'modelo': model, 'assessmentVersion': 1})
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(caught.exception.detail['codigo'], 'no_soportado')
        self.assertEqual(caught.exception.detail['assessment']['initialization']['status'], 'incompatible')

    def test_optional_metadata_preserves_legacy_result(self):
        model = fixture([('2', 'kg')])
        plain = resolver_modelo({'modelo': model})
        result = resolver_modelo({'modelo': model, 'assessmentVersion': 1})
        leer_resultados(result)
        evidence = result['procedencia'].pop('assessment')
        self.assertEqual(result, plain)
        self.assertEqual(evidence['initialization']['status'], 'compatible')
        self.assertEqual(evidence['certification']['status'], 'not_evaluable')

    def test_same_initial_state_has_three_distinct_certificates(self):
        for temperature, expected in ((None, 'not_evaluable'), ('1000', 'passed'), ('100', 'failed')):
            model = network_model(horizon='1')
            if temperature:
                model['datos']['boundary.temperature'] = copy.deepcopy(model['datos']['volumen.A.T0'])
                model['datos']['boundary.temperature']['declaracion']['texto'] = temperature
                model['intercambios'][0]['temperaturaFronteraId'] = 'boundary.temperature'
            result = resolver_modelo({'modelo': model, 'assessmentVersion': 1})
            self.assertEqual(result['estado'], 'resuelto')
            evidence = result['procedencia']['assessment']
            self.assertEqual(evidence['initialization']['status'], 'compatible')
            self.assertEqual(evidence['certification']['status'], expected)
            leer_resultados(result)

    def test_stale_signature_invalid_codes_and_forged_certification_reject(self):
        from core.compilador.assessment import read_assessment
        model = fixture([('2', 'kg')]); evidence = assess(model)
        changed = fixture([('3', 'kg')])
        with self.assertRaises(ValueError): read_assessment(evidence, model=changed)
        bad = copy.deepcopy(evidence); bad['structure']['code'] = 'INITIALIZATION_COMPATIBLE'
        with self.assertRaises(ValueError): read_assessment(bad)
        result = resolver_modelo({'modelo': model, 'assessmentVersion': 1})
        certificate = result['procedencia']['assessment']['certification']
        certificate.update(status='passed', code='CERTIFICATION_PASSED')
        with self.assertRaises(ErrorResultados): leer_resultados(result)


if __name__ == '__main__':
    unittest.main()
