"""Independent algebra, premise connectivity and shared family identities."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp
from core.balances import material_derivation as material, momentum_derivation as momentum
from core.balances.energy_equations import equation_graph as energy_graph, lower_equilibrium_rate
from core.modelo.operation_journal import JournalError
from core.balances.momentum_transport import extend_transport
from core.modelo.equation_manipulation import EquationGraph
from core.modelo.equation_workbench import _dimension
from core.termodinamica.equations import equation_graph as thermo_graph, StateDifferential as D


def context(changes, namespace='energyDerivation'):
    return {'volumenes':[{'id':'v','componenteIds':[1,2],
                         'frontera':{'tipo':'presion_prescrita'},
                         'supuestos':{'materia':{**material.fundamental_formulation(), 'restoImpermeable':True}}}],
            'corrientes':[{'id':'s','desde':None,'hasta':'v','componenteIds':[1,2]}],
            'motores':{namespace:{'volumes':{'v':{'origin':'recorded','operations':[
                {'id':'physical-'+str(i),'title':str(change),'changes':change} for i,change in enumerate(changes)]}}}}}


def quantity(graph, name):
    return next(f for node in graph.nodes.values() for f in node.equation.atoms(sp.Function)
                if f.func.__name__==name)


def transport(state):
    graph=EquationGraph()
    for axis,(rate,convective,force) in zip('xyz',momentum.cartesian_relations(momentum.fundamental())):
        graph.add('local.'+axis,rate+convective,force,'Cauchy '+axis)
    final=extend_transport(graph,momentum.normalize({**momentum.fundamental(),**state}))
    return graph,final


class PhysicalEquationGraphTests(unittest.TestCase):
    def test_uniform_internal_inventory_does_not_reinterpret_total_kinetic_energy(self):
        graph,final,_=energy_graph(context([{'uniforme':True}]),'v')
        definition=graph.nodes['energy.v.uniform-inventory']
        self.assertIn('energy.v.internal-inventory-definition',definition.inputs)
        self.assertNotEqual(graph.nodes['energy.v.inventory-definition'].equation.lhs,definition.equation.lhs)
        self.assertIn('energy.v.uniform-inventory',final)

    def test_symbolic_transform_summary_preserves_the_exact_current_family_graphs(self):
        from core.compilador.presentation import symbolic_formulation_summary
        from core.modelo.equation_workbench import fundamental_report
        draft={'format':'rage.fundamental-equations','version':3,'modelId':'unbound',
               'materialJournal':{'origin':'recorded','operations':[]},'ports':[],
               'definition':{'format':'rage.equation-workbench','version':1,'operations':[],'cursor':0}}
        report=fundamental_report(draft);summary=symbolic_formulation_summary(draft)
        self.assertFalse(report['execution']['supported'])
        for family in summary['families']:
            self.assertEqual(family['volumes'][0]['steps'],[r for r in report['equations'] if r['family']==family['id'] and r['current']])
        draft['definition']={'format':'rage.equation-workbench','version':1,'cursor':1,
                             'operations':[{'kind':'expand','family':'energy','sources':['missing-source']}]}
        with self.assertRaisesRegex(JournalError,'no longer match'):symbolic_formulation_summary(draft)

    def test_compound_expression_cannot_inherit_the_first_quantity_unit(self):
        V=sp.Function('V__v')(sp.Symbol('t',real=True));pressure=sp.Function('P__v')(sp.Symbol('t',real=True))
        units={pressure:'Pa',V:'m3'}
        self.assertEqual(_dimension(V*pressure,units),{'M':1,'L':2,'T':-2})
        with self.assertRaises(JournalError):_dimension(V+pressure,units)

    def test_equilibrium_lowering_uses_graph_signs_and_rejects_retained_terms(self):
        changes=[{'separarPresion':True},{'entalpia':True},{'sinCinetica':True},
                 {'sinTrabajoViscoso':True},{'sinFuerzasVolumen':True},{'sinFuenteVolumetrica':True},
                 {'presionUniforme':True},{'presionPrescrita':True},{'forma':'total'}]
        model=context(changes)
        self.assertEqual(lower_equilibrium_rate(model,'v'),[('stream','s',1.0),('heat','v',1.0),('pressure','v',1.0)])
        model['corrientes'][0].update(desde='v',hasta=None)
        self.assertEqual(lower_equilibrium_rate(model,'v')[0],('stream','s',-1.0))
        model['motores']['energyDerivation']['volumes']['v']['operations'].append(
            {'id':'keep-source','title':'Retain the volumetric source','changes':{'sinFuenteVolumetrica':False}})
        with self.assertRaisesRegex(JournalError,'retained first-law term'):lower_equilibrium_rate(model,'v')

    def test_enthalpy_transport_and_pressure_product_rule(self):
        changes=[{'separarPresion':True},{'entalpia':True},{'sinCinetica':True},
                 {'sinTrabajoViscoso':True},{'sinFuerzasVolumen':True},{'sinFuenteVolumetrica':True},
                 {'presionUniforme':True},{'presionPrescrita':True},{'forma':'total'}]
        graph,final,units=energy_graph(context(changes),'v')
        eq=graph.nodes[final[0]].equation
        t=sp.Symbol('t',real=True)
        V,P,H=(quantity(graph,n+'__v') for n in ('V','P','H'))
        h=quantity(graph,'energy_average_0__s');heat=quantity(graph,'energy_heat_rate__v')
        flow=sum(sp.Function('q__s__'+str(i))(t) for i in (1,2))
        # Independent open-system first law: dH = sum(mdot*h)+Q+V*dP.
        self.assertEqual(sp.simplify(eq.lhs-sp.diff(H,t)),0)
        self.assertEqual(sp.simplify(eq.rhs-(flow*h+heat+V*sp.diff(P,t))),0)
        self.assertEqual(_dimension(eq.lhs,units),_dimension(eq.rhs,units))
        self.assertEqual(graph.nodes[final[0]].kind,'balance')

    def test_pressure_work_internal_and_enthalpy_forms_are_equivalent(self):
        changes=[{'separarPresion':True},{'sinCinetica':True},{'sinTrabajoViscoso':True},
                 {'sinFuerzasVolumen':True},{'sinFuenteVolumetrica':True},{'presionUniforme':True},{'forma':'total'}]
        graph,final,_=energy_graph(context(changes),'v')
        eq=graph.nodes[final[0]].equation;t=sp.Symbol('t',real=True)
        P,V=(quantity(graph,n+'__v') for n in ('P','V'))
        # Work of the moving wall survives the partition of p/rho transport.
        self.assertEqual(sp.expand(eq.rhs).coeff(sp.diff(V,t)),-P)
        self.assertFalse(any(str(f.func).startswith('boundary_velocity') for f in eq.atoms(sp.Function)))

    def test_energy_cursor_replays_actual_assumptions_without_mutation(self):
        model=context([{'sinCinetica':True},{'sinFuenteVolumetrica':True}])
        original=copy.deepcopy(model)
        full=energy_graph(model,'v')[0]
        model['motores']['energyDerivation']['volumes']['v']['cursor']=1
        undone=energy_graph(model,'v')[0]
        self.assertNotIn('energy.v.sinFuenteVolumetrica.condition',undone.nodes)
        model['motores']['energyDerivation']['volumes']['v']['cursor']=2
        self.assertEqual(full.rows(),energy_graph(model,'v')[0].rows())
        del model['motores']['energyDerivation']['volumes']['v']['cursor']
        self.assertEqual(model,original)

    def test_integral_stress_density_and_gravity_reach_inventory_equations(self):
        graph,final=transport({'form':'integral','pressureStress':True,'newtonian':True,
                              'constantViscosity':True,'referenceDensity':True,
                              'uniformGravity':True,'verticalGravity':True})
        eq=graph.nodes[final[2]].equation
        self.assertFalse(any(f.func.__name__.startswith('sigma_') for f in eq.atoms(sp.Function)))
        self.assertFalse(any(f.func.__name__ in ('rho','b_z','mu') and len(f.args)>1 for f in eq.atoms(sp.Function)))
        self.assertIn(sp.Symbol('g',real=True),eq.free_symbols)
        self.assertIn('transport.z.constitutive',graph.nodes)
        self.assertIn('transport.reference-density',graph.nodes['transport.z.constitutive'].inputs)
        self.assertEqual(_dimension(eq.lhs,{}),_dimension(eq.rhs,{}))

    def test_fixed_boundary_removes_only_boundary_motion(self):
        moving,final=transport({'form':'integral'})
        fixed,selected=transport({'form':'integral','fixedBoundary':True})
        t=sp.Symbol('t',real=True)
        for a,b in zip(final,selected):
            eq=moving.nodes[a].equation
            boundary={f:0 for f in eq.atoms(sp.Function) if f.func.__name__.startswith('boundary_v_')}
            self.assertEqual(sp.expand(eq.rhs.xreplace(boundary).doit()-fixed.nodes[b].equation.rhs.doit()),0)
            self.assertTrue(fixed.nodes[b].equation.lhs.has(sp.Derivative))
            self.assertTrue(fixed.nodes[b].equation.lhs.has(t))

    def test_axial_torque_and_rotor_power_match_independent_reference(self):
        graph,final=transport({'form':'ports','fixedBoundary':True,'uniformSections':True,
                              'impermeableWall':True,'angularMomentum':True,'rotorActuator':True,
                              'equalPortMassFlow':True,'noOtherTorque':True,'zeroAngularAccumulation':True,
                              'zeroInletSwirl':True,'shaftDynamics':True,'radialOutlet':True,'idealBladeGuidance':True})
        eq=graph.nodes['angular.guided-transfer'].equation;t=sp.Symbol('t',real=True)
        omega=sp.Function('omega')(t);Q=sp.Function('Q')(t)
        r=sp.Symbol('r2',real=True);b=sp.Symbol('outlet_width',real=True);beta=sp.Symbol('blade_angle',real=True)
        reference=omega**2*r**2-omega*Q*sp.cot(beta)/(2*sp.pi*b)
        self.assertEqual(sp.simplify(eq.rhs-reference),0)
        self.assertAlmostEqual(float(eq.rhs.subs({omega:20,Q:.03,r:.2,b:.02,beta:sp.pi/3})),
                               16-20*.03/(2*float(sp.pi)*.02*3**.5))
        rotor=graph.nodes['rotor.power'].equation
        self.assertEqual(sp.expand(rotor.rhs-omega*(sp.Function('motor_torque')(t)-sp.Function('fluid_torque')(t)-sp.Function('bearing_torque')(t))),0)
        self.assertIn('angular.ports',final)  # Dynamic law retained beside zero-rate compatibility.
        self.assertEqual(_dimension(eq.lhs,{}),_dimension(eq.rhs,{}))

    def test_radial_geometry_does_not_require_guidance_or_inject_it(self):
        graph,final=transport({'form':'ports','fixedBoundary':True,'uniformSections':True,
                              'impermeableWall':True,'angularMomentum':True,'radialOutlet':True})
        self.assertIn('angular.annulus',final)
        self.assertNotIn('angular.guidance',graph.nodes)
        self.assertNotIn('angular.shaft-power',graph.nodes)

    def test_thermodynamic_legendre_and_gibbs_duhem_identities(self):
        graph,_,units=thermo_graph(context([], 'thermodynamicDerivation'),'v')
        U,H,G,S,T,P,V=(quantity(graph,n+'__v') for n in ('U','H','G','S','T','P','V'))
        n=[quantity(graph,'n_'+str(i)+'__v') for i in (1,2)]
        mu=[quantity(graph,'mu_'+str(i)+'__v') for i in (1,2)]
        self.assertEqual(sp.expand(graph.nodes['thermodynamics.v.dH-reduced'].equation.rhs-(T*D(S)+V*D(P)+sum(a*D(b) for a,b in zip(mu,n)))),0)
        eq=graph.nodes['thermodynamics.v.gibbs-duhem'].equation
        self.assertEqual(sp.expand(eq.lhs-eq.rhs-(sum(a*D(b) for a,b in zip(n,mu))+S*D(T)-V*D(P))),0)
        self.assertEqual(_dimension(eq.lhs,units),_dimension(eq.rhs,units))


if __name__=='__main__':unittest.main()
