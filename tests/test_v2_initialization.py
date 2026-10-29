"""Step (b): common admission/initialization, never a legacy solver fallback."""
import contextlib
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import unifac
from core.compilador import compilar, NoSoportado
from core.modelo import desde_ensamblaje_v2, ErrorModelo
from test_common_admission import model, request
from solicitudes_v2 import Red


def archives():
    for path in sorted((ROOT/'docs/ejemplos').rglob('*-peticion.json')):
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if value.get('revision') == 2 and 'volumenes' in value and 'paquetes' in value:
            yield path, value


class V2Initialization(unittest.TestCase):
    def test_up_initialization_matches_separate_tp_state(self):
        for package, species in [('mezcla-ideal', ('benceno', 'tolueno')), ('agua-iapws95', ('agua',))]:
            for pressure in ('101325', '200000'):
                with self.subTest(package=package, pressure=pressure):
                    req = Red('up', species, tf=('1', 's')).paquete('p', package).volumen(
                        'A', 'p', {name: ('0.5', 'mol') for name in species}, ('T', '330', 'K'),
                        P=(pressure, 'Pa'), base='molar', adiabatico=True).solicitud()
                    baseline = compilar(desde_ensamblaje_v2(req))
                    initial = baseline.inicial(); state = baseline._estados(0, initial, rapido=False)['A']
                    changed = copy.deepcopy(req)
                    changed['volumenes'][0]['inicial']['energia'] = {'tipo': 'U', 'datoId': 'volumen.A.T0'}
                    changed['datos']['volumen.A.T0'].update(magnitud='energia')
                    changed['datos']['volumen.A.T0']['declaracion'].update(texto=repr(state.U), unidad='J')
                    system = compilar(desde_ensamblaje_v2(changed)); y = system.inicial()
                    got = system._estados(0, y, rapido=False)['A']
                    np.testing.assert_allclose([got.T, got.P, got.V, got.U, got.H],
                                               [state.T, state.P, state.V, state.U, state.H], rtol=2e-8, atol=1e-7)

    def test_archived_admission_and_initialization(self):
        rows = list(archives()); self.assertEqual(len(rows), 25)
        manifest, admitted, rejected = [], [], []
        original_assignment = unifac.asignacion
        def missing_assignment(cas, variant='original'):
            if cas == '141-78-6':
                raise unifac.FaltaDatoUNIFAC('Simulated missing acetate assignment, as in the archive generator.',
                                           {'tipo': 'asignacion_ausente', 'cas': cas, 'variante': variant})
            return original_assignment(cas, variant)
        for path, req in rows:
            with self.subTest(request=req['solicitudId']):
                response_path = path.with_name(path.name.replace('-peticion', '-respuesta'))
                for source in (path, response_path):
                    if source.exists():
                        manifest.append([source.relative_to(ROOT).as_posix(), hashlib.sha256(source.read_bytes()).hexdigest()])
                if not response_path.exists():
                    with self.assertRaises((ErrorModelo, NoSoportado)):
                        compilar(desde_ensamblaje_v2(req))
                    rejected.append(req['solicitudId']); continue
                response = json.loads(response_path.read_text(encoding='utf8'))
                validation = response.get('validacion', response)
                expected = {d['codigo'] for d in validation['diagnosticos']
                            if d['estado'] in ('invalido', 'incompleto', 'conflicto', 'no_soportado')
                            and not d['codigo'].startswith('MOTOR_ENS_DETENIDO_')}
                context = patch.object(unifac, 'asignacion', missing_assignment) if 'simulado' in path.name else contextlib.nullcontext()
                with context:
                    if expected:
                        with self.assertRaises(NoSoportado) as caught:
                            compilar(desde_ensamblaje_v2(req))
                        actual = {d['nativeCode'] for d in caught.exception.diagnostics}
                        self.assertTrue(expected <= actual, (expected, actual))
                        rejected.append(req['solicitudId']); continue
                    system = compilar(desde_ensamblaje_v2(req)); y = system.inicial()
                    states = system._estados(0, y, rapido=False)
                    for owner, initial in validation['inicializacion']['volumenes'].items():
                        self.assertEqual(initial['estado'], 'compatible')
                        for identity, target in initial['variables'].items():
                            field = identity.removeprefix('volumen.'+owner+'.')
                            volume = system.por_id[owner]
                            actual = y[volume.i_n][volume.comp.index(int(field[2:]))] if field.startswith('n.') else getattr(states[owner], field)
                            self.assertAlmostEqual(actual, target, delta=1e-7*max(abs(target), 1e-10), msg=identity)
                    admitted.append(req['solicitudId'])
                    print(json.dumps({'initialization': req['solicitudId'], 'volumes': len(states), 'status': 'compatible'}), flush=True)
        digest = hashlib.sha256(json.dumps(sorted(manifest), ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '0931e2c77e83011aead32888d78239fc08e66dabc8dad9cb9fa20a6ea1c9657d')
        self.assertEqual((len(admitted), len(rejected)), (19, 6))

    def test_pure_substitutions_reach_shared_closure_and_fingerprint(self):
        _, req = next((p, r) for p, r in archives() if 'resolver-sustitucion-vl' in p.name)
        modified = compilar(desde_ensamblaje_v2(req))
        plain_request = copy.deepcopy(req); plain_request['paquetes'][0].pop('datosPuros')
        plain = compilar(desde_ensamblaje_v2(plain_request))
        self.assertNotEqual(modified.vols[0].cierre.sis.huella(), plain.vols[0].cierre.sis.huella())
        a = modified._estados(0, modified.inicial(), rapido=False)[modified.vols[0].id]
        b = plain._estados(0, plain.inicial(), rapido=False)[plain.vols[0].id]
        self.assertNotEqual(a.V, b.V)

    def test_reversal_requires_both_donors_and_preserves_explicit_closure(self):
        value = model(flow=-0.001)
        value['corrientes'][0]['extraccion']['B'] = {'tipo': 'mezcla_homogenea'}
        system = compilar(value); y = system.inicial(); rate = system.rhs(0, y)
        # Separate molar accounting: B sends 0.001 mol/s with x=(0.1,0.9).
        np.testing.assert_allclose(rate[system.por_id['A'].i_n], [0.0001, 0.0009], atol=1e-15)
        value['datos']['corriente.s.F']['declaracion']['texto'] = '0.001*cos(t)'
        value['corrientes'][0]['extraccion'].pop('B')
        with self.assertRaises(NoSoportado):
            compilar(value)

    def test_initial_policy_and_closure_failures_have_located_diagnostics(self):
        value = model()
        value['datos']['volumen.A.T0']['declaracion']['texto'] = '10000'
        with self.assertRaises(NoSoportado) as caught:
            compilar(value).inicial()
        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic['initializationStatus'], 'incompatible')
        self.assertEqual(diagnostic['path'], 'volumenes[0].inicial')
        self.assertTrue(diagnostic['nativeCode'].startswith('MOTOR_ENS_INICIAL_'))

    def test_common_bdf_inspection_matches_executed_method_scope(self):
        from core.compilador.report import compilation_report
        value = model(); value['estudio']['metodoSolicitado'] = 'bdf'
        report = compilation_report(value)
        self.assertEqual(report['method'], 'BDF')
        self.assertTrue(next(row['available'] for row in report['strategy']['methods'] if row['id'] == 'BDF'))


if __name__ == '__main__':
    unittest.main()
