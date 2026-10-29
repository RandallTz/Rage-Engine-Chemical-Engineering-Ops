"""F0: every declared initial constraint must hold, regardless of row order."""
import copy
import itertools
import json
from pathlib import Path
import sys
import unittest

import numpy as np
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.api_modelo import describe_compilation, resolver_modelo
from core.compilador import NoSoportado, resolver
from core.compilador.explicito import SistemaExplicito
from core.compilador.report import compilation_report


def fixture(values):
    # Reuse the existing internal depletion law dm/dt=-1 kg/h; only initial
    # data/constraints change. No new physical equation or product template.
    model = json.loads((ROOT/'docs/ejemplos/modelo-comun/explicito-agotamiento.json').read_text(encoding='utf-8'))['modelo']
    model['datos']['estudio.tf']['declaracion'].update(texto='1', unidad='s')
    model['estudio']['muestras'] = 3
    initial = model['matematico']['condiciones'][0]
    parameter = next(s for s in model['matematico']['simbolos'] if s['id'] == 'm0')
    datum = model['datos']['matematico.m0']
    model['matematico']['condiciones'] = []
    for index, (value, unit) in enumerate(values):
        identity = 'initial_value_'+str(index)
        symbol = copy.deepcopy(parameter); symbol.update(id=identity, nombre=identity)
        model['matematico']['simbolos'].append(symbol)
        data = copy.deepcopy(datum); data['declaracion'].update(texto=value, unidad=unit)
        model['datos']['matematico.'+identity] = data
        condition = copy.deepcopy(initial)
        condition['id'] = 'initial_'+str(index)
        condition['ecuacion']['id'] = 'initial_equation_'+str(index)
        condition['ecuacion']['derecha'] = {'tipo': 'simbolo', 'id': identity}
        model['matematico']['condiciones'].append(condition)
    return model


class ExplicitInitialization(unittest.TestCase):
    def test_conflicts_reject_in_every_order_in_compilation_and_solve(self):
        original = fixture([('2', 'kg'), ('3', 'kg'), ('2000', 'g')])
        identities = ['initial_0', 'initial_1', 'initial_2']
        for method in ('rk45', 'bdf'):
            for order in itertools.permutations(original['matematico']['condiciones']):
                model = copy.deepcopy(original)
                model['estudio']['metodoSolicitado'] = method
                model['matematico']['condiciones'] = list(order)
                for action in (SistemaExplicito, compilation_report, resolver):
                    with self.subTest(method=method, order=[c['id'] for c in order], action=action.__name__):
                        with self.assertRaises(NoSoportado) as caught:
                            action(model)
                        diagnostic = caught.exception.diagnostics[0]
                        self.assertEqual(diagnostic['code'], 'INITIALIZATION_CONSTRAINT_CONFLICT')
                        self.assertEqual(diagnostic['stage'], 'initialization')
                        self.assertEqual(diagnostic['initializationStatus'], 'incompatible')
                        self.assertEqual(diagnostic['variableId'], 'm')
                        self.assertEqual(diagnostic['conditionIds'], identities)
                        self.assertEqual(diagnostic['valuesSI'], [2, 3, 2])
                        self.assertEqual(diagnostic['unitSI'], 'kg')
                        self.assertEqual(diagnostic['path'], 'matematico.condiciones')
                        self.assertEqual(diagnostic['equationIds'], ['initial_equation_'+str(i) for i in range(3)])

    def test_http_boundaries_preserve_structured_initialization_rejection(self):
        for reverse in (False, True):
            model = fixture([('2', 'kg'), ('3', 'kg')])
            if reverse:
                model['matematico']['condiciones'].reverse()
            for endpoint in (describe_compilation, resolver_modelo):
                with self.subTest(reverse=reverse, endpoint=endpoint.__name__):
                    with self.assertRaises(HTTPException) as caught:
                        endpoint({'modelo': model})
                    self.assertEqual(caught.exception.status_code, 422)
                    self.assertEqual(caught.exception.detail['codigo'], 'no_soportado')
                    self.assertEqual(caught.exception.detail['diagnostics'][0]['code'], 'INITIALIZATION_CONSTRAINT_CONFLICT')

    def test_equal_si_constraints_preserve_the_independent_depletion_reference(self):
        for method in ('rk45', 'bdf'):
            for reverse in (False, True):
                model = fixture([('2', 'kg'), ('2000', 'g')])
                model['estudio']['metodoSolicitado'] = method
                if reverse:
                    model['matematico']['condiciones'].reverse()
                result = resolver(model)
                self.assertEqual(result['estado'], 'resuelto')
                times = np.array(result['ejes'][0]['valores'])
                mass = next(s['valores'] for s in result['series'] if s['id'] == 'campo.m')
                np.testing.assert_allclose(mass, 2-times/3600, rtol=0, atol=1e-12)
                self.assertEqual(len(compilation_report(model)['variables']), 1)

    def test_conflicts_are_not_hidden_by_integration_tolerances(self):
        # One representable SI difference is still contradictory; no new
        # physical equality tolerance is borrowed from the time integrator.
        model = fixture([('2', 'kg'), (repr(float(np.nextafter(2., 3.))), 'kg')])
        for reverse in (False, True):
            with self.assertRaises(NoSoportado) as caught:
                SistemaExplicito(model)
            self.assertEqual(caught.exception.diagnostics[0]['code'], 'INITIALIZATION_CONSTRAINT_CONFLICT')
            model['matematico']['condiciones'].reverse()

    def test_undefined_repeated_constraint_has_a_structured_rejection(self):
        for expression in (
            {'tipo': 'cociente', 'numerador': {'tipo': 'simbolo', 'id': 'initial_value_1'},
             'denominador': {'tipo': 'numero', 'valor': 0}},
            {'tipo': 'producto', 'argumentos': [{'tipo': 'simbolo', 'id': 'initial_value_1'},
                                              {'tipo': 'numero', 'valor': 1e308}]},
        ):
            for reverse in (False, True):
                model = fixture([('2', 'kg'), ('2', 'kg')])
                model['matematico']['condiciones'][1]['ecuacion']['derecha'] = expression
                if reverse:
                    model['matematico']['condiciones'].reverse()
                with self.assertRaises(HTTPException) as caught:
                    resolver_modelo({'modelo': model})
                self.assertEqual(caught.exception.status_code, 422)
                diagnostic = caught.exception.detail['diagnostics'][0]
                self.assertEqual(diagnostic['code'], 'INITIALIZATION_OUT_OF_DOMAIN')
                self.assertEqual(diagnostic['conditionIds'], ['initial_0', 'initial_1'])
                self.assertNotIn('valuesSI', diagnostic)
                json.dumps(diagnostic, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
