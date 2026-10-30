"""Semi-explicit DAE admission and an independently referenced physical graph."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_f3_nonlinear_algebraic import thermal_case, reference
from core.compilador.derived import DerivedSystem, LoweringError, resolve_system


def dae_case(owners=('domain_one','domain_two')):
    model, _ = thermal_case(owners)
    model['id'] = 'internal-index1-thermal'
    model['estudio']['metodoSolicitado'] = 'bdf'
    s = model['motores']['derivedExecution']; s['version'] = 4
    def datum(key, value, unit):
        model['datos'][key] = {'magnitud': key, 'funcion': 'parametro',
            'declaracion': {'texto': str(value), 'unidad': unit},
            'origen': {'propietarioId': 'estudio', 'ruta': key}}
        return key
    # Reuse fresh law authoring, but retain caloric temperatures in the block.
    # Given differential inventories are fixed; algebraic guesses are not data.
    for i, owner in enumerate(owners):
        state = s['states'][2*i+1]['quantityId']
        s['initialValues'][state] = datum('dae.energy.'+owner, 36000 if i == 0 else 0, 'J')
        row = next(r for r in s['reconstructions'] if r['equationId'] == 'thermodynamics.'+owner+'.caloric-inventory')
        s['reconstructions'].remove(row); s['algebraic'].append(row)
        del s['initialValues'][row['quantityId']]
        s['nonlinear']['variables'][row['quantityId']] = {key: datum('dae.'+owner+'.'+key, value, 'K') for key, value in
            [('seedDataId', 330), ('lowerDataId', 290), ('upperDataId', 370), ('scaleDataId', 60)]}
        s['nonlinear']['residualScales'][row['equationId']] = 'scale.energy'
    bounds = {}
    for i,row in enumerate(s['states']):
        unit,lo,hi = ('kg',1,4) if i%2==0 else ('J',-9000,63000)
        bounds[row['quantityId']] = {key:datum('dae.state.'+str(i)+'.'+key, value, unit)
                                    for key,value in [('lowerDataId',lo),('upperDataId',hi)]}
    s['dae'] = {'stateBounds': bounds, 'driftTolerance': 1e-9}
    return model


class DAEAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = dae_case()

    def test_thermal_bdf_reference_and_refinement(self):
        metrics=[]
        for factor in (1., .1):
            model=copy.deepcopy(self.model)
            model['estudio']['rtol']*=factor
            model['estudio']['atol']={k:v*factor for k,v in model['estudio']['atol'].items()}
            s=model['motores']['derivedExecution']
            for key in ('residualTolerance','stepTolerance'):s['nonlinear'][key]*=factor
            s['dae']['driftTolerance']*=factor
            system=DerivedSystem(model)
            with patch.object(system.numeric,'rhs',side_effect=AssertionError('Nested closure must supply RHS')):
                result=resolve_system(system)
            self.assertEqual(result['estado'],'resuelto')
            series={r['id']:np.array(r['valores']) for r in result['series']}
            expected=np.array([reference(t) for t in result['ejes'][0]['valores']])
            error=0.
            for i,column in enumerate((0,3,1,2)):
                values=series['observable.'+s['algebraic'][i]['quantityId']]
                error=max(error,float(np.max(abs(values-expected[:,column])))/(240 if i==0 else 60))
            for i,capacity,column in [(1,600,1),(3,900,2)]:
                energy=series['campo.'+s['states'][i]['quantityId']]
                error=max(error,float(np.max(abs(energy-capacity*(expected[:,column]-300))))/36000)
            for i,mass in [(0,2),(2,3)]:
                self.assertLessEqual(float(np.max(abs(series['campo.'+s['states'][i]['quantityId']]-mass)))/mass,1e-6)
            conservation=max(v['valor'] for v in result['verificaciones'] if v['id'].startswith('conservation.'))
            self.assertLessEqual(error,1e-5);self.assertLessEqual(conservation,1e-6)
            evidence=result['procedencia']['daeDiagnostics']
            self.assertGreater(evidence['acceptedChecks'],0)
            self.assertLessEqual(evidence['maxResidual'],s['dae']['driftTolerance'])
            self.assertEqual(system.report['derivedExecution']['dae']['index'],1)
            self.assertEqual(system.report['derivedExecution']['dae']['initialization'],'fixed_differential_states')
            from core.resultados.formato import leer_resultados
            leer_resultados(result)
            metrics.append({'factor':factor,'error':error,'conservation':conservation})
        self.assertLess(metrics[1]['error'],metrics[0]['error'])
        print(json.dumps(metrics),flush=True)

    def test_only_bdf(self):
        model=copy.deepcopy(self.model);model['estudio']['metodoSolicitado']='rk45'
        with self.assertRaises(LoweringError) as caught:DerivedSystem(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'],'dae_method_unsupported')

    def test_initial_and_contract_rejections(self):
        from core.modelo.derived_execution import read_definition
        base=self.model['motores']['derivedExecution']
        for change in (lambda s:s['dae'].update(driftTolerance=1e-8),
                       lambda s:s['dae']['stateBounds'].pop(s['states'][0]['quantityId']),
                       lambda s:s.update(version=3),
                       lambda s:s['dae'].update(freeStates=True)):
            bad=copy.deepcopy(base);change(bad)
            with self.assertRaises(ValueError):read_definition(bad)
        cases=[('dae_initial_states_required',lambda m:m['motores']['derivedExecution']['initialValues'].pop(base['states'][1]['quantityId'])),
               ('dae_bounds_invalid',lambda m:m['datos'][base['dae']['stateBounds'][base['states'][0]['quantityId']]['upperDataId']]['declaracion'].update(texto='0')),
               ('dae_domain',lambda m:m['datos']['dae.energy.domain_one']['declaracion'].update(texto='100000')),
               ('invalid_initialization',lambda m:m['motores']['derivedExecution']['initialValues'].update({base['algebraic'][0]['quantityId']:base['nonlinear']['variables'][base['algebraic'][0]['quantityId']]['seedDataId']}))]
        for code,mutate in cases:
            with self.subTest(code=code):
                bad=copy.deepcopy(self.model);mutate(bad)
                with self.assertRaises(LoweringError) as caught:DerivedSystem(bad)
                d=caught.exception.diagnostics[0];self.assertEqual(d['code'],code)
                self.assertIn('stage',d);self.assertIn('sourceSignature',d)

    def test_drift_and_conservation_retain_checked_prefix(self):
        for code,target in [('dae_constraint_drift','residual'),('dae_conservation_drift','conservation')]:
            with self.subTest(code=code):
                system=DerivedSystem(copy.deepcopy(self.model))
                original=system.dae.accepted
                def check(t,state):
                    if t>=20:
                        if target=='residual':
                            z,_=system.solve_algebraic(t,state);z[0]+=1
                            system.dae.residual(t,state,z)
                        else:
                            changed=state.copy();changed[system.size]+=36000
                            original(t,changed)
                    return original(t,state)
                with patch.object(system.dae,'accepted',side_effect=check):result=resolve_system(system)
                self.assertEqual(result['estado'],'parcial')
                self.assertLess(result['ejes'][0]['valores'][-1],20)
                self.assertEqual(result['procedencia']['nonlinearDiagnostics']['failures'][0]['code'],code)

    def test_fixed_initial_states_and_call_order(self):
        system=DerivedSystem(copy.deepcopy(self.model));state=system.initial()
        np.testing.assert_array_equal(state[:4],[2,36000,3,0])
        z,_=system.solve_algebraic(0,state)
        np.testing.assert_allclose(z,[240,340,360,300],rtol=0,atol=1e-8)
        first=system.rhs(0,state);system.rhs(.01,state+first*.01)
        np.testing.assert_array_equal(system.rhs(0,state),first)

    def test_replayed_derivatives_reject_with_future_option(self):
        from m1_acceptance import SharedAuthor
        from core.compilador.derived import source_signature
        model=copy.deepcopy(self.model);author=SharedAuthor(model)
        author.definition=copy.deepcopy(model['motores']['equationWorkbench']);author.refresh()
        s=model['motores']['derivedExecution']
        key=author.append('differentiate',family='energy',sources=[s['algebraic'][0]['equationId']],symbol=s['timeId'])
        model,replayed,_=author.finish({});s=model['motores']['derivedExecution']
        s['sourceSignature']=source_signature(model,replayed)
        for field in ('algebraic','states'):
            bad=copy.deepcopy(model);selection=bad['motores']['derivedExecution']
            old=selection[field][0]['equationId'];selection[field][0]['equationId']=key
            if field=='algebraic':
                scale=selection['nonlinear']['residualScales'].pop(old)
                selection['nonlinear']['residualScales'][key]=scale
            with self.subTest(field=field):
                with self.assertRaises(LoweringError) as caught:DerivedSystem(bad)
                self.assertEqual(caught.exception.diagnostics[0]['code'],'dae_implicit_unsupported')
                self.assertIn('IDA',str(caught.exception))

    def test_no_valid_publication_is_failed(self):
        from core.solvers import Detencion
        system=DerivedSystem(copy.deepcopy(self.model))
        def fail(t,state):
            try:system.dae.failure('dae_constraint_drift','Injected no-valid-sample failure',t,'publication')
            except Exception as error:
                stop=Detencion(error.code,str(error));stop.diagnostics=error.diagnostics;raise stop
        with patch.object(system,'solve_algebraic',side_effect=fail):result=resolve_system(system)
        self.assertEqual(result['estado'],'fallido');self.assertEqual(result['ejes'][0]['valores'],[])

    def test_publication_conservation_is_checked_separately(self):
        system=DerivedSystem(copy.deepcopy(self.model));original=system.dae.conservation
        def corrupted(t,state,stage='runtime'):
            if stage=='publication' and t>=20:
                state=state.copy();state[system.size]+=36000
            return original(t,state,stage)
        with patch.object(system.dae,'conservation',side_effect=corrupted):result=resolve_system(system)
        self.assertEqual(result['estado'],'parcial')
        self.assertEqual(result['ejes'][0]['valores'][-1],15.)
        failure=result['procedencia']['nonlinearDiagnostics']['failures'][0]
        self.assertEqual(failure['code'],'dae_conservation_drift')
        self.assertEqual(failure['stage'],'publication')

    def test_parameters_units_names_and_permutation(self):
        from test_f3_nonlinear_algebraic import variant_reference
        model=dae_case(('renamed_first','renamed_second'));s=model['motores']['derivedExecution']
        model['datos']['solve.firstConductance']['declaracion']={'texto':'15000','unidad':'mW/K'}
        model['datos']['solve.secondConductance']['declaracion']['texto']='9'
        model['datos']['solve.nonlinearResistance']['declaracion']['texto']='1/40000'
        s['states'].reverse();s['algebraic'].reverse()
        system=DerivedSystem(model);result=resolve_system(system)
        self.assertEqual(result['estado'],'resuelto')
        qid=next(system.ids[q] for q in system.algebraic_quantities if str(q)=='contactHeat(t)')
        actual=next(r['valores'] for r in result['series'] if r['id']=='observable.'+qid)
        expected=[variant_reference(t,600,900,15,9,1/40000,360,300)[0] for t in result['ejes'][0]['valores']]
        self.assertLess(float(np.max(abs(np.array(actual)-expected)))/240,1e-5)

    def test_assessment_separates_missing_states_from_conflict(self):
        from core.compilador.assessment import assess_model
        bad=copy.deepcopy(self.model);s=bad['motores']['derivedExecution']
        del s['initialValues'][s['states'][1]['quantityId']]
        self.assertEqual(assess_model(bad)['initialization']['status'],'pending')
        bad=copy.deepcopy(self.model);bad['datos']['dae.energy.domain_one']['declaracion']['texto']='100000'
        self.assertEqual(assess_model(bad)['initialization']['status'],'incompatible')


class IndexCertificateTests(unittest.TestCase):
    def test_nonthermal_nested_bdf_reference(self):
        from core.solvers import integrar
        from core.solvers.nonlinear import solve
        class System:
            def rhs(self,t,x):
                z,_=solve(lambda z:[z[0]-x[0]**2],lambda z:[[1.]], [1.],[[0.,5.]],[4.],[4.])
                return -z
            def firma(self,t,x):return None
        result=integrar(System(),[2.],2.,rtol=1e-9,atol=1e-11,max_step=.02,metodo='BDF')
        self.assertIsNone(result.detenida)
        for t in np.linspace(0,2,21):self.assertLess(abs(result.y(t)[0]-2/(1+2*t)),1e-7)

    def test_exact_index_and_rejections(self):
        import sympy as sp
        from core.compilador.dae import certify_index
        from core.solvers.nonlinear import NonlinearError
        x,z=sp.symbols('x z');box={x:(sp.S.One,sp.Integer(3)),z:(sp.S.Zero,sp.Integer(10))}
        self.assertEqual(certify_index([z-x*x],[z],box)['index'],1)
        for expression,code in [(x,'dae_index_unsupported'),(z*z-x,'dae_index_not_certified'),
                                (sp.sin(z)-x,'dae_index_not_certified'),
                                (sp.Derivative(sp.Function('q')(x),x)-z,'dae_implicit_unsupported')]:
            with self.subTest(code=code):
                with self.assertRaises(NonlinearError) as caught:certify_index([expression],[z],box)
                self.assertEqual(caught.exception.code,code);self.assertIn('IDA',str(caught.exception))
        with self.assertRaises(NonlinearError) as caught:certify_index([z,z],[z],box)
        self.assertEqual(caught.exception.code,'dae_partition_invalid')

    def test_interval_denominators_and_even_powers(self):
        import sympy as sp
        from core.compilador.dae import interval
        x=sp.Symbol('x');box={x:(sp.Integer(-2),sp.Integer(3))}
        self.assertEqual(interval(x*x,box),(0,9))
        with self.assertRaises(ValueError):interval(1/x,box)


if __name__=='__main__':
    if '--publication' in sys.argv:
        from backend.api_modelo import resolver_modelo
        model=dae_case()
        print(json.dumps({'model':model,'result':resolver_modelo({'modelo':model,'assessmentVersion':1})}))
    else:unittest.main()
