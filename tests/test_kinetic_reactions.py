"""F5 kinetic deductions through shared authoring; independent batch references."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest
import numpy as np
import sympy as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from m1_acceptance import thermal_source, SharedAuthor
from core.balances import material_derivation as material, energy_derivation as energy
from core.balances.reaction_equations import declarations
from core.modelo import leer_modelo_comun
from core.modelo.lector import ErrorModelo
from core.mathematics.dimensions import catalog
from core.modelo.equation_workbench import build, edit, describe_for_authoring
from core.compilador.derived import DerivedSystem, resolve_system, source_signature, LoweringError
from core.compilador.compilador import AdmissionError


def kinetic_case(adiabatic=False, method='rk45', activation=0, owner='cell', stoichiometry=('-1', '1'), molar_masses=(0.02, 0.02), atoms=(1, 1), reverse_rate=None):
    # Reuse only the shared law-authoring driver, never frozen M1 documents.
    model = thermal_source((owner,))
    model['id'] = 'internal-kinetic-reference'
    model['nombre'] = 'Internal kinetic reference'
    model['componentes'] = [{'id': i, 'nombre': label, 'simbolo': label} for i, label in [(1, 'A'), (2, 'B')]]
    model['motores'].pop('thermodynamicDerivation')
    volume = model['volumenes'][0]; volume['componenteIds'] = [1, 2]
    volume['termodinamica'] = {'tipo': 'supuesto', 'supuesto': 'fase_no_evaluada',
        'motivo': 'Explicit single-phase caloric premises, including formation reference, authored below'}
    def datum(key, value, unit, role='parametro'):
        model['datos'][key] = {'magnitud': key, 'funcion': role,
            'declaracion': {'texto': str(value), 'unidad': unit},
            'origen': {'propietarioId': owner, 'ruta': key}}
        return key
    journal = {'format': 'rage.material-derivation', 'version': 1, 'volumes': {}}
    for action in ('start', 'fixed_boundary', 'integrate', 'total', 'impermeable_remainder', 'uniform_generation', 'uniform_consumption'):
        journal = material.edit_journal(journal, owner, {'kind': action})
    model['motores']['materialDerivation'] = journal
    volume['supuestos']['materia'] = material.replay_volume(journal['volumes'][owner])[-1]
    for flag in ('monofasico', 'sinCambioFase', 'densidadConstante', 'modelo'):
        volume['supuestos']['energia'].pop(flag, None)
    if adiabatic:
        ej = model['motores']['energyDerivation']
        ej = energy.edit_journal(ej, owner, {'kind': 'adiabatic'})
        model['motores']['energyDerivation'] = ej
        volume['supuestos']['energia'] = energy.replay(ej['volumes'][owner], energy.fundamental, energy.normalize)[-1]
    else:
        volume['balances']['energia'] = False
    volume['inicial']['cantidades'] = {'base': 'molar', 'datoIds': {
        '1': datum('initialA', 2, 'mol', 'inicial'), '2': datum('initialB', 0, 'mol', 'inicial')}}
    config = {'volumeDataId': datum('reactingVolume', 0.5, 'm3'),
        'molarMassDataIds': {'1': datum('molarMassA', molar_masses[0], 'kg/mol'), '2': datum('molarMassB', molar_masses[1], 'kg/mol')},
        'elements': {'X': {'1': atoms[0], '2': atoms[1]}},
        'reactions': [{'id': 'conversion', 'stoichiometry': dict(zip(('1', '2'), stoichiometry)),
                       'orders': {'1': 1}, 'rateConstantDataId': datum('rateConstant', 0.1, '1/s')}]}
    if activation:
        config['reactions'][0]['arrhenius'] = {'energyDataId': datum('activationEnergy', activation, 'J/mol'),
            'temperatureDataId': datum('rateTemperature', 300, 'K')}
    if reverse_rate is not None:
        config['reactions'].append({'id':'reverse','stoichiometry':{'1':'1','2':'-1'},'orders':{'2':1},
            'rateConstantDataId':datum('reverseRate',reverse_rate,'1/s')})
    model['motores']['kineticReactions'] = {'format': 'rage.kinetic-reactions', 'version': 1, 'volumes': {owner: config}}
    volume['frontera']['datoId'] = config['volumeDataId']
    author = SharedAuthor(model); t = sp.Symbol('t', real=True)
    amounts = [sp.Function('amount_'+str(c)+'__'+owner)(t) for c in (1, 2)]
    outputs = []
    for c, n in zip(('1', '2'), amounts):
        m = sp.Function('m__'+owner+'__'+c)(t)
        key = next(k for k in author.selected if k.startswith('matter.'+owner+'.'+c+'.') and author.source.nodes[k].equation.lhs == sp.diff(m, t))
        key = author.append('substitute', sources=[key], relation='reaction.'+owner+'.amount.'+c, symbol=author.quantity(m))
        key = author.append('expand', sources=[key])
        for source, stem in [('generation', 'g'), ('consumption', 'c')]:
            key = author.append('substitute', sources=[key], relation='reaction.'+owner+'.'+source+'.'+c,
                symbol=author.quantity(sp.Function(stem+'__'+owner+'__'+c)(t)))
        key = author.append('isolate', sources=[key], symbol=author.quantity(sp.diff(n, t)))
        outputs.append(key)
    T = sp.Function('T__'+owner)(t); U = sp.Function('U__'+owner)(t)
    caloric = None
    if adiabatic:
        # Thermodynamic constitutive premise, not a reaction heat source:
        # u_A = Cv*(T-Tref), u_B = formationB + Cv*(T-Tref).
        for name, unit in [('molarCapacity', 'J/(mol*K)'), ('formationB', 'J/mol'), ('caloricReference', 'K')]:
            author.append('declare_symbol', family='thermodynamics', name=name, unit=unit)
        caloric = author.relation(author.quantity(U),
            f'({author.quantity(amounts[0])}+{author.quantity(amounts[1])})*molarCapacity*({author.quantity(T)}-caloricReference)+{author.quantity(amounts[1])}*formationB',
            'Uniform single phase; constant molar Cv; formation reference included once in total internal energy', family='thermodynamics', kind='constitutive')
        author.append('declare_domain', family='thermodynamics', sources=[caloric], symbol=author.quantity(T),
            domain='interval', lower='290', upper='450', lowerOpen=False, upperOpen=False, endpointUnit='K',
            reason='Declared validity of the single-phase caloric relation')
    model['motores']['equationWorkbench'] = author.definition
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    def qid(q): return next(k for k, v in quantities.items() if v == q)
    selection = {'format': 'rage.derived-execution', 'version': 1, 'sourceSignature': source_signature(model, replayed),
        'timeId': qid(t), 'states': [{'quantityId': qid(q), 'equationId': k} for q, k in zip(amounts, outputs)],
        'parameters': {}, 'initialValues': {qid(amounts[0]): 'initialA', qid(amounts[1]): 'initialB'},
        'initialEquations': [], 'reconstructions': [], 'checks': []}
    _, _, bindings, _ = declarations(model, owner)
    selection['parameters'] = {qid(q): d for q, d in bindings.items()}
    if adiabatic:
        key = next(k for k in author.selected if k.startswith('energy.'+owner+'.') and author.source.nodes[k].equation.lhs == sp.diff(U, t))
        selection['states'].append({'quantityId': qid(U), 'equationId': key})
        selection['initialValues'][qid(U)] = datum('initialEnergy', 0, 'J', 'inicial')
        selection['reconstructions'].append({'quantityId': qid(T), 'equationId': caloric})
        for name, value, unit in [('molarCapacity', 100, 'J/(mol*K)'), ('formationB', -10000, 'J/mol'), ('caloricReference', 300, 'K')]:
            selection['parameters'][qid(replayed.introduced[name])] = datum(name, value, unit)
        selection['checks'].append({'equationId': key, 'scaleDataId': datum('energyScale', 20000, 'J')})
    else:
        selection['parameters'][qid(T)] = datum('isothermalTemperature', 300, 'K')
    selection['reconstructions'].append({'quantityId': qid(sp.Function('m_total__'+owner)(t)), 'equationId': 'matter.'+owner+'.total-definition'})
    selection['checks'].append({'equationId': 'matter.'+owner+'.total', 'scaleDataId': datum('massScale', 0.04, 'kg')})
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': datum('duration', 40, 's', 'estudio'),
        'metodoSolicitado': method, 'muestras': 41, 'rtol': 1e-9, 'atol': {'cantidad': 1e-11, 'energia': 1e-7}}
    model['motores']['derivedExecution'] = selection
    return model


class KineticReactions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.isothermal = kinetic_case()
        cls.adiabatic = kinetic_case(adiabatic=True)

    def test_isothermal_analytic(self):
        for method in ('rk45', 'bdf'):
            model = copy.deepcopy(self.isothermal); model['estudio']['metodoSolicitado'] = method
            system = DerivedSystem(model); result = resolve_system(system)
            self.assertEqual(result['estado'], 'resuelto')
            times = np.array(result['ejes'][0]['valores'])
            values = {s['id']: np.array(s['valores']) for s in result['series']}
            a, b = [values['campo.'+row['quantityId']] for row in model['motores']['derivedExecution']['states']]
            error=float(np.max(abs(a-2*np.exp(-0.1*times))))
            self.assertLess(error, 1e-7)
            self.assertLess(np.max(abs(b-(2-2*np.exp(-0.1*times)))), 1e-7)
            self.assertLess(max(v['valor'] for v in result['verificaciones']), 1e-6)
            print(json.dumps({'kineticReference':method,'amountErrorMol':error}))

    def test_adiabatic_known_rise(self):
        model = copy.deepcopy(self.adiabatic)
        system = DerivedSystem(model); result = resolve_system(system)
        self.assertEqual(result['estado'], 'resuelto')
        times = np.array(result['ejes'][0]['valores'])
        temperature = next(np.array(s['valores']) for s in result['series'] if s['id'] == 'observable.'+model['motores']['derivedExecution']['reconstructions'][0]['quantityId'])
        expected = 300+100*(1-np.exp(-0.1*times))
        error=float(np.max(abs(temperature-expected)))
        self.assertLess(error, 1e-6)
        self.assertLess(max(v['valor'] for v in result['verificaciones']), 1e-6)
        print(json.dumps({'adiabaticTemperatureErrorK':error,'finalTemperatureK':float(temperature[-1])}))

    def test_recorded_algebra_total_and_separate_kinetics(self):
        model = self.isothermal; replayed = build(model)
        self.assertTrue(all(r.signature_status == 'pinned' for r in replayed.receipts))
        self.assertTrue(any(r.before and r.after and r.before != r.after for r in replayed.receipts))
        self.assertEqual(replayed.graph.nodes['reaction.cell.kinetics.conversion'].kind, 'constitutive')
        self.assertTrue(replayed.graph.nodes['matter.cell.total'].dependent)
        self.assertTrue(replayed.graph.nodes['matter.cell.sum'].inputs)
        for component in (1, 2):
            root = replayed.graph.nodes[f'matter.cell.{component}.local']
            self.assertTrue(root.equation.has(sp.Derivative))
            self.assertFalse(root.inputs)
        system = DerivedSystem(model)
        self.assertEqual(len(system.states), 2)
        self.assertEqual(system._normalize(replayed.graph.nodes['matter.cell.total'].equation.lhs-replayed.graph.nodes['matter.cell.total'].equation.rhs), 0)

    def test_zero_element_counts_omit_unevaluated_products(self):
        model = copy.deepcopy(self.isothermal)
        elements = model['motores']['kineticReactions']['volumes']['cell']['elements']
        elements['absent'] = {'1': 0, '2': 0}
        elements['charge'] = {'1': 0, '2': 0}
        graph, _, _, _ = declarations(model, 'cell')
        for element in ('absent', 'charge'):
            equation = graph.nodes['reaction.cell.element.'+element+'.conversion'].equation
            self.assertEqual(equation.lhs, sp.Integer(0))
            self.assertEqual(equation.rhs, sp.Integer(0))

    def test_undo_redo_and_stale_source(self):
        model = copy.deepcopy(self.isothermal)
        definition = model['motores']['equationWorkbench']
        report = edit(model, {'kind': 'undo'})
        model['motores']['equationWorkbench'] = report['definition']
        with self.assertRaises(LoweringError):DerivedSystem(model)
        model['motores']['equationWorkbench'] = edit(model, {'kind': 'redo'})['definition']
        self.assertEqual(definition, model['motores']['equationWorkbench'])
        DerivedSystem(model)
        del model['motores']['kineticReactions']
        preview = describe_for_authoring(model)
        self.assertFalse(preview['execution']['supported'])
        self.assertTrue(preview['equations'])
        self.assertEqual(preview['definition'], definition)
        with self.assertRaises(LoweringError):DerivedSystem(model)

    def test_rejected_declarations(self):
        mutations = [
            lambda m,e,r:r.update(stoichiometry={'1':'-1','2':'2'}),
            lambda m,e,r:m['datos']['molarMassB']['declaracion'].update(texto='0.03'),
            lambda m,e,r:r['stoichiometry'].update({'1':'1/0'}),
            lambda m,e,r:r.update(orders={'1':2}),
            lambda m,e,r:m['datos']['rateConstant']['declaracion'].update(texto='-1'),
            lambda m,e,r:m['datos']['reactingVolume']['declaracion'].update(unidad='s'),
            lambda m,e,r:m['datos']['rateConstant']['declaracion'].update(unidad='not_a_unit'),
            lambda m,e,r:m['volumenes'][0]['frontera'].update(datoId='cell.volume'),
            lambda m,e,r:m['volumenes'][0].update(volumenDatoId='cell.volume'),
            lambda m,e,r:r.update(equilibrium=True),
            lambda m,e,r:e['elements'].update(charge={'1':1,'2':0}),
        ]
        for index, mutation in enumerate(mutations):
            model=copy.deepcopy(self.isothermal);entry=model['motores']['kineticReactions']['volumes']['cell']
            mutation(model,entry,entry['reactions'][0])
            with self.subTest(mutation=index):
                with self.assertRaises(ErrorModelo):leer_modelo_comun(model)

    def test_binding_conflict_and_negative_initial(self):
        model=copy.deepcopy(self.isothermal)
        selected=model['motores']['derivedExecution']
        key=next(q for q,d in selected['parameters'].items() if d=='rateConstant')
        selected['parameters'][key]='initialA'
        with self.assertRaises(LoweringError):DerivedSystem(model)
        model=copy.deepcopy(self.isothermal);model['datos']['initialA']['declaracion']['texto']='-1'
        with self.assertRaises(AdmissionError) as error:DerivedSystem(model)
        self.assertEqual(error.exception.diagnostics[0]['code'], 'INITIALIZATION_OUT_OF_DOMAIN')

    def test_labels_and_units_preserve_execution(self):
        model=copy.deepcopy(self.isothermal);signature=source_signature(model)
        model['nombre']='Renamed';model['componentes'][0]['nombre']='Renamed species'
        self.assertEqual(signature,source_signature(model))
        model['datos']['rateConstant']['declaracion']={'texto':'6','unidad':'1/min'}
        system=DerivedSystem(model)
        np.testing.assert_allclose(system.numeric.rhs(0,system.initial_state)[:2],[-0.2,0.2],rtol=1e-14)

    def test_nonconserved_moles_and_conserved_mass(self):
        model=kinetic_case(stoichiometry=('-1','2'),molar_masses=(0.04,0.02),atoms=(2,1))
        result=resolve_system(DerivedSystem(model));values={s['id']:np.array(s['valores']) for s in result['series']}
        a,b=[values['campo.'+row['quantityId']] for row in model['motores']['derivedExecution']['states']]
        self.assertGreater(a[-1]+b[-1],3.9)
        self.assertLess(np.max(abs(0.04*a+0.02*b-0.08)),1e-10)

    def test_arrhenius_and_adiabatic_refinement(self):
        model=kinetic_case(adiabatic=True,activation=5000)
        from scipy.integrate import solve_ivp
        # Independent temperature/composition reduction, not the compiler RHS.
        def rhs(t,n):
            temperature=400-50*n[0]
            return [-0.1*math.exp(-5000/8.31446261815324*(1/temperature-1/300))*n[0]]
        reference=solve_ivp(rhs,(0,40),[2.],method='DOP853',rtol=1e-12,atol=1e-13,dense_output=True)
        errors=[]
        for factor in (1.,.1):
            test=copy.deepcopy(model);test['estudio']['rtol']*=factor
            test['estudio']['atol']={k:v*factor for k,v in test['estudio']['atol'].items()}
            result=resolve_system(DerivedSystem(test));times=np.array(result['ejes'][0]['valores'])
            self.assertEqual(result['estado'],'resuelto')
            actual=next(np.array(s['valores']) for s in result['series'] if s['id']=='campo.'+test['motores']['derivedExecution']['states'][0]['quantityId'])
            errors.append(float(np.max(abs(actual-reference.sol(times)[0]))))
        self.assertLess(max(errors),1e-7)
        self.assertLess(errors[1],errors[0])

    def test_forward_reverse_superposition(self):
        model=kinetic_case(reverse_rate=0.05)
        result=resolve_system(DerivedSystem(model));times=np.array(result['ejes'][0]['valores'])
        a=next(np.array(s['valores']) for s in result['series'] if s['id']=='campo.'+model['motores']['derivedExecution']['states'][0]['quantityId'])
        expected=2/3+4/3*np.exp(-0.15*times)
        self.assertLess(np.max(abs(a-expected)),1e-7)

    def test_no_earlier_model_fallback_or_missing_caloric_closure(self):
        from core.compilador import resolver
        from core.compilador.compilador import NoSoportado
        model=copy.deepcopy(self.isothermal);del model['motores']['derivedExecution']
        with self.assertRaisesRegex(NoSoportado,'earlier generated or equilibrium model'):
            resolver(model)
        model=copy.deepcopy(self.adiabatic)
        model['motores']['derivedExecution']['reconstructions'].pop(0)
        with self.assertRaises(LoweringError):DerivedSystem(model)

    def test_source_substitution_cannot_be_skipped(self):
        model=copy.deepcopy(self.isothermal);replayed=build(model)
        for c,row in zip((1,2),model['motores']['derivedExecution']['states']):
            m=sp.Function(f'm__cell__{c}')(sp.Symbol('t',real=True))
            row['equationId']=next(k for k in replayed.selected if not k.startswith('operation.') and replayed.graph.nodes[k].equation.lhs==sp.diff(m,sp.Symbol('t',real=True)))
        with self.assertRaises(LoweringError) as error:DerivedSystem(model)
        self.assertEqual(error.exception.diagnostics[0]['code'],'kinetic_source_not_deduced')

    def test_shared_source_retention_operation_and_element_staleness(self):
        model=thermal_source(('cell',));journal=model['motores']['materialDerivation']
        before=build(model)
        updated=material.edit_journal(journal,'cell',{'kind':'reaction_sources'})
        model['motores']['materialDerivation']=updated
        model['volumenes'][0]['supuestos']['materia']=material.replay_volume(updated['volumes']['cell'])[-1]
        after=build(model)
        self.assertNotEqual(before.graph.nodes['matter.cell.total'].equation,after.graph.nodes['matter.cell.total'].equation)
        restored=material.edit_journal(updated,'cell',{'kind':'undo'})
        self.assertEqual(restored,journal)
        model=copy.deepcopy(self.isothermal)
        model['motores']['kineticReactions']['volumes']['cell']['elements']['X']={'1':2,'2':2}
        self.assertFalse(describe_for_authoring(model)['execution']['supported'])
        with self.assertRaises(LoweringError):DerivedSystem(model)

    def test_existing_author_compile_and_solve_handlers(self):
        from fastapi import HTTPException
        from backend.api_modelo import equation_workbench, describe_compilation, resolver_modelo
        model=copy.deepcopy(self.isothermal)
        inspected=equation_workbench({'modelo':model})
        self.assertTrue(any(r['id']=='reaction.cell.kinetics.conversion' for r in inspected['equations']))
        compiled=describe_compilation({'modelo':model})
        self.assertIn('derivedExecution',compiled)
        solved=resolver_modelo({'modelo':model})
        self.assertEqual(solved['estado'],'resuelto')
        del model['motores']['derivedExecution']
        with self.assertRaises(HTTPException) as error:resolver_modelo({'modelo':model})
        self.assertEqual(error.exception.status_code,422)


if __name__ == '__main__':
    if sys.argv[1:] == ['--publish']:
        model = kinetic_case()
        print(json.dumps({'model': model, 'development': describe_for_authoring(model)}))
    else:unittest.main()
