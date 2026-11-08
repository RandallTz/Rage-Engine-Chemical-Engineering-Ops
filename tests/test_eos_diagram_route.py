"""F8b lane A: HTTP route of the elevated-pressure EOS diagrams (backend/eos_diagrams.py, routes in
backend/api_modelo.py: GET /modelo/eos-diagrams/capabilities, POST /modelo/eos-diagrams).

The route adds no physics, so every published number is compared with the package operation it came from and with
the published references the F8b tests already use:
1. PSRK isotherm of methanol + toluene at 480 K (about 3 MPa) equals psrk.bubble_pressure on the same state.
2. Bubble-dew round trip: the dew curve of the bubble vapour composition returns the bubble pressure and liquid.
3. PSRK CO2 + ethanol at 333.15 K (Sima et al. 2011): the documented over-prediction (7.011 MPa against 6.06 MPa).
4. Peng-Robinson benzene + toluene at 333.15 K against Lee et al. 2009 (within 4 %) and cubic_flash.saturation.
5. Critical loci: PR benzene + toluene against cubic_critical; PSRK CO2 + ethanol against the Sima et al. 2011 line
   (x_CO2 = 0.892 and 0.931, within 7.5 K and 10 %) and psrk.critical_points.
6. Structured rejections (HTTP 200 with a diagnostic and a path), located causes, strict JSON.
Run: python tests/test_eos_diagram_route.py (about 1 min).
"""
import asyncio
import json
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx
from fastapi import FastAPI

from backend.api_modelo import router
from core.termodinamica import capa, cubic_critical as cc, cubic_flash as cf, psrk
from core.termodinamica.cubic_eos import PengRobinsonMixture
from test_psrk_mixture import SIMA_2011_ETOH_BUBBLE, SIMA_2011_ETOH_CRITICAL, KAPPA

warnings.filterwarnings('ignore')
CO2, ETOH, MEOH, TOL, BZ = '124-38-9', '64-17-5', '67-56-1', '108-88-3', '71-43-2'
app = FastAPI()
app.include_router(router)


def call(method, path, body=None):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as c:
            return await c.request(method, path, json=body, timeout=600)
    r = asyncio.run(run())
    assert r.status_code == 200, r.text
    json.loads(r.text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))   # strict JSON
    return r.json()


def comps(*cas):
    return [{'id': k + 1, 'identidadQuimica': {'cas': c}} for k, c in enumerate(cas)]


def req(op, pid, cas, **kw):
    return {'revision': 1, 'requestId': 't', 'operation': op, 'package': {'id': pid, 'version': '1'},
            'components': comps(*cas), **kw}


def post(body):
    return call('POST', '/modelo/eos-diagrams', body)


def T_(v):
    return {'valor': v, 'unidad': 'K'}


class Psrk(unittest.TestCase):
    P = capa.PSRK

    def test_isotherm_equals_the_package_bubble_point_at_elevated_pressure(self):
        out = post(req('isotherm', self.P, (MEOH, TOL), condition={'T': T_(480.0)}, fractionRange=[0.4, 0.8], points=2))
        self.assertEqual(out['status'], 'ok')
        eos = psrk.PSRKMixture((MEOH, TOL))
        for p in out['points']:
            x = p['liquid']['1']
            d = psrk.bubble_pressure(eos, 480.0, np.array([x, 1 - x]))
            self.assertLess(abs(p['P'] / d['P'] - 1), 1e-9)
            self.assertLess(abs(p['vapor']['1'] - d['y'][0]), 1e-9)
            self.assertEqual(p['certificate']['status'], 'pass')
        self.assertAlmostEqual(out['points'][0]['P'] / 1e6, 2.962, delta=0.003)     # roadmap F8b: 2.96 MPa

    def test_bubble_dew_round_trip(self):
        b = post(req('saturation_curve', self.P, (MEOH, TOL), composition={'1': 0.4, '2': 0.6}, kind='bubble',
                     temperatureRange={'from': T_(440.0), 'to': T_(480.0)}, points=3))
        self.assertEqual(b['status'], 'ok')
        for p in b['points']:
            y = p['vapor']
            d = post(req('saturation_curve', self.P, (MEOH, TOL), composition=y, kind='dew',
                         temperatureRange={'from': T_(p['T'] - 1.0), 'to': T_(p['T'])}, points=2))
            self.assertEqual(d['status'], 'ok')
            q = d['points'][-1]
            self.assertLess(abs(q['P'] / p['P'] - 1), 1e-7)
            self.assertLess(abs(q['liquid']['1'] - 0.4), 1e-7)

    def test_co2_ethanol_sima_2011_is_the_documented_over_prediction(self):
        out = post(req('isotherm', self.P, (CO2, ETOH), condition={'T': T_(333.15)}, fractionRange=[0.3317, 0.4303], points=2))
        self.assertEqual(out['status'], 'ok')
        self.assertAlmostEqual(out['points'][0]['P'] / 1e6, 7.011, delta=0.002)     # roadmap F8b layer entry
        data = {x: P for x, T, P in SIMA_2011_ETOH_BUBBLE if T == 333.15}
        for q in out['points']:
            dev = q['P'] / (data[round(q['liquid']['1'], 4)] * 1e3) - 1
            self.assertTrue(0.097 < dev < 0.647, dev)                                # +9.7 % to +64.7 %

    def test_critical_locus_against_sima_2011_and_the_package(self):
        out = post(req('critical_locus', self.P, (CO2, ETOH), fractionRange=[0.892, 0.931], points=2))
        self.assertEqual(out['status'], 'ok')
        eos = psrk.PSRKMixture((CO2, ETOH))
        ref = {x: (T, P * 1e3) for x, T, P in SIMA_2011_ETOH_CRITICAL}
        for p in out['points']:
            x = p['x']
            d = max(psrk.critical_points(eos, np.array([x, 1 - x]), **KAPPA), key=lambda r: r['T'])
            self.assertLess(abs(p['T'] - d['T']), 1e-6)
            self.assertLess(abs(p['P'] / d['P'] - 1), 1e-9)
            Tm, Pm = ref[round(x, 4)] if round(x, 4) in ref else ref[round(x, 3)]
            self.assertLess(abs(p['T'] - Tm), 7.5)
            self.assertLess(abs(p['P'] / Pm - 1), 0.10)

    def test_located_rejection_for_no_critical_point(self):
        out = post(req('critical_locus', self.P, (CO2, ETOH), fractionRange=[0.8315, 0.931], points=2))
        self.assertEqual(out['status'], 'partial')
        self.assertEqual([(r['x'], r['cause']) for r in out['rejected']], [(0.8315, 'no_critical_point_in_window')])


class PengRobinson(unittest.TestCase):
    P = capa.CUBICO
    LEE = {0.303: 28.3, 0.696: 42.0}              # kPa at 333.15 K (Lee et al. 2009)

    def test_benzene_toluene_isotherm(self):
        out = post(req('isotherm', self.P, (BZ, TOL), condition={'T': T_(333.15)}, fractionRange=[0.303, 0.696], points=2))
        self.assertEqual(out['status'], 'ok')
        eos = PengRobinsonMixture((BZ, TOL))
        for p in out['points']:
            x = p['liquid']['1']
            self.assertLess(abs(p['P'] / cf.saturation(eos, [x, 1 - x], T=333.15, kind='bubble')['P'] - 1), 1e-9)
            self.assertLess(abs(p['P'] / (self.LEE[round(x, 3)] * 1e3) - 1), 0.04)
            self.assertEqual(p['certificate']['status'], 'pass')

    def test_critical_locus_equals_heidemann_khalil(self):
        out = post(req('critical_locus', self.P, (BZ, TOL), fractionRange=[0.25, 0.75], points=2))
        self.assertEqual(out['status'], 'ok')
        eos = PengRobinsonMixture((BZ, TOL))
        for p in out['points']:
            x = p['x']
            d = max(cc.critical_points(eos, [x, 1 - x]), key=lambda r: r['T'])
            self.assertLess(abs(p['T'] - d['T']), 1e-6)
            self.assertLess(abs(p['P'] / d['P'] - 1), 1e-9)

    def test_missing_catalog_record_is_unsupported_not_a_default(self):
        out = post(req('isotherm', self.P, (CO2, ETOH), condition={'T': T_(333.15)}, points=3))
        self.assertEqual(out['status'], 'unsupported')
        self.assertEqual(out['diagnostics'][0]['code'], 'EOS_DIAG_NO_DATA')
        self.assertEqual(out['points'], [])


class Protocol(unittest.TestCase):
    def test_capabilities_list_both_packages(self):
        cap = call('GET', '/modelo/eos-diagrams/capabilities')
        self.assertEqual([p['model']['id'] for p in cap['packages']], [capa.CUBICO, capa.PSRK])
        self.assertEqual([o['id'] for o in cap['operations']], ['saturation_curve', 'isotherm', 'critical_locus'])

    def test_rejections_are_responses_with_paths(self):
        base = req('isotherm', capa.PSRK, (MEOH, TOL), condition={'T': T_(480.0)}, points=3)
        cases = [({**base, 'extra': 1}, 'invalid', 'extra'),
                 ({**base, 'package': {'id': 'mezcla-ideal', 'version': '1'}}, 'unsupported', 'package'),
                 ({**base, 'condition': {'T': {'valor': 480, 'unidad': 'F'}}}, 'invalid', 'condition.T.unidad'),
                 ({**base, 'points': 1000}, 'invalid', 'points'),
                 ({**base, 'components': comps(MEOH, TOL, BZ)}, 'unsupported', 'components'),
                 ({**base, 'revision': 2}, 'invalid', 'revision'),
                 ({k: v for k, v in base.items() if k != 'condition'}, 'incomplete', 'condition')]
        for body, status, path in cases:
            out = post(body)
            self.assertEqual(out['status'], status, path)
            self.assertIn(path, [d['path'] for d in out['diagnostics']])

    def test_dew_composition_must_sum_to_one(self):
        out = post(req('saturation_curve', capa.PSRK, (MEOH, TOL), composition={'1': 0.4, '2': 0.5}, kind='dew',
                       temperatureRange={'from': T_(400.0), 'to': T_(450.0)}, points=3))
        self.assertEqual(out['status'], 'invalid')

    def test_alpha_range_gate_is_a_located_rejection(self):
        out = post(req('isotherm', capa.PSRK, (CO2, ETOH), condition={'T': T_(150.0)}, points=3))
        self.assertEqual(out['points'], [])
        self.assertEqual({r['cause'] for r in out['rejected']}, {'alpha_below_fit_range'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
