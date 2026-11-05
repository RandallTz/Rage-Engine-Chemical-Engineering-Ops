"""Indexed stage contract and deterministic replay, without network solving."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.modelo.lector import leer_modelo_comun, ErrorModelo
from core.modelo.index_sets import expand_index_set
from core.modelo.template_instance import TemplateInstanceError


def source_model():
    source = json.loads(Path('docs/ejemplos/demo-0.2/flash-drum.rage-model.json').read_text(encoding='utf-8'))['model']['commonModel']
    model = copy.deepcopy(source)
    model['id'] = 'indexed-stage-test'
    model['datos']['solve.stageCount'] = {'magnitud': 'stageCount', 'funcion': 'estudio', 'declaracion': {'texto': '3', 'unidad': '1'}, 'origen': {'propietarioId': 'estudio', 'ruta': 'stageCount'}}
    model['indexSet'] = {'format': 'rage.index-set', 'version': 1, 'id': 'cascade', 'index': 'j', 'countDataId': 'solve.stageCount',
        'templates': {'generic': source}, 'genericStage': 'generic', 'variants': [],
        'connections': [{'outlet': 'liquid', 'inlet': 'feed', 'offset': 1}],
        'exposures': [{'id': 'feed', 'port': 'feed', 'at': 'first'}, {'id': 'liquid', 'port': 'liquid', 'at': 'last'},
            {'id': 'vapour', 'port': 'vapour', 'at': 'each'}, {'id': 'heat', 'port': 'heat', 'at': 'each'}]}
    return model


class IndexSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = source_model()
        cls.expanded = expand_index_set(cls.model)
        out = Path('.tmp/index-sets'); out.mkdir(exist_ok=True, parents=True)
        (out/'publication.json').write_text(json.dumps({'source': cls.model, 'expanded': cls.expanded}), encoding='utf-8')

    def test_three_replayed_stages_and_connections(self):
        result = self.expanded
        self.assertEqual(result['count'], 3)
        self.assertEqual(len(result['internalStreams']), 2)
        self.assertEqual(len(result['ports']), 8)
        identities = set()
        for stage in result['stages']:
            leer_modelo_comun(stage['model'])
            ids = {stage['model']['id'], *(v['id'] for v in stage['model']['volumenes']), *(s['id'] for s in stage['model']['corrientes'])}
            self.assertFalse(ids & identities); identities |= ids
            self.assertTrue(stage['provenance']['equationSignatures'])
            self.assertEqual(stage['model']['template']['recipe'], self.model['indexSet']['templates']['generic']['template']['recipe'])
        for row in result['internalStreams']:
            self.assertIsNotNone(row['stream']['desde']); self.assertIsNotNone(row['stream']['hasta'])
            self.assertNotIn('estadoExterior', row['stream'])
        self.assertEqual(result['execution'], 'not_lowered')

    def test_idempotence_and_resize_without_deduction(self):
        before = copy.deepcopy(self.model)
        self.assertEqual(self.expanded, expand_index_set(self.model))
        self.assertEqual(self.model, before)
        changed = copy.deepcopy(self.model); changed['datos']['solve.stageCount']['declaracion']['texto'] = '2'
        resized = expand_index_set(changed)
        self.assertEqual(resized['stages'], self.expanded['stages'][:2])
        self.assertEqual(len(resized['internalStreams']), 1)
        self.assertEqual(len(resized['ports']), 6)

    def test_strict_rejections_shared_with_typescript(self):
        cases = []
        def case(name, mutate):
            model = copy.deepcopy(self.model); mutate(model); cases.append({'name': name, 'model': model})
        case('unknown field', lambda m: m['indexSet'].update(extra=True))
        case('version', lambda m: m['indexSet'].update(version=2))
        case('missing template', lambda m: m['indexSet'].update(genericStage='absent'))
        case('unmarked template', lambda m: m['indexSet']['templates']['generic']['template'].update(equipment=False))
        case('missing outlet', lambda m: m['indexSet']['connections'][0].update(outlet='absent'))
        case('wrong direction', lambda m: m['indexSet']['connections'][0].update(outlet='feed'))
        case('wrong kind', lambda m: m['indexSet']['connections'][0].update(inlet='heat'))
        case('fractional n', lambda m: m['datos']['solve.stageCount']['declaracion'].update(texto='2.5'))
        case('zero n', lambda m: m['datos']['solve.stageCount']['declaracion'].update(texto='0'))
        case('negative n', lambda m: m['datos']['solve.stageCount']['declaracion'].update(texto='-1'))
        case('n units', lambda m: m['datos']['solve.stageCount']['declaracion'].update(unidad='s'))
        case('unbound port', lambda m: m['indexSet']['exposures'].pop())
        case('duplicate binding', lambda m: m['indexSet']['exposures'].append(copy.deepcopy(m['indexSet']['exposures'][0])))
        case('unknown rule field', lambda m: m['indexSet']['connections'][0].update(extra=True))
        case('wrong offset', lambda m: m['indexSet']['connections'][0].update(offset=0))
        case('missing variant template', lambda m: m['indexSet']['variants'].append({'at': 'first', 'template': 'absent'}))
        case('overlapping variants', lambda m: m['indexSet']['variants'].extend([{'at': 'first', 'template': 'generic'}, {'at': 1, 'template': 'generic'}]))
        case('unknown exposure port', lambda m: m['indexSet']['exposures'][0].update(port='absent'))
        case('bad exposure index', lambda m: m['indexSet']['exposures'][0].update(at=4))
        case('worksheet template mismatch', lambda m: m['template'].update(id='unrelated'))
        case('worksheet defaults mismatch', lambda m: m['datos']['solve.tf']['declaracion'].update(texto='999'))
        for row in cases:
            with self.subTest(row['name']), self.assertRaises(ErrorModelo): leer_modelo_comun(row['model'])
        Path('.tmp/index-sets/rejections.json').write_text(json.dumps(cases), encoding='utf-8')

    def test_variant_and_singleton(self):
        model = copy.deepcopy(self.model)
        model['indexSet']['templates']['boundary'] = copy.deepcopy(model['indexSet']['templates']['generic'])
        model['indexSet']['templates']['boundary']['template']['id'] = 'boundary-stage'
        model['indexSet']['variants'] = [{'at': 'first', 'template': 'boundary'}]
        leer_modelo_comun(model)
        model['datos']['solve.stageCount']['declaracion']['texto'] = '1'
        leer_modelo_comun(model)

    def test_stale_recipe_rejects_with_location(self):
        model = copy.deepcopy(self.model)
        operations = model['indexSet']['templates']['generic']['motores']['equationWorkbench']['operations']
        signed = next(op for op in operations if op.get('sourceSignatures'))
        key = next(iter(signed['sourceSignatures'])); signed['sourceSignatures'][key] = '0' * 64
        model['motores'] = copy.deepcopy(model['indexSet']['templates']['generic']['motores'])
        with self.assertRaises(TemplateInstanceError) as caught: expand_index_set(model)
        self.assertTrue(caught.exception.diagnostics[0]['path'])

    def test_http_rejects_execution(self):
        from backend.api_modelo import resolver_modelo, describe_compilation, model_assessment, steady_transform
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as caught: resolver_modelo({'modelo': self.model})
        self.assertEqual(caught.exception.detail['diagnostics'][0]['code'], 'index_set_not_lowered')
        for route, request in [
            (describe_compilation, {'modelo': self.model}),
            (model_assessment, {'format': 'rage.model-assessment.request', 'version': 1, 'model': self.model}),
            (steady_transform, {'format': 'rage.steady-transform.request', 'version': 1, 'model': self.model}),
        ]:
            with self.subTest(route=route.__name__), self.assertRaises(HTTPException) as rejected:
                route(request)
            self.assertEqual(rejected.exception.status_code, 422)


if __name__ == '__main__': unittest.main()
