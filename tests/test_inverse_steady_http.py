"""Common HTTP inverse steady publication; consumes the existing law-authoring mixer fixture."""
import asyncio
import copy
import json
from pathlib import Path
import sys
import unittest
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from backend.main import app
from test_f3_inverse_specifications import mixer, specification, series_value
from core.compilador.steady import read_report, read_result

async def request(path,body):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        return await client.post('/modelo/'+path,json=body)

class InverseSteadyHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model,named=mixer();cls.named=staticmethod(named)
        cls.record=specification(cls.model,[('outlet-fraction',named('x3'),.6,'1',.1)],[(named('F1'),1,.01,50,1,'mol/s')])
        cls.body={'modelo':cls.model,'inverseSpecification':cls.record}
        response=asyncio.run(request('resolver',cls.body))
        assert response.status_code==200,response.text
        cls.result=response.json()
        report=asyncio.run(request('compilation',cls.body));assert report.status_code==200,report.text
        cls.report=report.json()
        forward=asyncio.run(request('resolver',{'modelo':cls.model}));assert forward.status_code==200,forward.text
        cls.forward=forward.json()
        out=ROOT/'.tmp/f3-inverse-http';out.mkdir(parents=True,exist_ok=True)
        (out/'publication.json').write_text(json.dumps({'model':cls.model,'record':cls.record,'result':cls.result,'report':cls.report,'forward':cls.forward,'names':{key:named(key) for key in ['F1','F2','F3','x3']}}),encoding='utf-8')

    def test_real_http_mixer_and_roundtrip(self):
        self.assertAlmostEqual(series_value(self.result,self.named('F1')),6,places=11)
        self.assertAlmostEqual(series_value(self.result,self.named('x3')),.6,places=12)
        self.assertAlmostEqual(next(s['valores'] for s in self.result['series'] if s['id']=='steady.residual.specification.outlet-fraction'),0,places=12)
        read_report(self.report);read_result(self.result)
        self.assertEqual(self.report,self.result['procedencia']['compilation'])
        for key in ['selection','sourceSignature','formulationSignature','settingsSignature']:
            self.assertEqual(self.report[key],self.forward['procedencia']['compilation'][key])

    def test_target_only_changes_solve_fingerprints(self):
        body=copy.deepcopy(self.body);body['modelo']['datos'][self.record['specifications'][0]['targetDataId']]['declaracion']['texto']='0.5'
        response=asyncio.run(request('resolver',body));self.assertEqual(response.status_code,200,response.text)
        changed=response.json()['procedencia']['compilation']
        self.assertAlmostEqual(series_value(response.json(),self.named('F1')),3,places=11)
        for key in ['selection','sourceSignature','formulationSignature','settingsSignature']:self.assertEqual(changed[key],self.report[key])
        for key in ['signature','specificationSignature','dataSignature']:self.assertNotEqual(changed[key],self.report[key])

    def test_constant_grammar_variants_publish_over_http(self):
        # F3H-1: Python admits `pi` and unary plus, so the TS readers must read these publications.
        path=ROOT/'.tmp/f3-inverse-http/publication.json';variants={}
        for text in ['pi/6','+0.6']:
            body=copy.deepcopy(self.body);body['modelo']['datos'][self.record['specifications'][0]['targetDataId']]['declaracion']['texto']=text
            response=asyncio.run(request('resolver',body));self.assertEqual(response.status_code,200,response.text)
            report=asyncio.run(request('compilation',body));self.assertEqual(report.status_code,200,report.text)
            variants[text]={'result':response.json(),'report':report.json()}
        publication=json.loads(path.read_text(encoding='utf-8'));publication['variants']=variants
        path.write_text(json.dumps(publication),encoding='utf-8')

    def test_strict_record_and_structured_rejections(self):
        mutations=[lambda b:b['inverseSpecification'].update(version=True),lambda b:b['inverseSpecification'].update(extra=1),lambda b:b['inverseSpecification']['freedInputs'].clear(),lambda b:b['inverseSpecification']['freedInputs'][0].update(quantityId=self.named('x3')),lambda b:b.update(extra=True)]
        for path in ['resolver','compilation']:
            for change in mutations:
                body=copy.deepcopy(self.body);change(body)
                response=asyncio.run(request(path,body));self.assertEqual(response.status_code,422,response.text)
                self.assertIn('detail',response.json())
        body=copy.deepcopy(self.body);body['modelo']['datos'][self.record['specifications'][0]['targetDataId']]['declaracion']['unidad']='kg'
        response=asyncio.run(request('resolver',body));self.assertEqual(response.status_code,422,response.text)
        self.assertTrue(response.json()['detail']['diagnostics'])

    def test_unattainable_target_keeps_reachability_evidence(self):
        body=copy.deepcopy(self.body);body['modelo']['datos'][self.record['specifications'][0]['targetDataId']]['declaracion']['texto']='0.9'
        response=asyncio.run(request('resolver',body));self.assertEqual(response.status_code,422,response.text)
        detail=response.json()['detail'];diagnostic=detail['diagnostics'][0]
        self.assertEqual(diagnostic['code'],'inverse_target_unattainable')
        self.assertEqual(diagnostic['reachability']['kind'],'bound')
        self.assertTrue(diagnostic['path'])
        path=ROOT/'.tmp/f3-inverse-http/publication.json';publication=json.loads(path.read_text(encoding='utf-8'))
        publication['rejection']=response.json();path.write_text(json.dumps(publication),encoding='utf-8')

if __name__=='__main__':unittest.main()
