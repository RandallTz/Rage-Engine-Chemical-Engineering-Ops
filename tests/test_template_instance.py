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


class ColdReplayCertificationTests(unittest.TestCase):
    """RI-1 and RI-2 (queue item 6 re-review, 7 November 2026)."""

    def test_rebinding_is_checked_against_one_uncached_replay_of_the_instance(self):
        from unittest import mock
        from dataclasses import replace
        import sympy as sp
        from core.mathematics.preparation import enabled
        from core.modelo import template_instance, preparation_cache
        source=marked(flash);real=template_instance.build;cold_calls=[]
        def corrupted(model,*args):
            result=real(model,*args)
            if not enabled() and model['id']!=source['id']:
                cold_calls.append(model['id'])
                key=next(k for k,n in result.graph.nodes.items() if isinstance(n.equation,sp.Equality))
                node=result.graph.nodes[key]
                result.graph.nodes[key]=replace(node,equation=sp.Eq(node.equation.lhs,node.equation.rhs+1,evaluate=False))
            return result
        template_instance._COLD_VERIFIED.clear()
        with mock.patch.object(template_instance,'build',corrupted), \
             mock.patch.object(preparation_cache,'remember_verified_instance') as remember:
            with self.assertRaises(TemplateInstanceError) as raised:instantiate_template(source)
            remember.assert_not_called()
        self.assertTrue(cold_calls)
        # Located at the source equation whose cold replay differs.
        self.assertTrue(raised.exception.diagnostics[0]['path'].startswith('equations.'),raised.exception.diagnostics)
        # A matching cold replay certifies the recipe once; later instances reuse it.
        cold_calls.clear()
        def counted(model,*args):
            if not enabled():cold_calls.append(model['id'])
            return real(model,*args)
        with mock.patch.object(template_instance,'build',counted):
            instantiate_template(source)
            self.assertEqual(len(cold_calls),1)
            instantiate_template(source)
            self.assertEqual(len(cold_calls),1)

    def test_unmapped_boundary_identity_in_a_journal_rejects(self):
        # Only momentum inlet/outlet stream fields are remapped. A schema-valid
        # string elsewhere that equals a boundary identity (here a thermodynamic
        # package reference named like a stream) is ambiguous and is rejected,
        # located and without mutation, before any replay.
        source=marked(flash);stream=source['corrientes'][0]['id']
        owner=source['volumenes'][0]['id'];package=source['termodinamica']['paquetes'][0]['id']
        source['termodinamica']['paquetes'][0]['id']=stream
        for volume in source['volumenes']:
            if volume['termodinamica'].get('paqueteId')==package:volume['termodinamica']['paqueteId']=stream
        source['motores']['thermodynamicDerivation']['volumes'][owner]['operations'][0]['changes']['closure']['packageId']=stream
        before=copy.deepcopy(source)
        with self.assertRaises(TemplateInstanceError) as raised:instantiate_template(source)
        self.assertEqual(source,before)
        self.assertEqual(raised.exception.diagnostics[0]['path'],
                         f'motores.thermodynamicDerivation.volumes.{owner}.operations[0].changes.closure.packageId')


class PublishedEquipmentColdReplayTests(unittest.TestCase):
    """The published Demo 0.2 drum and CSTR instances replay cold to their certified signatures."""

    def test_drum_and_cstr_instances_match_a_cold_replay(self):
        from core.mathematics.preparation import preparation_policy
        from core.mathematics.provenance import equation_signature
        from core.compilador.derived_graph import source_signature
        from core.modelo import preparation_cache, template_instance
        from core.modelo.equation_workbench import build, _known_unit
        root=Path(__file__).resolve().parents[1]/'docs'/'ejemplos'/'demo-0.2'
        for name in ('flash-drum','continuous-reactor'):
            with self.subTest(template=name):
                source=json.loads((root/(name+'.rage-model.json')).read_text(encoding='utf-8'))['model']['commonModel']
                preparation_cache.clear();template_instance._COLD_VERIFIED.clear()
                response=json.loads(json.dumps(instantiate_template(source)))
                preparation_cache.clear()
                target=response['model'];p=response['provenance']
                with preparation_policy(cached=False):
                    replayed=build(target)
                    full=build(target,{**target['motores']['equationWorkbench'],
                                       'cursor':len(target['motores']['equationWorkbench']['operations'])})
                self.assertEqual(p['instanceSignature'],source_signature(target,replayed))
                self.assertEqual({row['instanceId'] for row in p['equationSignatures'].values()},set(full.graph.nodes))
                for old,row in p['equationSignatures'].items():
                    self.assertEqual(row['signature'],equation_signature(full.graph,row['instanceId'],full.units,_known_unit),old)
                if 'derivedExecution' in target['motores']:
                    self.assertEqual(target['motores']['derivedExecution']['sourceSignature'],source_signature(target,replayed))


if __name__=='__main__':unittest.main()
