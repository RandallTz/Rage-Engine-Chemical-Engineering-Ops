"""Operations change equations; geometry/configuration alone cannot inject laws."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sympy as sp
from core.modelo.equation_manipulation import EquationGraph
from core.modelo.operation_journal import JournalError
from core.balances import momentum_derivation as momentum
from core.balances.momentum_reductions import WALL_FLAGS,reduction_graphs


def recorded(flags):
    journal={'format':momentum.FORMAT,'version':1,'volumes':{}}
    journal=momentum.edit_journal(journal,'node',{'kind':'start'})
    for flag in flags:journal=momentum.edit_journal(journal,'node',{'kind':'set_assumption','name':flag,'value':True})
    return journal


class EquationManipulationTests(unittest.TestCase):
    def test_generic_algebra_and_differentiation_are_not_equipment_rules(self):
        x,y,t,a,b=sp.symbols('x y t a b',real=True);graph=EquationGraph()
        graph.add('input',a*x+b,y,'Arbitrary affine equation')
        result=graph.isolate('isolated','input',x,'Isolate an arbitrary unknown')
        self.assertEqual(sp.simplify(result.rhs-(y-b)/a),0)
        self.assertTrue(graph.nodes['isolated'].predicates)
        # The unknown must be declared dependent before differentiating this
        # identity. Treating x as a constant would falsely derive 0 = t.
        graph.substitute('specialized','isolated',{x:sp.Function('x')(t),a:2,b:3,y:t**2},'Substitute independent inputs')
        derivative=graph.differentiate('rate','specialized',t,'Differentiate the result')
        self.assertEqual(derivative.rhs,t)
        with self.assertRaises(JournalError):graph.add('bad',x,y,'Missing source',inputs=('missing',))

    def test_unknown_branches_are_not_silently_selected(self):
        x,y=sp.symbols('x y',real=True);graph=EquationGraph();graph.add('square',x*x,y,'Square relation')
        with self.assertRaises(JournalError):graph.isolate('branch','square',x,'Needs a branch')

    def test_profile_is_integrated_and_boundary_constants_are_actually_solved(self):
        state=momentum.fundamental();state.update({k:True for k in WALL_FLAGS})
        graph,relations,_,_=reduction_graphs(state);profile=relations['profile']
        r=next(s for s in profile.rhs.free_symbols if str(s)=='r');R=next(s for s in profile.rhs.free_symbols if str(s)=='R')
        s,_,_=momentum.reduced_relations()
        self.assertEqual(sp.simplify(profile.rhs.subs(r,R)),0)
        ode=sp.diff(r*sp.diff(profile.rhs,r),r)/r+s['loss']/(s['mu']*s['L'])
        self.assertEqual(sp.simplify(ode),0)
        independent_flux=sp.integrate(2*sp.pi*r*profile.rhs,(r,0,R))
        self.assertEqual(sp.simplify(independent_flux-sp.pi*R**4*s['loss']/(8*s['mu']*s['L'])),0)
        self.assertIn('wall.boundary-constant',graph.nodes)

    def test_missing_wall_condition_leaves_an_undetermined_constant(self):
        state=momentum.fundamental();state.update({k:True for k in WALL_FLAGS});state['noSlipWall']=False
        graph,relations,_,_=reduction_graphs(state)
        self.assertNotIn('loss',relations)
        self.assertIn('C_2',str(graph.nodes['wall.velocity-general'].equation))
        # The same generic operations handle a moving boundary: no second
        # prewritten profile is selected by a scenario name.
        R,U=sp.symbols('R U',positive=True);r=next(v for v in graph.nodes['wall.velocity-general'].equation.free_symbols if str(v)=='r')
        graph.substitute('moving-eval','wall.velocity-general',{r:R},'Evaluate at another boundary')
        graph.substitute('moving-data','moving-eval',{sp.Function('u')(R):U},'Declare a nonzero wall velocity')
        C=sp.Symbol('C_2',real=True);constant=graph.isolate('moving-constant','moving-data',C,'Solve the same boundary constant')
        profile=graph.substitute('moving-profile','wall.velocity-general',{C:constant.rhs},'Reconstruct the changed profile')
        self.assertEqual(sp.simplify(profile.rhs.subs(r,R)-U),0)

    def test_pressure_and_inventory_require_their_own_recorded_operations(self):
        flags=['pressureStress','negligibleConvection','negligibleViscousStress','zeroLocalAccumulation','uniformGravity','referenceDensity','verticalGravity']
        journal=recorded(flags);before=copy.deepcopy(journal)
        development=momentum.describe_volume(journal,'node')
        self.assertNotIn('storage.pressure',str(development['finalSteps']))
        self.assertEqual(before,journal)
        journal=momentum.edit_journal(journal,'node',{'kind':'set_assumption','name':'pressureReference','value':True})
        development=momentum.describe_volume(journal,'node')
        self.assertIn('storage.pressure',str(development['finalSteps']))
        self.assertNotIn('storage.height',str(development['couplingSteps']))
        journal=momentum.edit_journal(journal,'node',{'kind':'set_assumption','name':'prismaticStorage','value':True})
        self.assertIn('storage.height',str(momentum.describe_volume(journal,'node')['couplingSteps']))
        journal=momentum.edit_journal(journal,'node',{'kind':'undo'})
        self.assertNotIn('storage.height',str(momentum.describe_volume(journal,'node')['couplingSteps']))

    def test_each_graph_operation_publishes_actual_inputs_and_conditions(self):
        state=momentum.fundamental();state.update({k:True for k in WALL_FLAGS})
        graph,_,_,_=reduction_graphs(state)
        rows=graph.rows();self.assertGreater(len(rows),12)
        for row in rows:
            node=graph.nodes[row['id']]
            self.assertEqual(len(node.inputs),len(row['derivation']['beforeLatex']))
            self.assertTrue(all(source in graph.nodes for source in node.inputs))


if __name__=='__main__':unittest.main()
