"""Integrity of the frozen legacy distillation reference data (cleanup phase 2, clean-2).

The files in tests/reference_data/legacy-distillation/ were produced once by
tools/legacy_reference/freeze_legacy_distillation.py before the legacy Process
Simulation side is deleted. This test imports no legacy code, so it keeps running
after that deletion. It checks the manifest hashes, the format, units and
provenance, and re-derives the hand-checkable relations from the frozen numbers
alone. Run from the repository root:
    python tests/test_legacy_reference_data.py
"""
from pathlib import Path
import hashlib
import json
import math
import unittest

DATA = Path(__file__).resolve().parent / 'reference_data' / 'legacy-distillation'
FORMAT, VERSION = 'rage.legacy-reference', 1
KINDS = {'independent', 'cross-method', 'self-consistency', 'none'}
GRADES = {'cross-checked', 'legacy-output-only'}
EXPECTED = {'mccabe-thiele-benzene-toluene', 'ponchon-savarit-benzene-toluene', 'fug-alkanes',
            'column-flowsheet-fug-pump', 'http-column-presets'}


def load(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))


def finite_numbers(value, path='$'):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from finite_numbers(v, f'{path}.{k}')
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from finite_numbers(v, f'{path}[{i}]')
    elif isinstance(value, float):
        yield path, value


class LegacyReferenceData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load('manifest.json')
        cls.cases = {name[:-5]: load(name) for name in cls.manifest['files']}

    def test_manifest_hashes_and_inventory(self):
        self.assertEqual(self.manifest['format'], FORMAT + '.manifest')
        self.assertEqual(set(self.cases), EXPECTED)
        on_disk = {p.name for p in DATA.glob('*.json')} - {'manifest.json'}
        self.assertEqual(on_disk, set(self.manifest['files']))
        for name, digest in self.manifest['files'].items():
            self.assertEqual(hashlib.sha256((DATA / name).read_bytes()).hexdigest(), digest, name)

    def test_format_provenance_and_validation_fields(self):
        for id_, case in self.cases.items():
            with self.subTest(case=id_):
                self.assertEqual((case['format'], case['version'], case['id']), (FORMAT, VERSION, id_))
                for key in ('method', 'legacy', 'inputs', 'assumptions', 'thermodynamics', 'outputs', 'validation', 'units', 'provenance'):
                    self.assertIn(key, case)
                env = case['provenance']['environment']
                self.assertEqual(env['thermo'], case['thermodynamics']['provider']['version'])
                self.assertEqual(len(case['provenance']['commit']), 40)
                self.assertTrue(all(len(h) == 64 for h in case['provenance']['legacySourceSha256'].values()))
                self.assertIn(case['validation']['grade'], GRADES)
                for check in case['validation']['checks']:
                    self.assertIn(check['kind'], KINDS)
                    self.assertNotEqual(check.get('holdsInFrozenData'), False, check['id'])
                for path, number in finite_numbers(case):
                    self.assertTrue(math.isfinite(number), path)

    def test_mccabe_thiele_relations_from_frozen_numbers(self):
        o = self.cases['mccabe-thiele-benzene-toluene']['outputs']
        i = self.cases['mccabe-thiele-benzene-toluene']['inputs']
        D = i['F'] * (i['z_F'] - i['x_B']) / (i['x_D'] - i['x_B'])
        self.assertAlmostEqual(o['material_balance']['result']['D'], D, delta=1e-9 * D)
        self.assertAlmostEqual(o['material_balance']['result']['D'] + o['material_balance']['result']['B'], i['F'], delta=1e-9)
        loads, R = o['thermal_loads'], o['rating']['R']
        self.assertAlmostEqual(loads['Q_c'], D * (R + 1) * loads['Hvap_D'], delta=1e-9 * loads['Q_c'])
        self.assertAlmostEqual(o['partial_condenser']['N_partial'] - o['partial_condenser']['N_total'], 1.0, places=9)
        self.assertAlmostEqual(o['design_N_10']['recheck_N'], 10.0, places=6)
        self.assertAlmostEqual(R, 1.5 * o['R_min'], places=12)

    def test_binary_equilibrium_tables_are_consistent(self):
        for id_ in ('mccabe-thiele-benzene-toluene', 'ponchon-savarit-benzene-toluene'):
            t = self.cases[id_]['thermodynamics']['tables']
            with self.subTest(case=id_):
                # Modified Raoult at the bubble point: sum_i x_i gamma_i Psat_i(T) = P. Psat is tabulated on a T grid,
                # so check the light-component enrichment and monotonic bubble temperature instead of re-interpolating.
                self.assertTrue(all(y > x for x, y in zip(t['x_light'], t['y_light'])))
                self.assertTrue(all(a > b for a, b in zip(t['T_bubble'], t['T_bubble'][1:])))
                self.assertEqual(len(t['activity_coefficients']), len(t['x_light']))

    def test_fug_relations_from_frozen_numbers(self):
        case = self.cases['fug-alkanes']
        z, b = case['inputs']['z_F'], case['outputs']['base_case']
        for zi, di, bi in zip(z, b['d'], b['b']):
            self.assertAlmostEqual(di + bi, zi, places=9)
        self.assertAlmostEqual(b['d'][1] / z[1], 0.98, places=9)
        self.assertAlmostEqual(b['b'][2] / z[2], 0.98, places=9)
        self.assertLess(b['T_D'], b['T_F'])
        self.assertLess(b['T_F'], b['T_B'])
        self.assertLess(abs(b['N_min'] - case['outputs']['fenske_two_point_N_min']) / b['N_min'], 0.005)
        self.assertTrue(case['rejections']['nonadjacent_keys_negative_R_min']['rejected'])

    def test_cross_references_between_files(self):
        fug = self.cases['fug-alkanes']['outputs']['base_case']['N']
        chain = self.cases['column-flowsheet-fug-pump']['outputs']['pool']['columna.N']
        self.assertAlmostEqual(chain, fug, places=9)
        self.assertAlmostEqual(fug, 9.434906966491038, places=6)
        cross = self.cases['ponchon-savarit-benzene-toluene']['outputs']['cross_check_with_mccabe_thiele']
        self.assertEqual(len(cross), 6)
        self.assertTrue(all(abs(c['ratio'] - 1) <= 0.035 and c['monotone'] for c in cross))
        presets = {p['preset']: p for p in self.cases['http-column-presets']['outputs']['pairs']}
        self.assertEqual(set(presets), {'mccabe_thiele_benceno_tolueno', 'ponchon_savarit_benceno_tolueno', 'fug_alcanos'})
        self.assertTrue(all(p['status'] == 200 and p['response']['completo'] for p in presets.values()))


if __name__ == '__main__':
    unittest.main()
