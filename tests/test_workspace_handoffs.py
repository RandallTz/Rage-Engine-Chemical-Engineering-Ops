"""Cross-workspace provenance, method compatibility and independent balance reference."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.modelo import desde_ensamblaje_v2, ErrorModelo
from core.compilador.presentation import formulation_summary
from core.compilador.report import compilation_report
from test_transformed_execution import fixture, select


def example():
    document = json.loads((ROOT / 'docs/ejemplos/heated-filling-vessel.model.json').read_text(encoding='utf-8'))
    return desde_ensamblaje_v2(document['model']['redTermodinamica']['solicitud'])


class WorkspaceHandoffTests(unittest.TestCase):
    def test_summary_needs_no_numerical_initialization(self):
        model = example()
        model['estudio'] = None
        for datum in model['datos'].values():
            datum['declaracion']['texto'] = ''
        before = copy.deepcopy(model)
        summary = formulation_summary(model)
        self.assertEqual(model, before)
        self.assertEqual([f['id'] for f in summary['families']], ['matter', 'energy', 'momentum', 'thermodynamics'])
        self.assertFalse(summary['families'][2]['volumes'])
        self.assertTrue(all(v['status'] == 'recorded' for f in summary['families'] for v in f['volumes']))
        self.assertIn('unifac-original-public', str(summary))

    def test_mismatched_assumption_is_rejected(self):
        model = example()
        model['volumenes'][0]['supuestos']['energia']['adiabatico'] = True
        with self.assertRaises(ErrorModelo):
            formulation_summary(model)

    def test_missing_journal_is_explicit_not_invented(self):
        model = example()
        del model['motores']['energyDerivation']
        energy = formulation_summary(model)['families'][1]['volumes'][0]
        self.assertEqual(energy['status'], 'unrecorded')
        self.assertEqual(energy['steps'], [])

    def test_nested_method_capability_and_plan(self):
        report = compilation_report(example())
        self.assertEqual(report['method'], 'RK45')
        self.assertEqual([(m['id'], m['available']) for m in report['strategy']['methods']], [('RK45', True), ('BDF', False)])
        self.assertEqual([s['id'] for s in report['strategy']['steps']], ['initialization', 'partition', 'closure', 'balances', 'time-step', 'events', 'verification'])
        self.assertEqual([v['id'] for v in report['variables']], ['A.n.1', 'A.n.2', 'A.H'])
        self.assertIn('V_v', report['strategy']['steps'][3]['latex'])
        self.assertEqual([row['id'] for row in report['systemEquations']], ['materia.A.1', 'materia.A.2', 'energia.A', 'enthalpy.A', 'closure.A'])
        self.assertIn('feed', report['systemEquations'][0]['latex'])
        self.assertIn('heater', report['systemEquations'][2]['latex'])

    def test_explicit_and_scaled_method_plans_match_compiler(self):
        for scaled in (False, True):
            for method, expected in [('rk45', 'RK45'), ('bdf', 'BDF')]:
                model = select(fixture()) if scaled else fixture()
                model['estudio']['metodoSolicitado'] = method
                report = compilation_report(model)
                self.assertEqual(report['method'], expected)
                self.assertTrue(all(m['available'] for m in report['strategy']['methods']))
                latex = next(s['latex'] for s in report['strategy']['steps'] if s['id'] == 'time-step')
                self.assertIn('J_r' if expected == 'BDF' else 'a_{jl}', latex)
                self.assertNotIn('closure', [s['id'] for s in report['strategy']['steps']])


    def test_requested_unsupported_method_is_not_silently_replaced(self):
        from core.compilador import NoSoportado
        model = example()
        model['estudio']['metodoSolicitado'] = 'bdf'
        with self.assertRaises(NoSoportado):
            compilation_report(model)

    def test_oriented_display_matches_outlet_and_heat_loss_rhs(self):
        import numpy as np
        from core.compilador import compilar
        from core.paquetes_volumen import PaqueteMezcla
        model = example()
        model['corrientes'][0].update(desde='A', hasta=None)
        model['intercambios'][0].update(desde='A', hasta=None)
        report = compilation_report(model)
        self.assertIn('=-', report['systemEquations'][0]['latex'])
        self.assertIn('=-', report['systemEquations'][2]['latex'])
        system = compilar(model)
        y0 = system.inicial()
        rhs = system.rhs(0., y0)
        package = PaqueteMezcla('unifac-original-public', ['7732-18-5', '64-17-5'])
        initial = package.estado('TP', 300., 1e5, np.array([.8, .2]))
        self.assertAlmostEqual(rhs[0], -.001 * .8, delta=2e-12)
        self.assertAlmostEqual(rhs[1], -.001 * .2, delta=2e-12)
        self.assertAlmostEqual(rhs[2], -.001 * initial.H - 5., delta=2e-7)

    def test_example_against_analytical_inventory_and_enthalpy(self):
        import numpy as np
        from backend.motor_ensamblaje_v2 import resolver_v2
        from core.paquetes_volumen import PaqueteMezcla
        document = json.loads((ROOT / 'docs/ejemplos/heated-filling-vessel.model.json').read_text(encoding='utf-8'))
        request = document['model']['redTermodinamica']['solicitud']
        result = resolver_v2(request)
        self.assertEqual(result['estado'], 'resuelto')
        output = result['resultados']
        self.assertEqual(output['certificacion']['estado'], 'cumple')
        package = PaqueteMezcla('unifac-original-public', ['7732-18-5', '64-17-5'])
        initial = package.estado('TP', 300., 1e5, np.array([.8, .2]))
        feed_h, _ = package.transporte_TP(320., 1e5, np.array([.5, .5]))
        series = {row['variableId']: row['valores'] for row in output['series']}
        for k, time in enumerate(output['tiempos']):
            self.assertAlmostEqual(series['volumen.A.n.1'][k], .8 + .0005 * time, delta=2e-12)
            self.assertAlmostEqual(series['volumen.A.n.2'][k], .2 + .0005 * time, delta=2e-12)
            self.assertAlmostEqual(series['volumen.A.H'][k], initial.H + (.001 * feed_h + 5.) * time, delta=2e-6)
            self.assertAlmostEqual(series['volumen.A.H'][k], series['volumen.A.U'][k] + 1e5 * series['volumen.A.V'][k], delta=2e-6)
        self.assertTrue(all(row['maximoEscalado'] <= row['tolerancia'] for row in output['residuos']))


if __name__ == '__main__':
    unittest.main()
