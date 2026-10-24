"""Reduced hydraulic execution against analytical pressure and matrix exponential references."""
import copy
import json
import math
from pathlib import Path
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np
from scipy.linalg import expm

from core.modelo import leer_modelo_comun, ErrorModelo
from core.compilador import resolver, NoSoportado
from core.compilador.hydraulics import HydraulicSystem, AdmissionError, validate_admission
from core.compilador.report import compilation_report
from core.compilador.presentation import formulation_summary
from core.modelo.operation_journal import JournalError

ROOT=Path(__file__).resolve().parents[1]
if not (ROOT/'.tmp/hydraulic-models.json').exists():
    import subprocess
    subprocess.run(['node','frontend/verificar_hydraulics.mjs','--inputs-only'],cwd=ROOT,check=True)
MODELS=json.loads((ROOT/'.tmp/hydraulic-models.json').read_text(encoding='utf8'))
# Explicitly select variable-order BDF for the coupled execution reference.
# The historical fixture requests implicit Euler, which is now rejected.
MODELS[1]['estudio']['metodoSolicitado']='bdf'
def values(model,id_):return float(model['datos'][id_]['declaracion']['texto'])
def series(result,id_):return np.array(next(s['valores'] for s in result['series'] if s['id']==id_))
def requested_series(result,id_):
    time=np.array(result['ejes'][0]['valores']);requested=np.linspace(0,time[-1],121);indices=np.searchsorted(time,requested)
    np.testing.assert_allclose(time[indices],requested,atol=1e-12)
    return series(result,id_)[indices]


class HydraulicAdmissionTests(unittest.TestCase):
    def test_implicit_euler_is_rejected_instead_of_silently_running_bdf(self):
        for source in MODELS:
            model=copy.deepcopy(source)
            model['estudio']['metodoSolicitado']='euler_implicito'
            with self.subTest(model=model['id']):
                for operation in (compilation_report,resolver):
                    with self.assertRaisesRegex(NoSoportado,'Implicit Euler is not implemented') as failure:
                        operation(model)
                    self.assertEqual(failure.exception.diagnostics[0]['code'],'unsupported_method')
                    self.assertIn('Select BDF explicitly',failure.exception.diagnostics[0]['message'])

    def test_material_requirements_are_located_and_do_not_rewrite_history(self):
        from backend.api_modelo import hydraulic_admission, describe_compilation
        from fastapi import HTTPException
        model=copy.deepcopy(MODELS[1])
        changes={'vista':'campo','fija':False,'restoImpermeable':False,
                 'campo':{**next(v for v in model['volumenes'] if v['id']=='channel')['supuestos']['materia']['campo'],
                          'sinReaccion':False,'sinGeneracion':False,'sinConsumo':False}}
        next(v for v in model['volumenes'] if v['id']=='channel')['supuestos']['materia'].update(changes)
        model['motores']['materialDerivation']['volumes']['channel']['operations'].append(
            {'id':'restore-general-law','title':'Restore local transport and source terms','changes':changes})
        before=copy.deepcopy(model)
        with self.assertRaises(AdmissionError) as failure:validate_admission(model)
        issues=failure.exception.diagnostics
        self.assertEqual({issue['ownerId'] for issue in issues},{'channel'})
        self.assertEqual({issue['family'] for issue in issues},{'matter'})
        self.assertEqual({issue['code'] for issue in issues},{'total_form','boundary','boundary_remainder','generation','consumption'})
        with self.assertRaises(HTTPException) as api:hydraulic_admission({'modelo':model})
        self.assertEqual(api.exception.status_code,422)
        self.assertEqual(api.exception.detail['diagnostics'],issues)
        with self.assertRaises(HTTPException) as compiled:describe_compilation({'modelo':model})
        self.assertEqual(compiled.exception.detail['diagnostics'],issues)
        self.assertEqual(before,model)

    def test_physical_admission_does_not_evaluate_numerical_data(self):
        from backend.api_modelo import hydraulic_admission
        model=copy.deepcopy(MODELS[1])
        model['datos']['density']['declaracion']['texto']='-1'
        before=copy.deepcopy(model)
        report=hydraulic_admission({'modelo':model})
        self.assertEqual(report['diagnostics'],[])
        self.assertEqual(report['modelId'],model['id'])
        with self.assertRaises(Exception):HydraulicSystem(model)
        self.assertEqual(before,model)


class HydraulicExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results=[resolver(model) for model in MODELS]

    def test_examples_are_only_recorded_physical_inputs(self):
        for model in MODELS:
            original=copy.deepcopy(model);leer_modelo_comun(model);summary=formulation_summary(model)
            self.assertEqual(original,model);self.assertIsNone(model['matematico'])
            self.assertNotIn('unrecorded',str(summary));self.assertIn('path.pressure-form',str(summary))
        self.assertFalse(MODELS[0]['volumenes'][0]['balances']['materia'])
        self.assertTrue(any(v['balances']['materia'] for v in MODELS[1]['volumenes']))

    def test_prescribed_flow_recovers_pressure_against_independent_analytic_reference(self):
        model=MODELS[0];result=self.results[0];time=np.array(result['ejes'][0]['valores'])
        rho,mu,D,L=values(model,'density'),values(model,'viscosity'),values(model,'diameter'),values(model,'length')
        area=math.pi*D**2/4;resistance=128*mu*L/(math.pi*rho*D**4)
        q=.05+.02*(1-np.exp(-time/30));qdot=.02/30*np.exp(-time/30)
        expected=resistance*q+(L/area)*qdot
        np.testing.assert_allclose(series(result,'path.channel.drop'),expected,rtol=2e-12,atol=1e-8)
        np.testing.assert_allclose(series(result,'path.channel.inlet'),101325+expected,rtol=2e-12)
        mass=.05*time+.02*(time-30*(1-np.exp(-time/30)))
        np.testing.assert_allclose(series(result,'path.channel.transferred_mass'),mass,rtol=2e-8,atol=1e-9)
        self.assertGreater(expected[0],resistance*q[0],'The transient inertial pressure must not be discarded.')

    def test_coupled_inventories_and_flow_against_matrix_exponential(self):
        model=MODELS[1];result=self.results[1];system=HydraulicSystem(model)
        rho,mu,D,L,g=values(model,'density'),values(model,'viscosity'),values(model,'diameter'),values(model,'length'),values(model,'gravity')
        area=math.pi*D*D/4;resistance=128*mu*L/(math.pi*rho*D**4);inertance=L/area
        a,b=values(model,'upperArea'),values(model,'lowerArea')
        matrix=np.array([[0,0,-1],[0,0,1],[g/a/inertance,-g/b/inertance,-resistance/inertance]])
        initial=np.array([40.,10.,0.])
        expected=np.array([expm(matrix*t)@initial for t in result['ejes'][0]['valores']])
        actual=np.column_stack([series(result,k) for k in ['volume.upper.mass','volume.lower.mass','path.channel.flow']])
        np.testing.assert_allclose(actual,expected,rtol=3e-6,atol=2e-8)
        np.testing.assert_allclose(series(result,'path.channel.inlet'),101325+g*actual[:,0]/a,rtol=1e-12)
        np.testing.assert_allclose(series(result,'volume.upper.height'),actual[:,0]/(rho*a),rtol=1e-12)
        self.assertGreater(system.rhs(0,system.inicial())[next(p['index'] for p in system.paths)],0)

    def test_conservation_and_dissipation_are_published_without_phase_certification(self):
        for result in self.results:
            self.assertEqual('resuelto',result['estado'])
            for check in result['verificaciones']:self.assertLess(check['valor'],check['tolerancia'])
            self.assertGreaterEqual(min(series(result,'path.channel.dissipation')),0)
            self.assertLess(max(series(result,'path.channel.reynolds')),2100)
            self.assertIn('not certified',result['procedencia']['mensaje'])
        np.testing.assert_allclose(series(self.results[1],'volume.upper.mass')+series(self.results[1],'volume.lower.mass'),50,atol=1e-10)

    def test_dependent_totals_and_diagnostics_are_not_extra_physical_solver_states(self):
        prescribed=HydraulicSystem(MODELS[0]).report();coupled=HydraulicSystem(MODELS[1]).report()
        self.assertEqual(prescribed['variables'],[])
        self.assertEqual(len(coupled['variables']),3)
        self.assertEqual(coupled['auxiliaryStates'],2)
        self.assertEqual({v['id'] for v in coupled['variables']},{'volume.upper.mass','volume.lower.mass','path.channel.flow'})

    def test_unit_changes_use_the_shared_units_service(self):
        model=copy.deepcopy(MODELS[0]);model['datos']['area']['declaracion']={'texto':'3.141592653589793','unidad':'cm2'}
        model['datos']['flow']['declaracion']={'texto':'3 + 1.2*(1-exp(-t/30))','unidad':'kg/min'}
        changed=resolver(model)
        np.testing.assert_allclose(requested_series(changed,'path.channel.drop'),requested_series(self.results[0],'path.channel.drop'),rtol=1e-12,atol=1e-9)

    def test_reversed_head_reverses_flow_naturally(self):
        model=copy.deepcopy(MODELS[1])
        model['datos']['upper__inicial_1']['declaracion']['texto']='10';model['datos']['lower__inicial_1']['declaracion']['texto']='40'
        result=resolver(model)
        np.testing.assert_allclose(requested_series(result,'path.channel.flow'),-requested_series(self.results[1],'path.channel.flow'),rtol=1e-8,atol=1e-10)
        self.assertGreaterEqual(min(series(result,'path.channel.dissipation')),0)

    def test_stationary_initial_state_keeps_the_same_states_after_smooth_perturbation(self):
        model=copy.deepcopy(MODELS[1])
        for id_ in ['upper__inicial_1','lower__inicial_1']:model['datos'][id_]['declaracion']['texto']='25'
        steady=HydraulicSystem(model);np.testing.assert_allclose(steady.rhs(0,steady.inicial()),0,atol=1e-10)
        model['datos']['upperSurface']['declaracion']['texto']='101325 + 100*(1-exp(-t/30))'
        perturbed=HydraulicSystem(model)
        self.assertEqual(len(steady.inicial()),len(perturbed.inicial()))
        result=resolver(model);self.assertGreater(max(series(result,'path.channel.flow')),0)

    def test_overdetermination_bad_units_unrecorded_terms_and_independent_flows_fail_closed(self):
        mutations=[lambda m:m['motores']['hydraulicNetwork']['paths'][0].update(inletPressure={'kind':'datum','datumId':'outletPressure'}),lambda m:m['datos']['area']['declaracion'].update(unidad='m'),lambda m:m['motores']['momentumDerivation']['volumes']['channel']['operations'].append({'id':'unsupported','title':'Add incompatible zero storage','changes':{'zeroTotalAccumulation':True}}),lambda m:m['corrientes'][0]['materia']['caudalIds'].update({'1':'flow'})]
        for mutation in mutations:
            model=copy.deepcopy(MODELS[0]);mutation(model)
            with self.assertRaises((ErrorModelo,NoSoportado,JournalError)):resolver(model)

    def test_empty_inventory_stops_at_the_domain_boundary_without_clipping(self):
        model=copy.deepcopy(MODELS[1]);model['datos']['upper__inicial_1']['declaracion']['texto']='0.001';model['datos']['initialFlow']['declaracion']['texto']='0.1';model['datos']['estudio.tf']['declaracion']['texto']='1'
        result=resolver(model)
        self.assertEqual('parcial',result['estado']);self.assertLess(result['ejes'][0]['valores'][-1],1)
        self.assertLess(abs(series(result,'volume.upper.mass')[-1]),1e-7)

    def test_initial_medium_domain_errors_are_actionable_compilation_diagnostics(self):
        for datum,value,reason in [('flow','2','laminar'),('outletPressure','1000','pressure')]:
            model=copy.deepcopy(MODELS[0]);model['datos'][datum]['declaracion']['texto']=value
            with self.assertRaisesRegex(NoSoportado,reason):compilation_report(model)

    def test_report_exposes_real_states_methods_and_pressure_elimination(self):
        for model in MODELS:
            report=compilation_report(model)
            self.assertEqual({'RK45','BDF'},{m['id'] for m in report['strategy']['methods'] if m['available']})
            self.assertIn('Recovered pressure',report['matrix']);self.assertIn('impulse',report['auxiliaryPurpose'])
        bdf=copy.deepcopy(MODELS[0]);bdf['estudio']['metodoSolicitado']='bdf'
        result=resolver(bdf)
        np.testing.assert_allclose(requested_series(result,'path.channel.drop'),requested_series(self.results[0],'path.channel.drop'),rtol=1e-12,atol=1e-9)

    def test_hydraulic_bindings_cannot_supply_missing_geometry_deductions(self):
        model=copy.deepcopy(MODELS[1])
        operations=model['motores']['momentumDerivation']['volumes']['upper']['operations']
        operations[:]=[op for op in operations if 'prismaticStorage' not in op['changes']]
        summary=formulation_summary(model)
        matter=next(f for f in summary['families'] if f['id']=='matter')
        owner=next(v for v in matter['volumes'] if v['volumeId']=='upper')
        self.assertNotIn('storage.height',str(owner['steps']))
        with self.assertRaises(NoSoportado) as failure:resolver(model)
        self.assertTrue(any(issue['code']=='prismaticStorage' and issue['ownerId']=='upper'
                            for issue in failure.exception.__cause__.diagnostics))

    def test_compilation_is_independent_of_example_names_and_owner_ids(self):
        model=copy.deepcopy(MODELS[1]);rename={'upper':'node47','channel':'connection11','lower':'node3'}
        model['id']='arbitrary-input';model['nombre']='A different document title'
        for volume in model['volumenes']:volume['id']=rename[volume['id']]
        for stream in model['corrientes']:
            for end in ['desde','hasta']:stream[end]=rename.get(stream[end],stream[end])
        for namespace in ['materialDerivation','thermodynamicDerivation','momentumDerivation']:
            volumes=model['motores'][namespace]['volumes'];model['motores'][namespace]['volumes']={rename[k]:v for k,v in volumes.items()}
        for storage in model['motores']['hydraulicNetwork']['storages']:storage['volumeId']=rename[storage['volumeId']]
        for path in model['motores']['hydraulicNetwork']['paths']:
            path['volumeId']=rename[path['volumeId']]
            for end in ['inletPressure','outletPressure']:path[end]['volumeId']=rename[path[end]['volumeId']]
        result=resolver(model)
        np.testing.assert_allclose(requested_series(result,'path.connection11.flow'),requested_series(self.results[1],'path.channel.flow'),rtol=1e-12,atol=1e-12)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(HydraulicExecutionTests)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if result.wasSuccessful():
        from core.balances.momentum_derivation import describe_volume
        (ROOT/'.tmp/hydraulic-publications.json').write_text(json.dumps([{'report':compilation_report(m),'result':r,'developments':[describe_volume(m['motores']['momentumDerivation'],v['id'],m) for v in m['volumenes']]} for m,r in zip(MODELS,HydraulicExecutionTests.results)]),encoding='utf8')
    raise SystemExit(not result.wasSuccessful())
