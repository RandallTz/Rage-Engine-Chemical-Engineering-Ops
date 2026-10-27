"""F8: HTTP routes of the ternary liquid-liquid diagram and the composition-line slice
(backend/multicomponent_diagrams.py, routes in backend/routes_engine.py).

Every published value is checked against a reference reached by another path:
1. An analytic Margules liquid g^E/RT = A x0 x1 (species 2 ideal, A = 3): the equal-activity condition written here
   from its ln gamma, the exact plait point x0 = x1 = 1/A and the binary Margules edge ln((1-x)/x) = A(1-2x).
2. Benzene-water-ethanol (UNIFAC original) through the HTTP route: equal activity x_i gamma_i of every tie line from the
   package's liquid model directly (not through mu or the tracer), the package's TP flash (Gibbs minimization) at
   feeds on tie lines and inside the published L-L-V triangle, and the binary-edge pair against core/coexistencia_ll.
3. A composition line through the HTTP route along a published tie line: boundaries at its ends (lever rule).
4. Structured rejections (HTTP 200 with a diagnostic and a path) and strict JSON (no NaN).
Run: python tests/test_multicomponent_diagram_route.py (about 1.5 min).
"""
import json
import math
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import asyncio
import httpx
from fastapi import FastAPI

from backend import multicomponent_diagrams as service
from backend.routes_engine import router
from core import coexistencia_ll as ll
from core import diagramas_equilibrio as dg
from core import mezclas as mz
from core import ternary_liquid_liquid as tl
from test_ternary_liquid_liquid import margules_system

warnings.filterwarnings('ignore')
BZ, W, E, TO = '71-43-2', '7732-18-5', '64-17-5', '108-88-3'
UNIFAC = {'id': 'unifac-original-public', 'version': '1'}
P = 101325.0
app = FastAPI()
app.include_router(router)


class _Client:
    """Synchronous ASGI client without a port (TestClient does not start with the project's pinned versions)."""

    def _request(self, method, path, **kw):
        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
                return await c.request(method, path, timeout=600, **kw)
        return asyncio.run(run())

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, json=None):
        return self._request("POST", path, json=json)


client = _Client()


def components(*cas):
    return [{'id': k + 1, 'nombre': c, 'simbolo': f'C{k + 1}', 'identidadQuimica': {'cas': c}} for k, c in enumerate(cas)]


def ternary_body(T=300.0, cas=(BZ, W, E), model=UNIFAC, **extra):
    return {'revision': 1, 'requestId': 'route-test', 'components': components(*cas), 'model': model,
            'condition': {'T': {'valor': T, 'unidad': 'K'}, 'P': {'valor': P, 'unidad': 'Pa'}},
            'resolution': 'exploratoria', **extra}


def post(route, body):
    r = client.post(f'/motor/termodinamica/diagramas/{route}', json=body)
    assert r.status_code == 200, r.text
    json.loads(r.text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))   # strict JSON
    return r.json()


def vec(comp, ids=('1', '2', '3')):
    return np.array([comp[i] for i in ids])


def ln_activity(lngamma, x):
    return np.log(x) + lngamma(x)


class MargulesPublication(unittest.TestCase):
    """The route's publication of an analytic liquid (the test system is not a product package)."""

    @classmethod
    def setUpClass(cls):
        cls.A, T = 3.0, 300.0
        sis = margules_system(cls.A * T)
        budget = dg._Presupuesto(dg.PERFILES['exploratoria'])
        out = service._publish_ternary(sis, [1, 2, 3], T, P, tl.trace(sis, T, P, tl.PROFILES['exploratoria']),
                                       budget, 'mezcla-ideal')
        cls.out = json.loads(json.dumps(out, allow_nan=False))

    def margules_lngamma(self, x):
        A = self.A
        return np.array([A * x[1] * (1 - x[0]), A * x[0] * (1 - x[1]), -A * x[0] * x[1]])

    def test_every_tie_line_has_equal_analytic_activity(self):
        self.assertEqual(self.out['_status'], 'complete')
        self.assertGreater(len(self.out['tieLines']), 20)
        for t in self.out['tieLines']:
            a, b = (vec(p['composition']) for p in t['phases'])
            self.assertLessEqual(float(np.max(np.abs(ln_activity(self.margules_lngamma, a) -
                                                     ln_activity(self.margules_lngamma, b)))), 1e-9)
            self.assertEqual(t['certificate']['status'], 'pass')

    def test_plait_point_and_edge_are_exact(self):
        kinds = {p['kind']: p for p in self.out['specialPoints']}
        plait = kinds['plait_point']
        self.assertEqual(plait['certificate']['status'], 'pass')
        self.assertLessEqual(float(np.max(np.abs(vec(plait['composition']) - [1 / 3, 1 / 3, 1 / 3]))), 1e-6)
        edge = kinds['binary_edge']
        self.assertEqual(edge['absentComponentId'], 3)
        for p in edge['phases']:
            self.assertEqual(p['composition']['3'], 0.0)
        x = min(p['composition']['1'] for p in edge['phases'])
        self.assertLessEqual(abs(math.log((1 - x) / x) - self.A * (1 - 2 * x)), 1e-10)
        branch = self.out['branches'][0]
        self.assertEqual({e.get('specialPointId') for e in branch['ends']}, {plait['id'], edge['id']})


class BenzeneWaterEthanolRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sis = mz.Sistema(UNIFAC['id'], [BZ, W, E])
        cls.r = post('ternary-liquid-liquid', ternary_body())

    def test_identity_and_status(self):
        r = self.r
        self.assertEqual((r['status'], r['operation']), ('complete', 'ternary_liquid_liquid'))
        self.assertEqual(r['identity']['modelFingerprint'], self.sis.huella())
        self.assertEqual(r['condition']['T'], 300.0)
        self.assertEqual(len(r['branches']), 1)
        self.assertEqual(r['branches'][0]['tieLineIds'], [t['id'] for t in r['tieLines']])

    def test_equal_activity_from_the_liquid_model(self):
        lg = lambda x: self.sis.liq.lngamma(300.0, x)
        worst = 0.0
        for t in self.r['tieLines']:
            a, b = (vec(p['composition']) for p in t['phases'])
            self.assertAlmostEqual(float(a.sum()), 1.0, delta=1e-12)
            worst = max(worst, float(np.max(np.abs(ln_activity(lg, a) - ln_activity(lg, b)))))
        self.assertLessEqual(worst, 1e-9)

    def test_tie_lines_match_the_tp_flash(self):
        wide = [t for t in self.r['tieLines']
                if float(np.max(np.abs(vec(t['phases'][0]['composition']) - vec(t['phases'][1]['composition'])))) > 0.02]
        for t in wide[::max(1, len(wide) // 6)]:
            a, b = (vec(p['composition']) for p in t['phases'])
            state = self.sis.equilibrio_TP(300.0, P, 0.5 * (a + b))
            liquids = [f.x for f in state.fases if f.tipo == 'liquido']
            self.assertEqual(len(liquids), 2)
            for x in (a, b):
                self.assertLessEqual(min(float(np.max(np.abs(x - q))) for q in liquids), 1e-7)

    def test_plait_point_and_binary_edge(self):
        kinds = {p['kind']: p for p in self.r['specialPoints']}
        self.assertEqual(kinds['plait_point']['certificate']['status'], 'pass')
        edge = kinds['binary_edge']
        self.assertEqual(edge['absentComponentId'], 3)
        pair = ll.trace(mz.Sistema(UNIFAC['id'], [BZ, W]), 'Pxy', 300.0, ll.PROFILES['exploratoria'])[0].points[-1]
        got = sorted(p['composition']['1'] for p in edge['phases'])
        self.assertLessEqual(abs(got[0] - pair['xa']), 1e-8)
        self.assertLessEqual(abs(got[1] - pair['xb']), 1e-8)

    def test_three_phase_triangle_matches_the_tp_flash(self):
        r = post('ternary-liquid-liquid', ternary_body(T=340.0))
        tri = [p for p in r['specialPoints'] if p['kind'] == 'three_phase']
        self.assertEqual(len(tri), 1)
        self.assertEqual(tri[0]['certificate']['status'], 'pass')
        x = [vec(p['composition']) for p in tri[0]['phases']]
        state = self.sis.equilibrio_TP(340.0, P, sum(x) / 3)
        self.assertEqual(sorted(f.tipo for f in state.fases), ['liquido', 'liquido', 'vapor'])
        for v in x:
            self.assertLessEqual(min(float(np.max(np.abs(v - f.x))) for f in state.fases), 1e-7)

    def test_line_along_a_tie_line_crosses_at_its_ends(self):
        t = self.r['tieLines'][len(self.r['tieLines']) // 2]
        xa, xb = (vec(p['composition']) for p in t['phases'])
        d = xa - xb
        f = 0.5 * min(min(xa[i] / -d[i] for i in range(3) if d[i] < 0), min(xb[i] / d[i] for i in range(3) if d[i] > 0))
        zA, zB = xa + f * d, xb - f * d
        zB[2] = 1.0 - zB[0] - zB[1]
        zA[2] = 1.0 - zA[0] - zA[1]
        body = ternary_body(line={'start': {str(i + 1): float(zA[i]) for i in range(3)},
                                  'end': {str(i + 1): float(zB[i]) for i in range(3)}})
        r = post('composition-line', body)
        self.assertEqual(r['status'], 'complete')
        self.assertEqual(len(r['boundaries']), 2)
        for b, l_star in zip(r['boundaries'], [f / (1 + 2 * f), (1 + f) / (1 + 2 * f)]):
            self.assertLessEqual(abs(0.5 * sum(b['lInterval']) - l_star), 1e-8)
            two = b['before'] if len(b['before']['phases']) == 2 else b['after']
            for x in (xa, xb):
                self.assertLessEqual(min(float(np.max(np.abs(vec(p['composition']) - x))) for p in two['phases']), 1e-6)
        for row in r['rows']:
            self.assertAlmostEqual(sum(p['fraction'] for p in row['phases']), 1.0, delta=1e-12)
            self.assertEqual(list(row['feed']), ['1', '2', '3'])


class Rejections(unittest.TestCase):
    def rejected(self, route, body, status, code, path=None):
        r = post(route, body)
        self.assertEqual(r['status'], status, r['diagnostics'])
        self.assertIsNone(r['condition'])
        d = [x for x in r['diagnostics'] if x['code'] == code]
        self.assertTrue(d, r['diagnostics'])
        if path is not None:
            self.assertEqual(d[0]['path'], path)
        return r

    def test_species_counts(self):
        self.rejected('ternary-liquid-liquid', ternary_body(cas=(BZ, W)), 'unsupported',
                      'MOTOR_DIAG_COMPONENTES_NO_SOPORTADO', 'components')
        self.rejected('ternary-liquid-liquid', ternary_body(cas=(BZ, W, E, TO)), 'unsupported',
                      'MOTOR_DIAG_COMPONENTES_NO_SOPORTADO', 'components')
        one = ternary_body(cas=(BZ,), line={'start': {'1': 1.0}, 'end': {'1': 1.0}})
        self.rejected('composition-line', one, 'unsupported', 'MOTOR_DIAG_COMPONENTES_NO_SOPORTADO', 'components')

    def test_packages(self):
        self.rejected('ternary-liquid-liquid', ternary_body(model={'id': 'agua-iapws95', 'version': '1'}),
                      'unsupported', 'MOTOR_DIAG_PAQUETE_NO_DISPONIBLE', 'model')
        self.rejected('ternary-liquid-liquid', ternary_body(model={'id': UNIFAC['id'], 'version': '9'}),
                      'unsupported', 'MOTOR_DIAG_PAQUETE_NO_DISPONIBLE', 'model')

    def test_domain(self):
        self.rejected('ternary-liquid-liquid', ternary_body(T=1000.0), 'unsupported', 'MOTOR_DIAG_FUERA_DE_DOMINIO',
                      'condition.T')
        body = ternary_body()
        body['condition']['P'] = {'valor': 50.0, 'unidad': 'bar'}
        self.rejected('ternary-liquid-liquid', body, 'unsupported', 'MOTOR_DIAG_FUERA_DE_DOMINIO', 'condition.P')

    def test_data(self):
        body = ternary_body()
        body['condition']['T'] = {'valor': 300.0, 'unidad': 'm'}
        self.rejected('ternary-liquid-liquid', body, 'invalid', 'MOTOR_DIAG_UNIDAD', 'condition.T.unidad')
        body['condition']['T'] = {'valor': None, 'unidad': 'K'}
        self.rejected('ternary-liquid-liquid', body, 'incomplete', 'MOTOR_DIAG_DATO_INVALIDO', 'condition.T.valor')
        self.rejected('ternary-liquid-liquid', ternary_body(extra=1), 'invalid', 'MOTOR_DIAG_DATO_INVALIDO', 'extra')
        self.rejected('ternary-liquid-liquid', {**ternary_body(), 'revision': 2}, 'invalid', 'MOTOR_DIAG_REVISION')
        self.rejected('ternary-liquid-liquid', ternary_body(expectedModelFingerprint='sha256:other'), 'invalid',
                      'MOTOR_DIAG_HUELLA_DISTINTA', 'expectedModelFingerprint')
        r = post('ternary-liquid-liquid', [])
        self.assertEqual(r['status'], 'invalid')

    def test_line_ends(self):
        absent = ternary_body(line={'start': {'1': 0.5, '2': 0.5, '3': 0.0}, 'end': {'1': 0.2, '2': 0.8, '3': 0.0}})
        self.rejected('composition-line', absent, 'unsupported', 'MOTOR_DIAG_COMPONENTE_AUSENTE', 'line')
        self.rejected('composition-line', ternary_body(line={'start': {'1': 0.5, '2': 0.5}, 'end': {'1': 1, '2': 0, '3': 0}}),
                      'invalid', 'MOTOR_DIAG_DATO_INVALIDO', 'line.start')
        self.rejected('composition-line', ternary_body(line={'start': {'1': 0.5, '2': 0.4, '3': 0.0},
                                                             'end': {'1': 0.2, '2': 0.7, '3': 0.1}}),
                      'invalid', 'MOTOR_DIAG_DATO_INVALIDO', 'line')
        self.rejected('composition-line', ternary_body(), 'incomplete', 'MOTOR_DIAG_DATO_INVALIDO', 'line')

    def test_capabilities(self):
        r = client.get('/motor/termodinamica/diagramas/multicomponent/capabilities').json()
        self.assertEqual(r['revision'], 1)
        self.assertEqual({o['id'] for o in r['operations']}, {'ternary_liquid_liquid', 'composition_line'})
        self.assertIn(UNIFAC, [p['model'] for p in r['packages']])


if __name__ == '__main__':
    unittest.main()
