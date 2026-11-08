"""Zero-accumulation orchestration over the existing F3 physical fixture."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_f3_steady_state import thermal_case, analytic_reference
from core.modelo.steady_transform import prepare_steady_transform
from core.compilador.steady import SteadySystem
from core.compilador.derived import LoweringError


def dynamic_thermal():
    model = thermal_case()
    selection = model['motores']['derivedExecution']
    initial = {**selection['invariants'], **{r['quantityId']: selection['nonlinear']['variables'][r['quantityId']]['seedDataId']
        for r in selection['states'] if r['quantityId'] not in selection['invariants']}}
    caloric = [r for r in selection['algebraic'] if r['equationId'].endswith('.caloric-inventory')]
    selection['reconstructions'].extend(caloric)
    selection['algebraic'] = [r for r in selection['algebraic'] if r not in caloric]
    selection.update(version=3, initialValues=initial, initialEquations=[])
    selection.pop('unknowns'); selection.pop('invariants')
    ids = {r['quantityId'] for r in selection['algebraic']}; rows = {r['equationId'] for r in selection['algebraic']}
    selection['nonlinear']['variables'] = {k:v for k,v in selection['nonlinear']['variables'].items() if k in ids}
    selection['nonlinear']['residualScales'] = {k:v for k,v in selection['nonlinear']['residualScales'].items() if k in rows}
    model['datos']['check.firstLaw']['declaracion']['unidad']='J'
    model['datos']['transform.duration'] = {'magnitud':'time','funcion':'estudio','declaracion':{'texto':'1','unidad':'s'},'origen':{'propietarioId':'estudio','ruta':'time'}}
    model['estudio'] = {'tipo':'temporal','tiempoId':'transform.duration','metodoSolicitado':'rk45','muestras':3,'rtol':1e-6,'atol':{'cantidad':1e-8,'energia':1e-6}}
    return model


class SteadyTransformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = dynamic_thermal()
        cls.response = prepare_steady_transform(cls.source)

    def test_preserves_dynamic_source_and_data(self):
        before = copy.deepcopy(self.source)
        out = self.response['model']; selected = out['motores']['derivedExecution']
        self.assertEqual(selected['version'], 5)
        for key in ('states','parameters','algebraic','reconstructions'):
            self.assertEqual(selected[key], before['motores']['derivedExecution'][key])
        for key, datum in before['datos'].items(): self.assertEqual(out['datos'][key], datum)
        self.assertEqual(self.source, before)

    def test_invariants_seeds_and_handoff(self):
        selected = self.response['model']['motores']['derivedExecution']
        self.assertEqual(len(selected['invariants']), 2)
        for row in selected['states']:
            qid = row['quantityId']
            if qid not in selected['invariants']:
                self.assertEqual(selected['nonlinear']['variables'][qid]['seedDataId'], self.source['motores']['derivedExecution']['initialValues'][qid])
        self.assertEqual(sum(row['identity'] for row in self.response['report']['rows']), 2)
        self.assertTrue(all(row['before'] and row['after'] for row in self.response['report']['rows']))

    def test_same_steady_reference(self):
        system = SteadySystem(self.response['model'])
        result = system.solve()
        actual = {row['id']:row['valores'] for row in result['series']}
        for name, value in analytic_reference(self.source).items():
            qid = next(key for key, quantity in system.quantities.items() if str(quantity)==name)
            self.assertAlmostEqual(actual['steady.'+qid], value, delta=1e-6)
        directory=Path(__file__).resolve().parents[1]/'.tmp/steady-transform'
        directory.mkdir(parents=True,exist_ok=True)
        (directory/'publication.json').write_text(json.dumps({'source':self.source,'response':self.response}),encoding='utf-8')

    def test_no_retransform_or_stale_fallback(self):
        with self.assertRaises(LoweringError): prepare_steady_transform(self.response['model'])
        bad=copy.deepcopy(self.source);bad['motores']['derivedExecution']['sourceSignature']='0'*64
        with self.assertRaises(LoweringError): prepare_steady_transform(bad)

    def test_reapplication_reuses_generated_data(self):
        source=copy.deepcopy(self.source)
        source['datos']=copy.deepcopy(self.response['model']['datos'])
        again=prepare_steady_transform(source)
        self.assertEqual(again['model']['datos'],self.response['model']['datos'])

    def test_package_drums_solve_with_model_defaults(self):
        from demo01_flash import frozen_model
        from demo02_drum import frozen_model as equipment_model
        from core.compilador.steady import read_result
        for name,source in [('package',frozen_model()),('equipment',equipment_model())]:
            with self.subTest(model=name):
                response=prepare_steady_transform(source)
                system=SteadySystem(response['model']);result=system.solve();read_result(result)
                self.assertEqual(result['estado'],'resuelto')
                closure=system.closures.closures[0]
                temperature_id=next(k for k,q in system.quantities.items() if q==closure.T)
                actual=next(row['valores'] for row in result['series'] if row['id']=='closure.'+temperature_id)
                # Independently established long-time dynamic/package reference,
                # shared by both withdrawal models (their holdups differ).
                self.assertAlmostEqual(actual,362.5404885146,delta=1e-5)
                for variable in response['report']['variables']:
                    if variable['unit']=='kg':self.assertGreater(variable['boundsSI'][0],0)
                repeated=copy.deepcopy(source);repeated['datos']=response['model']['datos']
                again=prepare_steady_transform(repeated)
                self.assertEqual(again['model']['datos'],response['model']['datos'])
                output=Path('.tmp/steady-transform');output.mkdir(parents=True,exist_ok=True)
                (output/(name+'.json')).write_text(json.dumps(dict(source=source,response=response,result=result)),encoding='utf-8')

    def test_defaults_do_not_depend_on_unrelated_data_or_initial_holdup(self):
        from demo01_flash import frozen_model
        from core.compilador.steady import read_result
        base = frozen_model()
        reference = prepare_steady_transform(base)

        def scales(response):
            return {k: v['declaracion']['texto'] for k, v in response['model']['datos'].items() if k.endswith('.residualScale') or k.endswith('.checkScale')}
        # RT-6: unused data of the residual dimensions never set a scale.
        padded = copy.deepcopy(base)
        for key, text, unit in [('unused.flow', '1e6', 'kg/s'), ('unused.power', '1e12', 'W')]:
            padded['datos'][key] = {'magnitud': key, 'funcion': 'estudio',
                'declaracion': {'texto': text, 'unidad': unit}, 'origen': {'propietarioId': 'estudio', 'ruta': key}}
        self.assertEqual(scales(prepare_steady_transform(padded)), scales(reference))
        # RT-7: the root does not depend on the initial holdup.
        for first, second in [('1.0', '4.0'), ('0.001', '0.004')]:
            with self.subTest(holdups=(first, second)):
                light = copy.deepcopy(base)
                light['datos']['drum.mass']['declaracion']['texto'] = first
                light['datos']['drum.mass2']['declaracion']['texto'] = second
                response = prepare_steady_transform(light)
                system = SteadySystem(response['model']); result = system.solve(); read_result(result)
                self.assertEqual(result['estado'], 'resuelto')
                closure = system.closures.closures[0]
                temperature_id = next(k for k, q in system.quantities.items() if q == closure.T)
                actual = next(row['valores'] for row in result['series'] if row['id'] == 'closure.' + temperature_id)
                self.assertAlmostEqual(actual, 362.5404885146, delta=1e-5)

    def test_http_rejection_is_preserved(self):
        from backend.api_modelo import steady_transform
        from fastapi import HTTPException
        from demo01_reactor import frozen_model
        with self.assertRaises(HTTPException) as caught:
            steady_transform({'format':'rage.steady-transform.request','version':1,'model':frozen_model()})
        self.assertEqual(caught.exception.status_code,422)
        self.assertTrue(caught.exception.detail['diagnostics'])
        print('Demo reactor rejection:',json.dumps(caught.exception.detail))
        with self.assertRaises(HTTPException): steady_transform({'format':'rage.steady-transform.request','version':2,'model':self.source})


if __name__=='__main__': unittest.main()
