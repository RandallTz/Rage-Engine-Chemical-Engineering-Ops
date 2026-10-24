"""Domain premises, complete quadratic branches and independent references."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sympy as sp
from core.mathematics import EquationGraph,MathematicsError
from core.mathematics.contract import FORMAT,read_definition
from core.mathematics.dimensions import catalog,dimension
from core.mathematics.constants import unit_basis,si_magnitude,UnitBasis
from core.unidades import exact_conversion
from core.mathematics.session import replay_operations,edit_history


class MathematicalDomainTests(unittest.TestCase):
    def setUp(self):
        self.x,self.a=sp.symbols('arbitrary_quantity arbitrary_parameter',real=True)
        self.graph=EquationGraph()
        self.graph.add('root',self.x**2,self.a,'Declared square relation',family='neutral',kind='definition')
        self.units={self.x:'m/s',self.a:'m^2/s^2'}
        self.definition={'format':FORMAT,'version':1,'operations':[],'cursor':0}

    def replay(self,definition=None):
        return replay_operations(self.graph,['root'],{'root':'region'},self.units,definition or self.definition)

    def quantity(self,value):
        return next(key for key,quantity in catalog(self.graph,self.units).items() if quantity==value)

    def action(self,kind,operation=None):
        self.definition=edit_history(self.graph,['root'],{'root':'region'},self.units,self.definition,
                                     {'kind':kind,**({'operation':operation} if operation else {})})
        return self.replay()

    def domain(self,quantity,domain,**bounds):
        self.action('append',{'kind':'declare_domain','family':'neutral','sources':['root'],
                             'symbol':self.quantity(quantity),'domain':domain,'reason':'Explicit test validity regime',**bounds})
        return 'operation.'+str(self.definition['cursor'])

    def isolate(self,domains):
        return self.action('append',{'kind':'isolate','family':'neutral','sources':['root'],
                                     'symbol':self.quantity(self.x),'domains':domains})

    def test_positive_and_negative_quadratic_branches_use_recorded_parameter_domains(self):
        parameter=self.domain(self.a,'positive');target=self.domain(self.x,'positive')
        result=self.isolate([parameter,target]);node=result.graph.nodes['operation.3']
        self.assertEqual(node.equation.rhs,sp.sqrt(self.a))
        for a in (1,4,9,25):
            # Independent numeric square-root reference, then original residual.
            value=float(node.equation.rhs.subs(self.a,a))
            self.assertEqual(value,a**0.5);self.assertAlmostEqual(value*value-a,0)
        self.assertEqual(sorted(admitted for _,admitted in node.branches),[False,True])
        self.assertEqual(result.receipts[-1].branches,node.branches)
        self.assertEqual(set(self.definition['operations'][-1]['sourceSignatures']),{'root',parameter,target})
        self.assertEqual(result.receipts[-1].before[-1][1],sp.Contains(self.x,sp.Interval.open(0,sp.oo),evaluate=False))
        self.assertTrue(any('Explicit test validity' in c for c in result.receipts[-1].conditions))
        self.action('undo');self.action('undo')
        negative=self.domain(self.x,'negative');result=self.isolate([parameter,negative])
        self.assertEqual(result.graph.nodes['operation.3'].equation.rhs,-sp.sqrt(self.a))

    def test_membership_is_a_condition_and_never_an_invented_equality(self):
        key=self.domain(self.x,'nonnegative');result=self.replay()
        node=result.graph.nodes[key]
        self.assertIsInstance(node.equation,sp.Contains)
        self.assertEqual(node.kind,'constraint');self.assertTrue(result.requires_lowering)
        self.assertEqual(self.graph.domains,{})
        self.assertNotIn(key,self.graph.nodes)

    def test_two_real_branches_remain_ambiguous_and_failed_append_is_atomic(self):
        a=self.domain(self.a,'positive');x=self.domain(self.x,'real');original=copy.deepcopy(self.definition)
        with self.assertRaisesRegex(MathematicsError,'2 branches'):self.isolate([a,x])
        self.assertEqual(self.definition,original)

    def test_unresolved_parameter_sign_cannot_silently_choose_a_branch(self):
        a=self.domain(self.a,'real');x=self.domain(self.x,'positive')
        with self.assertRaisesRegex(MathematicsError,'unresolved'):self.isolate([a,x])

    def test_contradictory_domains_are_rejected_without_mutating_history(self):
        self.domain(self.x,'positive');before=copy.deepcopy(self.definition)
        with self.assertRaisesRegex(MathematicsError,'contradictory'):self.domain(self.x,'negative')
        self.assertEqual(self.definition,before)

    def test_numeric_zero_and_complex_roots_respect_open_closed_domains(self):
        self.graph.nodes['root'].equation=sp.Eq(self.x**2,0,evaluate=False)
        domain=self.domain(self.x,'nonnegative');result=self.isolate([domain])
        self.assertEqual(result.graph.nodes['operation.2'].equation.rhs,0)
        self.action('undo');self.action('undo');domain=self.domain(self.x,'positive')
        with self.assertRaisesRegex(MathematicsError,'0 branches'):self.isolate([domain])
        self.definition={'format':FORMAT,'version':1,'operations':[],'cursor':0}
        self.graph.nodes['root'].equation=sp.Eq(self.x**2,-4,evaluate=False)
        # Use a dimensionless equation for numeric constants in this reference.
        self.units[self.x]='1';domain=self.domain(self.x,'real')
        with self.assertRaisesRegex(MathematicsError,'0 branches'):self.isolate([domain])

    def test_domain_ids_are_typed_and_target_domain_is_required(self):
        a=self.domain(self.a,'positive')
        with self.assertRaisesRegex(MathematicsError,'selected quantity'):self.isolate([a])
        with self.assertRaisesRegex(MathematicsError,'recorded domain'):self.isolate(['root'])

    def test_domain_changes_behind_same_id_invalidate_pinned_branch(self):
        a=self.domain(self.a,'positive');x=self.domain(self.x,'positive');self.isolate([a,x])
        changed=copy.deepcopy(self.definition);changed['operations'][1]['domain']='negative'
        with self.assertRaisesRegex(MathematicsError,'same ID'):self.replay(changed)
        self.assertEqual(self.replay().graph.nodes['operation.3'].equation.rhs,sp.sqrt(self.a))
        before=copy.deepcopy(self.definition);self.action('undo');self.action('redo')
        self.assertEqual(self.definition,before)

    def test_substitution_keeps_branch_inputs_and_all_alternatives(self):
        self.graph.add('consumer',2*self.x,sp.Symbol('output',real=True),'Declared relation',family='neutral')
        self.units[sp.Symbol('output',real=True)]='m/s'
        a=self.domain(self.a,'positive');x=self.domain(self.x,'negative')
        result=self.action('append',{'kind':'substitute','family':'neutral','sources':['consumer'],'relation':'root',
                                     'symbol':self.quantity(self.x),'domains':[a,x]})
        node=result.graph.nodes['operation.3']
        self.assertEqual(node.equation.lhs,-2*sp.sqrt(self.a))
        self.assertEqual(node.inputs,('consumer','root',a,x));self.assertEqual(len(node.branches),2)

    def test_malformed_domain_records_and_signature_coverage_are_rejected(self):
        op={'kind':'declare_domain','family':'neutral','sources':['root'],'symbol':'x','domain':'positive','reason':'Premise'}
        for invalid in [{**op,'domain':'automatic'},{**op,'domains':['root']},
                        {'kind':'isolate','family':'neutral','sources':['root'],'symbol':'x','domains':['domain'],
                         'sourceSignatures':{'root':'a'*64}}]:
            with self.assertRaises(MathematicsError):read_definition({**self.definition,'operations':[invalid],'cursor':1})

    def test_nonpolynomial_and_higher_degree_branches_remain_explicit_findings(self):
        for expression in (self.x**3,sp.exp(self.x)):
            graph=copy.deepcopy(self.graph)
            graph.nodes['root'].equation=sp.Eq(expression,self.a,evaluate=False)
            # Exercise the typed solver directly, without changing pinned roots.
            graph.declare_domain('domain','root',self.x,'positive','Required branch')
            with self.assertRaisesRegex(MathematicsError,'polynomial'):graph.solve_in_domains(graph.nodes['root'].equation,self.x,['domain'])

    def test_symbolic_leading_coefficient_keeps_excluded_degenerate_regime(self):
        coefficient=sp.Symbol('coefficient',real=True);self.units[coefficient]='1'
        self.graph.nodes['root'].equation=sp.Eq(coefficient*self.x**2,self.a,evaluate=False)
        c=self.domain(coefficient,'positive');a=self.domain(self.a,'positive');x=self.domain(self.x,'positive')
        result=self.isolate([c,a,x]);node=result.graph.nodes['operation.4']
        self.assertEqual(sp.simplify(node.equation.rhs-sp.sqrt(self.a/coefficient)),0)
        self.assertTrue(any(isinstance(condition,sp.Unequality) and 'coefficient' in str(condition) for condition in node.predicates))
        value=float(node.equation.rhs.subs({coefficient:2,self.a:18}))
        self.assertEqual(value,3);self.assertEqual(2*value**2,18)

    def test_domain_premises_cannot_bypass_dimensions_or_affine_units(self):
        self.units[self.a]='s'
        with self.assertRaisesRegex(MathematicsError,'dimensions'):self.domain(self.x,'positive')
        self.units[self.a]='m^2/s^2';self.units[self.x]='degC'
        # Use a zero RHS so the absolute-unit guard is tested separately.
        self.graph.nodes['root'].equation=sp.Eq(self.x,0,evaluate=False)
        with self.assertRaisesRegex(MathematicsError,'absolute unit'):self.domain(self.x,'positive')

    def test_replay_preserves_unevaluated_equalities_and_source_nodes(self):
        equation=sp.Eq(self.x**2,-4,evaluate=False)
        self.graph.nodes['root'].equation=equation
        result=self.replay()
        self.assertIs(result.graph.nodes['root'].equation,equation)
        result.graph.nodes['root'].title='Edited replay title'
        self.assertNotEqual(result.graph.nodes['root'].title,self.graph.nodes['root'].title)

    def test_bounded_parameter_interval_proves_radical_membership_exactly(self):
        a=self.domain(self.a,'interval',lower='1',upper='4',lowerOpen=False,upperOpen=False)
        x=self.domain(self.x,'interval',lower='1',upper='2',lowerOpen=False,upperOpen=False)
        result=self.isolate([a,x]);equation=result.graph.nodes['operation.3'].equation
        self.assertEqual(equation.rhs,sp.sqrt(self.a))
        for parameter in [sp.Rational(1),sp.Rational(9,4),sp.Rational(4)]:
            value=equation.rhs.subs(self.a,parameter)
            self.assertEqual(value**2,parameter);self.assertTrue(1<=value<=2)

    def test_open_interval_endpoints_reject_an_excluded_numeric_root(self):
        self.units[self.x]='1';self.graph.nodes['root'].equation=sp.Eq(self.x**2,4,evaluate=False)
        x=self.domain(self.x,'interval',lower='0',upper='2',lowerOpen=False,upperOpen=False)
        self.assertEqual(self.isolate([x]).graph.nodes['operation.2'].equation.rhs,2)
        self.action('undo');self.action('undo')
        x=self.domain(self.x,'interval',lower='0',upper='2',lowerOpen=False,upperOpen=True)
        with self.assertRaisesRegex(MathematicsError,'0 branches'):self.isolate([x])

    def test_invalid_empty_or_executable_endpoint_text_is_rejected_atomically(self):
        before=copy.deepcopy(self.definition)
        for lower,upper,opened in [('2','1',False),('1','1',True),('1/0','2',False),('__import__("os")','2',False),('nan','2',False)]:
            with self.assertRaises(MathematicsError):
                self.domain(self.x,'interval',lower=lower,upper=upper,lowerOpen=opened,upperOpen=False)
            self.assertEqual(self.definition,before)

    def test_interval_intersection_detects_contradictory_sign_premises(self):
        self.domain(self.x,'interval',lower='1/2',upper='2',lowerOpen=False,upperOpen=False)
        with self.assertRaisesRegex(MathematicsError,'contradictory'):self.domain(self.x,'negative')

    def test_zero_parameter_case_is_an_actual_substitution_before_isolation(self):
        a=self.domain(self.a,'zero');x=self.domain(self.x,'nonnegative')
        result=self.isolate([a,x]);case=result.graph.nodes['operation.3.case']
        self.assertEqual(case.rule,'domain_case')
        self.assertEqual(case.equation,sp.Eq(self.x**2,0,evaluate=False))
        self.assertIn('root',case.inputs);self.assertIn(a,case.inputs)
        self.assertEqual(result.graph.nodes['operation.3'].equation.rhs,0)
        self.assertEqual(result.receipts[-1].after[0][0],'operation.3.case')

    def test_zero_leading_coefficient_reduces_the_actual_polynomial_degree(self):
        coefficient=sp.Symbol('coefficient',real=True);self.units[coefficient]='1'
        self.graph.nodes['root'].equation=sp.Eq(coefficient*self.x**2+self.x,self.a,evaluate=False)
        # Dimensionless regression polynomial; no implicit dimensioned constants.
        self.units[self.x]='1';self.units[self.a]='1'
        c=self.domain(coefficient,'zero');a=self.domain(self.a,'positive');x=self.domain(self.x,'positive')
        result=self.isolate([c,a,x])
        self.assertEqual(result.graph.nodes['operation.4.case'].equation,sp.Eq(self.x,self.a,evaluate=False))
        self.assertEqual(result.graph.nodes['operation.4'].equation.rhs,self.a)
        self.assertFalse(any(isinstance(condition,sp.Unequality) and 'coefficient' in str(condition) for condition in result.graph.nodes['operation.4'].predicates))

    def test_zero_coefficient_identity_and_inconsistent_cases_are_distinct(self):
        coefficient=sp.Symbol('coefficient',real=True);self.units[coefficient]='m/s'
        self.graph.nodes['root'].equation=sp.Eq(coefficient*self.x,self.a,evaluate=False)
        c=self.domain(coefficient,'zero');a=self.domain(self.a,'zero');x=self.domain(self.x,'real')
        with self.assertRaisesRegex(MathematicsError,'identity'):self.isolate([c,a,x])
        self.action('undo');self.action('undo')
        a=self.domain(self.a,'positive');x=self.domain(self.x,'real')
        with self.assertRaisesRegex(MathematicsError,'inconsistent'):self.isolate([c,a,x])

    def test_dimensionless_singleton_interval_replays_an_explicit_parameter_value(self):
        self.units[self.x]='1';self.units[self.a]='1'
        a=self.domain(self.a,'interval',lower='9/4',upper='2.25',lowerOpen=False,upperOpen=False)
        x=self.domain(self.x,'positive');result=self.isolate([a,x])
        self.assertEqual(result.graph.nodes['operation.3'].equation.rhs,sp.Rational(3,2))
        self.assertEqual(result.graph.nodes['operation.3.case'].equation.rhs,sp.Rational(9,4))

    def test_nonzero_dimensioned_singleton_retains_units_through_actual_substitution(self):
        a=self.domain(self.a,'interval',lower='4',upper='4',lowerOpen=False,upperOpen=False)
        x=self.domain(self.x,'positive')
        result=self.isolate([a,x]);value=result.graph.nodes['operation.3'].equation.rhs
        self.assertEqual(value,2*unit_basis({'L':1,'T':-1}))
        self.assertEqual(dimension(value,{}),dimension(self.x,self.units))
        self.assertEqual(result.graph.nodes['operation.3.case'].equation.rhs,value**2)
        self.assertEqual(si_magnitude(value),2)
        self.assertFalse(any(isinstance(q,UnitBasis) for q in catalog(result.graph,result.units).values()))
        self.action('undo');self.assertEqual(self.action('redo').graph.rows(),result.graph.rows())

    def test_exact_conversion_uses_catalog_rationals_not_rounded_float_factors(self):
        from fractions import Fraction
        for unit,expected in [('cm',Fraction(1,100)),('km/hour',Fraction(5,18)),('inch',Fraction(127,5000)),('bar',Fraction(100000))]:
            self.assertEqual(exact_conversion(unit)['factor'],expected)

    def test_explicit_scaled_bounds_keep_declaration_conversion_and_typed_case(self):
        self.units[self.x]='cm/s'
        a=self.domain(self.a,'interval',lower='40000',upper='40000',lowerOpen=False,upperOpen=False,endpointUnit='cm^2/s^2')
        x=self.domain(self.x,'interval',lower='100',upper='200',lowerOpen=False,upperOpen=False,endpointUnit='cm/s')
        result=self.isolate([a,x]);value=result.graph.nodes['operation.3'].equation.rhs
        self.assertEqual(si_magnitude(value),2)
        self.assertEqual(result.graph.domains[x].allowed,sp.Interval(1,2))
        self.assertEqual(result.graph.nodes[a].inputs,(a+'.declared',))
        self.assertIn('cm^2/s^2',result.graph.nodes[a+'.declared'].title)
        self.assertEqual(result.receipts[0].after[0][0],a+'.declared')
        self.assertEqual(result.receipts[0].after[1][0],a)
        self.assertEqual(dimension(value,{}),{'L':1,'T':-1})
        self.assertTrue(result.requires_lowering)

    def test_conversion_preserves_rational_open_bounds_and_parameter_proofs(self):
        a=self.domain(self.a,'interval',lower='10000',upper='40000',lowerOpen=False,upperOpen=False,endpointUnit='cm^2/s^2')
        x=self.domain(self.x,'interval',lower='18/5',upper='36/5',lowerOpen=False,upperOpen=False,endpointUnit='km/hour')
        result=self.isolate([a,x]);self.assertEqual(result.graph.nodes['operation.3'].equation.rhs,sp.sqrt(self.a))
        self.action('undo');self.action('undo')
        x=self.domain(self.x,'interval',lower='18/5',upper='36/5',lowerOpen=False,upperOpen=True,endpointUnit='km/hour')
        with self.assertRaisesRegex(MathematicsError,'unresolved'):self.isolate([a,x])

    def test_unit_changes_invalidate_pinned_domain_consumers(self):
        a=self.domain(self.a,'interval',lower='4',upper='4',lowerOpen=False,upperOpen=False,endpointUnit='m^2/s^2')
        x=self.domain(self.x,'positive');self.isolate([a,x]);changed=copy.deepcopy(self.definition)
        changed['operations'][0]['endpointUnit']='cm^2/s^2'
        with self.assertRaisesRegex(MathematicsError,'same ID'):self.replay(changed)

    def test_incompatible_affine_and_misplaced_endpoint_units_are_rejected(self):
        before=copy.deepcopy(self.definition)
        for unit in ['kg','degC','unknownUnit']:
            with self.assertRaises(MathematicsError):
                self.domain(self.x,'interval',lower='1',upper='2',lowerOpen=False,upperOpen=False,endpointUnit=unit)
            self.assertEqual(before,self.definition)
        with self.assertRaisesRegex(MathematicsError,'only to interval'):self.domain(self.x,'positive',endpointUnit='m/s')

    def test_converted_membership_cannot_be_used_as_an_algebraic_equation(self):
        a=self.domain(self.a,'interval',lower='4',upper='4',lowerOpen=False,upperOpen=False,endpointUnit='m^2/s^2')
        with self.assertRaisesRegex(MathematicsError,'not an equation'):
            self.action('append',{'kind':'factor','family':'neutral','sources':[a+'.declared']})

    def test_typed_constants_support_substitution_differentiation_and_dimensional_rejection(self):
        t=sp.Symbol('coordinate',real=True);y=sp.Function('output')(t);self.units.update({y:'m/s',t:'s'})
        self.graph.add('consumer',2*self.x,y,'Declared second relation',family='neutral')
        a=self.domain(self.a,'interval',lower='9',upper='9',lowerOpen=False,upperOpen=False,endpointUnit='m^2/s^2')
        x=self.domain(self.x,'positive')
        result=self.action('append',{'kind':'substitute','family':'neutral','sources':['consumer'],'relation':'root','symbol':self.quantity(self.x),'domains':[a,x]})
        self.assertEqual(si_magnitude(result.graph.nodes['operation.3'].equation.lhs),6)
        result=self.action('append',{'kind':'differentiate','family':'neutral','sources':['operation.3'],'symbol':self.quantity(t)})
        self.assertEqual(result.graph.nodes['operation.4'].equation,sp.Eq(0,sp.diff(y,t),evaluate=False))
        with self.assertRaisesRegex(MathematicsError,'incompatible'):
            dimension(2*unit_basis({'L':1})+unit_basis({'T':1}),{})

    def test_interval_endpoints_do_not_silently_mix_scaled_coordinate_units(self):
        self.units[self.x]='cm/s'
        with self.assertRaisesRegex(MathematicsError,'SI-scale'):
            self.domain(self.x,'interval',lower='0',upper='2',lowerOpen=False,upperOpen=False)

    def test_irrelevant_singleton_premises_do_not_manufacture_a_case_step(self):
        a=self.domain(self.a,'zero');x=self.domain(self.x,'positive');graph=self.replay().graph
        graph.add('fixed',self.x**2,4,'Independent numeric relation',family='neutral')
        self.assertEqual(graph.specialize_domains('no-op','fixed',self.x,[a,x]),'fixed')
        self.assertNotIn('no-op',graph.nodes)

    def test_changing_interval_openness_invalidates_pinned_operations(self):
        a=self.domain(self.a,'positive');x=self.domain(self.x,'interval',lower='0',upper='100',lowerOpen=False,upperOpen=False)
        # Bound the parameter so every root membership can be proved.
        self.action('undo');self.action('undo')
        a=self.domain(self.a,'interval',lower='1',upper='4',lowerOpen=False,upperOpen=False)
        x=self.domain(self.x,'interval',lower='1',upper='2',lowerOpen=False,upperOpen=False)
        self.isolate([a,x]);changed=copy.deepcopy(self.definition)
        changed['operations'][1]['upperOpen']=True
        with self.assertRaisesRegex(MathematicsError,'same ID'):self.replay(changed)


if __name__=='__main__':unittest.main()
