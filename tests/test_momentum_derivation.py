"""Fundamental-law momentum deduction; independent mechanics and units checks."""
import copy
import math
import unittest
import sympy as sp

from test_workspace_handoffs import example
from core.balances import momentum_derivation as momentum
from core.modelo import leer_modelo_comun, ErrorModelo
from core.modelo.adaptadores import a_ensamblaje_v2, desde_ensamblaje_v2
from core.modelo.operation_journal import JournalError
from core.compilador.presentation import formulation_summary
from core.compilador.compilador import compilar, resolver, NoSoportado
from core.compilador.report import compilation_report
from core.unidades import interpretar

BASE = ['pressure_stress','newtonian','mass_continuity','constant_viscosity','divergence_free','integrate','fixed_boundary','uniform_sections','impermeable_wall','ports']
PUMP = BASE + ['angular_momentum','rotor_actuator','shaft_dynamics','equal_port_mass_flow','no_other_torque','zero_angular_accumulation','zero_inlet_swirl','radial_outlet','ideal_blade_guidance','reference_density','adiabatic_passage','zero_passage_energy','lossless_passage']
HYDRAULIC = BASE + ['constant_area','reference_density','uniform_gravity','hydraulic','darcy_weisbach']


def journal(sequence=PUMP):
    result = {'format':momentum.FORMAT,'version':1,'volumes':{}}
    for kind in ['start'] + sequence:
        result = momentum.edit_journal(result, 'A', {'kind':kind})
    return result


def model_with_momentum(sequence=PUMP, active=True):
    model = example()
    model['volumenes'][0]['balances']['momento'] = active
    model['motores']['momentumDerivation'] = journal(sequence)
    return model


class MomentumDerivationTests(unittest.TestCase):
    def test_fundamental_is_cauchy_not_a_pump_or_incompressible_model(self):
        development = momentum.describe_volume(journal([]), 'A')
        self.assertEqual(1, len(development['steps']))
        self.assertIn('boldsymbol\\sigma', development['steps'][0]['latex'])
        self.assertTrue(all(not development['formulation'][key] for key in momentum.FLAGS))
        self.assertEqual([], development['couplingSteps'])

    def test_pump_path_replays_every_assumption_without_mutating_source(self):
        value = journal(); before = copy.deepcopy(value)
        development = momentum.describe_volume(value, 'A')
        self.assertEqual(value, before)
        self.assertTrue(development['formulation']['newtonian'])
        self.assertTrue(development['formulation']['idealBladeGuidance'])
        for title in ['Cauchy','Newtonian','Gauss','Reynolds','triangle','angular','pressure rise']:
            self.assertIn(title.lower(), str(development).lower())
        self.assertTrue(all(step['family']=='momentum' for step in development['steps']))
        self.assertEqual({'matter','energy','thermodynamics'}, {step['family'] for step in development['couplingSteps']})
        self.assertTrue(any('dL_f' in step['latex'] for step in development['steps']))
        self.assertTrue(any('frac{dE_f}{dt}' in step['latex'] for step in development['couplingSteps']))
        self.assertTrue(any('d\\omega' in step['latex'] for step in development['steps']))

    def test_no_skipping_assumptions_and_no_hidden_zero_storage(self):
        for kind in ['newtonian','ports','hydraulic','ideal_blade_guidance','zero_angular_accumulation','lossless_passage','shaft_dynamics']:
            with self.subTest(kind=kind), self.assertRaises(JournalError):
                momentum.edit_journal(journal([]),'A',{'kind':kind})
        forged = journal([])
        forged['volumes']['A']['operations'] = [{'id':'jump','title':'Jump directly to a pump','changes':{**momentum.fundamental(),'form':'ports'}}]
        with self.assertRaises(JournalError):momentum.read_journal(forged)
        ports = journal(BASE)
        with self.assertRaises(JournalError):momentum.edit_journal(ports,'A',{'kind':'integrate'})
        missing_energy_constraint = journal(PUMP[:-2])
        with self.assertRaises(JournalError):momentum.edit_journal(missing_energy_constraint,'A',{'kind':'lossless_passage'})
        straight_rotor = journal(HYDRAULIC+['angular_momentum'])
        with self.assertRaises(JournalError):momentum.edit_journal(straight_rotor,'A',{'kind':'radial_outlet'})

    def test_undo_preserves_earlier_operations_and_returns_the_previous_formulation(self):
        previous = journal(PUMP[:-1]); full = journal()
        restored = momentum.edit_journal(full,'A',{'kind':'undo'})
        self.assertEqual(previous, restored)
        self.assertNotEqual(previous, full)

    def test_newtonian_stress_divergence_against_independent_tensor_differentiation(self):
        x,y,z = sp.symbols('x y z'); coordinates=(x,y,z)
        velocity=sp.Matrix([x*x+y*z,y*y+z*x,z*z+x*y]); mu,lam=sp.Rational(7,10),sp.Rational(-1,5)
        gradient=velocity.jacobian(coordinates); divergence=sp.trace(gradient)
        stress=mu*(gradient+gradient.T)+lam*divergence*sp.eye(3)
        actual=sp.Matrix([sum(sp.diff(stress[i,j],coordinates[j]) for j in range(3)) for i in range(3)])
        reference=mu*sp.Matrix([sum(sp.diff(v,q,2) for q in coordinates) for v in velocity])+(mu+lam)*sp.Matrix([sp.diff(divergence,q) for q in coordinates])
        self.assertEqual(sp.zeros(3,1), sp.simplify(actual-reference))
        self.assertIn(r'(\mu+\lambda)', momentum.equation({**momentum.fundamental(),'pressureStress':True,'newtonian':True,'constantViscosity':True}))

    def test_inertance_preserves_acceleration_at_a_stationary_point_and_after_perturbation(self):
        s,relations,_ = momentum.reduced_relations()
        lhs,rhs=relations['inertance']; values={s['L']:4,s['A']:0.02,s['rho']:1000,s['g']:9.81,s['z1']:0,s['z2']:1,s['p1']:110000,s['p2']:100000,s['loss']:190,s['drive']:0}
        self.assertAlmostEqual(0,float(rhs.subs(values)))
        values[s['drive']]=6000
        rate=float(rhs.subs(values))/(4/0.02)
        self.assertAlmostEqual(30,rate)
        # Independent integral impulse: Delta(momentum)=force*dt, I=L*mdot.
        dt=0.125; delta_mass_flow=(0.02*6000*dt)/4
        self.assertAlmostEqual(delta_mass_flow,rate*dt)
        self.assertAlmostEqual(6000,float(lhs.subs({**values,s['massFlowRate']:rate})))
        self.assertTrue(any(step['latex']==momentum.scalar_latex('inertance') for step in momentum.describe_volume(journal(HYDRAULIC),'A')['steps']))

    def test_signed_losses_are_dissipative_in_both_flow_directions_and_at_zero(self):
        s,relations,_ = momentum.reduced_relations(); expression=relations['loss'][1]
        base={s['f']:0.03,s['L']:8,s['D']:0.1,s['K']:2,s['rho']:998,s['A']:math.pi*0.1**2/4}
        for flow in [-2,0,2]:
            pressure=float(expression.subs({**base,s['massFlow']:flow}))
            velocity=flow/(998*base[s['A']])
            reference=(0.03*8/0.1+2)*998/2*velocity*abs(velocity)
            self.assertAlmostEqual(reference,pressure)
            self.assertGreaterEqual(pressure*flow/998,0)

    def test_centrifugal_transfer_against_velocity_triangle_angular_flux_and_power(self):
        s,relations,_ = momentum.reduced_relations()
        omega,radius,width,flow,rho,beta=180,0.12,0.015,0.008,997,math.radians(35)
        cm=flow/(2*math.pi*radius*width); swirl=omega*radius-cm/math.tan(beta)
        torque_reference=(rho*flow)*radius*swirl
        values={s['speed']:omega,s['r2']:radius,s['b2']:width,s['Q']:flow,s['beta2']:beta,s['massFlow']:rho*flow}
        torque=float(relations['idealTorque'][1].subs(values)); specific=float(relations['idealTransfer'][1].subs(values))
        self.assertAlmostEqual(torque_reference,torque,places=10)
        self.assertAlmostEqual(torque*omega,rho*flow*specific,places=9)
        radial_blades=float(relations['idealTransfer'][1].subs({**values,s['beta2']:sp.pi/2}))
        self.assertAlmostEqual((omega*radius)**2,radial_blades)

    def test_pressure_rise_is_static_pressure_not_total_pressure_inserted_into_eos(self):
        s,relations,_=momentum.reduced_relations(); values={s['rho']:1000,s['transfer']:200,s['c1']:2,s['c2']:4,s['g']:9.81,s['z1']:0,s['z2']:3}
        pressure=float(relations['pressureRise'][1].subs(values))
        self.assertAlmostEqual(1000*(200-6-9.81*3),pressure)
        self.assertNotEqual(1000*200,pressure)

    def test_rotor_equation_against_angular_impulse_and_kinetic_power(self):
        s,relations,_=momentum.reduced_relations(); net=float(relations['rotor'][1].subs({s['motorTorque']:12,s['fluidTorque']:8,s['bearingTorque']:1}))
        J,omega=0.6,100; acceleration=net/J
        self.assertAlmostEqual(5,acceleration)
        self.assertAlmostEqual(J*omega*acceleration,omega*(12-8-1))

    def test_strict_common_native_roundtrip_and_wrong_stream_orientation(self):
        model=model_with_momentum(); original=copy.deepcopy(model)
        self.assertIs(model,leer_modelo_comun(model))
        self.assertEqual(model['motores']['momentumDerivation'],desde_ensamblaje_v2(a_ensamblaje_v2(model))['motores']['momentumDerivation'])
        bad=copy.deepcopy(model);bad['motores']['momentumDerivation']=momentum.edit_journal(journal(),'A',{'kind':'bind_ports','inletStreamId':'feed','outletStreamId':'feed'})
        with self.assertRaises(ErrorModelo):leer_modelo_comun(bad)
        self.assertEqual(original,model)

    def test_coupled_handoff_keeps_each_family_in_its_panel_and_marks_execution_pending(self):
        summary=formulation_summary(model_with_momentum())
        for family in summary['families']:
            for volume in family['volumes']:
                for step in volume['steps']:
                    if 'family' in step:self.assertEqual(family['id'],step['family'])
        self.assertIn('Euler',str(summary));self.assertIn('pending',str(summary))
        self.assertEqual('recorded',summary['families'][2]['volumes'][0]['status'])
        no_history=example();no_history['volumenes'][0]['balances']['momento']=True
        self.assertEqual('unrecorded',formulation_summary(no_history)['families'][2]['volumes'][0]['status'])

    def test_no_existing_solver_can_ignore_active_momentum(self):
        model=model_with_momentum()
        for function in (compilar,resolver,compilation_report):
            with self.subTest(function=function.__name__),self.assertRaisesRegex(NoSoportado,'Momentum'):
                function(model)
        from backend.motor_ensamblaje_v2 import validar_v2
        self.assertIn('MOTOR_ENS_MOMENTUM_JOURNAL',str(validar_v2(a_ensamblaje_v2(model))))

    def test_api_preview_is_read_only_and_does_not_invent_legacy_history(self):
        from backend.api_modelo import momentum_derivation
        model=example();before=copy.deepcopy(model)
        result=momentum_derivation({'modelo':model,'volumeId':'A'})
        self.assertTrue(result['preview']);self.assertIsNone(result['journal']);self.assertEqual(model,before)
        for action in [{'kind':'ports'},{'kind':'start','extra':True}]:
            with self.assertRaises(Exception) as caught:momentum_derivation({'modelo':model,'volumeId':'A','action':action})
            self.assertEqual(422,caught.exception.status_code)

    def test_every_published_scalar_relation_is_dimensionally_homogeneous(self):
        from fractions import Fraction
        s,relations,_=momentum.reduced_relations()
        units={'L':'m','A':'m2','massFlow':'kg/s','massFlowRate':'kg/s2','p1':'Pa','p2':'Pa','drive':'Pa','loss':'Pa','rho':'kg/m3','g':'m/s2','z1':'m','z2':'m','f':'1','D':'m','K':'1','J':'kg*m2','speed':'1/s','acceleration':'1/s2','motorTorque':'N*m','fluidTorque':'N*m','bearingTorque':'N*m','r2':'m','b2':'m','Q':'m3/s','beta2':'1','transfer':'J/kg','c1':'m/s','c2':'m/s','mu':'Pa*s'}
        dimensions={s[key]:interpretar(unit)['dimension'] for key,unit in units.items()}
        def clean(d):return {key:value for key,value in d.items() if value}
        def dimension(expr):
            if expr in dimensions:return dimensions[expr]
            if expr.is_number:return {}
            if expr.func==sp.Abs:return dimension(expr.args[0])
            if expr.func==sp.cot:self.assertEqual({},dimension(expr.args[0]));return {}
            if expr.is_Add:
                terms=[dimension(arg) for arg in expr.args];self.assertTrue(all(term==terms[0] for term in terms));return terms[0]
            if expr.is_Mul:
                result={}
                for arg in expr.args:
                    for key,value in dimension(arg).items():result[key]=result.get(key,Fraction(0))+value
                return clean(result)
            if expr.is_Pow:return clean({key:value*Fraction(expr.exp) for key,value in dimension(expr.base).items()})
            self.fail('Unknown dimensional expression: '+str(expr))
        for name,(lhs,rhs) in relations.items():
            with self.subTest(relation=name):self.assertEqual(dimension(lhs),dimension(rhs))
        for variable in momentum.describe_volume(journal(),'A')['variables']:interpretar(variable['unit'])

    def test_invalid_persisted_operations_are_rejected(self):
        for mutate in [lambda j:j.update(version=2),lambda j:j['volumes']['A']['operations'][0]['changes'].update(pressureStress='yes'),lambda j:j['volumes']['A']['operations'].append(copy.deepcopy(j['volumes']['A']['operations'][0])),lambda j:j['volumes']['A'].update(unknown=True)]:
            value=journal();mutate(value)
            with self.assertRaises(JournalError):momentum.read_journal(value)

    def test_cartesian_reduction_matches_pressure_driven_channel_and_hydrostatics(self):
        # Independent exact solution: plane Poiseuille flow plus transverse gravity.
        state=momentum.fundamental()
        for key in ['pressureStress','newtonian','massContinuity','constantViscosity','divergenceFree','velocityInvariantX','velocityInvariantZ','zeroVelocityY','zeroVelocityZ','zeroLocalAccumulation']:
            state=momentum.normalize({**state,key:True})
        equations=momentum.cartesian_relations(state)
        for rate,convective,force in equations:
            functions=(rate+convective-force).atoms(sp.Function)
            replacements={}
            for f in functions:
                by_name={str(q):q for q in f.args};x=by_name.get('x',sp.Symbol('x',real=True));y=by_name.get('y',sp.Symbol('y',real=True))
                replacements[f]={'rho':sp.Integer(997),'mu':sp.Rational(1,1000),'lambda':0,'v_x':100*y*(sp.Rational(1,10)-y)/(2*sp.Rational(1,1000)),'p':100000-100*x-997*sp.Rational(981,100)*y,'b_x':0,'b_y':-sp.Rational(981,100),'b_z':0}[f.func.__name__]
            self.assertEqual(0,sp.simplify((rate+convective-force).subs(replacements).doit()))
        self.assertIn('p',str(equations[0][2]))
        self.assertIn('p',str(equations[1][2]),'Zero transverse velocity must retain transverse pressure compatibility.')
        self.assertIn(r'\partial',momentum.component_latex(state))

    def test_field_invariance_is_distinct_from_velocity_invariance_and_zero_velocity(self):
        base=momentum.normalize({**momentum.fundamental(),'pressureStress':True,'zeroVelocityZ':True})
        self.assertIn('p',str(momentum.cartesian_relations(base)[2][2]))
        invariant=momentum.normalize({**base,'invariantZ':True})
        self.assertNotIn('Derivative(p',str(momentum.cartesian_relations(invariant)[2][2]))
        self.assertIn('b_z',str(momentum.cartesian_relations(invariant)[2][2]))
        self.assertEqual(3,len(momentum.cartesian_relations(invariant)))
        self.assertEqual(0,momentum.cartesian_relations(invariant)[2][0])

    def test_reduced_inviscid_model_retains_pressure_driven_transient_acceleration(self):
        state=momentum.normalize({**momentum.fundamental(),'pressureStress':True,'negligibleConvection':True,'negligibleViscousStress':True,'negligibleBodyForce':True})
        equations=momentum.cartesian_relations(state)
        x,y,z,t=sp.symbols('x y z t',real=True);rho=sp.Symbol('rho',positive=True)
        for i,(rate,transport,force) in enumerate(equations):
            self.assertEqual(0,transport)
            self.assertNotEqual(0,rate,'Zero velocity at an instant must not remove its time derivative.')
            functions=(rate-force).atoms(sp.Function)
            replacements={f:(rho if f.func.__name__=='rho' else (i+1)*t if f.func.__name__.startswith('v_') else 100000-rho*(x+2*y+3*z)) for f in functions}
            self.assertEqual(0,sp.simplify((rate-force).subs(replacements).doit()))
        value=journal(['pressure_stress'])
        for key in ['negligibleConvection','negligibleViscousStress','negligibleBodyForce']:
            value=momentum.edit_journal(value,'A',{'kind':'set_assumption','name':key,'value':True})
        self.assertNotIn('transport_properties',str(momentum.describe_volume(value,'A')['requirements']))

    def test_independent_switch_order_removal_and_dynamic_constraint(self):
        operations=['invariantZ','zeroVelocityZ','negligibleBodyForce','zeroLocalAccumulation']
        def edited(keys):
            value=journal([])
            for key in keys:value=momentum.edit_journal(value,'A',{'kind':'set_assumption','name':key,'value':True})
            return value
        first=momentum.describe_volume(edited(operations),'A');second=momentum.describe_volume(edited(list(reversed(operations))),'A')
        self.assertEqual(first['formulation'],second['formulation'])
        self.assertEqual(first['finalSteps'],second['finalSteps'])
        self.assertIn('local-compatibility',str(first['finalSteps']))
        self.assertIn('partial',first['finalSteps'][0]['latex'])
        removed=momentum.edit_journal(edited(operations),'A',{'kind':'set_assumption','name':'zeroLocalAccumulation','value':False})
        self.assertFalse(momentum.describe_volume(removed,'A')['formulation']['zeroLocalAccumulation'])
        self.assertNotIn('local-compatibility',str(momentum.describe_volume(removed,'A')['finalSteps']))
        with self.assertRaises(JournalError):momentum.edit_journal(removed,'A',{'kind':'integrate'})

    def test_angular_storage_is_independent_and_removed_couplings_do_not_survive(self):
        value=journal(BASE+['angular_momentum','zero_angular_accumulation'])
        partial=momentum.describe_volume(value,'A')
        self.assertFalse(partial['formulation']['equalPortMassFlow'])
        self.assertFalse(any(row['id'].endswith('.euler') for row in partial['couplingSteps']))
        for key in ['noOtherTorque','equalPortMassFlow']:
            value=momentum.edit_journal(value,'A',{'kind':'set_assumption','name':key,'value':True})
        self.assertTrue(any(row['id'].endswith('.euler') for row in momentum.describe_volume(value,'A')['couplingSteps']))
        value=momentum.edit_journal(value,'A',{'kind':'set_assumption','name':'noOtherTorque','value':False})
        self.assertFalse(any(row['id'].endswith('.euler') for row in momentum.describe_volume(value,'A')['couplingSteps']))
        full=journal(PUMP[:-1])
        full=momentum.edit_journal(full,'A',{'kind':'set_assumption','name':'idealBladeGuidance','value':False})
        development=momentum.describe_volume(full,'A')
        self.assertNotIn('final.torque',str(development['finalSteps']))
        self.assertFalse(any(row['id'].endswith('.ideal-head') for row in development['couplingSteps']))

    def test_controls_publish_real_dependencies_and_set_actions_are_strict(self):
        value=journal(['pressure_stress','newtonian','constant_viscosity'])
        before=copy.deepcopy(value);development=momentum.describe_volume(value,'A')
        self.assertEqual(set(momentum.FLAGS),{row['key'] for row in development['controls']})
        control=next(row for row in development['controls'] if row['key']=='newtonian')
        self.assertFalse(control['canChange']);self.assertIn('viscosity',control['reason'])
        for action in [{'kind':'set_assumption','name':'newtonian','value':False},{'kind':'set_assumption','name':'arbitrary','value':True},{'kind':'set_assumption','name':'expandCartesian','value':1},{'kind':'set_assumption','name':'expandCartesian','value':True,'extra':1}]:
            with self.assertRaises(JournalError):momentum.edit_journal(value,'A',action)
        self.assertEqual(value,before)
        # Conservation can be integrated before constitutive closure is selected.
        self.assertEqual('integral',momentum.describe_volume(journal(['integrate']),'A')['formulation']['form'])

    def test_total_stationarity_preserves_hydraulic_inertia_and_undo(self):
        value=journal(HYDRAULIC)
        value=momentum.edit_journal(value,'A',{'kind':'set_assumption','name':'zeroTotalAccumulation','value':True})
        development=momentum.describe_volume(value,'A')
        self.assertIn(r'\frac{d\dot m}{dt}',development['finalSteps'][0]['latex'])
        self.assertIn('final.total-constraint',str(development['finalSteps']))
        self.assertFalse(momentum.describe_volume(momentum.edit_journal(value,'A',{'kind':'undo'}),'A')['formulation']['zeroTotalAccumulation'])


if __name__=='__main__':unittest.main()
