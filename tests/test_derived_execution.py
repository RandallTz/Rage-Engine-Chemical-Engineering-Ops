"""M1 numerical-bridge evidence, not the complete U1 acceptance gate."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np
from scipy.linalg import expm
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from derived_execution_inputs import fixture
from core.compilador import resolver, compilar, NoSoportado
from core.compilador.derived import DerivedSystem, LoweringError, resolve_system, source_signature
from core.compilador.presentation import formulation_summary
from core.compilador.report import compilation_report
from core.compilador.explicito import SistemaExplicito
from core.mathematics.dimensions import catalog
from core.modelo import leer_modelo_comun, ErrorModelo
from core.modelo.equation_workbench import edit
from core.resultados import leer_resultados


def numerical_reference(name, reference, times):
    """Analytic A/C and an independently assembled matrix for B."""
    expected = {}; scales = {}
    def add(quantity, values, scale):
        expected[quantity] = np.broadcast_to(values, len(times)); scales[quantity] = scale
    if name == 'a':
        total = sum(reference['initialMass']); decay = np.exp(-reference['massFlow']*times/total)
        first = total*reference['feedMassFraction'] + (reference['initialMass'][0]-total*reference['feedMassFraction'])*decay
        target = reference['feedTemperature'] + reference['heatRate']/(reference['massFlow']*reference['specificCapacity'])
        temperature = target + (reference['initialTemperature']-target)*decay
        for index, masses in enumerate((first, total-first), 1):
            add(f'm__mixture__{index}(t)', masses, reference['massScale'])
            add(f'amount{index}(t)', masses/reference['molarMass'][index-1], reference['moleScale'])
        add('m_total__mixture(t)', total, reference['massScale'])
        add('T__mixture(t)', temperature, reference['temperatureScale'])
        add('U__mixture(t)', total*reference['specificCapacity']*(temperature-reference['referenceTemperature']), reference['energyScale'])
    elif name == 'c':
        capacities = np.array(reference['mass'])*np.array(reference['specificCapacity'])
        initial = reference['initialTemperature']; equilibrium = np.dot(capacities, initial)/sum(capacities)
        decay = np.exp(-reference['conductance']*(1/capacities[0]+1/capacities[1])*times)
        for index, owner in enumerate(('region_a', 'region_b')):
            temperature = equilibrium+(initial[index]-equilibrium)*decay
            add(f'm__{owner}__1(t)', reference['mass'][index], reference['massScale'])
            add(f'm_total__{owner}(t)', reference['mass'][index], reference['massScale'])
            add(f'T__{owner}(t)', temperature, reference['temperatureScale'])
            add(f'U__{owner}(t)', capacities[index]*(temperature-reference['referenceTemperature']), reference['energyScale'])
    else:
        area = math.pi*reference['diameter']**2/4
        inertance = reference['length']/area
        resistance = 128*reference['viscosity']*reference['length']/(math.pi*reference['density']*reference['diameter']**4)
        gravity = reference['gravity']; a, b = reference['storageArea']
        matrix = np.array([[0, 0, -1], [0, 0, 1], [gravity/(a*inertance), -gravity/(b*inertance), -resistance/inertance]])
        initial = np.array([*reference['initialMass'], reference['initialFlow']])
        states = np.array([expm(matrix*t)@initial for t in times])
        for index, owner in enumerate(('upper', 'lower')):
            add(f'm__{owner}__1(t)', states[:, index], reference['massScale'])
            add(f'm_total__{owner}(t)', states[:, index], reference['massScale'])
            add(f'h__{owner}(t)', states[:, index]/(reference['density']*reference['storageArea'][index]), reference['heightScale'])
            add(f'p__{owner}(z_0__{owner}, t)', reference['surfacePressure']+gravity*states[:, index]/reference['storageArea'][index], reference['pressureScale'])
        for stream in ('s1', 's2'):
            add(f'q__{stream}__1(t)', states[:, 2], reference['flowScale'])
        for quantity in ('m_total__channel(t)', 'm__channel__1(t)'):
            add(quantity, reference['density']*area*reference['length'], reference['massScale'])
    return expected, scales


class DerivedExecutionTests(unittest.TestCase):
    publications = {}; metrics = []

    @classmethod
    def setUpClass(cls):
        cls.documents = {}; cls.systems = {}
        cls.frozen = {name: hashlib.sha256((ROOT/f'tests/reference_data/m1-{name}.json').read_bytes()).hexdigest() for name in 'abc'}
        for name in 'abc':
            print('Building bridge from frozen M1-'+name.upper(), flush=True)
            model, document, replayed = fixture(name)
            cls.documents[name] = (model, document, replayed)
            cls.systems[name] = DerivedSystem(model)

    @classmethod
    def tearDownClass(cls):
        for name, digest in cls.frozen.items():
            assert hashlib.sha256((ROOT/f'tests/reference_data/m1-{name}.json').read_bytes()).hexdigest() == digest
        (ROOT/'.tmp/m1-bridge-publications.json').write_text(json.dumps({'publications': cls.publications, 'metrics': cls.metrics}, indent=2), encoding='utf8')

    def compare_reference(self, name, result):
        system = self.systems[name]; reference = self.documents[name][1]['reference']
        expected, scales = numerical_reference(name, reference, np.array(result['ejes'][0]['valores']))
        quantities = {key: str(q) for key, q in system.quantities.items()}
        maximum = 0.0; checked = 0
        for series in result['series']:
            if not series['id'].startswith(('campo.', 'observable.')):
                continue
            key = series['id'].split('.', 1)[1]; quantity = quantities[key]
            self.assertIn(quantity, expected)
            error = float(np.max(np.abs(np.array(series['valores'])-expected[quantity]))/scales[quantity])
            maximum = max(maximum, error); checked += 1
        self.assertGreaterEqual(checked, len(system.states))
        conservation = max(v['valor'] for v in result['verificaciones'])
        self.assertLess(maximum, 1e-5); self.assertLess(conservation, 1e-6)
        return maximum, conservation

    def test_all_three_identity_graphs_use_rk45_and_bdf_with_frozen_references(self):
        for name, system in self.systems.items():
            self.assertIsInstance(system.numeric, SistemaExplicito)
            original_method = system.method
            original_request = system.model['estudio']['metodoSolicitado']
            for method in ('RK45', 'BDF'):
                with self.subTest(case=name, method=method):
                    system.method = method
                    system.model['estudio']['metodoSolicitado'] = method.lower()
                    system.report = system._report()
                    result = leer_resultados(resolve_system(system))
                    self.assertEqual(result['estado'], 'resuelto')
                    error, conservation = self.compare_reference(name, result)
                    metric = {'case': name.upper(), 'method': method, 'scaledError': error, 'conservationResidual': conservation}
                    self.metrics.append(metric); print(json.dumps(metric), flush=True)
                    self.publications[name+'.'+method] = copy.deepcopy({'model': self.documents[name][0], 'report': system.report, 'result': result})
            system.method = original_method
            system.model['estudio']['metodoSolicitado'] = original_request
            system.report = system._report()

    def test_compilation_rows_are_exactly_the_transform_rows_and_totals_are_reconstructed(self):
        for name, system in self.systems.items():
            summary = formulation_summary(self.documents[name][0])
            actual = {row['id']: row for row in system.report['equationWorkbench']['equations']}
            for family in summary['families']:
                for volume in family['volumes']:
                    for row in volume['steps']:
                        self.assertEqual(actual[row['id']], row)
            total_ids = {row['quantityId'] for row in system.selection['reconstructions'] if 'total' in str(system._quantity(row['quantityId']))}
            self.assertTrue(total_ids)
            self.assertFalse(total_ids & set(system.state_ids))
            self.assertEqual(len(system.report['variables']), 3 if name in 'ab' else 4)
            self.assertTrue(system.report['derivedExecution']['runtimeConditions'])

    def test_the_public_compiler_and_solve_routes_use_the_bridge_without_old_adapters(self):
        from unittest.mock import patch
        from backend.api_modelo import describe_compilation, resolver_modelo, derived_execution_source
        model = copy.deepcopy(self.documents['c'][0]); original = copy.deepcopy(model)
        unselected = copy.deepcopy(model); unselected['motores'].pop('derivedExecution')
        source = derived_execution_source({'modelo': unselected})
        self.assertEqual(source['sourceSignature'], model['motores']['derivedExecution']['sourceSignature'])
        with (patch('core.compilador.hydraulics.HydraulicSystem', side_effect=AssertionError('No physical-adapter fallback')),
              patch('core.balances.generar', side_effect=AssertionError('No legacy balance fallback'))):
            compiled = compilar(model)
            self.assertIsInstance(compiled, DerivedSystem)
            self.assertTrue(np.array_equal(compiled.inicial(), self.systems['c'].inicial()))
            report = describe_compilation({'modelo': model})
            result = resolver_modelo({'modelo': model})
        self.assertEqual(report['derivedExecution'], self.systems['c'].report['derivedExecution'])
        self.assertEqual(result['procedencia']['motor'], 'rage.compilador.derived')
        self.assertEqual(result['procedencia']['compilation']['signature'], report['signature'])
        self.assertEqual(model, original)

    def test_unsupported_recorded_operation_has_a_located_compilation_error(self):
        model = copy.deepcopy(self.documents['c'][0])
        key = model['motores']['derivedExecution']['states'][0]['equationId']
        # A valid typed authoring operation, but not an executable lumped ODE.
        report = edit(model, {'kind': 'append', 'operation': {
            'kind': 'volume_integrate', 'family': 'matter', 'sources': [key]}})
        model['motores']['equationWorkbench'] = report['definition']
        model['motores']['derivedExecution']['sourceSignature'] = source_signature(model)
        model['motores']['derivedExecution']['states'][0]['equationId'] = 'operation.26'
        with self.assertRaises(NoSoportado) as caught:
            compilation_report(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'unsupported_rate')
        self.assertEqual(caught.exception.diagnostics[0]['equationId'], 'operation.26')

    def test_changed_graph_or_removed_signatures_never_fall_back(self):
        original = self.documents['c'][0]
        changed = copy.deepcopy(original)
        changed['motores']['equationWorkbench']['operations'][2]['right'] = '-' + changed['motores']['equationWorkbench']['operations'][2]['right']
        with self.assertRaises(NoSoportado):
            resolver(changed)
        changed = copy.deepcopy(original)
        operation = next(op for op in changed['motores']['equationWorkbench']['operations'] if op.get('sourceSignatures'))
        del operation['sourceSignatures']
        with self.assertRaises(NoSoportado) as caught:
            resolver(changed)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'unsigned_operation')

    def test_missing_data_units_and_initial_domains_are_rejected(self):
        original = self.documents['c'][0]
        for data_id, value, unit in [('region_a.capacity', '500', 'kg'), ('region_a.mass', '-2', 'kg'),
                                      ('region_a.temperature', '400', 'K'), ('region_a.minimumTemperature', '365', 'K')]:
            changed = copy.deepcopy(original); changed['datos'][data_id]['declaracion'] = {'texto': value, 'unidad': unit}
            with self.subTest(data=data_id), self.assertRaises(NoSoportado):
                compilation_report(changed)
        changed = copy.deepcopy(original)
        key = next(iter(changed['motores']['derivedExecution']['parameters']))
        del changed['motores']['derivedExecution']['parameters'][key]
        with self.assertRaises(NoSoportado):
            compilation_report(changed)

    def test_missing_selected_data_has_structured_diagnostics_at_python_and_http_boundaries(self):
        from backend.api_modelo import describe_compilation, resolver_modelo
        from fastapi import HTTPException
        for field in ('parameters', 'initialValues', 'checks', 'scaling'):
            model = copy.deepcopy(self.documents['c'][0]); selection = model['motores']['derivedExecution']
            if field == 'checks':
                selection[field][0]['scaleDataId'] = 'missing.selected.datum'
            elif field == 'scaling':
                selection[field] = {q: 'missing.selected.datum' for q in [selection['timeId'], *(r['quantityId'] for r in selection['states'])]}
            else:
                selection[field][next(iter(selection[field]))] = 'missing.selected.datum'
            for run in (DerivedSystem, compilar, compilation_report, resolver):
                with self.subTest(field=field, boundary=run.__name__), self.assertRaises(LoweringError) as caught:
                    run(model)
                self.assertEqual(caught.exception.diagnostics[0]['code'], 'missing_data')
            for run in (describe_compilation, resolver_modelo):
                with self.assertRaises(HTTPException) as caught:
                    run({'modelo': model})
                self.assertEqual(caught.exception.status_code, 422)
                self.assertEqual(caught.exception.detail['diagnostics'][0]['code'], 'missing_data')

    def test_implicit_euler_is_rejected_instead_of_running_bdf(self):
        from core.compilador.compilador import temporal_method
        from core.compilador.hydraulics import HydraulicSystem
        for name in 'bc':
            model = copy.deepcopy(self.documents[name][0])
            model['estudio']['metodoSolicitado'] = 'euler_implicito'
            with self.assertRaises(NoSoportado) as caught:
                compilation_report(model)
            self.assertEqual(caught.exception.diagnostics[0]['code'], 'unsupported_method')
        lowered = copy.deepcopy(self.systems['c'].lowered)
        lowered['estudio']['metodoSolicitado'] = 'euler_implicito'
        with self.assertRaisesRegex(NoSoportado, 'not implicit Euler'):
            SistemaExplicito(lowered)
        hydraulic = copy.deepcopy(self.documents['b'][0]); hydraulic['motores'].pop('derivedExecution')
        hydraulic['motores'].pop('equationWorkbench')
        hydraulic['estudio']['metodoSolicitado'] = 'euler_implicito'
        with self.assertRaisesRegex(NoSoportado, 'not implicit Euler'):
            HydraulicSystem(hydraulic)
        with self.assertRaisesRegex(NoSoportado, 'not implicit Euler'):
            temporal_method('euler_implicito')

    def test_scaled_units_preserve_constants_and_labels_preserve_execution_identity(self):
        model = copy.deepcopy(self.documents['c'][0]); model['nombre'] = 'Renamed'
        model['componentes'][0]['nombre'] = 'A display name'
        model['datos']['region_a.mass']['declaracion'] = {'texto': '2000', 'unidad': 'g'}
        system = DerivedSystem(model)
        self.assertEqual(system.initial_values, self.systems['c'].initial_values)
        renamed = copy.deepcopy(self.documents['c'][0]); renamed['nombre'] = 'Only a label'
        renamed['componentes'][0]['nombre'] = 'Only a component label'
        self.assertEqual(DerivedSystem(renamed).report['signature'], self.systems['c'].report['signature'])
        self.assertNotEqual(system.report['signature'], self.systems['c'].report['signature'])

    def test_optional_multiplicative_scaling_uses_the_existing_engine(self):
        model = copy.deepcopy(self.documents['c'][0]); selection = model['motores']['derivedExecution']
        def datum(key, value, unit):
            model['datos'][key] = {'magnitud': 'scale', 'funcion': 'parametro',
                'declaracion': {'texto': str(value), 'unidad': unit}, 'origen': {'propietarioId': 'estudio', 'ruta': key}}
            return key
        selection['scaling'] = {selection['timeId']: datum('scale.time', 75, 's')}
        for row in selection['states']:
            q = self.systems['c']._quantity(row['quantityId']); unit = self.systems['c']._unit(q)
            selection['scaling'][row['quantityId']] = datum('scale.'+row['quantityId'], 60000 if unit == 'J' else 5, unit)
        system = DerivedSystem(model)
        self.assertEqual(type(system.scaled).__module__, 'core.compilador.transformed')
        self.assertEqual(system.report['formulation'], 'scaled')
        for method in ('RK45', 'BDF'):
            system.method = method; system.model['estudio']['metodoSolicitado'] = method.lower(); system.report = system._report()
            result = leer_resultados(resolve_system(system)); error, conservation = self.compare_reference('c', result)
            metric = {'case': 'C scaled', 'method': method, 'scaledError': error, 'conservationResidual': conservation}
            self.metrics.append(metric); print(json.dumps(metric), flush=True)
            self.publications['c.scaled.'+method] = copy.deepcopy({'model': model, 'report': system.report, 'result': result})

    def test_runtime_caloric_domain_violation_stops_the_run_explicitly(self):
        model = copy.deepcopy(self.documents['a'][0])
        model['datos']['solve.suppliedHeat']['declaracion']['texto'] = '20000'
        result = resolver(model)
        self.assertEqual(result['estado'], 'parcial')
        self.assertTrue(any(e['codigo'] == 'agotamiento' for e in result['eventos']))
        self.assertLess(result['ejes'][0]['valores'][-1], float(model['datos']['solve.finalTime']['declaracion']['texto']))

    def test_versioned_selection_is_strict_and_does_not_modify_frozen_inputs(self):
        model = copy.deepcopy(self.documents['a'][0]); original = copy.deepcopy(model)
        self.assertEqual(leer_modelo_comun(model), model); self.assertEqual(model, original)
        model['motores']['derivedExecution']['rhs'] = 'Not an input'
        with self.assertRaises(ErrorModelo):
            leer_modelo_comun(model)

    def test_existing_hydraulic_medium_guards_are_not_bypassed(self):
        for key, value, expected in [('initialFlow', '2', 'laminar_domain'), ('minimumPressure', '1000000', 'pressure_domain'),
                                      ('solve.radius', '0.02', 'inconsistent_parameter_premise'),
                                      ('solve.radius', '-0.01', 'inconsistent_geometry')]:
            model = copy.deepcopy(self.documents['b'][0]); model['datos'][key]['declaracion']['texto'] = value
            with self.subTest(data=key), self.assertRaises(NoSoportado) as caught:
                compilation_report(model)
            self.assertEqual(caught.exception.diagnostics[0]['code'], expected)

    def test_a_new_spatial_condition_is_rejected_rather_than_treated_as_a_reduced_proof_premise(self):
        model = copy.deepcopy(self.documents['c'][0]); replayed = self.documents['c'][2]
        quantity = next((key, value) for key, value in {**catalog(replayed.graph, replayed.units), **replayed.introduced}.items()
                        if isinstance(value, sp.core.function.AppliedUndef) and value.func.__name__ == 'rho_mixture__region_a')
        report = edit(model, {'kind': 'append', 'operation': {'kind': 'declare_domain', 'family': 'energy',
            'sources': ['energy.region_a.inventory-definition'], 'symbol': quantity[0], 'domain': 'positive',
            'reason': 'A new pointwise condition needs a supported spatial lowering'}})
        model['motores']['equationWorkbench'] = report['definition']
        model['motores']['derivedExecution']['sourceSignature'] = source_signature(model)
        with self.assertRaises(NoSoportado) as caught:
            compilation_report(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'unsupported_spatial_condition')

    def test_contradicted_parameter_premises_are_reported_before_unsupported_operations(self):
        for data, value, premise in [('drive', '1', 'operation.14'), ('outletElevation', '1', 'operation.16')]:
            model = copy.deepcopy(self.documents['b'][0])
            model['datos'][data]['declaracion']['texto'] = value
            with self.subTest(data=data), self.assertRaises(NoSoportado) as caught:
                compilation_report(model)
            self.assertEqual(caught.exception.diagnostics[0]['code'], 'inconsistent_parameter_premise')
            self.assertEqual(caught.exception.diagnostics[0]['equationId'], premise)

    def test_nonzero_runtime_guard_detects_a_crossing_between_opposite_signs(self):
        # This is a numerical-domain test, independent of physical family or
        # equipment. A nonzero trajectory cannot cross the excluded zero.
        t = sp.Symbol('time', real=True); q = sp.Function('quantity')(t)
        for initial, forbidden in [(2, -1), (-2, 1)]:
            system = DerivedSystem.__new__(DerivedSystem)
            system.time = t; system.parameter_values = {}; system.initial_values = {q: sp.Integer(initial)}; system.margins = []
            system._predicate_margin(sp.Ne(q, 0, evaluate=False), 'source')
            margin, strict, _, _ = system.margins[0]
            self.assertTrue(strict)
            self.assertGreater(float(margin.subs(q, initial)), 0)
            self.assertLess(float(margin.subs(q, forbidden)), 0)


class MatterLoweringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from matter_lowering_inputs import matter_case
        cls.models = {name: matter_case(name) for name in ('decay', 'filling', 'dilution')}

    def test_malformed_envelopes_keep_strict_reader_diagnostics(self):
        from backend.api_modelo import describe_compilation
        from fastapi import HTTPException
        for field in ('motores', 'datos'):
            model = copy.deepcopy(self.models['decay']); model[field] = []
            with self.assertRaises(HTTPException) as caught:
                describe_compilation({'modelo': model})
            self.assertEqual(caught.exception.status_code, 422)
            self.assertIn('ruta', caught.exception.detail)

    def test_density_volume_cases_against_independent_analytic_references(self):
        publications = {}
        for name, original in self.models.items():
            for method in ('rk45', 'bdf'):
                for factor in (1, 0.1):
                    model = copy.deepcopy(original)
                    model['estudio']['metodoSolicitado'] = method
                    model['estudio']['rtol'] *= factor
                    model['estudio']['atol']['cantidad'] *= factor
                    system = DerivedSystem(model)
                    result = leer_resultados(resolve_system(system))
                    self.assertEqual(result['estado'], 'resuelto')
                    t = np.array(result['ejes'][0]['valores'])
                    # Independent mass accounting: quadratic sink in a fixed
                    # volume, fixed-density feed, and prescribed-volume dilution.
                    if name == 'decay':
                        density = 3/(1+0.3*t); volume = np.full_like(t, 2)
                    elif name == 'filling':
                        density = np.full_like(t, 3); volume = 2+0.2*t
                    else:
                        volume = 2+0.2*t; density = (6+0.3*t)/volume
                    expected = volume if name == 'filling' else density
                    state = next(s for s in result['series'] if s['id'] == 'campo.'+system.state_ids[0])
                    error = float(np.max(np.abs(np.array(state['valores'])-expected))/3)
                    self.assertLess(error, 2e-8)
                    mass_id = next(row['quantityId'] for row in system.selection['reconstructions'] if str(system._quantity(row['quantityId'])) == 'm__region__7(t)')
                    mass = next(s for s in result['series'] if s['id'] == 'observable.'+mass_id)
                    self.assertLess(np.max(np.abs(np.array(mass['valores'])-density*volume))/6, 2e-8)
                    self.assertEqual(len(system.report['variables']), 1)
                    self.assertTrue(system.report['derivedExecution']['runtimeConditions'])
                    print(json.dumps({'matter': name, 'method': method, 'toleranceFactor': factor, 'scaledError': error}), flush=True)
                    publications[name+'.'+method+'.'+str(factor)] = {'model': model, 'report': system.report, 'result': result}
        (ROOT/'.tmp/matter-lowering-publications.json').write_text(json.dumps(publications), encoding='utf8')

    def test_source_ancestry_replay_and_transform_are_preserved(self):
        from core.modelo.equation_workbench import build
        from matter_lowering_inputs import matter_case
        for name, model in self.models.items():
            system = DerivedSystem(json.loads(json.dumps(model)))
            key = system.selection['states'][0]['equationId']
            ancestors = set()
            def visit(identity):
                if identity in ancestors:
                    return
                ancestors.add(identity)
                for parent in system.graph.nodes[identity].inputs:
                    visit(parent)
            visit(key)
            self.assertIn('matter.region.7.local', ancestors)
            self.assertIn('matter.region.7.mean-inventory', ancestors)
            summary = formulation_summary(model)
            self.assertTrue(any(row['id'] == key for family in summary['families'] for volume in family['volumes'] for row in volume['steps']))
            renamed = copy.deepcopy(model); renamed['nombre'] = 'Display only'
            self.assertEqual(source_signature(renamed), source_signature(model))
            # A different owner/component uses identical generic lowering.
            other = DerivedSystem(matter_case(name, owner='other_region', component=23))
            np.testing.assert_allclose(other.rhs(0, other.initial()), system.rhs(0, system.initial()), atol=1e-14)
            self.assertEqual(len(build(model).receipts), model['motores']['equationWorkbench']['cursor'])

    def test_singular_missing_closure_undo_and_constraints_fail_closed(self):
        for name in self.models:
            model = copy.deepcopy(self.models[name])
            data = 'density' if name == 'filling' else 'volume' if name == 'decay' else 'initialVolume'
            model['datos'][data]['declaracion']['texto'] = '0'
            with self.subTest(case=name), self.assertRaises(LoweringError):
                DerivedSystem(model)
        original = self.models['dilution']
        changed = copy.deepcopy(original)
        changed['motores']['derivedExecution']['reconstructions'] = [r for r in changed['motores']['derivedExecution']['reconstructions'] if r['equationId'] != 'operation.3']
        changed['motores']['equationWorkbench']['cursor'] = 2
        changed['motores']['derivedExecution']['sourceSignature'] = source_signature(changed)
        with self.assertRaises(LoweringError):
            DerivedSystem(changed)
        changed = copy.deepcopy(original)
        before = changed['motores']['equationWorkbench']
        changed['motores']['equationWorkbench'] = edit(changed, {'kind': 'undo'})['definition']
        with self.assertRaisesRegex(LoweringError, 'changed'):
            DerivedSystem(changed)
        changed['motores']['equationWorkbench'] = edit(changed, {'kind': 'redo'})['definition']
        self.assertEqual(changed['motores']['equationWorkbench'], before)
        DerivedSystem(changed)
        changed = copy.deepcopy(original)
        entry = changed['motores']['materialDerivation']['volumes']['region']
        entry['operations'].append({'id': 'stationary', 'title': 'Permanent zero rate', 'changes': {'sinAcumulacion': True}})
        changed['volumenes'][0]['supuestos']['materia']['sinAcumulacion'] = True
        changed['motores']['derivedExecution']['sourceSignature'] = source_signature(changed)
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(changed)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'uncovered_balance')
        self.assertEqual(caught.exception.diagnostics[0]['equationId'], 'matter.region.7.stationary')


if __name__ == '__main__':
    unittest.main()
