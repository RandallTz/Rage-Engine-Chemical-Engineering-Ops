"""F0-1/F0-2 regression: the catalog publishes each admitted species' temperature range per package, and the
package domain is declared as the envelope of those ranges.

Independent reference: each range is recomputed here from the pure data the catalog itself publishes
(vapor-pressure and ideal-gas Cp ranges, T <= 0.9 Tc) and from the parameter-table bounds written below, not
from the runtime code path. Behavior: the public evaluate contract must accept a pure species just inside its
range and reject it just outside with MOTOR_ESTADO_FUERA_DE_DOMINIO; a mixture is limited to the intersection.

Before the fix the catalog admitted ethyl acetate in UNIFAC-LLE at 10-40 C without a range, while every
system containing it was rejected below 298 K. Run from the repository root:
    python tests/test_catalog_species_domains.py
"""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.motor_catalogo import catalogo_publico
from backend.motor_termodinamica import capacidades, evaluar

# Parameter-table temperature bounds, from their sources (not read from the code under test).
TABLE_BOUNDS = {'unifac-original-lle-public': (283.15, 313.15),   # Magnussen et al. 1981, 10-40 C
                'nrtl-lle-agua-butanol': (293.0, 373.0)}          # IUPAC SDS-15 mutual-solubility fit range
WATER, ETHYL_ACETATE = '7732-18-5', '141-78-6'
DOMAIN = 'MOTOR_ESTADO_FUERA_DE_DOMINIO'


def request(model, fractions, T, P=101325.0):
    components = [{'id': i + 1, 'nombre': cas, 'simbolo': f'C{i + 1}', 'identidadQuimica': {'cas': cas}}
                  for i, cas in enumerate(fractions)]
    return {'revision': 1, 'solicitudId': 'f0', 'propietarioId': 'volumen:f0', 'componentes': components,
            'declaracion': {'modelo': {'id': model, 'version': '1'},
                            'especificacion': {'tipo': 'TP', 'T': {'valor': T, 'unidad': 'K'}, 'P': {'valor': P, 'unidad': 'Pa'},
                                               'composicion': {'base': 'molar',
                                                               'fracciones': {str(i + 1): x for i, x in enumerate(fractions.values())}}},
                            'politica': {'cantidad': 'sin_restriccion', 'cambioInterno': 'permitido', 'evaluacion': 'equilibrio_estable'}}}


def codes(response):
    return [d.get('codigo') for d in response.get('diagnosticos', [])]


class CatalogSpeciesDomains(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = catalogo_publico()
        cls.substances = {s['cas']: s for s in cls.catalog['sustancias']}
        cls.packages = {p['modelo']['id']: p for p in cls.catalog['paquetes']}
        cls.models = {m['id']: m for m in capacidades()['modelos']}

    def reference(self, model, cas):
        if model.startswith('agua-iapws95'):
            return tuple(self.models[model]['dominio']['T'])
        props = {p['id']: p for p in self.substances[cas]['datosPuros']['propiedades']}
        psat, cp = props['presion_vapor'], props['cp_gas_ideal']
        lo = max(psat['dominio']['T'][0], cp['dominio']['T'][0])
        hi = min(psat['dominio']['T'][1], cp['dominio']['T'][1], 0.9 * psat['coeficientes']['Tc'])
        if model in TABLE_BOUNDS:
            lo, hi = max(lo, TABLE_BOUNDS[model][0]), min(hi, TABLE_BOUNDS[model][1])
        return lo, hi

    def test_every_admitted_species_publishes_its_range(self):
        for model, package in self.packages.items():
            for entry in package['especies']:
                with self.subTest(model=model, cas=entry['cas']):
                    if not entry['admitida']:
                        self.assertNotIn('dominio', entry)
                        continue
                    lo, hi = entry['dominio']['T']
                    ref = self.reference(model, entry['cas'])
                    self.assertAlmostEqual(lo, ref[0], delta=1e-9 * ref[0])
                    self.assertAlmostEqual(hi, ref[1], delta=1e-9 * ref[1])
                    self.assertTrue(entry['dominio']['motivo'])

    def test_package_domain_is_the_envelope_and_matches_the_state_route(self):
        for model, package in self.packages.items():
            with self.subTest(model=model):
                ranges = [e['dominio']['T'] for e in package['especies'] if e['admitida']]
                self.assertEqual(package['dominio']['T'], [min(r[0] for r in ranges), max(r[1] for r in ranges)])
                self.assertEqual(package['dominio']['T'], list(self.models[model]['dominio']['T']))
                self.assertEqual(package['dominio']['P'], list(self.models[model]['dominio']['P']))
                self.assertIn('envelope', package['dominio']['motivo'].lower())

    def test_unifac_lle_ethyl_acetate_range(self):
        entry = next(e for e in self.packages['unifac-original-lle-public']['especies'] if e['cas'] == ETHYL_ACETATE)
        self.assertTrue(entry['admitida'])
        self.assertEqual(entry['dominio']['T'], [298.0, 313.15])

    def test_runtime_honours_the_published_range(self):
        model = 'unifac-original-lle-public'
        for cas in (ETHYL_ACETATE, WATER):
            lo, hi = next(e for e in self.packages[model]['especies'] if e['cas'] == cas)['dominio']['T']
            with self.subTest(cas=cas):
                self.assertNotIn(DOMAIN, codes(evaluar(request(model, {cas: 1.0}, lo + 0.01))))
                self.assertNotIn(DOMAIN, codes(evaluar(request(model, {cas: 1.0}, hi - 0.01))))
                self.assertIn(DOMAIN, codes(evaluar(request(model, {cas: 1.0}, lo - 0.01))))
                self.assertIn(DOMAIN, codes(evaluar(request(model, {cas: 1.0}, hi + 0.01))))

    def test_mixture_is_limited_to_the_intersection(self):
        model = 'unifac-original-lle-public'
        mixture = {WATER: 0.5, ETHYL_ACETATE: 0.5}
        self.assertIn(DOMAIN, codes(evaluar(request(model, mixture, 290.0))))     # inside water's range only
        self.assertNotIn(DOMAIN, codes(evaluar(request(model, mixture, 300.0))))  # inside both ranges
        self.assertNotIn(DOMAIN, codes(evaluar(request(model, {WATER: 1.0}, 290.0))))


if __name__ == '__main__':
    unittest.main()
