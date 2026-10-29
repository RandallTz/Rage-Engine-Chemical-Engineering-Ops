"""Step (c): certified common publication against independent physical controls."""
from pathlib import Path
import copy
import sys
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.compilador import resolver
from core.resultados import leer_resultados
from core.resultados import ErrorResultados
from core import ensamblaje_red as network
from core.mezclas import FueraDeAlcance
from test_common_admission import model, request
from backend.motor_ensamblaje_v2 import resolver_v2


def detail(result):
    leer_resultados(result)
    return result['procedencia']['equilibrium']


class CommonNetworkResults(unittest.TestCase):
    def test_supercritical_event_preserves_identity_and_first_law(self):
        from solicitudes_v2 import Red
        from core.modelo import desde_ensamblaje_v2
        value = (Red('super', ('agua',), tf=('200', 's'), muestras=5).paquete('w', 'agua-iapws95')
                 .volumen('A', 'w', {'agua': ('1', 'kg')}, ('T', '630', 'K'), P=('300', 'bar'))
                 .calor('q', None, 'A', Q=('2', 'kW'), Tfrontera=('1000', 'K')))
        result = resolver(desde_ensamblaje_v2(value.solicitud()))
        output = detail(result)
        self.assertEqual(result['estado'], 'resuelto')
        events = output['eventos']
        self.assertEqual([e['codigo'] for e in events], ['cambio_denominacion'])
        self.assertNotEqual(events[0]['faseIdsAntes'], events[0]['faseIdsDespues'])
        self.assertIn(events[0]['tiempo'], output['tiempos'])
        series = {s['variableId']: np.array(s['valores']) for s in output['series']}
        enthalpy = series['volumen.A.H']
        np.testing.assert_allclose(enthalpy-enthalpy[0], 2000*np.array(output['tiempos']), atol=1e-3, rtol=1e-6)
        self.assertTrue(np.all(np.diff(series['volumen.A.T']) > 0))

    def test_corrupted_work_is_retained_as_failed_physical_evidence(self):
        original = network.muestras
        def corrupted(red, trajectory):
            rows = copy.deepcopy(original(red, trajectory))
            rows[-1][1][network.Sistema(red).i_W] += 1000.
            return rows
        with patch.object(network, 'muestras', side_effect=corrupted):
            result = resolver(model(horizon='1'))
        output = detail(result)
        self.assertEqual(result['estado'], 'resuelto')
        self.assertEqual(output['certificacion']['estado'], 'no_cumple')
        self.assertGreater(next(r for r in output['residuos'] if r['ecuacionId']=='mecanica.A.trabajo')['maximoEscalado'], 1.)
        self.assertEqual(len(output['tiempos']), 3)
        self.assertIn('MOTOR_ENS_CERTIFICACION_NO_CUMPLE', [d['codigo'] for d in result['procedencia']['diagnostics']])

    def test_common_solver_publishes_existing_science_without_legacy_solve(self):
        with (patch('backend.motor_ensamblaje_v2.resolver_v2', side_effect=AssertionError('legacy solve')),
              patch.object(network, 'integrar', side_effect=AssertionError('legacy integrator'))):
            result = resolver(model())
        output = detail(result)
        self.assertEqual(result['estado'], 'resuelto')
        self.assertEqual(output['certificacion']['estado'], 'no_evaluable')
        self.assertEqual(output['segundaLey']['estado'], 'no_evaluable')
        series = {s['variableId']: np.array(s['valores']) for s in output['series']}
        times = np.array(output['tiempos'])
        np.testing.assert_allclose(series['volumen.A.n.1']+series['volumen.A.n.2'], 1-.001*times, atol=1e-12)
        np.testing.assert_allclose(series['corriente.s.ndot'], .001, atol=1e-15)
        np.testing.assert_allclose(series['calor.q.Q'], 100, atol=1e-15)
        work = 101325*(series['volumen.A.V']-series['volumen.A.V'][0])
        np.testing.assert_allclose(series['volumen.A.W'], work, rtol=1e-5, atol=1e-6)
        for owner, states in output['estados'].items():
            self.assertEqual(len(states), len(times))
            for state in states:
                self.assertEqual(state['potenciales']['unidades'], {'mu':'J/mol', 'G':'J', 'A':'J', 'S':'J/K'})
        self.assertTrue(output['procedenciaModelo'][0]['huella'])

    def test_small_scale_work_drift_is_not_physical_success(self):
        native = resolver_v2(request(scale=1e-6, horizon='100'))
        output = native['resultados']
        series = {s['variableId']: s['valores'] for s in output['series']}
        reference = 101325*(series['volumen.A.V'][-1]-series['volumen.A.V'][0])
        relative = abs(series['volumen.A.W'][-1]/reference-1)
        self.assertGreater(relative, .02)
        self.assertLess(relative, .04)
        self.assertEqual(native['estado'], 'resuelto')
        self.assertEqual(output['certificacion']['estado'], 'no_cumple')
        result = resolver(model(scale=1e-6, horizon='100'))
        common = detail(result)
        residual = next(r for r in common['residuos'] if r['ecuacionId']=='mecanica.A.trabajo')
        if residual['maximoEscalado'] > residual['tolerancia']:
            self.assertEqual(common['certificacion']['estado'], 'no_cumple')
            self.assertIn('MOTOR_ENS_CERTIFICACION_NO_CUMPLE', [d['codigo'] for d in result['procedencia']['diagnostics']])
        self.assertEqual(result['procedencia']['physicalCertification'], common['certificacion'])

    def test_negative_second_law_retains_evaluated_evidence(self):
        value = model()
        value['datos']['boundary.temperature'] = copy.deepcopy(value['datos']['volumen.A.T0'])
        value['datos']['boundary.temperature']['declaracion']['texto'] = '100'
        value['intercambios'][0]['temperaturaFronteraId'] = 'boundary.temperature'
        result = resolver(value); output = detail(result)
        self.assertEqual(result['estado'], 'resuelto')
        self.assertEqual(output['segundaLey']['estado'], 'no_cumple')
        self.assertEqual(output['certificacion']['estado'], 'no_cumple')
        self.assertEqual(output['certificacion']['ultimaMuestraCertificada'], 0)
        self.assertLess(output['segundaLey']['generacionMinima'], 0)
        self.assertEqual(len(output['tiempos']), 3)
        wrong = copy.deepcopy(result)
        wrong['procedencia']['physicalCertification']['estado'] = 'cumple'
        with self.assertRaises(ErrorResultados):
            leer_resultados(wrong)

    def test_publication_failure_keeps_only_a_certified_prefix(self):
        from backend import motor_ensamblaje_v2 as native
        evaluate = native.evaluacion_volumen
        calls = 0
        def fail_after_initial(*args):
            nonlocal calls
            calls += 1
            if calls > 2:
                raise FueraDeAlcance('no_convergente', 'Injected unavailable sample')
            return evaluate(*args)
        with patch.object(native, 'evaluacion_volumen', side_effect=fail_after_initial):
            result = resolver(model())
        output = detail(result)
        self.assertEqual(result['estado'], 'parcial')
        self.assertEqual(output['tiempos'], [0.])
        self.assertFalse(output['certificacion']['alcance']['completa'])
        self.assertTrue(all(len(s['valores'])==1 for s in output['series']))
        self.assertTrue(all(len(rows)==1 for rows in output['estados'].values()))
        self.assertEqual(result['eventos'], [])
        self.assertIn('MOTOR_ENS_MUESTRA_NO_CERTIFICADA', [d['codigo'] for d in result['procedencia']['diagnostics']])
        with patch.object(native, 'evaluacion_volumen', side_effect=FueraDeAlcance('no_convergente', 'No first sample')):
            failed = resolver(model())
        self.assertEqual(failed['estado'], 'fallido')
        self.assertEqual(failed['series'], [])
        self.assertIsNone(failed['procedencia']['physicalCertification'])

    def test_singular_heat_is_rejected_over_the_declared_horizon(self):
        from core.compilador.compilador import AdmissionError
        value = model(horizon='100')
        value['datos']['calor.q.Q']['declaracion']['texto'] = '100/(t-50)'
        with self.assertRaises(AdmissionError) as caught:
            resolver(value)
        self.assertIn('t=50', str(caught.exception))
        self.assertEqual(caught.exception.diagnostics[0]['nativeCode'], 'MOTOR_ENS_EXPRESION')

    def test_midrun_thermodynamic_probe_failure_is_structured(self):
        from core.compilador.compilador import SistemaCompilado
        original = SistemaCompilado.event_state
        def unavailable(self, t, y):
            if t > .2:
                raise FueraDeAlcance('fuera_de_dominio', 'Injected physical domain boundary')
            return original(self, t, y)
        with patch.object(SistemaCompilado, 'event_state', unavailable):
            result = resolver(model(horizon='1'))
        self.assertEqual(result['estado'], 'parcial')
        self.assertLessEqual(result['ejes'][0]['valores'][-1], .2)
        self.assertIn('MOTOR_ENS_DETENIDO_FUERA_DE_DOMINIO', [d['codigo'] for d in result['procedencia']['diagnostics']])

    def test_initial_probe_failure_is_a_located_rejection(self):
        from core.compilador.compilador import SistemaCompilado, AdmissionError
        with patch.object(SistemaCompilado, 'event_state', side_effect=FueraDeAlcance('no_convergente', 'Unavailable initial probe')):
            with self.assertRaises(AdmissionError) as caught:
                resolver(model())
        self.assertEqual(caught.exception.diagnostics[0]['nativeCode'], 'MOTOR_ENS_INICIAL_NO_CONVERGENTE')
        self.assertEqual(caught.exception.diagnostics[0]['path'], 'volumenes')

if __name__ == '__main__':
    unittest.main()
