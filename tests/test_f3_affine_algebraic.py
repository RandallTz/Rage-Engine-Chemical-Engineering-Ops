"""F3 internal shared-law derivation and independent analytic thermal control."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from m1_acceptance import author_thermal, SharedAuthor
from core.compilador.derived import DerivedSystem, LoweringError, source_signature, resolve_system
from core.mathematics.linear_system import ConstantAffineBlock, AffineBlockError
from core.mathematics.dimensions import catalog


class AffineRuntimeStopTests(unittest.TestCase):
    def test_classified_block_failure_retains_accepted_prefix(self):
        from core.solvers import integrar, Detencion
        system = DerivedSystem.__new__(DerivedSystem)
        system.algebraic_block = object()
        system.numeric = SimpleNamespace(dominio=lambda t, y: np.array([]))
        def rhs(t, y):
            if t >= 0.5:
                raise Detencion('algebraic_solve_failed', 'Injected block failure at 0.5 s')
            return np.array([1.0])
        system.rhs = rhs
        result = integrar(system, np.array([0.0]), 1.0, max_step=0.1)
        self.assertEqual(result.detenida.codigo, 'algebraic_solve_failed')
        self.assertGreater(result.t_fin, 0)
        self.assertLessEqual(result.t_fin, 0.5)
        self.assertAlmostEqual(float(result.y_fin[0]), result.t_fin, places=12)
        self.assertIsNone(system.stop_from_exception(RuntimeError('Unclassified programming error')))


def thermal_case():
    # Re-author the laws through the shared APIs. Never read/write frozen inputs.
    model, _, outputs = author_thermal(('body_one', 'body_two'))
    model['id'] = 'internal-affine-thermal'
    model['nombre'] = 'Internal affine-block acceptance'
    for owner in ('body_one', 'body_two'):
        model['datos'][owner+'.capacity']['declaracion']['texto'] = '300'
    author = SharedAuthor(model)
    author.definition = copy.deepcopy(model['motores']['equationWorkbench'])
    author.refresh()
    t = sp.Symbol('t', real=True)
    temperatures = [sp.Function('T__'+o)(t) for o in ('body_one', 'body_two')]
    q = author.quantity
    append = lambda kind, **fields: author.append(kind, family='thermodynamics', **fields)
    append('declare_function', name='meanTemperature', unit='K', dependencies=[q(t)])
    append('declare_function', name='temperatureDifference', unit='K', dependencies=[q(t)])
    mean = append('declare_relation', left='meanTemperature', right=f'({q(temperatures[0])}+{q(temperatures[1])})/2',
                  relationKind='definition', reason='Arithmetic mean temperature coordinate')
    difference = append('declare_relation', left='temperatureDifference', right=f'{q(temperatures[0])}-{q(temperatures[1])}',
                        relationKind='definition', reason='Signed temperature difference coordinate')
    second = append('isolate', sources=[difference], symbol=q(temperatures[1]))
    substituted = append('substitute', sources=[mean], relation=second, symbol=q(temperatures[1]))
    first = append('isolate', sources=[substituted], symbol=q(temperatures[0]))
    second = append('substitute', sources=[second], relation=first, symbol=q(temperatures[0]))
    for owner in ('body_one', 'body_two'):
        row = outputs[owner+'.energy']
        for temperature, relation in zip(temperatures, (first, second)):
            row = author.substitute(row, relation, temperature, family='energy')
        outputs[owner+'.energy'] = row
    model, replayed, outputs = author.finish(outputs)
    def named(name):
        return next(key for key, value in {**catalog(replayed.graph, replayed.units), **replayed.introduced}.items() if str(value) == name)
    def datum(key, value, unit, role='parametro'):
        model['datos'][key] = {'magnitud': key, 'funcion': role, 'declaracion': {'texto': str(value), 'unidad': unit},
                               'origen': {'propietarioId': 'estudio', 'ruta': key}}
        return key
    selection = {'format': 'rage.derived-execution', 'version': 2, 'sourceSignature': source_signature(model, replayed),
        'timeId': named('t'), 'states': [], 'parameters': {}, 'initialValues': {}, 'initialEquations': [],
        'reconstructions': [], 'checks': [], 'algebraic': [
            {'quantityId': named('meanTemperature(t)'), 'equationId': first},
            {'quantityId': named('temperatureDifference(t)'), 'equationId': second}]}
    for owner in ('body_one', 'body_two'):
        mass = sp.Function('m__'+owner+'__1')(t)
        mass_row = next(key for key in reversed(replayed.selected) if isinstance(replayed.graph.nodes[key].equation, sp.Equality)
                        and replayed.graph.nodes[key].equation.lhs == sp.diff(mass, t))
        for field, equation in [('m__'+owner+'__1(t)', mass_row), ('U__'+owner+'(t)', outputs[owner+'.energy'])]:
            selection['states'].append({'quantityId': named(field), 'equationId': equation})
        selection['initialValues'][named(str(mass))] = owner+'.mass'
        selection['initialValues'][named('T__'+owner+'(t)')] = owner+'.temperature'
        caloric = 'thermodynamics.'+owner+'.caloric-inventory'
        selection['initialEquations'].append(caloric)
        selection['reconstructions'].extend([
            {'quantityId': named('T__'+owner+'(t)'), 'equationId': caloric},
            {'quantityId': named('m_total__'+owner+'(t)'), 'equationId': 'matter.'+owner+'.total-definition'}])
        for field, data in [('caloric_capacity', 'capacity'), ('T_reference', 'referenceTemperature'), ('u_reference', 'referenceEnergy')]:
            selection['parameters'][named(field+'__'+owner)] = owner+'.'+data
    selection['parameters'][named('conductance')] = datum('solve.conductance', 6, 'W/K')
    selection['checks'] = [{'equationId': outputs['totalEnergy'], 'scaleDataId': datum('scale.energy', 36000, 'J')}]
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': datum('solve.horizon', 300, 's', 'estudio'),
        'metodoSolicitado': 'rk45', 'muestras': 61, 'rtol': 1e-9, 'atol': {'cantidad': 1e-11, 'energia': 1e-6}}
    model['motores']['derivedExecution'] = selection
    return model, author


class AffineExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print('Authoring fresh thermal laws and coupled coordinates through shared operations...', flush=True)
        cls.hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'tests/reference_data').glob('m1-?.json')}
        cls.model, cls.author = thermal_case()
        cls.system = DerivedSystem(cls.model)
        print('Fresh affine thermal compilation admitted.', flush=True)

    @classmethod
    def tearDownClass(cls):
        for path, digest in cls.hashes.items():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest

    def test_legacy_cycle_is_a_failing_before_control(self):
        model = copy.deepcopy(self.model)
        selection = model['motores']['derivedExecution']
        selection['version'] = 1
        selection['reconstructions'].extend(selection.pop('algebraic'))
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'cyclic_reconstruction')

    def test_both_methods_against_independent_reference_and_refinement(self):
        system = self.system
        for method in ('RK45', 'BDF'):
            for refinement in (1, 0.1):
                system.method = method
                system.numeric.metodo = method
                system.model['estudio']['metodoSolicitado'] = method.lower()
                system.model['estudio']['rtol'] = 1e-9*refinement
                system.model['estudio']['atol'] = {'cantidad': 1e-8*refinement, 'energia': 1e-8*refinement}
                system.numeric.atol[:] = 1e-8*refinement
                system.report = system._report()
                self.assertTrue(any(rate.has(*system.algebraic_quantities) for rate in system.runtime_rates))
                with patch.object(system.algebraic_block, 'solve', wraps=system.algebraic_block.solve) as solve, \
                     patch.object(system.numeric, 'rhs', side_effect=AssertionError('No reduced-RHS fallback')):
                    result = resolve_system(system)
                    self.assertGreater(solve.call_count, 61)
                self.assertEqual(result['estado'], 'resuelto')
                times = np.array(result['ejes'][0]['valores'])
                series = {s['id']: np.array(s['valores']) for s in result['series']}
                difference = series['observable.'+system.algebraic_rows[1]['quantityId']]
                error = float(np.max(np.abs(difference-60*np.exp(-times/60)))/60)
                energy = sum(series['campo.'+system.ids[q]] for q in system.states if str(q).startswith('U__'))
                conservation = float(np.max(np.abs(energy-36000))/36000)
                print(method, refinement, 'scaled error', error, 'conservation', conservation, flush=True)
                self.assertLessEqual(error, 1e-5)
                self.assertLessEqual(conservation, 1e-6)
                self.assertTrue(all(v['valor'] <= v['tolerancia'] for v in result['verificaciones']))
                mean = series['observable.'+system.algebraic_rows[0]['quantityId']]
                self.assertLessEqual(float(np.max(np.abs(mean-(324+6*np.exp(-times/60)))))/60, 1e-5)

    def test_full_models_reject_singular_nonlinear_and_time_varying_blocks(self):
        for variant, code in [('singular', 'singular_algebraic_block'), ('nonlinear', 'nonlinear_algebraic_block'),
                              ('time', 'nonconstant_algebraic_matrix')]:
            author = copy.copy(self.author)
            author.model = copy.deepcopy(self.model)
            author.definition = copy.deepcopy(self.author.definition)
            author.refresh()
            selection = author.model['motores']['derivedExecution']
            if variant == 'singular':
                row = author.append('multiply', family='thermodynamics', sources=[selection['algebraic'][0]['equationId']], right='2')
                selection['algebraic'][1]['equationId'] = row
            else:
                temperature = author.quantity(sp.Function('T__body_one')(sp.Symbol('t', real=True)))
                if variant == 'nonlinear':
                    reference = author.quantity(sp.Symbol('T_reference__body_one', real=True))
                    right = f'meanTemperature+temperatureDifference^2/{reference}'
                else:
                    author.append('declare_symbol', family='thermodynamics', name='timeScale', unit='s')
                    selection['parameters'][author.quantity(sp.Symbol('timeScale', real=True))] = 'solve.horizon'
                    right = f'meanTemperature+temperatureDifference*{author.quantity(sp.Symbol("t", real=True))}/timeScale'
                row = author.relation(temperature, right, 'Adverse algebraic-block regression', family='thermodynamics')
                selection['algebraic'][0]['equationId'] = row
            model, replayed, _ = author.finish({})
            model['motores']['derivedExecution']['sourceSignature'] = source_signature(model, replayed)
            with self.subTest(variant=variant), self.assertRaises(LoweringError) as caught:
                DerivedSystem(model)
            self.assertEqual(caught.exception.diagnostics[0]['code'], code)
            self.assertIn('equationId', caught.exception.diagnostics[0])

    def test_permutation_initial_consistency_and_runtime_stop(self):
        model = copy.deepcopy(self.model)
        selection = model['motores']['derivedExecution']
        selection['algebraic'].reverse()
        system = DerivedSystem(model)
        np.testing.assert_allclose(system.rhs(0, system.initial()), self.system.rhs(0, self.system.initial()), rtol=0, atol=1e-12)
        selection['initialValues'][selection['algebraic'][0]['quantityId']] = 'body_one.temperature'
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'invalid_initialization')
        from core.solvers import Detencion
        with patch.object(system.algebraic_block, 'solve', side_effect=AffineBlockError('algebraic_solve_failed', 'Regression failure')):
            with self.assertRaises(Detencion) as stop:
                system.rhs(0, system.initial())
            self.assertIn('Regression failure', str(stop.exception))

    def test_generic_block_rejections(self):
        x, z, t = sp.symbols('x z t')
        cases = [([x+z, 2*x+2*z], 'singular_algebraic_block'),
                 ([x*x+z, x-z], 'nonlinear_algebraic_block'),
                 ([t*x+z, x-z], 'nonconstant_algebraic_matrix'),
                 ([sp.Rational(1,10)**400*x, z], 'ill_conditioned_algebraic_block')]
        for residuals, code in cases:
            with self.subTest(code=code), self.assertRaises(AffineBlockError) as caught:
                ConstantAffineBlock(residuals, [x, z], {})
            self.assertEqual(caught.exception.code, code)

    def test_parameter_units_perturbation_and_undo(self):
        model = copy.deepcopy(self.model)
        model['datos']['solve.conductance']['declaracion'] = {'texto': '6000', 'unidad': 'mW/K'}
        system = DerivedSystem(model)
        np.testing.assert_allclose(system.rhs(0, system.initial()), self.system.rhs(0, self.system.initial()), rtol=0, atol=1e-12)
        model['datos']['solve.conductance']['declaracion']['texto'] = '7500'
        model['datos']['body_one.capacity']['declaracion']['texto'] = '400'
        system = DerivedSystem(model)
        result = resolve_system(system)
        times = np.array(result['ejes'][0]['valores'])
        difference = next(np.array(row['valores']) for row in result['series'] if row['id']=='observable.'+system.algebraic_rows[1]['quantityId'])
        tau = 800*900/(7.5*(800+900))
        self.assertLess(float(np.max(np.abs(difference-60*np.exp(-times/tau))))/60, 1e-5)
        model['motores']['equationWorkbench']['cursor'] -= 1
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'stale_formulation')


if __name__ == '__main__':
    if '--publication' in sys.argv:
        model, _ = thermal_case()
        from backend.api_modelo import resolver_modelo
        print(json.dumps({'model': model, 'result': resolver_modelo({'modelo': model, 'assessmentVersion': 1})}))
    else:
        unittest.main()
