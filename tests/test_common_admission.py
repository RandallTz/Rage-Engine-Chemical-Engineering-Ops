"""R7 admission regressions, also used by the v2 compatibility migration."""
import asyncio
import copy
from pathlib import Path
import sys
import unittest

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from solicitudes_v2 import Red
from core.modelo import desde_ensamblaje_v2
from core.compilador import compilar, NoSoportado


def request(scale=1.0, flow=0.001, heat=100.0, horizon='10'):
    red = Red('admission', ('benceno', 'tolueno'), tf=(horizon, 's'), muestras=3).paquete('p', 'mezcla-ideal')
    for owner, amounts, temperature in [('A', (0.4, 0.6), 330), ('B', (0.1, 0.9), 300)]:
        red.volumen(owner, 'p', {name: (str(scale*n), 'mol') for name, n in zip(('benceno', 'tolueno'), amounts)},
                    ('T', str(temperature), 'K'), P=('101325', 'Pa'), base='molar', adiabatico=owner == 'B')
    red.corriente('s', 'A', 'B', ('benceno', 'tolueno'), (str(scale*flow), 'mol/s'), base='molar',
                  extraccion={'A': {'tipo': 'mezcla_homogenea'}})
    red.calor('q', None, 'A', Q=(str(scale*heat), 'W'))
    return red.solicitud()


def model(**kwargs):
    return desde_ensamblaje_v2(request(**kwargs))


class CommonAdmission(unittest.TestCase):
    def rejection(self, value, code):
        with self.assertRaises(NoSoportado) as caught:
            compilar(value)
        diagnostics = caught.exception.diagnostics
        self.assertIn(code, [row['code'] for row in diagnostics])
        self.assertTrue(all(row.get('path') for row in diagnostics))
        return diagnostics

    def test_units_are_checked_by_consuming_role(self):
        for data_id, unit in [('calor.q.Q', 'degC'), ('corriente.s.F', 'kg/s'), ('corriente.s.F', 'K'),
                              ('volumen.A.P', 'J'), ('volumen.A.T0', 'W'), ('volumen.A.n0.1', 'kg'),
                              ('estudio.tf', 'K')]:
            with self.subTest(data=data_id, unit=unit):
                value = model()
                value['datos'][data_id]['declaracion'].update(texto='0', unidad=unit)
                self.rejection(value, 'incompatible_dimension')

    def test_invalid_initial_data_and_horizon_fail_before_integration(self):
        for data_id, text, code in [('estudio.tf', '0', 'invalid_horizon'), ('estudio.tf', '-1', 'invalid_horizon'),
                                    ('volumen.B.n0.1', '-0.1', 'invalid_inventory'),
                                    ('volumen.B.n0.1', 'nan', 'invalid_data'), ('calor.q.Q', '1e999', 'invalid_data')]:
            with self.subTest(data=data_id, text=text):
                value = model(); value['datos'][data_id]['declaracion']['texto'] = text
                self.rejection(value, code)
        value = model()
        for key in ('volumen.B.n0.1', 'volumen.B.n0.2'):
            value['datos'][key]['declaracion']['texto'] = '0'
        self.rejection(value, 'invalid_inventory')

    def test_missing_extraction_and_duplicate_cas_are_rejected(self):
        missing = model(); missing['corrientes'][0].pop('extraccion')
        duplicate = model(); duplicate['componentes'][1]['identidadQuimica'] = copy.deepcopy(duplicate['componentes'][0]['identidadQuimica'])
        for value, code in [(model(flow=-0.001), 'missing_extraction'), (missing, 'missing_extraction'),
                            (duplicate, 'duplicate_chemical_identity')]:
            with self.subTest(code=code):
                self.rejection(value, code)

    def test_non_si_data_and_label_changes_preserve_the_physical_rhs(self):
        baseline = compilar(model()); initial = baseline.inicial()
        value = model()
        for key, text, unit in [('calor.q.Q', '0.1', 'kW'), ('corriente.s.F', '0.000001', 'kmol/s'),
                                ('volumen.A.T0', '56.85', 'degC'), ('volumen.A.P', '1.01325', 'bar')]:
            value['datos'][key]['declaracion'].update(texto=text, unidad=unit)
        value['nombre'] = 'Different display label'
        system = compilar(value); changed = system.inicial()
        np.testing.assert_allclose(changed, initial, rtol=1e-12, atol=1e-10)
        np.testing.assert_allclose(system.rhs(0, changed), baseline.rhs(0, initial), rtol=1e-12, atol=1e-12)

    def test_physical_assumptions_cannot_silently_disappear(self):
        for key, declared, code in [('densidadMediaConstante', True, 'formulation_densidad'),
                                    ('densidadComunPuertos', True, 'formulation_densidad'),
                                    ('generacionUniforme', True, 'formulation_fuentes'),
                                    ('reglasEstado', {'fases': {'cantidad': 'monofasico'}}, 'formulation_politica')]:
            with self.subTest(assumption=key):
                value = model(); value['volumenes'][0]['supuestos']['materia'][key] = declared
                self.rejection(value, code)

    def test_scope_topology_and_hidden_data_are_rejected(self):
        cases = []
        value = model(); value['corrientes'][0]['hasta'] = 'A'; cases.append((value, 'invalid_topology'))
        value = model(); value['corrientes'][0]['extraccion']['A'] = {}; cases.append((value, 'invalid_extraction'))
        value = model(); value['estudio']['muestras'] = 1002; cases.append((value, 'invalid_samples'))
        value = model(); value['estudio'] = None; cases.append((value, 'missing_study'))
        value = model(); value['estudio']['rtol'] = 0; cases.append((value, 'invalid_tolerance'))
        value = model(); value['estudio']['atol']['energia'] = -1; cases.append((value, 'invalid_tolerance'))
        value = model(); value['termodinamica']['paquetes'][0]['modelo']['version'] = 'missing'; cases.append((value, 'unsupported_package'))
        value = model(); value['datos']['volumen.A.n0.1']['declaracion']['texto'] = '1+t'; cases.append((value, 'time_dependent_initial_data'))
        value = model(); value['corrientes'][0]['materia']['caudalId'] = 'calor.q.Q'; cases.append((value, 'incompatible_dimension'))
        value = model(); value['volumenes'][1]['inicial']['cantidades']['datoIds'] = {}; cases.append((value, 'invalid_inventory'))
        for cas in (None, [], 123):
            value = model(); value['componentes'][0]['identidadQuimica'] = {'cas': cas}
            cases.append((value, 'missing_chemical_identity'))
        value = model(); value['componentes'][0]['identidadQuimica']['cas'] = '71-43-3'; cases.append((value, 'invalid_chemical_identity'))
        value = model(); value['componentes'][0]['masaMolar'] = {'cantidad': {'valor': 1, 'unidad': 'kg/mol'}}
        cases.append((value, 'inconsistent_molar_mass'))
        value = model(); value['componentes'][0]['masaMolar'] = {'cantidad': {'valor': 1, 'unidad': 'K'}}
        cases.append((value, 'invalid_molar_mass'))
        for value, code in cases:
            with self.subTest(code=code):
                self.rejection(value, code)

    def test_http_admission_is_structured(self):
        from fastapi import FastAPI
        from backend.api_modelo import router
        app = FastAPI(); app.include_router(router)
        values = []
        for key, text in [('estudio.tf', '0'), ('volumen.B.n0.1', '-0.1'), ('volumen.B.n0.1', 'nan')]:
            value = model(); value['datos'][key]['declaracion']['texto'] = text; values.append(value)
        value = model(); value['volumenes'][1]['componenteIds'] = []; values.append(value)
        value = model(); value['volumenes'][1]['inicial']['cantidades']['datoIds'] = {}; values.append(value)
        value = model(); value['componentes'][0]['identidadQuimica'] = {}; values.append(value)
        value = model(); value['estudio'] = None; values.append(value)
        value = model(horizon='100')
        value['datos']['volumen.A.P']['declaracion']['texto'] = '101325 - 2026.5*t'
        values.append(value)
        for identity, expression in [('volumen.A.P','101325-200000*exp(-1e8*(t-0.125)^2)'),
                                     ('calor.q.Q','sqrt(25-t)'), ('calor.q.Q','1/(t-0.125)')]:
            value=model(horizon='100')
            value['datos'][identity]['declaracion']['texto']=expression
            values.append(value)
        value = model(); value.update(componentes=[], volumenes=[], corrientes=[], intercambios=[]); values.append(value)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url='http://test') as client:
                for value in values:
                    for endpoint in ('resolver', 'compilation'):
                        response = await client.post('/modelo/'+endpoint, json={'modelo': value})
                        self.assertEqual(response.status_code, 422, response.text[:200])
                        self.assertIsInstance(response.json()['detail'], dict)
        asyncio.run(check())

    def test_time_dependent_positive_roles_cover_the_horizon(self):
        from backend.motor_ensamblaje_v2 import validar_v2
        req = request(horizon='100')
        req['datos']['volumen.A.P']['declaracion']['texto'] = '101325 - 2026.5*t'
        native, _ = validar_v2(req)
        self.assertIn('MOTOR_ENS_FUERA_DE_MAGNITUD', [d['codigo'] for d in native['diagnosticos']])
        # Independent arithmetic: P(50) = 0; the full declared horizon is 100 s.
        self.assertEqual(101325 / 2026.5, 50)
        diagnostics = self.rejection(desde_ensamblaje_v2(req), 'invalid_physical_value')
        self.assertIn('MOTOR_ENS_FUERA_DE_MAGNITUD', [d['nativeCode'] for d in diagnostics])

    def test_horizon_bounds_reject_between_grid_failures(self):
        cases = [('volumen.A.P', '101325 - 200000*exp(-1e8*(t-0.125)^2)'),
                 ('calor.q.Q', 'sqrt(25-t)'), ('calor.q.Q', '1/(t-0.125)')]
        for identity, expression in cases:
            with self.subTest(expression=expression):
                value = model(horizon='100')
                value['datos'][identity]['declaracion']['texto'] = expression
                # Independent witnesses: P(0.125)=-98675 Pa; sqrt is undefined
                # after 25 s; the denominator is zero at 0.125 s.
                with self.assertRaises(NoSoportado) as caught:
                    compilar(value)
                self.assertTrue(caught.exception.diagnostics)
                self.assertTrue(any(identity in d['path'] or 'frontera' in d['path'] for d in caught.exception.diagnostics))

    def test_horizon_bounds_accept_finite_nonlinear_data(self):
        value = model(horizon='100')
        value['datos']['volumen.A.P']['declaracion']['texto'] = '101325 + 10000*sin(t)'
        value['datos']['calor.q.Q']['declaracion']['texto'] = '100*cos(t)'
        # Independent global bounds: P in [91325,111325], Q in [-100,100].
        compilar(value)

    def test_unavailable_enclosure_is_a_structured_rejection(self):
        value = model(horizon='100')
        value['datos']['calor.q.Q']['declaracion']['texto'] = '2^sin(t)'
        # This expression is finite, but variable powers are outside the
        # interval evaluator's declared scope. It must fail closed, not sample.
        diagnostics = self.rejection(value, 'unbounded_time_data')
        self.assertIn('MOTOR_ENS_EXPRESION', [d['nativeCode'] for d in diagnostics])

    def test_pressure_derivative_must_be_finite_over_the_horizon(self):
        value=model(horizon='100')
        value['datos']['volumen.A.P']['declaracion']['texto']='101325+sqrt(t)'
        # P is positive and finite, but its required work term V*dP/dt has
        # dP/dt=1/(2*sqrt(t)), undefined at the initial endpoint.
        self.rejection(value,'invalid_data')


if __name__ == '__main__':
    unittest.main()
