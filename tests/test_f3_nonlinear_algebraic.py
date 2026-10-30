"""Fresh physical journals and independent implicit analytic F3 reference."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from m1_acceptance import thermal_source, SharedAuthor
from core.compilador.derived import DerivedSystem, LoweringError, source_signature, resolve_system
from core.mathematics.dimensions import catalog


def thermal_case(owners=('domain_one','domain_two')):
    model = thermal_source(owners)
    model.update(id='internal-nonlinear-acceptance', nombre='Internal nonlinear contact acceptance')
    for owner in owners:
        model['datos'][owner+'.capacity']['declaracion']['texto']='300'
    author = SharedAuthor(model)
    q = author.quantity
    t = sp.Symbol('t', real=True)
    def append(kind, **fields):
        return author.append(kind, family='energy', **fields)
    append('declare_function', name='contactHeat', unit='W', dependencies=[q(t)])
    append('declare_function', name='contactTemperature', unit='K', dependencies=[q(t)])
    for name, unit in [('firstConductance','W/K'),('secondConductance','W/K'),('nonlinearResistance','W^-2')]:
        append('declare_symbol', name=name, unit=unit)
    temperatures=[sp.Function('T__'+o)(t) for o in owners]
    first=append('declare_relation',left='contactHeat',right=f'firstConductance*({q(temperatures[0])}-contactTemperature)',
                 relationKind='constitutive',reason='Declared passive linear contact; no interface storage')
    second=append('declare_relation',left='contactHeat+nonlinearResistance*contactHeat^3',right=f'secondConductance*(contactTemperature-{q(temperatures[1])})',
                  relationKind='constitutive',reason='Declared monotone nonlinear contact resistance; not a conservation law')
    for name in ('firstConductance','secondConductance'):
        append('declare_domain',sources=[first if name=='firstConductance' else second],symbol=name,domain='positive',reason='Positive passive conductance')
    append('declare_domain',sources=[second],symbol='nonlinearResistance',domain='nonnegative',reason='Monotone passive resistance')
    energy_rows=[]
    for owner, sign in zip(owners,('-', '')):
        heat=sp.Function('energy_heat_rate__'+owner)(t)
        energy=sp.Function('U__'+owner)(t)
        boundary=append('declare_relation',left=q(heat),right=sign+'contactHeat',relationKind='constraint',
                        reason='Only heat transfer; equal and opposite across an interface without storage')
        balance=next(key for key in author.selected if key.startswith('energy.'+owner+'.') and author.source.nodes[key].equation.lhs==sp.diff(energy,t))
        energy_rows.append(author.substitute(balance,boundary,heat,family='energy'))
        caloric='thermodynamics.'+owner+'.caloric-inventory'
        for expr in [sp.Function('m__'+owner+'__1')(t),sp.Symbol('caloric_capacity__'+owner, real=True)]:
            author.append('declare_domain',family='thermodynamics',sources=[caloric],symbol=q(expr),domain='positive',reason='Positive caloric inventory')
        author.append('declare_domain',family='thermodynamics',sources=[caloric],symbol=q(sp.Function('T__'+owner)(t)),domain='interval',lower='290',upper='370',lowerOpen=False,upperOpen=False,endpointUnit='K',reason='Declared caloric interval')
    total=append('combine',sources=energy_rows)
    model,replayed,_=author.finish({})
    def named(name):
        return next(key for key,value in {**catalog(replayed.graph,replayed.units),**replayed.introduced}.items() if str(value)==name)
    def datum(key,value,unit,role='parametro'):
        model['datos'][key]={'magnitud':key,'funcion':role,'declaracion':{'texto':str(value),'unidad':unit},'origen':{'propietarioId':'estudio','ruta':key}}
        return key
    selection={'format':'rage.derived-execution','version':3,'sourceSignature':source_signature(model,replayed),'timeId':named('t'),
               'states':[],'parameters':{},'initialValues':{},'initialEquations':[],'reconstructions':[],
               'checks':[{'equationId':total,'scaleDataId':datum('scale.energy',36000,'J')}],
               'algebraic':[{'quantityId':named('contactHeat(t)'),'equationId':first},{'quantityId':named('contactTemperature(t)'),'equationId':second}]}
    for owner,energy_row in zip(owners,energy_rows):
        mass=sp.Function('m__'+owner+'__1')(t)
        mass_row=next(key for key in reversed(replayed.selected) if isinstance(replayed.graph.nodes[key].equation,sp.Equality) and replayed.graph.nodes[key].equation.lhs==sp.diff(mass,t))
        selection['states'].extend([{'quantityId':named(str(mass)),'equationId':mass_row},{'quantityId':named('U__'+owner+'(t)'),'equationId':energy_row}])
        selection['initialValues'].update({named(str(mass)):owner+'.mass',named('T__'+owner+'(t)'):owner+'.temperature'})
        caloric='thermodynamics.'+owner+'.caloric-inventory'
        selection['initialEquations'].append(caloric)
        selection['reconstructions'].extend([{'quantityId':named('T__'+owner+'(t)'),'equationId':caloric},
            {'quantityId':named('m_total__'+owner+'(t)'),'equationId':'matter.'+owner+'.total-definition'}])
        for field,data in [('caloric_capacity','capacity'),('T_reference','referenceTemperature'),('u_reference','referenceEnergy')]:
            selection['parameters'][named(field+'__'+owner)]=owner+'.'+data
    for name,value,unit in [('firstConductance',12,'W/K'),('secondConductance',12,'W/K'),('nonlinearResistance','1/57600','W^-2')]:
        selection['parameters'][named(name)]=datum('solve.'+name,value,unit)
    variables={}
    for name,seed,lower,upper,scale,unit in [('contactHeat(t)',100,0,300,240,'W'),('contactTemperature(t)',330,290,370,60,'K')]:
        variables[named(name)]={key:datum('nonlinear.'+name+'.'+key,value,unit) for key,value in [('seedDataId',seed),('lowerDataId',lower),('upperDataId',upper),('scaleDataId',scale)]}
    selection['nonlinear']={'variables':variables,'residualScales':{key:datum('residual.'+key,240,'W') for key in (first,second)},
                            'residualTolerance':1e-10,'stepTolerance':1e-12,'maxIterations':30,'maxBacktracks':20}
    model['motores']['derivedExecution']=selection
    model['estudio']={'tipo':'temporal','tiempoId':datum('solve.horizon',300,'s','estudio'),'metodoSolicitado':'rk45','muestras':61,'rtol':1e-8,'atol':{'cantidad':1e-10,'energia':1e-6}}
    return model,author


def reference(t):
    lo,hi=0.,240.
    for _ in range(100):
        q=(lo+hi)/2
        if 60*math.log(240/q)+(57600-q*q)/1280 > t: lo=q
        else: hi=q
    q=(lo+hi)/2;delta=q/6+q**3/691200
    return q,324+.6*delta,324-.4*delta,324+.6*delta-q/12


def variant_reference(t, c1, c2, g1, g2, a, initial1, initial2):
    """Conservation plus scalar quadrature inversion, independent of Newton."""
    sign=1 if initial1>=initial2 else -1
    difference=abs(initial1-initial2); r=1/g1+1/g2; b=a/g2; s=1/c1+1/c2
    lo,hi=0.,difference/r
    for _ in range(100):
        q=(lo+hi)/2
        if r*q+b*q**3<difference: lo=q
        else: hi=q
    q0=(lo+hi)/2
    lo,hi=0.,q0
    for _ in range(100):
        q=(lo+hi)/2
        elapsed=r/s*math.log(q0/q)+3*b/(2*s)*(q0*q0-q*q)
        if elapsed>t: lo=q
        else: hi=q
    q=sign*(lo+hi)/2;delta=r*q+b*q**3
    equilibrium=(c1*initial1+c2*initial2)/(c1+c2)
    first=equilibrium+c2/(c1+c2)*delta
    return q,first,equilibrium-c1/(c1+c2)*delta,first-q/g1


class NonlinearAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'tests/reference_data').glob('m1-?.json')}
        cls.model,cls.author=thermal_case()
        Path('.tmp/f3-nonlinear/model.json').write_text(json.dumps(cls.model,indent=2),encoding='utf-8')
        cls.system=DerivedSystem(cls.model)

    @classmethod
    def tearDownClass(cls):
        for p,digest in cls.hashes.items(): assert hashlib.sha256(p.read_bytes()).hexdigest()==digest

    def test_both_integrators_reference_and_refinement(self):
        metrics=[]
        for method in ('RK45','BDF'):
            for factor in (1.,.1):
                model=copy.deepcopy(self.model)
                model['estudio'].update(metodoSolicitado=method.lower(),rtol=1e-8*factor)
                model['estudio']['atol']={'cantidad':1e-10*factor,'energia':1e-6*factor}
                model['motores']['derivedExecution']['nonlinear'].update(residualTolerance=1e-10*factor,stepTolerance=1e-12*factor)
                system=DerivedSystem(model)
                with patch.object(system.numeric,'rhs',side_effect=AssertionError('Forbidden reduced RHS')):
                    result=resolve_system(system)
                self.assertEqual(result['estado'],'resuelto')
                times=result['ejes'][0]['valores']; rows={s['id']:s['valores'] for s in result['series']}
                expected=np.array([reference(t) for t in times])
                actual=np.array([rows['observable.'+r['quantityId']] for r in system.algebraic_rows]).T
                error=max(np.max(abs(actual[:,0]-expected[:,0]))/240,np.max(abs(actual[:,1]-expected[:,3]))/60)
                for owner,column in [('domain_one',1),('domain_two',2)]:
                    row=next(r for r in system.selection['reconstructions'] if str(system._quantity(r['quantityId']))=='T__'+owner+'(t)')
                    error=max(error,np.max(abs(np.array(rows['observable.'+row['quantityId']])-expected[:,column]))/60)
                conservation=max(v['valor'] for v in result['verificaciones'] if v['id'].startswith('conservation.'))
                self.assertLessEqual(error,1e-5);self.assertLessEqual(conservation,1e-6)
                self.assertGreater(system.algebraic_block.calls,61)
                metrics.append(dict(method=method,factor=factor,error=float(error),conservation=conservation))
                Path('.tmp/f3-nonlinear/result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
                from core.resultados.formato import leer_resultados
                leer_resultados(result)
            self.assertLess(metrics[-1]['error'],metrics[-2]['error'])
        print(json.dumps(metrics),flush=True)
        Path('.tmp/f3-nonlinear/metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')

    def test_initialization_conflict_and_old_versions(self):
        bad=copy.deepcopy(self.model);s=bad['motores']['derivedExecution']
        s['initialValues'][s['algebraic'][0]['quantityId']]=s['nonlinear']['variables'][s['algebraic'][0]['quantityId']]['seedDataId']
        with self.assertRaises(LoweringError) as caught: DerivedSystem(bad)
        self.assertEqual(caught.exception.diagnostics[0]['code'],'invalid_initialization')
        bad=copy.deepcopy(self.model);s=bad['motores']['derivedExecution'];s['version']=2;del s['nonlinear']
        with self.assertRaises(LoweringError) as caught: DerivedSystem(bad)
        self.assertEqual(caught.exception.diagnostics[0]['code'],'nonlinear_algebraic_block')

    def test_deterministic_rejected_stage_order(self):
        system=self.system;initial=system.initial()
        first=system.rhs(0,initial)
        system.rhs(.3,initial+first*.3)
        np.testing.assert_array_equal(system.rhs(0,initial),first)
        from core.solvers import Detencion
        outside=initial.copy();outside[1]=600*80  # 380 K exceeds the declared 370 K bound.
        with self.assertRaises(Detencion) as caught:system.rhs(1,outside)
        self.assertEqual(caught.exception.codigo,'nonlinear_domain')
        self.assertEqual(caught.exception.diagnostics[0]['stage'],'runtime')
        np.testing.assert_array_equal(system.rhs(0,initial),first)

    def test_model_admission_rejections_are_located(self):
        def change_data(model,key,text,unit=None):
            model['datos'][key]['declaracion']['texto']=str(text)
            if unit: model['datos'][key]['declaracion']['unidad']=unit
        cases=[]
        seed=self.model['motores']['derivedExecution']['nonlinear']['variables']
        qid=self.model['motores']['derivedExecution']['algebraic'][0]['quantityId']
        cases.extend([
            ('nonlinear_invalid_seed',lambda m:change_data(m,seed[qid]['seedDataId'],-1)),
            ('nonlinear_invalid_settings',lambda m:change_data(m,seed[qid]['scaleDataId'],0)),
            ('invalid_data',lambda m:change_data(m,seed[qid]['scaleDataId'],240,'K')),
            ('nonlinear_iteration_limit',lambda m:m['motores']['derivedExecution']['nonlinear'].update(maxIterations=1)),
            ('nonlinear_stagnation',lambda m:m['motores']['derivedExecution']['nonlinear'].update(stepTolerance=100)),
            ('stale_formulation',lambda m:m['motores']['equationWorkbench'].update(cursor=m['motores']['equationWorkbench']['cursor']-1)),
            ('invalid_derived_formulation',lambda m:m['motores']['derivedExecution']['algebraic'].pop()),
            ('invalid_derived_formulation',lambda m:m['motores']['derivedExecution']['algebraic'].append(copy.deepcopy(m['motores']['derivedExecution']['algebraic'][0]))),
        ])
        for code,mutate in cases:
            with self.subTest(code=code):
                model=copy.deepcopy(self.model);mutate(model)
                with self.assertRaises(LoweringError) as caught: DerivedSystem(model)
                diagnostic=caught.exception.diagnostics[0]
                self.assertEqual(diagnostic['code'],code)
                self.assertIn('path',diagnostic);self.assertIn('stage',diagnostic)

    def test_units_permutation_seeds_and_affine_state_dependence(self):
        model=copy.deepcopy(self.model);selection=model['motores']['derivedExecution']
        selection['algebraic'].reverse();selection['states'].reverse()
        model['datos']['solve.firstConductance']['declaracion']={'texto':'12000','unidad':'mW/K'}
        qid=selection['algebraic'][1]['quantityId']
        model['datos'][selection['nonlinear']['variables'][qid]['seedDataId']]['declaracion']['texto']='200'
        system=DerivedSystem(model);z,_=system.solve_algebraic(0,system.initial())
        np.testing.assert_allclose(z,[340,240],rtol=0,atol=1e-8)
        # A state-dependent coefficient remains rejected by the unchanged v2 gate.
        from core.mathematics.linear_system import ConstantAffineBlock,AffineBlockError
        x,z,y=sp.symbols('x z y')
        with self.assertRaises(AffineBlockError) as caught: ConstantAffineBlock([y*x+z,x-z],[x,z],{})
        self.assertEqual(caught.exception.code,'nonconstant_algebraic_matrix')

    def test_runtime_failure_retains_published_prefix(self):
        from core.solvers import Detencion
        from core.solvers.nonlinear import NonlinearError
        system=DerivedSystem(copy.deepcopy(self.model))
        original=system.algebraic_block.evaluate
        def failing(t,state,stage='runtime'):
            if t>=20:
                error=NonlinearError('nonlinear_iteration_limit','Injected late closure failure',**system.algebraic_block.location(t,stage))
                error.diagnostics=[error.diagnostic];raise error
            return original(t,state,stage)
        with patch.object(system.algebraic_block,'evaluate',side_effect=failing): result=resolve_system(system)
        self.assertEqual(result['estado'],'parcial')
        self.assertGreater(result['ejes'][0]['valores'][-1],0)
        self.assertLessEqual(result['ejes'][0]['valores'][-1],20)
        self.assertEqual(result['procedencia']['nonlinearDiagnostics']['failures'][0]['code'],'nonlinear_iteration_limit')
        from core.resultados.formato import leer_resultados
        leer_resultados(result)

    def test_parameter_perturbation_affine_limit_reversal_and_renaming(self):
        renamed,_=thermal_case(('arbitrary_alpha','arbitrary_beta'))
        for model,owners,capacity,g1,g2,a,temperatures in [
            (copy.deepcopy(self.model),('domain_one','domain_two'),400,15,9,1/40000,(350,310)),
            (renamed,('arbitrary_alpha','arbitrary_beta'),300,12,12,0,(300,360)),
        ]:
            for key,value in [('firstConductance',g1),('secondConductance',g2),('nonlinearResistance',a)]:
                model['datos']['solve.'+key]['declaracion']['texto']=str(value)
            model['datos'][owners[0]+'.capacity']['declaracion']['texto']=str(capacity)
            for owner,temp in zip(owners,temperatures):model['datos'][owner+'.temperature']['declaracion']['texto']=str(temp)
            selection=model['motores']['derivedExecution'];qid=selection['algebraic'][0]['quantityId']
            settings=selection['nonlinear']['variables'][qid]
            model['datos'][settings['lowerDataId']]['declaracion']['texto']='-500'
            model['datos'][settings['upperDataId']]['declaracion']['texto']='500'
            system=DerivedSystem(model);result=resolve_system(system)
            self.assertEqual(result['estado'],'resuelto')
            actual=next(s['valores'] for s in result['series'] if s['id']=='observable.'+qid)
            expected=[variant_reference(t,2*capacity,900,g1,g2,a,*temperatures)[0] for t in result['ejes'][0]['valores']]
            self.assertLess(np.max(abs(np.array(actual)-expected))/240,1e-5)

    def test_affine_review_edges_remain_rejections(self):
        from core.mathematics.linear_system import ConstantAffineBlock,AffineBlockError
        x,z=sp.symbols('x z')
        with self.assertRaises(AffineBlockError) as caught:
            ConstantAffineBlock([x+z,x+(1+sp.Rational('8.8e-8'))*z],[x,z],{})
        self.assertEqual(caught.exception.code,'ill_conditioned_algebraic_block')
        ConstantAffineBlock([x+z,x+(1+sp.Rational('8.9706e-8'))*z],[x,z],{})
        # A replayed physical model with a selected state-dependent linear block
        # must reject at the unchanged v2 gate, before other ancestry checks.
        model=copy.deepcopy(self.model)
        author=SharedAuthor(model)
        author.definition=copy.deepcopy(model['motores']['equationWorkbench']);author.refresh()
        time=sp.Symbol('t',real=True)
        mass=sp.Function('m__domain_one__1')(time)
        temp1=sp.Function('T__domain_one')(time);temp2=sp.Function('T__domain_two')(time)
        author.append('declare_symbol',family='energy',name='referenceMass',unit='kg')
        first=author.append('declare_relation',family='energy',left=f'contactHeat*{author.quantity(mass)}',
                            right=f'firstConductance*referenceMass*({author.quantity(temp1)}-contactTemperature)',
                            relationKind='constitutive',reason='Adverse state-dependent contact coefficient')
        second=author.append('declare_relation',family='energy',left='contactHeat',
                             right=f'secondConductance*(contactTemperature-{author.quantity(temp2)})',
                             relationKind='constitutive',reason='Adverse linear replacement for v2 admission control')
        model,replayed,_=author.finish({})
        selection=model['motores']['derivedExecution'];selection['version']=2;del selection['nonlinear']
        selection['algebraic'][0]['equationId']=first;selection['algebraic'][1]['equationId']=second
        qid=next(k for k,v in {**catalog(replayed.graph,replayed.units),**replayed.introduced}.items() if str(v)=='referenceMass')
        selection['parameters'][qid]='domain_one.mass'
        selection['sourceSignature']=source_signature(model,replayed)
        with self.assertRaises(LoweringError) as caught:DerivedSystem(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'],'nonconstant_algebraic_matrix')



if __name__=='__main__':
    if '--publication' in sys.argv:
        model,_=thermal_case()
        from backend.api_modelo import resolver_modelo
        print(json.dumps({'model':model,'result':resolver_modelo({'modelo':model,'assessmentVersion':1})}))
    else:
        unittest.main()
