"""Neutral operation replay and independent references below physical adapters."""
import ast
import copy
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import sympy as sp
from core.mathematics import EquationGraph, MathematicsError
from core.mathematics.contract import FORMAT,read_definition
from core.mathematics.dimensions import catalog,dimension
from core.mathematics.provenance import equation_signature
from core.mathematics.session import edit_history,replay_operations
from core.mathematics.operators import VolumeIntegral,BoundaryFlux


class MathematicalKernelTests(unittest.TestCase):
    def setUp(self):
        self.graph=EquationGraph();self.units={};self.definition={'format':FORMAT,'version':1,'operations':[],'cursor':0}

    def root(self,key,left,right,group='arbitrary',kind='balance',conditions=()):
        self.graph.add(key,left,right,'Declared input '+key,family=group,kind=kind,assumptions=conditions)

    def replay(self,definition=None):
        return replay_operations(self.graph,list(self.graph.nodes),{key:'region' for key in self.graph.nodes},self.units,definition or self.definition)

    def quantity(self,expression):
        result=self.replay()
        return next(key for key,value in {**catalog(result.graph,result.units),**result.introduced}.items() if value==expression)

    def action(self,kind,operation=None):
        self.definition=edit_history(self.graph,list(self.graph.nodes),{key:'region' for key in self.graph.nodes},self.units,self.definition,
                                     {'kind':kind,**({'operation':operation} if operation else {})})
        return self.replay()

    def append(self,kind,sources=None,group='arbitrary',**arguments):
        return self.action('append',{'kind':kind,'family':group,**({'sources':sources} if sources else {}),**arguments})

    def test_kernel_import_boundary_has_no_physical_model_or_solver_dependency(self):
        forbidden=('core.balances','core.termodinamica','core.modelo','core.compilador')
        for path in (ROOT/'core/mathematics').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf8'))):
                modules=[node.module or ''] if isinstance(node,ast.ImportFrom) else [alias.name for alias in node.names] if isinstance(node,ast.Import) else []
                self.assertFalse(any(module.startswith(forbidden) for module in modules),str(path))
        # Also test actual import side effects in a fresh interpreter.
        code='import sys; import core.mathematics.session; assert not any(k.startswith('+repr(forbidden)+') for k in sys.modules)'
        subprocess.run([sys.executable,'-c',code],cwd=ROOT,check=True,capture_output=True)

    def test_quantity_names_never_select_units_or_rules(self):
        rho,L=sp.symbols('rho L',real=True)
        self.assertEqual(dimension(rho,{rho:'ohm'}),dimension(L,{L:'ohm'}))
        with self.assertRaises(MathematicsError):dimension(rho,{})
        self.assertEqual(EquationGraph().nodes,{})

    def test_nonpolynomial_inverse_is_not_certified_by_one_sympy_solution(self):
        x,a=sp.symbols('x a',real=True)
        self.root('exponential',sp.exp(x),a)
        with self.assertRaisesRegex(MathematicsError,'domain and branch'):
            self.graph.isolate('inverse','exponential',x,'Unsupported inverse')
        self.assertNotIn('inverse',self.graph.nodes)

    def test_calculus_rejects_constrained_scalars_without_a_dependent_quantity(self):
        F,k,x=sp.symbols('F k x',real=True)
        self.units={F:'N',k:'N/m',x:'m'};self.root('hooke',F,k*x,kind='constitutive')
        for kind in ('differentiate','integrate'):
            with self.assertRaisesRegex(MathematicsError,'depending on the selected coordinate'):
                self.append(kind,['hooke'],symbol=self.quantity(x),**({'name':'C'} if kind=='integrate' else {}))
        self.assertEqual(self.definition['cursor'],0)

    def test_forbidden_substitution_rejects_poles_and_cancelled_denominators(self):
        x,y=sp.symbols('x y',real=True);self.units={x:'1',y:'1'}
        self.root('pole',y,1/(x-1));self.root('point',x,1,kind='constraint')
        with self.assertRaisesRegex(MathematicsError,'validity condition'):
            self.append('substitute',['pole'],relation='point',symbol=self.quantity(x))
        qx,qy=self.quantity(x),self.quantity(y)
        self.append('declare_relation',left=qy,right=f'({qx}^2-1)/({qx}-1)',relationKind='definition',reason='Declared rational function')
        stored=copy.deepcopy(self.definition)
        with self.assertRaisesRegex(MathematicsError,'validity condition'):
            self.append('substitute',['operation.1'],relation='point',symbol=qx)
        self.assertEqual(stored,self.definition)

    def test_finite_guard_covers_every_graph_entry_point(self):
        x=sp.Symbol('x',real=True)
        for invalid in (sp.zoo,sp.nan,sp.oo,-sp.oo):
            with self.assertRaisesRegex(MathematicsError,'not finite'):
                self.graph.add('bad',x,invalid,'Invalid law')
            self.assertNotIn('bad',self.graph.nodes)
        self.root('root',x,1)
        with self.assertRaisesRegex(MathematicsError,'not finite'):
            self.graph.transform('bad','root',lambda value:sp.zoo,'Invalid transform','test')

    def test_real_domains_reject_imaginary_root_and_logarithm_substitutions(self):
        x,y=sp.symbols('x y',real=True);self.units={x:'1',y:'1'}
        self.root('root',y,sp.sqrt(x-2));self.root('logarithm',y,sp.log(x))
        self.root('one',x,1,kind='constraint');self.root('negative',x,-1,kind='constraint')
        self.assertIn(sp.Ge(x-2,0,evaluate=False),self.graph.nodes['root'].predicates)
        self.assertIn(sp.Gt(x,0,evaluate=False),self.graph.nodes['logarithm'].predicates)
        for source,relation in [('root','one'),('logarithm','negative')]:
            with self.assertRaisesRegex(MathematicsError,'validity condition'):
                self.append('substitute',[source],relation=relation,symbol=self.quantity(x))
        for imaginary in (sp.I,sp.pi*sp.I,1+sp.I):
            with self.assertRaisesRegex(MathematicsError,'non-real'):
                self.graph.add('invalid',y,imaginary,'Non-real numeric input')
        self.assertEqual(self.definition['cursor'],0)

    def test_root_guards_survive_parser_cancellation_and_allow_real_boundary(self):
        x,y=sp.symbols('x y',real=True);self.units={x:'1',y:'1'}
        self.root('anchor',y,x);qx,qy=self.quantity(x),self.quantity(y)
        self.root('negative',x,-1,kind='constraint')
        for exponent in ('1/2','0.5'):
            self.definition={'format':FORMAT,'version':1,'operations':[],'cursor':0}
            result=self.append('declare_relation',left=qy,right=f'({qx}^({exponent}))^2',reason='Declared real-root relation')
            self.assertEqual(result.graph.nodes['operation.1'].equation.rhs,x)
            self.assertIn(sp.Ge(x,0,evaluate=False),result.graph.nodes['operation.1'].predicates)
            with self.assertRaisesRegex(MathematicsError,'validity condition'):
                self.append('substitute',['operation.1'],relation='negative',symbol=qx)
        self.graph.add('root',y,sp.sqrt(x),'Real square root')
        self.assertEqual(self.graph.substitute('boundary','root',{x:0},'Admit the zero endpoint').rhs,0)
        self.assertEqual(self.graph.substitute('positive','root',{x:9},'Admit a positive point').rhs,3)
        self.graph.add('inverse',y,1/sp.sqrt(x),'Inverse root')
        with self.assertRaisesRegex(MathematicsError,'validity condition'):
            self.graph.substitute('invalid','inverse',{x:0},'Exclude the inverse-root pole')

    def test_plain_isolation_cannot_contradict_recorded_zero_domain(self):
        a,y,b=sp.symbols('a y b',real=True);self.units={q:'1' for q in (a,y,b)}
        self.root('root',a*y,a*b)
        self.append('declare_domain',['root'],symbol=self.quantity(a),domain='zero',reason='Explicit singular regime')
        with self.assertRaisesRegex(MathematicsError,'validity condition|nonzero condition'):
            self.append('isolate',['root'],symbol=self.quantity(y))

    def test_typed_cancelled_guard_survives_transitive_substitution(self):
        a,y,b=sp.symbols('a y b',real=True);self.units={q:'1' for q in (a,y,b)}
        self.root('root',a*y,a*b);self.root('singular',a,0,kind='constraint')
        self.append('isolate',['root'],symbol=self.quantity(y))
        result=self.append('expand',['operation.1'])
        self.assertIn(sp.Ne(a,0,evaluate=False),result.graph.predicates_for('operation.2'))
        # a no longer occurs in y=b, but its guard remains attached to the proof.
        with self.assertRaisesRegex(MathematicsError,'validity condition'):
            result.graph.substitute('invalid','operation.2',{a:0},'Forbidden specialization')
        self.assertNotIn('invalid',result.graph.nodes)
        with self.assertRaisesRegex(MathematicsError,'validity condition'):
            self.append('declare_domain',['root'],symbol=self.quantity(a),domain='zero',reason='Contradicts the admitted regime')

    def test_condition_signatures_pin_hidden_quantities_and_ignore_display_aliases(self):
        a,y,b=sp.symbols('a y b',real=True);self.units={q:'1' for q in (a,y,b)}
        self.root('root',y,b,conditions=(sp.Ne(a,0,evaluate=False),))
        signature=equation_signature(self.graph,'root',self.units)
        self.graph.names[a]='displayAlias'
        self.assertEqual(signature,equation_signature(self.graph,'root',self.units))
        self.units[a]='m'
        self.assertNotEqual(signature,equation_signature(self.graph,'root',self.units))
        self.units[a]='1';self.graph.nodes['root'].predicates=(sp.Gt(a,0,evaluate=False),)
        self.assertNotEqual(signature,equation_signature(self.graph,'root',self.units))

    def test_generated_predicate_signatures_are_stable_across_python_hash_seeds(self):
        code="""import sympy as s
from core.mathematics import EquationGraph
from core.mathematics.provenance import equation_signature
x,y,z,w=s.symbols('x y z w',real=True)
g=EquationGraph();g.add('law',y,1/x+1/(z-1)+1/(w+2),'Several denominators')
print(equation_signature(g,'law',{q:'1' for q in (x,y,z,w)}))
"""
        signatures=[subprocess.run([sys.executable,'-c',code],cwd=ROOT,env={**os.environ,'PYTHONHASHSEED':str(seed)},
                                   check=True,capture_output=True,text=True).stdout.strip() for seed in (1,2,31)]
        self.assertEqual(len(set(signatures)),1)

    def test_real_log_integral_retains_negative_coordinate_branch(self):
        from core.mathematics.validity import HoldsOnInterval
        x=sp.Symbol('x',real=True);y=sp.Function('y')(x)
        self.units={x:'1',y:'1'};self.root('ode',sp.diff(y,x),1/x)
        result=self.append('integrate',['ode'],symbol=self.quantity(x),name='C')
        equation=result.graph.nodes['operation.1'].equation
        self.assertEqual(equation.rhs,sp.log(sp.Abs(x))+sp.Symbol('C',real=True))
        self.assertTrue(any(isinstance(p,HoldsOnInterval) for p in result.graph.predicates_for('operation.1')))
        for point in (-3,-1,1,4):
            self.assertEqual(sp.diff(equation.rhs,x).subs(x,point),sp.Rational(1,point))

    def test_substitution_and_zero_application_respect_recorded_quantity_domains(self):
        x,y=sp.symbols('x y',real=True);self.units={x:'1',y:'1'}
        self.root('root',y,x);self.root('negative',x,-1,kind='constraint')
        self.append('declare_domain',['root'],symbol=self.quantity(x),domain='positive',reason='Strictly positive quantity')
        with self.assertRaisesRegex(MathematicsError,'validity condition'):
            self.append('substitute',['root'],relation='negative',symbol=self.quantity(x))
        with self.assertRaisesRegex(MathematicsError,'validity condition'):
            self.append('apply_zero',['root'],symbol=self.quantity(x),reason='Incompatible zero value')

    def test_real_root_primitive_keeps_its_radicand_condition(self):
        x=sp.Symbol('x',real=True);y=sp.Function('y')(x)
        self.units={x:'1',y:'1'};self.root('ode',sp.diff(y,x),sp.sqrt(x))
        result=self.append('integrate',['ode'],symbol=self.quantity(x),name='C')
        self.assertIn(sp.Ge(x,0,evaluate=False),result.graph.nodes['operation.1'].predicates)
        self.assertTrue(result.requires_lowering)
        for point in (1,4,9):
            self.assertEqual(sp.diff(result.graph.nodes['operation.1'].equation.rhs,x).subs(x,point),sp.sqrt(point))
        with self.assertRaisesRegex(MathematicsError,'validity condition'):
            result.graph.substitute('invalid','operation.1',{x:-1},'Outside the real primitive domain')

    def test_product_chain_rule_is_derived_and_evaluates_against_analytic_reference(self):
        t=sp.Symbol('tau',real=True);m=sp.Function('inventory')(t);T=sp.Function('state')(t)
        U=sp.Function('potential')(t);u=sp.Function('specific')(T);c=sp.Symbol('coefficient',real=True)
        self.units={t:'s',m:'kg',T:'K',U:'J',u:'J/kg',c:'J/(kg*K)'}
        self.root('inventory-definition',U,m*u,kind='definition')
        self.root('property-premise',u,c*T,kind='constitutive')
        self.append('differentiate',['inventory-definition'],symbol=self.quantity(t))
        result=self.append('substitute',['operation.1'],relation='property-premise',symbol=self.quantity(u))
        eq=result.graph.nodes['operation.2'].equation
        expected=c*(T*sp.diff(m,t)+m*sp.diff(T,t))
        self.assertEqual(sp.simplify(eq.rhs-expected),0)
        actual=eq.rhs.subs({m:2+t,T:300+3*t}).doit().subs({c:4,t:2})
        self.assertEqual(actual,4*(306+4*3))
        self.assertEqual(dimension(eq.lhs,result.units),dimension(eq.rhs,result.units))
        self.assertEqual(result.receipts[1].before[0][1],result.graph.nodes['operation.1'].equation)
        self.assertEqual(result.receipts[1].after[-1][1],eq)
        with self.assertRaises(TypeError):
            result.receipts[1].input_signatures['inventory-definition']='changed'

    def test_electrical_storage_uses_the_same_dependency_and_chain_operations(self):
        t=sp.Symbol('xi',real=True);L=sp.Function('L')(t);I=sp.Function('I')(t)
        linkage=sp.Function('linkage')(t);voltage=sp.Function('voltage')(t)
        self.units={t:'s',L:'H',I:'A',linkage:'Wb',voltage:'V'}
        self.root('storage',linkage,L*I,group='electrical',kind='constitutive')
        self.root('induction',voltage,sp.diff(linkage,t),group='field')
        self.append('change_dependencies',['storage'],group='electrical',symbol=self.quantity(L),dependencies=[],reason='Time-independent inductance over this model domain')
        self.append('differentiate',['operation.1'],group='electrical',symbol=self.quantity(t))
        result=self.append('substitute',['induction'],group='field',relation='operation.2',symbol=self.quantity(sp.diff(linkage,t)))
        eq=result.graph.nodes['operation.3'].equation;constant=sp.Symbol('L',real=True)
        self.assertEqual(sp.simplify(eq.rhs-constant*sp.diff(I,t)),0)
        self.assertEqual(eq.rhs.subs(I,sp.sin(2*t)).doit().subs({constant:3,t:0}),6)
        self.assertTrue(result.requires_lowering)
        self.assertTrue(any('Time-independent' in condition for condition in result.receipts[-1].conditions))

    def test_mechanical_conservation_and_constitutive_substitution_retain_distinction(self):
        t=sp.Symbol('t0',real=True);x=sp.Function('x')(t);m,k=sp.symbols('m k',positive=True)
        external=sp.Function('external')(t);restoring=sp.Function('restoring')(t)
        self.units={t:'s',x:'m',m:'kg',k:'N/m',external:'N',restoring:'N'}
        self.root('conservation',m*sp.diff(x,t,2),external-restoring,group='motion')
        self.root('constitutive',restoring,k*x,group='material',kind='constitutive')
        result=self.append('substitute',['conservation'],group='motion',relation='constitutive',symbol=self.quantity(restoring))
        eq=result.graph.nodes['operation.1'].equation
        self.assertEqual(sp.expand(eq.lhs-eq.rhs-(m*sp.diff(x,t,2)+k*x-external)),0)
        self.assertEqual(result.graph.nodes['constitutive'].kind,'constitutive')
        self.assertEqual(result.graph.nodes['operation.1'].inputs,('conservation','constitutive'))

    def test_cross_group_addition_is_governed_by_dimensions(self):
        a,b,c,d=sp.symbols('a b c d',real=True)
        self.units={q:'A' for q in (a,b,c,d)}
        self.root('first',a,b,group='alpha');self.root('second',c,d,group='beta')
        result=self.append('combine',['first','second'],group='coupled')
        self.assertEqual(result.graph.nodes['operation.1'].equation,sp.Eq(a+c,b+d,evaluate=False))
        self.assertTrue(result.graph.nodes['operation.1'].dependent)
        self.units[c]=self.units[d]='V'
        with self.assertRaises(MathematicsError):self.replay()

    def test_linear_isolation_keeps_cancelled_zero_coefficient_branch_explicit(self):
        a,x,b=sp.symbols('a x b',real=True);self.units={q:'1' for q in (a,x,b)}
        self.root('root',a*x,a*b)
        result=self.append('isolate',['root'],symbol=self.quantity(x))
        eq=result.graph.nodes['operation.1'].equation
        self.assertEqual(eq,sp.Eq(x,b,evaluate=False))
        self.assertTrue(any('a' in condition and 'neq' in condition for condition in result.receipts[0].conditions))
        # At a=0 the root is an identity and cannot determine x=b.
        self.assertEqual((self.graph.nodes['root'].equation.lhs-self.graph.nodes['root'].equation.rhs).subs(a,0),0)

    def test_substitution_keeps_the_same_singular_coefficient_condition(self):
        a,x,b,y=sp.symbols('a x b y',real=True);self.units={q:'1' for q in (a,x,b,y)}
        self.root('root',y,x+1);self.root('relation',a*x,a*b,kind='definition')
        result=self.append('substitute',['root'],relation='relation',symbol=self.quantity(x))
        self.assertEqual(result.graph.nodes['operation.1'].equation.rhs,b+1)
        self.assertTrue(any('a' in c and 'neq' in c for c in result.receipts[-1].conditions))

    def test_source_signatures_ignore_labels_but_detect_changed_content_and_units(self):
        a,b=sp.symbols('a b',real=True);self.units={a:'kg',b:'kg'};self.root('root',a,b)
        result=self.append('expand',['root'])
        signature=self.definition['operations'][0]['sourceSignatures']['root']
        self.graph.nodes['root'].title='A different display title';self.graph.names[a]='renamed'
        self.assertEqual(signature,equation_signature(self.graph,'root',self.units))
        self.graph.nodes['root'].equation=sp.Eq(a,2*b,evaluate=False)
        with self.assertRaisesRegex(MathematicsError,'same ID'):self.replay()
        self.graph.nodes['root'].equation=sp.Eq(a,b,evaluate=False)
        self.units[a]=self.units[b]='g'
        with self.assertRaisesRegex(MathematicsError,'same ID'):self.replay()
        self.assertEqual(result.graph.nodes['root'].equation,sp.Eq(a,b,evaluate=False))

    def test_failed_append_is_atomic_and_undo_redo_preserve_the_branch(self):
        a,b=sp.symbols('a b',real=True);self.units={a:'kg',b:'kg'};self.root('root',a,b)
        self.append('expand',['root']);stored=copy.deepcopy(self.definition)
        source_before=self.graph.rows();units_before=copy.deepcopy(self.units)
        with self.assertRaises(MathematicsError):self.append('isolate',['root'],symbol='missing')
        self.assertEqual(self.definition,stored);self.assertEqual(self.graph.rows(),source_before);self.assertEqual(self.units,units_before)
        undone=self.action('undo');self.assertNotIn('operation.1',undone.graph.nodes)
        self.assertEqual(len(self.definition['operations']),1)
        redone=self.action('redo');self.assertEqual(redone.graph.nodes['operation.1'].equation,sp.Eq(a,b,evaluate=False))
        self.action('undo');self.append('factor',['root'])
        self.assertEqual([op['kind'] for op in self.definition['operations']],['factor'])

    def test_unsigned_legacy_history_is_never_assigned_new_past_signatures(self):
        a,b=sp.symbols('a b',real=True);self.units={a:'1',b:'1'};self.root('root',a,b)
        self.definition['operations']=[{'kind':'expand','family':'arbitrary','sources':['root']}];self.definition['cursor']=1
        result=self.replay()
        self.assertNotIn('sourceSignatures',result.definition['operations'][0])
        self.assertEqual({},result.receipts[0].input_signatures)
        self.assertIn('root',result.receipts[0].calculated_input_signatures)
        self.assertEqual('legacy/unsigned',result.receipts[0].signature_status)
        self.assertTrue(result.requires_lowering)
        self.assertEqual(self.definition,result.definition)

    def test_partial_integration_constant_retains_other_dependencies_and_units(self):
        r,t=sp.symbols('r0 tau0',real=True);f=sp.Function('f')(r,t)
        self.units={r:'m',t:'s',f:'Pa'};self.root('root',sp.diff(f,r),0)
        result=self.append('integrate',['root'],symbol=self.quantity(r),name='integrationQuantity')
        constant=result.introduced['integrationQuantity']
        self.assertEqual(constant.args,(t,));self.assertEqual(dimension(constant,result.units),dimension(f,self.units))

    def test_reynolds_transport_uses_the_declared_evolution_coordinate(self):
        coordinate=sp.Symbol('arbitrary_clock',real=True);density=sp.Function('density')(coordinate)
        self.units={coordinate:'s',density:'kg/m3'}
        self.root('root',VolumeIntegral(sp.Derivative(density,coordinate,evaluate=False)),0)
        result=self.append('reynolds',['root'])
        equation=result.graph.nodes['operation.1'].equation
        self.assertTrue(equation.has(BoundaryFlux))
        self.assertTrue(equation.has(sp.Derivative(VolumeIntegral(density),coordinate,evaluate=False)))
        self.assertEqual(dimension(equation.lhs,result.units),{'M':1,'T':-1})
        self.assertIn('operation.1.theorem.1',[key for key,_ in result.receipts[0].after])

    def test_malformed_signature_and_nonstring_inputs_are_strictly_rejected(self):
        for sources,signatures in [(['root'],{'root':'bad'}),(['root'],{}),([{}],{})]:
            definition={'format':FORMAT,'version':1,'cursor':1,'operations':[{'kind':'expand','family':'arbitrary','sources':sources,'sourceSignatures':signatures}]}
            with self.assertRaises(MathematicsError):read_definition(definition)


if __name__=='__main__':unittest.main()
