"""Equation authoring invariants, independent of the requested pressure curves."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sympy as sp
from core.balances.material_equations import equation_graph,VolumeIntegral,BoundaryFlux,Divergence
from core.modelo.equation_workbench import describe,describe_for_authoring,edit,build,ensure_executable,fundamental_report,FORMAT
from core.modelo.operation_journal import JournalError
from core.balances import material_derivation as material,momentum_derivation as momentum
from core.compilador.hydraulics import HydraulicSystem
from core.compilador.presentation import formulation_summary,symbolic_formulation_summary
from core.modelo import leer_modelo_comun

ROOT=Path(__file__).resolve().parents[1]
if not (ROOT/'.tmp/hydraulic-models.json').exists():
    import subprocess
    subprocess.run(['node','frontend/verificar_hydraulics.mjs','--inputs-only'],cwd=ROOT,check=True)
BASE=json.loads((ROOT/'.tmp/hydraulic-models.json').read_text(encoding='utf8'))[1]
# These tests exercise equation handoffs; choose the supported implicit method.
BASE['estudio']['metodoSolicitado']='bdf'


class EquationWorkbenchTests(unittest.TestCase):
    symbolic_publications=[]
    @classmethod
    def tearDownClass(cls):
        model=copy.deepcopy(BASE)
        result=edit(model,{'kind':'append','operation':{'kind':'combine','family':'matter','sources':['matter.upper.1.closed','matter.lower.1.closed']}})
        model['motores']['equationWorkbench']=result['definition']
        stale=copy.deepcopy(model);stale['volumenes'][0]['supuestos']['materia']['vista']='campo'
        (ROOT/'.tmp/equation-workbench-publications.json').write_text(json.dumps({'source':describe(BASE),'combined':result,'recovered':describe_for_authoring(stale),'draft':fundamental_report({'format':'rage.fundamental-equations','version':1,'modelId':'blank'}),'symbolic':cls.symbolic_publications,'compilation':HydraulicSystem(model).report()}),encoding='utf8')
    def model(self):return copy.deepcopy(BASE)
    def append(self,model,operation):
        result=edit(model,{'kind':'append','operation':operation})
        model['motores']['equationWorkbench']=result['definition']
        return result
    def quantity(self,report,name):return next(q['id'] for q in report['quantities'] if q['name']==name)

    def test_invalid_calculus_history_blocks_transform_and_recovers_without_erasing_it(self):
        draft={'format':'rage.fundamental-equations','version':3,'modelId':'validity-regression',
               'materialJournal':{'origin':'recorded','operations':[]},'ports':[],
               'definition':{'format':FORMAT,'version':1,'operations':[],'cursor':0}}
        for name,unit in [('force','N'),('stiffness','N/m'),('position','m')]:
            draft['definition']=fundamental_report(draft,{'kind':'append','operation':{
                'kind':'declare_symbol','family':'matter','name':name,'unit':unit}})['definition']
        draft['definition']=fundamental_report(draft,{'kind':'append','operation':{
            'kind':'declare_relation','family':'matter','left':'force','right':'stiffness*position',
            'relationKind':'constitutive','reason':'Declared mechanical premise'}})['definition']
        operation={'kind':'differentiate','family':'matter','sources':['operation.4'],'symbol':'position'}
        with self.assertRaisesRegex(JournalError,'depending on the selected coordinate'):
            fundamental_report(draft,{'kind':'append','operation':operation})
        # An older unsigned record stays saved, but cannot publish the former
        # false consequence 0 = stiffness or reach Transform/Solve as a prefix.
        draft['definition']['operations'].append(operation);draft['definition']['cursor']=5
        before=copy.deepcopy(draft)
        recovered=fundamental_report(draft)
        self.assertEqual(recovered['replay']['failedOperation'],5)
        self.assertEqual(recovered['definition'],draft['definition'])
        self.assertFalse(recovered['execution']['supported'])
        self.assertNotIn('operation.5',[row['id'] for row in recovered['equations']])
        with self.assertRaises(JournalError):symbolic_formulation_summary(draft)
        self.assertEqual(draft,before)
        undone=fundamental_report(draft,{'kind':'undo'})
        self.assertEqual(undone['definition']['cursor'],4)
        self.assertEqual(len(undone['definition']['operations']),5)
        draft['definition']=undone['definition']
        with self.assertRaises(JournalError):fundamental_report(draft,{'kind':'redo'})
        self.symbolic_publications.append(recovered)

    def test_real_root_substitution_is_rejected_in_the_public_symbolic_handoff(self):
        draft={'format':'rage.fundamental-equations','version':3,'modelId':'real-root-regression',
               'materialJournal':{'origin':'recorded','operations':[]},'ports':[],
               'definition':{'format':FORMAT,'version':1,'operations':[],'cursor':0}}
        for name in ('rootOutput','rootInput'):
            draft['definition']=fundamental_report(draft,{'kind':'append','operation':{
                'kind':'declare_symbol','family':'matter','name':name,'unit':'1'}})['definition']
        initial=copy.deepcopy(draft)
        for exponent in ('1/2','0.5'):
            draft=copy.deepcopy(initial)
            for left,right in [('rootOutput',f'(rootInput-2)^({exponent})'),('rootInput','1')]:
                draft['definition']=fundamental_report(draft,{'kind':'append','operation':{
                    'kind':'declare_relation','family':'matter','left':left,'right':right,
                    'relationKind':'definition','reason':'Declared N1 regression premise'}})['definition']
            operation={'kind':'substitute','family':'matter','sources':['operation.3'],'relation':'operation.4','symbol':'rootInput'}
            with self.assertRaisesRegex(JournalError,'validity condition'):
                fundamental_report(draft,{'kind':'append','operation':operation})
            draft['definition']['operations'].append(operation);draft['definition']['cursor']=5
            recovered=fundamental_report(draft)
            self.assertEqual(recovered['replay']['failedOperation'],5)
            self.assertFalse(recovered['execution']['supported'])
            with self.assertRaises(JournalError):symbolic_formulation_summary(draft)
            self.symbolic_publications.append(recovered)

    def test_recorded_domains_select_a_branch_and_reach_transform_without_solver_fallback(self):
        model=self.model()
        for name,unit in [('branchQuantity','m/s'),('branchParameter','m^2/s^2')]:
            self.append(model,{'kind':'declare_symbol','family':'matter','name':name,'unit':unit})
        self.append(model,{'kind':'declare_relation','family':'matter','left':'branchQuantity^2','right':'branchParameter',
                           'relationKind':'constitutive','reason':'Explicit regression premise; not derived from conservation'})
        for name in ['branchParameter','branchQuantity']:
            self.append(model,{'kind':'declare_domain','family':'matter','sources':['operation.3'],'symbol':name,
                               'domain':'positive','reason':'Positive validity regime for the declared test relation'})
        report=self.append(model,{'kind':'isolate','family':'matter','sources':['operation.3'],'symbol':'branchQuantity',
                                  'domains':['operation.4','operation.5']})
        branch=next(row for row in report['equations'] if row['id']=='operation.6')
        self.assertEqual([b['admitted'] for b in branch['derivation']['branches']].count(True),1)
        self.assertFalse(report['execution']['supported'])
        summary=formulation_summary(model)
        rows=next(f for f in summary['families'] if f['id']=='matter')['volumes'][-1]['steps']
        self.assertEqual(next(row for row in rows if row['id']=='operation.6'),branch)
        with self.assertRaises(JournalError):ensure_executable(model)
        with self.assertRaises(JournalError):HydraulicSystem(model).report()
        self.symbolic_publications.append(report)
        # A domain edit behind the same condition ID requires actual replay review.
        changed=copy.deepcopy(model)
        changed['motores']['equationWorkbench']['operations'][4]['domain']='negative'
        recovered=describe_for_authoring(changed)
        self.assertEqual(recovered['replay']['failedOperation'],6)
        self.assertEqual(recovered['definition'],changed['motores']['equationWorkbench'])
        self.assertFalse(recovered['execution']['supported'])
        self.symbolic_publications.append(recovered)

    def test_interval_and_singleton_cases_use_the_same_persisted_workbench_and_summary(self):
        model=self.model()
        for name in ['caseQuantity','caseParameter']:
            self.append(model,{'kind':'declare_symbol','family':'matter','name':name,'unit':'1'})
        self.append(model,{'kind':'declare_relation','family':'matter','left':'caseQuantity^2','right':'caseParameter',
                           'relationKind':'constitutive','reason':'Declared regression premise, not a conservation consequence'})
        self.append(model,{'kind':'declare_domain','family':'matter','sources':['operation.3'],'symbol':'caseParameter',
                           'domain':'zero','reason':'Explicit zero-parameter case'})
        self.append(model,{'kind':'declare_domain','family':'matter','sources':['operation.3'],'symbol':'caseQuantity',
                           'domain':'nonnegative','reason':'Nonnegative quantity regime'})
        operation={'kind':'isolate','family':'matter','sources':['operation.3'],'symbol':'caseQuantity','domains':['operation.4','operation.5']}
        report=self.append(model,operation)
        case=next(row for row in report['equations'] if row['id']=='operation.6.case')
        self.assertEqual(case['derivation']['rule'],'domain_case')
        self.assertEqual(case['derivation']['inputIds'],['operation.3','operation.4','operation.5'])
        summary=formulation_summary(model)
        self.assertIn(case,next(f for f in summary['families'] if f['id']=='matter')['volumes'][-1]['steps'])
        draft={'format':'rage.fundamental-equations','version':3,'modelId':'symbolic-case-handoff',
               'materialJournal':{'origin':'recorded','operations':[]},'ports':[],'definition':report['definition']}
        symbolic=fundamental_report(draft)
        symbolic_case=next(row for row in symbolic['equations'] if row['id']=='operation.6.case')
        symbolic_summary=symbolic_formulation_summary(draft)
        self.assertIn(symbolic_case,next(f for f in symbolic_summary['families'] if f['id']=='matter')['volumes'][0]['steps'])
        self.assertFalse(report['execution']['supported']);self.symbolic_publications.append(report)
        for _ in range(3):
            updated=edit(model,{'kind':'undo'});model['motores']['equationWorkbench']=updated['definition']
        for name,lower,upper in [('caseParameter','1','4'),('caseQuantity','1','2')]:
            self.append(model,{'kind':'declare_domain','family':'matter','sources':['operation.3'],'symbol':name,
                               'domain':'interval','lower':lower,'upper':upper,'lowerOpen':False,'upperOpen':False,
                               'reason':'Bounded exact interval regime'})
        report=self.append(model,operation)
        self.assertNotIn('operation.6.case',[row['id'] for row in report['equations']])
        self.assertEqual(describe( model),report)
        with self.assertRaises(JournalError):ensure_executable(model)
        self.symbolic_publications.append(report)

    def test_dimensioned_cases_and_unit_conversions_survive_all_model_handoffs(self):
        model=self.model()
        for name,unit in [('unitQuantity','cm/s'),('unitParameter','m^2/s^2')]:
            self.append(model,{'kind':'declare_symbol','family':'matter','name':name,'unit':unit})
        self.append(model,{'kind':'declare_relation','family':'matter','left':'unitQuantity^2','right':'unitParameter',
                           'relationKind':'constitutive','reason':'Explicit regression premise, not deduced from conservation'})
        for name,lower,upper,unit in [('unitParameter','40000','40000','cm^2/s^2'),('unitQuantity','100','200','cm/s')]:
            self.append(model,{'kind':'declare_domain','family':'matter','sources':['operation.3'],'symbol':name,
                               'domain':'interval','lower':lower,'upper':upper,'lowerOpen':False,'upperOpen':False,
                               'endpointUnit':unit,'reason':'Declared dimensioned validity regime'})
        report=self.append(model,{'kind':'isolate','family':'matter','sources':['operation.3'],'symbol':'unitQuantity',
                                  'domains':['operation.4','operation.5']})
        self.assertNotIn('replay',report);self.assertEqual(describe(model),report)
        expected=[row for row in report['equations'] if row['id'].startswith(('operation.4','operation.5','operation.6'))]
        self.assertEqual(len(expected),6)
        self.assertIn('\\mathrm{m}',next(row for row in expected if row['id']=='operation.6')['latex'])
        summary=formulation_summary(model)
        rows=next(f for f in summary['families'] if f['id']=='matter')['volumes'][-1]['steps']
        for row in expected:self.assertIn(row,rows)
        draft={'format':'rage.fundamental-equations','version':3,'modelId':'dimensioned-case-handoff',
               'materialJournal':{'origin':'recorded','operations':[]},'ports':[],'definition':report['definition']}
        symbolic=fundamental_report(draft);summary=symbolic_formulation_summary(draft)
        rows=next(f for f in summary['families'] if f['id']=='matter')['volumes'][0]['steps']
        for row in symbolic['equations']:
            if row['id'].startswith(('operation.4','operation.5','operation.6')):self.assertIn(row,rows)
        self.assertFalse(report['execution']['supported'])
        with self.assertRaises(JournalError):ensure_executable(model)
        with self.assertRaises(JournalError):HydraulicSystem(model).report()
        self.symbolic_publications.extend([report,symbolic])
        changed=copy.deepcopy(model);changed['motores']['equationWorkbench']['operations'][3]['endpointUnit']='m^2/s^2'
        recovered=describe_for_authoring(changed)
        self.assertEqual(recovered['replay']['failedOperation'],6)
        self.assertEqual(recovered['definition'],changed['motores']['equationWorkbench'])
        self.assertFalse(recovered['execution']['supported']);self.symbolic_publications.append(recovered)
        updated=edit(model,{'kind':'undo'});model['motores']['equationWorkbench']=updated['definition']
        self.assertNotIn('operation.6.case',[row['id'] for row in updated['equations']])
        self.assertEqual(edit(model,{'kind':'redo'}),report)

    def test_component_and_domain_sums_cancel_internal_flux_without_extra_states(self):
        model=self.model();model['componentes'].append({'id':2,'nombre':'Another species','simbolo':'B'})
        for v in model['volumenes']:v['componenteIds']=[1,2]
        for s in model['corrientes']:s['componenteIds']=[1,2]
        all_rates=[]
        for v in model['volumenes']:
            graph,final,bindings=equation_graph(model,v['id'],v['supuestos']['materia'])
            independent=[graph.nodes[i].equation for i in final if not graph.nodes[i].dependent]
            self.assertEqual(len(independent),2)
            total=graph.nodes[f"matter.{v['id']}.total"]
            self.assertTrue(total.dependent)
            self.assertEqual(sp.simplify(total.equation.rhs-sum(e.rhs for e in independent)),0)
            all_rates.extend(e.rhs for e in independent)
        self.assertEqual(sp.simplify(sum(all_rates)),0)

    def test_names_and_numeric_binding_configuration_do_not_inject_equations(self):
        model=self.model();original=describe(model)['equations']
        model['nombre']='Different experiment'
        for i,v in enumerate(model['volumenes']):v['nombre']='Arbitrary domain '+str(i)
        del model['motores']['hydraulicNetwork']
        self.assertEqual(original,describe(model)['equations'])
        for row in original:
            self.assertNotIn('floor',row['latex']);self.assertNotIn('surface',row['latex'])

    def test_every_hydraulic_source_row_has_consistent_declared_dimensions(self):
        from core.modelo.equation_workbench import _dimension
        graph,_,_,units,*_=build(self.model())
        for key,node in graph.nodes.items():
            with self.subTest(equation=key):
                left,right=_dimension(node.equation.lhs,units),_dimension(node.equation.rhs,units)
                if left is not None and right is not None:self.assertEqual(left,right)

    def test_bound_momentum_ports_use_the_material_component_flow_identities(self):
        graph,*_=build(self.model());t=sp.Symbol('t',real=True)
        rhs=graph.nodes['momentum.channel.transport.x.ports'].equation.rhs
        self.assertTrue(rhs.has(sp.Function('q__s1__1')(t)))
        self.assertTrue(rhs.has(sp.Function('q__s2__1')(t)))
        self.assertFalse(any(f.func.__name__.startswith('port_mass_') for f in rhs.atoms(sp.Function)))

    def test_combination_undo_redo_and_persistent_roundtrip(self):
        model=self.model();sources=['matter.'+v['id']+'.1.closed' for v in model['volumenes']]
        result=self.append(model,{'kind':'combine','family':'matter','sources':sources})
        graph,*_=build(model)
        self.assertEqual(graph.nodes['operation.1'].equation.rhs,0)
        self.assertTrue(graph.nodes['operation.1'].dependent)
        self.assertEqual(graph.nodes['operation.1'].inputs,tuple(sources))
        self.assertEqual(leer_modelo_comun(model)['motores']['equationWorkbench'],result['definition'])
        model['motores']['equationWorkbench']=edit(model,{'kind':'undo'})['definition']
        self.assertEqual(model['motores']['equationWorkbench']['cursor'],0)
        self.assertEqual(len(model['motores']['equationWorkbench']['operations']),1)
        self.assertEqual(edit(model,{'kind':'redo'})['equations'][-1],result['equations'][-1])

    def test_primitives_can_rebuild_local_integral_gauss_and_reynolds(self):
        model=self.model();self.append(model,{'kind':'volume_integrate','family':'matter','sources':['matter.upper.1.local']})
        self.append(model,{'kind':'gauss','family':'matter','sources':['operation.1']})
        result=self.append(model,{'kind':'reynolds','family':'matter','sources':['operation.2']})
        graph,*_=build(model);eq=graph.nodes['operation.3'].equation
        self.assertTrue(eq.has(BoundaryFlux));self.assertIn('operation.3.theorem.1',graph.nodes)
        self.assertTrue(result['execution']['supported'])
        with self.assertRaises(JournalError):self.append(model,{'kind':'gauss','family':'matter','sources':['matter.upper.1.closed']})

    def test_physical_assumptions_change_expressions_and_dynamic_law_is_retained(self):
        model=self.model();state=material.fundamental_formulation()
        full,_,_=equation_graph(model,'upper',state)
        state['campo']={**state['campo'],'sinReaccion':True,'sinConveccion':True,'sinDifusion':True}
        reduced,final,_=equation_graph(model,'upper',state)
        self.assertEqual(reduced.nodes[final[0]].equation.rhs,0)
        self.assertNotEqual(full.nodes['matter.upper.1.local'].equation,reduced.nodes[final[0]].equation)
        state['sinAcumulacion']=True
        constrained,final,_=equation_graph(model,'upper',state)
        self.assertTrue(constrained.nodes[final[0]].equation.lhs.has(sp.Derivative))
        self.assertEqual(constrained.nodes['matter.upper.1.stationary'].kind,'constraint')

    def test_pinned_operation_detects_changed_algebra_behind_the_same_source_id(self):
        model=self.model();source='matter.upper.1.closed'
        self.append(model,{'kind':'expand','family':'matter','sources':[source]})
        saved=copy.deepcopy(model['motores']['equationWorkbench'])
        self.assertEqual(set(saved['operations'][0]['sourceSignatures']),{source})
        changed=copy.deepcopy(model)
        field=changed['volumenes'][0]['supuestos']['materia']['campo']
        field.update(sinReaccion=False,sinGeneracion=False,sinConsumo=False)
        entry=changed['motores']['materialDerivation']['volumes']['upper']
        entry['operations'].append({'id':'retain-source','title':'Retain material sources','changes':{'campo':copy.deepcopy(field)}})
        if 'cursor' in entry:entry['cursor']=len(entry['operations'])
        report=describe_for_authoring(changed)
        self.assertEqual(report['replay']['failedOperation'],1)
        self.assertIn('same ID',report['replay']['message'])
        self.assertIn(source,{row['id'] for row in report['equations']})
        self.assertEqual(report['definition'],saved)
        with self.assertRaises(JournalError):ensure_executable(changed)
        undone=edit(changed,{'kind':'undo'})
        self.assertEqual(undone['definition']['operations'],saved['operations'])
        self.assertEqual(undone['definition']['cursor'],0)

    def test_dimension_checked_definitions_do_not_masquerade_as_derived_laws(self):
        model=self.model();report=self.append(model,{'kind':'declare_symbol','family':'matter','name':'inventoryA','unit':'kg'})
        report=self.append(model,{'kind':'declare_symbol','family':'matter','name':'inventoryB','unit':'kg'})
        self.append(model,{'kind':'declare_symbol','family':'matter','name':'duration','unit':'s'})
        with self.assertRaisesRegex(JournalError,'incompatible dimensions'):
            self.append(model,{'kind':'declare_relation','family':'matter','left':'inventoryA','right':'duration','reason':'A deliberately invalid relation'})
        report=self.append(model,{'kind':'declare_relation','family':'matter','left':'inventoryA','right':'2*inventoryB','reason':'Declared inventory ratio'})
        self.assertFalse(report['execution']['supported'])
        self.assertEqual(report['equations'][-1]['kind'],'definition')
        with self.assertRaises(JournalError):ensure_executable(model)
        with self.assertRaises(Exception):self.append(model,{'kind':'declare_relation','family':'matter','left':'inventoryA','right':"__import__('os')",'reason':'Must not evaluate code'})

    def test_incompatible_equations_cannot_be_added_and_generation_dimensions_are_not_gravity(self):
        model=self.model()
        with self.assertRaisesRegex(JournalError,'compatible dimensions'):
            self.append(model,{'kind':'combine','family':'matter','sources':['matter.upper.1.closed','matter.upper.total-definition']})
        from core.modelo.equation_workbench import _dimension
        dim=_dimension(sp.Function('g__upper__1')(sp.Symbol('t',real=True)),{})
        self.assertEqual(dim,{'M':1,'L':-3,'T':-1})

    def test_ui_aliases_are_replaced_by_stable_quantity_identities(self):
        model=self.model();report=describe(model)
        a=next(q for q in report['quantities'] if q['name']=='m__upper__1(t)')
        b=next(q for q in report['quantities'] if q['name']=='m__lower__1(t)')
        report=self.append(model,{'kind':'declare_relation','family':'matter','left':a['input'],'right':b['input'],'reason':'Declared comparison'})
        operation=report['definition']['operations'][0]
        self.assertEqual(operation['left'],a['id']);self.assertEqual(operation['right'],b['id'])
        self.assertEqual(describe(model)['equations'][-1]['latex'],report['equations'][-1]['latex'])

    def test_source_history_rewinds_to_cauchy_and_can_be_restored(self):
        model=self.model();journal=model['motores']['momentumDerivation'];count=len(journal['volumes']['channel']['operations'])
        journal=momentum.edit_journal(journal,'channel',{'kind':'seek','index':0})
        self.assertEqual(journal['volumes']['channel']['cursor'],0)
        self.assertEqual(len(journal['volumes']['channel']['operations']),count)
        self.assertEqual(momentum.describe_volume(journal,'channel')['formulation']['form'],'local')
        journal=momentum.edit_journal(journal,'channel',{'kind':'seek','index':count})
        self.assertEqual(momentum.describe_volume(journal,'channel')['formulation']['form'],'hydraulic')

    def test_exact_operation_graph_reaches_transform_solve_and_results_report(self):
        model=self.model();self.append(model,{'kind':'combine','family':'matter','sources':['matter.upper.1.closed','matter.lower.1.closed']})
        summary=formulation_summary(model)
        handed=next(v for f in summary['families'] if f['id']=='matter' for v in f['volumes'] if v['volumeId']=='system')['steps'][-1]
        report=HydraulicSystem(model).report()['equationWorkbench']
        self.assertEqual(handed,report['equations'][-1])
        np_rates=HydraulicSystem(model).rhs(0,HydraulicSystem(model).inicial())
        self.assertEqual(float(np_rates[0]+np_rates[1]),0)

    def test_scope_does_not_accidentally_couple_fields_of_distinct_domains(self):
        model=self.model()
        for entry in model['motores']['momentumDerivation']['volumes'].values():entry['cursor']=0
        graph,*_=build(model)
        a=graph.nodes['momentum.upper.local.x'].equation.atoms(sp.Function)
        b=graph.nodes['momentum.lower.local.x'].equation.atoms(sp.Function)
        self.assertFalse(a&b)

    def test_material_inventory_and_momentum_geometry_share_expression_identity(self):
        model=self.model();graph,*_=build(model)
        mass=graph.nodes['matter.upper.total-definition'].equation.lhs
        height=graph.nodes['momentum.upper.storage.height'].equation
        self.assertTrue(height.rhs.has(mass))
        self.assertEqual(graph.nodes['momentum.channel.path.mass-compatibility'].equation.lhs,0)
        flow=sp.Function('q__s1__1')(sp.Symbol('t',real=True))
        self.assertTrue(graph.nodes['momentum.channel.path.pressure-form'].equation.has(sp.diff(flow,sp.Symbol('t',real=True))))

    def test_endpoint_returns_replay_and_rejects_missing_inputs(self):
        from fastapi import HTTPException
        from backend.api_modelo import equation_workbench
        result=equation_workbench({'modelo':self.model()})
        self.assertEqual(result['modelId'],BASE['id'])
        with self.assertRaises(HTTPException) as failure:equation_workbench({'modelo':self.model(),'action':{'kind':'append','operation':{'kind':'combine','family':'matter','sources':['missing']}}})
        self.assertEqual(failure.exception.status_code,422)

    def test_preview_is_pure_and_record_revalidates_the_current_source(self):
        from backend.api_modelo import equation_workbench
        model=self.model();before=copy.deepcopy(model)
        action={'kind':'append','operation':{'kind':'combine','family':'matter','sources':['matter.upper.1.closed','matter.lower.1.closed']}}
        preview=equation_workbench({'modelo':model,'action':action})
        self.assertEqual(model,before,'Preview must not persist or mutate any source.')
        self.assertEqual(preview['definition']['cursor'],1)
        self.assertEqual(equation_workbench({'modelo':model})['definition']['cursor'],0)
        recorded=equation_workbench({'modelo':model,'action':action})
        self.assertEqual(recorded,preview)
        model['motores']['equationWorkbench']=recorded['definition']
        self.assertEqual(equation_workbench({'modelo':model})['definition']['cursor'],1)

    def test_changed_source_keeps_fundamentals_and_full_history_without_silent_execution(self):
        from backend.api_modelo import equation_workbench
        model=self.model()
        self.append(model,{'kind':'expand','family':'matter','sources':['matter.upper.1.local']})
        self.append(model,{'kind':'combine','family':'matter','sources':['matter.upper.1.closed','matter.lower.1.closed']})
        model['volumenes'][0]['supuestos']['materia']['vista']='campo'
        journal=model['motores']['materialDerivation']['volumes']['upper']
        journal['operations'].append({'id':'review-local-form','title':'Return to local form','changes':{'vista':'campo'}})
        snapshot=copy.deepcopy(model)
        report=equation_workbench({'modelo':model})
        self.assertEqual(model,snapshot,'Reading recovery must never modify the saved model.')
        self.assertEqual(report['replay']['completed'],1)
        self.assertEqual(report['replay']['failedOperation'],2)
        self.assertEqual(report['definition'],snapshot['motores']['equationWorkbench'])
        self.assertFalse(report['execution']['supported'])
        self.assertTrue(any(r['id']=='matter.upper.1.local' for r in report['equations']))
        self.assertTrue(any(r['id']=='operation.1' for r in report['equations']))
        self.assertFalse(any(r['id']=='operation.2' for r in report['equations']))
        with self.assertRaises(JournalError):ensure_executable(model)
        with self.assertRaises(JournalError):edit(model,{'kind':'append','operation':{'kind':'expand','family':'matter','sources':['operation.2']}})
        restored=edit(model,{'kind':'undo'})
        self.assertNotIn('replay',restored)
        self.assertEqual(len(restored['definition']['operations']),2)
        self.assertEqual(restored['definition']['cursor'],1)
        self.assertEqual(describe_for_authoring(BASE)['equations'],describe(BASE)['equations'])

    def test_recovery_of_multiple_stale_operations_is_reversible_and_draft_errors_stay_errors(self):
        model=self.model()
        self.append(model,{'kind':'combine','family':'matter','sources':['matter.upper.1.closed','matter.lower.1.closed']})
        self.append(model,{'kind':'expand','family':'matter','sources':['operation.1']})
        model['volumenes'][0]['supuestos']['materia']['vista']='campo'
        partial=edit(model,{'kind':'undo'})
        self.assertEqual(partial['replay']['completed'],0)
        self.assertEqual(len(partial['definition']['operations']),2)
        paused=edit(model,{'kind':'rewind'})
        self.assertEqual(paused['definition']['cursor'],0)
        self.assertEqual(len(paused['definition']['operations']),2)
        with self.assertRaises(JournalError):describe_for_authoring(model,{'format':FORMAT,'version':1,'operations':[],'cursor':1})

    def test_blank_model_previews_the_same_law_without_inventing_a_component(self):
        from backend.api_modelo import equation_workbench
        preview=equation_workbench({'draft':{'format':'rage.fundamental-equations','version':1,'modelId':'blank'}})
        self.assertTrue(preview['draft']);self.assertFalse(preview['execution']['supported'])
        self.assertEqual(preview['definition']['operations'],[])
        self.assertTrue(all(row['ownerId']=='unbound' for row in preview['equations']))
        self.assertEqual(preview['equations'][0]['id'],'fundamental.matter')
        self.assertNotIn('components',preview)
        self.assertTrue(all(not row['derivation']['inputIds'] for row in preview['equations']))
        with self.assertRaises(Exception):equation_workbench({'draft':{'format':'rage.fundamental-equations','version':1,'modelId':'blank'},'action':{'kind':'append'}})

    def test_unbound_journal_edits_replay_and_undo_without_fake_species(self):
        from backend.api_modelo import equation_workbench
        request={'format':'rage.fundamental-equations','version':2,'modelId':'blank','materialJournal':{'origin':'recorded','operations':[]},'ports':[]}
        initial=equation_workbench({'draft':request})
        full=copy.deepcopy(request)
        full['materialJournal']['operations']=[{'id':'total','title':'Integrate to total','changes':{'vista':'cantidad'}},{'id':'fixed','title':'Fixed boundary','changes':{'fija':True}},{'id':'closed','title':'Close boundary','changes':{'restoImpermeable':True}},{'id':'source','title':'Uniform generation','changes':{'generacionUniforme':True}},{'id':'volume','title':'Use volume','changes':{'cantidadVolumen':True}},{'id':'density','title':'Constant mean density','changes':{'densidadMediaConstante':True}}]
        result=equation_workbench({'draft':full})
        matter=lambda r:[row for row in r['equations'] if row['family']=='matter' and row['current']]
        self.assertNotEqual(matter(initial),matter(result));self.assertEqual(result['findings'],[])
        self.assertFalse(any('relative-flux' in row['id'] for row in result['equations']), 'An unbound index is not a pure species.')
        self.assertTrue(any('product_rule'==row['derivation']['rule'] for row in result['equations']))
        self.assertFalse(result['execution']['supported'])
        undone=copy.deepcopy(full);undone['materialJournal']['operations'].pop()
        self.assertNotEqual(matter(equation_workbench({'draft':undone})),matter(result))
        self.assertEqual(equation_workbench({'draft':full}),result)
        changed=copy.deepcopy(request);changed['momentumJournal']={'format':'rage.momentum-derivation','version':1,'volumes':{'dominio':{'origin':'recorded','operations':[{'id':'force','title':'Neglect body force','changes':{'negligibleBodyForce':True}}]}}}
        momentum_report=equation_workbench({'draft':changed})
        self.assertNotEqual([e for e in initial['equations'] if e['family']=='momentum'],[e for e in momentum_report['equations'] if e['family']=='momentum'])
        changed['momentumJournal']['volumes']['dominio']['cursor']=0
        self.assertEqual([e for e in initial['equations'] if e['family']=='momentum'],[e for e in equation_workbench({'draft':changed})['equations'] if e['family']=='momentum'])
        self.symbolic_publications.extend([initial,result,momentum_report])

    def test_mean_density_product_and_uniform_sources_against_analytic_reference(self):
        model=self.model();state=material.fundamental_formulation()
        state.update(vista='cantidad',restoImpermeable=True,cantidadVolumen=True,expandirProducto=True,generacionUniforme=True,consumoUniforme=True)
        model['corrientes']=[]
        graph,final,_=equation_graph(model,'upper',state)
        equation=graph.nodes[final[0]].equation;t=sp.Symbol('t',real=True)
        values={f:(2+t if str(f.func).startswith('rho_mean') else 3+2*t if str(f.func).startswith('V__') else 5 if str(f.func).startswith('g__') else 1) for f in equation.atoms(sp.Function)}
        evaluated=equation.xreplace(values).doit()
        self.assertEqual(sp.simplify(evaluated.lhs-(7+4*t)),0)
        self.assertEqual(sp.simplify(evaluated.rhs-4*(3+2*t)),0)
        state.update(fija=True,densidadMediaConstante=True)
        fixed,final,_=equation_graph(model,'upper',state)
        self.assertEqual(fixed.nodes[final[0]].equation.lhs,0)
        self.assertTrue(fixed.nodes['matter.upper.1.inventory-form'].equation.lhs.has(sp.Derivative),'The original dynamic law must survive a zero-rate reduction.')

    def test_coordinate_metrics_and_fick_against_analytic_reference(self):
        model=self.model();state=material.fundamental_formulation()
        state.update(coordenadas='cilindricas',expandida=True,invariantes=[False,True,True])
        state['campo'].update(sinReaccion=True,sinDifusion=True)
        graph,final,_=equation_graph(model,'upper',state)
        rhs=graph.nodes[final[0]].equation.rhs
        values={f:(3 if str(f.func).startswith('rho__') else 4 if str(f.func).startswith('velocity_r') else 0) for f in rhs.atoms(sp.Function)}
        self.assertEqual(rhs.xreplace(values).doit().subs(sp.Symbol('r',real=True),2),-6)
        state.update(coordenadas='esfericas',invariantes=[False,True,True]);state['campo'].update(sinConveccion=True,sinDifusion=False,difusion='laplaciano')
        graph,final,_=equation_graph(model,'upper',state,unbound=True)
        rhs=graph.nodes[final[0]].equation.rhs;r=sp.Symbol('r',real=True)
        values={f:(r**2 if str(f.func).startswith('rho__') else 2) for f in rhs.atoms(sp.Function) if f.func.__module__ is None}
        self.assertEqual(sp.simplify(rhs.xreplace(values).doit()),12,'D=2 times the spherical Laplacian of r squared is 12.')
        from core.modelo.equation_workbench import _dimension
        self.assertEqual(_dimension(rhs,{}),{'L':-3,'M':1,'T':-1})

    def test_unbound_preview_rejects_bad_journal_or_duplicate_ports(self):
        request={'format':'rage.fundamental-equations','version':2,'modelId':'blank','materialJournal':{'origin':'recorded','operations':[]},'ports':[{'id':1,'sentido':'entrada'},{'id':1,'sentido':'salida'}]}
        with self.assertRaises(JournalError):fundamental_report(request)
        request['ports']=[];request['materialJournal']['operations']=[{'id':'bad','title':'Bad boolean','changes':{'fija':'true'}}]
        with self.assertRaises(ValueError):fundamental_report(request)

    def test_density_volume_summary_uses_the_same_current_graph(self):
        model=self.model();volume=model['volumenes'][0]
        volume['supuestos']['materia']['cantidadVolumen']=True
        model['motores']['materialDerivation']['volumes'][volume['id']]['operations'].append({'id':'density-volume','title':'Use mean density','changes':{'cantidadVolumen':True}})
        report=describe(model);summary=formulation_summary(model)
        expected=[r['latex'] for r in report['equations'] if r['family']=='matter' and r['ownerId']==volume['id'] and r['current'] and r['id'].startswith('matter.')]
        actual=next(v['steps'] for family in summary['families'] if family['id']=='matter' for v in family['volumes'] if v['volumeId']==volume['id'])
        self.assertEqual([r['latex'] for r in actual if r['id'].startswith('matter.')],expected)

    def test_integrated_momentum_retains_gauss_reynolds_and_moving_boundary_flux(self):
        request={'format':'rage.fundamental-equations','version':2,'modelId':'blank','materialJournal':{'origin':'recorded','operations':[]},'ports':[],'momentumJournal':{'format':'rage.momentum-derivation','version':1,'volumes':{'dominio':{'origin':'recorded','operations':[{'id':'integral','title':'Integrate momentum','changes':{'form':'integral'}}]}}}}
        report=fundamental_report(request)
        current=[row for row in report['equations'] if row['family']=='momentum' and row['current']]
        self.assertEqual(len(current),3)
        self.assertTrue(all(row['derivation']['rule']=='add_to_both_sides' for row in current))
        for axis in 'xyz':
            prefix='momentum.dominio.transport.'+axis
            rows={r['id']:r for r in report['equations']}
            self.assertIn(prefix+'.gauss',rows)
            self.assertIn(prefix+'.reynolds',rows)
            self.assertIn(prefix+'.reynolds',rows[prefix+'.transport']['derivation']['inputIds'])
            self.assertIn('boundary',rows[prefix+'.rate']['latex'])
        self.symbolic_publications.append(report)

    def test_dependent_quantities_preserve_chain_rule_and_dimensional_relations(self):
        model=self.model();time=self.quantity(describe(model),'t')
        self.append(model,{'kind':'declare_function','family':'energy','name':'temperature','unit':'K','dependencies':[time]})
        self.append(model,{'kind':'declare_function','family':'energy','name':'specificEnergy','unit':'J/kg','dependencies':['temperature']})
        self.append(model,{'kind':'declare_symbol','family':'energy','name':'heatCapacity','unit':'J/(kg*K)'})
        self.append(model,{'kind':'declare_relation','family':'energy','relationKind':'constitutive','left':'specificEnergy','right':'heatCapacity*temperature','reason':'Declared constant caloric coefficient'})
        report=self.append(model,{'kind':'differentiate','family':'energy','sources':['operation.4'],'symbol':time})
        graph,*_=build(model);t=sp.Symbol('t',real=True);temperature=sp.Function('temperature')(t)
        self.assertEqual(graph.nodes['operation.4'].kind,'constitutive')
        u=sp.Function('specificEnergy')(temperature);cp=sp.Symbol('heatCapacity',real=True)
        self.assertEqual(graph.nodes['operation.5'].equation.lhs,sp.diff(u,t))
        self.assertEqual(graph.nodes['operation.5'].equation.rhs,cp*sp.diff(temperature,t))
        self.assertNotEqual(graph.nodes['operation.5'].equation.lhs,0)
        from core.modelo.equation_workbench import _dimension
        self.assertEqual(_dimension(graph.nodes['operation.5'].equation.lhs,build(model)[3]),{'L':2,'T':-3})
        report=self.append(model,{'kind':'substitute','family':'energy','sources':['operation.5'],'relation':'operation.4','symbol':'specificEnergy'})
        graph,*_=build(model);equation=graph.nodes['operation.6'].equation
        self.assertEqual(sp.simplify(equation.lhs-equation.rhs),0)
        self.assertEqual(equation.lhs.xreplace({temperature:300+t*t,cp:4}).doit(),8*t)
        self.assertEqual(graph.nodes['operation.6'].inputs,('operation.5','operation.4'))
        self.assertFalse(report['execution']['supported'])
        self.symbolic_publications.append(report)
        with self.assertRaises(JournalError):ensure_executable(model)
        with self.assertRaises(JournalError):self.append(model,{'kind':'declare_function','family':'energy','name':'temperature','unit':'s','dependencies':[time]})
        with self.assertRaises(JournalError):self.append(model,{'kind':'declare_function','family':'energy','name':'bad','unit':'K','dependencies':['absent']})
        with self.assertRaises(JournalError):self.append(model,{'kind':'declare_function','family':'energy','name':'bad','unit':'K','dependencies':[]})

    def test_dependency_and_zero_assumptions_act_on_expressions_without_erasing_laws(self):
        model=self.model();time=self.quantity(describe(model),'t')
        self.append(model,{'kind':'declare_symbol','family':'matter','name':'position','unit':'m'})
        self.append(model,{'kind':'declare_function','family':'matter','name':'fieldA','unit':'kg','dependencies':['position',time]})
        self.append(model,{'kind':'declare_function','family':'matter','name':'fieldB','unit':'kg','dependencies':['position',time]})
        self.append(model,{'kind':'declare_relation','family':'matter','left':'fieldA','right':'2*fieldB','reason':'Declared relation between inventories'})
        self.append(model,{'kind':'differentiate','family':'matter','sources':['operation.4'],'symbol':'position'})
        before=build(model)[0].nodes['operation.5'].equation
        result=self.append(model,{'kind':'change_dependencies','family':'matter','sources':['operation.5'],'symbol':'fieldA','dependencies':[time],'reason':'Field A is uniform along position'})
        graph,*_=build(model)
        self.assertEqual(graph.nodes['operation.6'].equation.lhs,0)
        self.assertEqual(graph.nodes['operation.6'].equation.rhs,before.rhs)
        self.assertEqual(graph.nodes['operation.5'].equation,before)
        self.assertEqual(graph.nodes['operation.6.condition'].kind,'constraint')
        self.assertFalse(result['execution']['supported'])
        self.append(model,{'kind':'apply_zero','family':'matter','sources':['operation.6'],'symbol':'fieldB','reason':'No inventory B'})
        self.assertEqual(build(model)[0].nodes['operation.7'].equation,sp.Eq(0,0,evaluate=False))
        undone=edit(model,{'kind':'undo'});model['motores']['equationWorkbench']=undone['definition']
        self.assertEqual(edit(model,{'kind':'redo'})['definition']['cursor'],7)
        self.symbolic_publications.append(result)
        with self.assertRaises(JournalError):self.append(model,{'kind':'change_dependencies','family':'matter','sources':['operation.5'],'symbol':'fieldA','dependencies':['fieldB'],'reason':'Invalid dependency'})

    def test_equation_scaling_records_nonzero_domain_and_rejects_singular_arithmetic(self):
        model=self.model();self.append(model,{'kind':'declare_symbol','family':'matter','name':'coefficient','unit':'1'})
        report=self.append(model,{'kind':'divide','family':'matter','sources':['matter.upper.1.closed'],'right':'coefficient'})
        graph,*_=build(model);source=graph.nodes['matter.upper.1.closed'].equation;scaled=graph.nodes['operation.2'].equation
        coefficient=sp.Symbol('coefficient',real=True)
        self.assertEqual(sp.simplify(scaled.lhs*coefficient-source.lhs),0)
        self.assertIn(sp.Ne(coefficient,0,evaluate=False),graph.nodes['operation.2'].predicates)
        self.assertFalse(report['execution']['supported'],'A new validity condition needs numerical enforcement before execution.')
        with self.assertRaises(JournalError):ensure_executable(model)
        for factor in ('0','1/0','coefficient-coefficient'):
            with self.assertRaises(JournalError):self.append(model,{'kind':'divide','family':'matter','sources':['matter.upper.1.closed'],'right':factor})
        self.append(model,{'kind':'declare_relation','family':'matter','left':'coefficient/coefficient','right':'1','reason':'Valid only away from zero'})
        self.assertIn(sp.Ne(coefficient,0,evaluate=False),build(model)[0].nodes['operation.3'].predicates,'Cancellation must not erase the domain condition.')
        self.symbolic_publications.append(report)

    def test_dimensions_are_checked_before_arithmetic_cancellation(self):
        model=self.model()
        self.append(model,{'kind':'declare_symbol','family':'matter','name':'massValue','unit':'kg'})
        self.append(model,{'kind':'declare_symbol','family':'matter','name':'timeValue','unit':'s'})
        with self.assertRaisesRegex(JournalError,'incompatible dimensions'):
            self.append(model,{'kind':'declare_relation','family':'matter','left':'massValue+timeValue-timeValue','right':'massValue','reason':'Invalid intermediate sum'})
        with self.assertRaisesRegex(JournalError,'exponent must be dimensionless'):
            self.append(model,{'kind':'declare_relation','family':'matter','left':'massValue^timeValue','right':'massValue','reason':'Invalid exponent'})
        with self.assertRaisesRegex(JournalError,'Classify a relation'):
            self.append(model,{'kind':'declare_relation','family':'matter','relationKind':'balance','left':'massValue','right':'0','reason':'A premise cannot pretend to be a derived conservation law'})
        result=self.append(model,{'kind':'declare_relation','family':'matter','relationKind':'constraint','left':'massValue','right':'0','reason':'Prescribed zero inventory'})
        self.assertEqual(result['equations'][-1]['kind'],'constraint');self.assertFalse(result['execution']['supported'])

    def test_partial_integration_retains_functional_constant_and_units(self):
        model=self.model();time=self.quantity(describe(model),'t')
        self.append(model,{'kind':'declare_symbol','family':'matter','name':'distance','unit':'m'})
        self.append(model,{'kind':'declare_function','family':'matter','name':'densityField','unit':'kg/m3','dependencies':['distance',time]})
        self.append(model,{'kind':'declare_relation','family':'matter','left':'densityField','right':'0','reason':'A zero field for this algebraic reference'})
        report=self.append(model,{'kind':'integrate','family':'matter','sources':['operation.3'],'symbol':'distance','name':'integrationValue'})
        graph,*_=build(model);t=sp.Symbol('t',real=True)
        self.assertEqual(graph.nodes['operation.4'].equation.rhs,sp.Function('integrationValue')(t))
        from core.unidades import interpretar
        quantity=next(q for q in report['quantities'] if q['id']=='integrationValue')
        self.assertEqual(interpretar(quantity['unit'])['dimension'],{'M':1,'L':-2})
        self.symbolic_publications.append(report)

    def test_unbound_v3_can_record_preview_replay_and_undo_without_inventing_components(self):
        from backend.api_modelo import equation_workbench
        request={'format':'rage.fundamental-equations','version':3,'modelId':'unbound-edit','materialJournal':{'origin':'recorded','operations':[]},'ports':[],
                 'definition':{'format':FORMAT,'version':1,'operations':[],'cursor':0}}
        original=copy.deepcopy(request)
        result=equation_workbench({'draft':request,'action':{'kind':'append','operation':{'kind':'declare_function','family':'matter','name':'newInventory','unit':'kg','dependencies':[self.quantity(fundamental_report(request),'t')]}}})
        self.assertEqual(request,original,'Preview never writes into the source request.')
        self.assertTrue(result['draft']);self.assertFalse(result['execution']['supported'])
        request['definition']=result['definition']
        self.assertEqual(fundamental_report(json.loads(json.dumps(request))),result)
        undone=equation_workbench({'draft':request,'action':{'kind':'undo'}})
        self.assertEqual(undone['definition']['cursor'],0);self.assertEqual(len(undone['definition']['operations']),1)
        request['definition']=undone['definition']
        self.assertEqual(equation_workbench({'draft':request,'action':{'kind':'redo'}}),result)
        request['definition']=copy.deepcopy(result['definition']);request['definition']['operations'][0]['dependencies']=['removed-quantity']
        recovered=fundamental_report(request)
        self.assertEqual(recovered['replay']['completed'],0);self.assertEqual(recovered['definition'],request['definition'])
        self.symbolic_publications.extend([result,recovered])

    def test_variable_fick_coefficient_and_port_definitions(self):
        model=self.model();state=material.fundamental_formulation()
        state.update(expandida=True,invariantes=[False,True,True])
        state['campo'].update(sinReaccion=True,sinConveccion=True,difusion='fick')
        graph,final,_=equation_graph(model,'upper',state,unbound=True)
        rhs=graph.nodes[final[0]].equation.rhs;x=sp.Symbol('x',real=True)
        values={f:(x*x if str(f.func).startswith('rho__') else x if str(f.func).startswith('D__') else 3) for f in rhs.atoms(sp.Function) if f.func.__module__ is None}
        self.assertEqual(sp.simplify(rhs.xreplace(values).doit()),4*x)
        state=material.fundamental_formulation();state.update(vista='cantidad',uniforme=True)
        model['corrientes'][0]['constante']=True
        graph,final,_=equation_graph(model,'upper',state)
        self.assertTrue(any(n.rule=='uniform_surface_integral' for n in graph.nodes.values()))
        self.assertTrue(any(graph.nodes[k].kind=='constraint' and 'constant-port' in k for k in final))


if __name__=='__main__':unittest.main()
