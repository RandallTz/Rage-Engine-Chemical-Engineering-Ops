"""Replay and numerical equivalence of template test copies; fixtures stay unmarked."""
import copy
import json
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo01_flash import frozen_model as flash
from demo01_reactor import frozen_model as reactor
from test_template_record import cases
from core.modelo.template_instance import instantiate_template, TemplateInstanceError
from core.compilador.derived import DerivedSystem, resolve_system


def marked(factory):
    model=factory()
    model['template']=copy.deepcopy(cases()[0][2]['template'])
    # Demo 0.1 copies exercise general template replay, not complete equipment.
    model['template']['equipment']=False
    if factory is reactor:
        model['template'].update(id='test-reactor',equipment=False,ports=[])
    model['template']['recipe']['journals']=[k for k in model['motores'] if k in
        ('materialDerivation','energyDerivation','thermodynamicDerivation','momentumDerivation','equationWorkbench')]
    return model


class TemplateInstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources=[marked(flash),marked(reactor)]
        cls.responses=[instantiate_template(source) for source in cls.sources]
        output=Path('.tmp/template-instance');output.mkdir(parents=True,exist_ok=True)
        (output/'publication.json').write_text(json.dumps(dict(source=cls.sources[0],response=cls.responses[0])),encoding='utf-8')

    def test_fresh_identity_and_unconnected_boundaries(self):
        source=self.sources[0];before=copy.deepcopy(source);again=instantiate_template(source)
        self.assertEqual(before,source)
        for response in (self.responses[0],again):
            target=response['model'];maps=response['provenance']['identityMap']
            self.assertNotEqual(target['id'],source['id'])
            for key,rows in [('volumes',source['volumenes']),('streams',source['corrientes']),('ports',source['template']['ports'])]:
                self.assertEqual(set(maps[key]),{r['id'] for r in rows})
                self.assertFalse(set(maps[key])&set(maps[key].values()))
            for original,new in zip(source['corrientes'],target['corrientes']):
                for end in ('desde','hasta'):self.assertEqual(new[end],None if original[end] is None else maps['volumes'][original[end]])
            for key,datum in source['datos'].items():self.assertEqual(datum['declaracion'],target['datos'][key]['declaracion'])
            self.assertEqual(target['template']['id'],source['template']['id'])
            self.assertEqual(target['template']['equipment'],source['template']['equipment'])
        self.assertNotEqual(again['model']['id'],self.responses[0]['model']['id'])
        self.assertFalse(set(again['provenance']['identityMap']['volumes'].values())&set(self.responses[0]['provenance']['identityMap']['volumes'].values()))
        self.assertNotIn('template',flash());self.assertNotIn('template',reactor())

    def test_signed_replay_evidence(self):
        for source,response in zip(self.sources,self.responses):
            p=response['provenance'];self.assertTrue(p['equationSignatures'])
            self.assertEqual(set(p['equationSignatures']),set(p['identityMap']['equations']))
            old=source['motores']['equationWorkbench'];new=response['model']['motores']['equationWorkbench']
            self.assertEqual(old['cursor'],new['cursor']);self.assertEqual(len(old['operations']),len(new['operations']))
            self.assertEqual(p,response['model']['procedencia']['templateInstance'])

    def test_stale_and_unsigned_histories_reject_without_mutation(self):
        for unsigned in (False,True):
            source=copy.deepcopy(self.sources[0])
            op=next(op for op in source['motores']['equationWorkbench']['operations'] if op.get('sourceSignatures'))
            if unsigned:op.pop('sourceSignatures')
            else:op['sourceSignatures'][next(iter(op['sourceSignatures']))]='0'*64
            before=copy.deepcopy(source)
            with self.assertRaises(TemplateInstanceError) as raised:instantiate_template(source)
            self.assertEqual(source,before)
            self.assertEqual(raised.exception.diagnostics[0]['path'],'motores.equationWorkbench')

    def test_missing_template_and_invalid_recipe_reject(self):
        with self.assertRaises(TemplateInstanceError) as raised:instantiate_template(flash())
        self.assertEqual(raised.exception.diagnostics[0]['path'],'template')
        source=copy.deepcopy(self.sources[0]);source['template']['recipe']['journals']=['absent']
        with self.assertRaises(TemplateInstanceError):instantiate_template(source)
        source=copy.deepcopy(self.sources[0]);source['motores']['energyDerivation']=None
        with self.assertRaises(TemplateInstanceError) as raised:instantiate_template(source)
        self.assertEqual(raised.exception.diagnostics[0]['path'],'motores.energyDerivation')

    def test_full_demo_results_are_equivalent(self):
        for source,response in zip(self.sources,self.responses):
            with self.subTest(model=source['id']):
                before=resolve_system(DerivedSystem(source));after=resolve_system(DerivedSystem(response['model']))
                self.assertEqual(before['estado'],after['estado']);self.assertEqual(before['estado'],'resuelto')
                np.testing.assert_allclose(before['ejes'][0]['valores'],after['ejes'][0]['valores'],rtol=1e-12,atol=1e-12)
                maps=response['provenance']['identityMap'];renames={**maps['quantities'],**maps['volumes'],**maps['streams'],**maps['exchanges']}
                def renamed(key):
                    for old,new in sorted(renames.items(),key=lambda pair:-len(pair[0])):key=key.replace(old,new)
                    return key
                values={row['id']:row for row in after['series']}
                self.assertEqual({renamed(row['id']) for row in before['series']},set(values))
                for row in before['series']:
                    np.testing.assert_allclose(row['valores'],values[renamed(row['id'])]['valores'],rtol=2e-8,atol=1e-7,err_msg=row['id'])

    def test_http_protocol_and_located_rejection(self):
        import asyncio
        import httpx
        from backend.main import app
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                good=await client.post('/modelo/template-instance',json=dict(format='rage.template-instance.request',version=1,model=self.sources[0]))
                self.assertEqual(good.status_code,200,good.text);self.assertEqual(good.json()['format'],'rage.template-instance.response')
                for body in ({},dict(format='rage.template-instance.request',version=True,model=self.sources[0]),dict(format='rage.template-instance.request',version=1,model=flash())):
                    bad=await client.post('/modelo/template-instance',json=body)
                    self.assertEqual(bad.status_code,422);self.assertTrue(bad.json()['detail']['diagnostics'][0]['path'])
        asyncio.run(check())


if __name__=='__main__':unittest.main()
