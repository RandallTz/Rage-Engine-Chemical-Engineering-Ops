"""Steady specialization of recorded laws; independent scalar reference."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from m1_acceptance import thermal_source, SharedAuthor
from core.compilador import resolver
from core.compilador.derived import source_signature
from core.mathematics.dimensions import catalog
from core.compilador.steady import SteadySystem, LoweringError, steady_result_signature


def polynomial_case(expressions=('u^2+v-6', 'u-v'), names=('u', 'v'), seed=(1, 1), bounds=((.1, 4), (.1, 4)), derivative_order=0):
    """Internal mathematical control, authored with generic declaration operations."""
    model = {'formato': 'rage.modelo', 'version': 0, 'id': 'polynomial-control', 'nombre': 'Polynomial control',
             'componentes': [], 'termodinamica': {'paquetes': []}, 'volumenes': [], 'corrientes': [],
             'intercambios': [], 'datos': {}, 'matematico': None, 'estudio': None, 'motores': {}, 'procedencia': {'tipo': 'nuevo'}}
    author = SharedAuthor(model)
    author.append('declare_symbol', name='clock', unit='s')
    clock = sp.Symbol('clock', real=True)
    for name in names:
        if derivative_order: author.append('declare_function', name=name, unit='1', dependencies=[author.quantity(clock)])
        else: author.append('declare_symbol', name=name, unit='1')
    rows = [author.relation(expression, '0', 'Internal polynomial admission control', kind='constitutive') for expression in expressions]
    for _ in range(derivative_order):
        rows = [author.append('differentiate', sources=[row], symbol=author.quantity(clock)) for row in rows]
    model, replayed, _ = author.finish({})
    def datum(key, value):
        model['datos'][key] = {'magnitud': key, 'funcion': 'parametro', 'declaracion': {'texto': str(value), 'unidad': '1'},
                               'origen': {'propietarioId': 'estudio', 'ruta': key}}
        return key
    named = lambda name: author.quantity(sp.Function(name)(clock) if derivative_order and name in names else sp.Symbol(name, real=True))
    variables = {named(name): {key: datum(name+'.'+key, value) for key, value in
                 [('seedDataId', initial), ('lowerDataId', bound[0]), ('upperDataId', bound[1]), ('scaleDataId', 1)]}
                 for name, initial, bound in zip(names, seed, bounds)}
    model['motores']['derivedExecution'] = {'format': 'rage.derived-execution', 'version': 5,
        'sourceSignature': source_signature(model, replayed), 'timeId': named('clock'),
        'states': [{'quantityId': named(name), 'equationId': row} for name, row in zip(names, rows)] if derivative_order else [],
        'algebraic': [] if derivative_order else [{'quantityId': named(name), 'equationId': row} for name, row in zip(names, rows)],
        'unknowns': list(variables), 'parameters': {}, 'invariants': {}, 'reconstructions': [], 'checks': [],
        'nonlinear': {'variables': variables, 'residualScales': {row: datum(row+'.scale', 1) for row in rows},
                      'residualTolerance': 1e-10, 'stepTolerance': 1e-12, 'maxIterations': 30, 'maxBacktracks': 20}}
    model['estudio'] = {'tipo': 'steady', 'version': 1, 'metodoSolicitado': 'damped_newton'}
    return model


def thermal_case(owners=('region_one', 'region_two'), sink_positive=True):
    model = thermal_source(owners)
    model.update(id='internal-steady-thermal', nombre='Internal steady thermal acceptance')
    for owner in owners:
        model['datos'][owner+'.capacity']['declaracion']['texto'] = '300'
    author = SharedAuthor(model)
    q = author.quantity
    t = sp.Symbol('t', real=True)
    def add(kind, **fields):
        return author.append(kind, family='energy', **fields)
    for name, unit in [('contactHeat', 'W'), ('contactTemperature', 'K'), ('sinkHeat', 'W')]:
        add('declare_function', name=name, unit=unit, dependencies=[q(t)])
    parameters = [('firstConductance', 12, 'W/K'), ('secondConductance', 12, 'W/K'),
                  ('nonlinearResistance', '1/57600', 'W^-2'), ('sinkConductance', 6, 'W/K'),
                  ('heatInput', 120, 'W'), ('reservoirTemperature', 300, 'K')]
    for name, _, unit in parameters:
        add('declare_symbol', name=name, unit=unit)
    temperatures = [sp.Function('T__'+owner)(t) for owner in owners]
    first = add('declare_relation', left='contactHeat', right=f'firstConductance*({q(temperatures[0])}-contactTemperature)',
                relationKind='constitutive', reason='Declared passive contact law; no interface storage')
    second = add('declare_relation', left='contactHeat+nonlinearResistance*contactHeat^3',
                 right=f'secondConductance*(contactTemperature-{q(temperatures[1])})',
                 relationKind='constitutive', reason='Declared nonlinear contact law, not a conservation consequence')
    sink = add('declare_relation', left='sinkHeat', right=f'sinkConductance*({q(temperatures[1])}-reservoirTemperature)',
               relationKind='constitutive', reason='Declared heat transfer to an imposed reservoir')
    for name, row in [('firstConductance', first), ('secondConductance', second), ('sinkConductance', sink)]:
        if name == 'sinkConductance' and not sink_positive: continue
        add('declare_domain', sources=[row], symbol=name, domain='positive', reason='Positive passive conductance')
    add('declare_domain', sources=[second], symbol='nonlinearResistance', domain='nonnegative', reason='Monotone contact premise')
    energy_rows = []
    for owner, boundary_expression in zip(owners, ('heatInput-contactHeat', 'contactHeat-sinkHeat')):
        heat = sp.Function('energy_heat_rate__'+owner)(t)
        energy = sp.Function('U__'+owner)(t)
        boundary = add('declare_relation', left=q(heat), right=boundary_expression, relationKind='constraint',
                       reason='Exhaustive boundary heat; equal and opposite contact with no interface storage')
        balance = next(key for key in author.selected if key.startswith('energy.'+owner+'.') and author.source.nodes[key].equation.lhs == sp.diff(energy, t))
        energy_rows.append(author.substitute(balance, boundary, heat, family='energy'))
        caloric = 'thermodynamics.'+owner+'.caloric-inventory'
        for expr in (sp.Function('m__'+owner+'__1')(t), sp.Symbol('caloric_capacity__'+owner, real=True)):
            author.append('declare_domain', family='thermodynamics', sources=[caloric], symbol=q(expr), domain='positive', reason='Positive caloric inventory')
        author.append('declare_domain', family='thermodynamics', sources=[caloric], symbol=q(sp.Function('T__'+owner)(t)),
                      domain='interval', lower='290', upper='370', lowerOpen=False, upperOpen=False,
                      endpointUnit='K', reason='Declared caloric validity interval')
    total = add('combine', sources=energy_rows)
    model, replayed, _ = author.finish({})
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    def named(name):
        return next(key for key, value in quantities.items() if str(value) == name)
    def datum(key, value, unit):
        model['datos'][key] = {'magnitud': key, 'funcion': 'parametro',
            'declaracion': {'texto': str(value), 'unidad': unit}, 'origen': {'propietarioId': 'estudio', 'ruta': key}}
        return key
    selection = {'format': 'rage.derived-execution', 'version': 5, 'sourceSignature': source_signature(model, replayed),
        'timeId': named('t'), 'states': [], 'algebraic': [], 'unknowns': [], 'parameters': {}, 'invariants': {},
        'reconstructions': [], 'checks': [{'equationId': total, 'scaleDataId': datum('check.firstLaw', 240, 'W')}]}
    for owner, row in zip(owners, energy_rows):
        mass = sp.Function('m__'+owner+'__1')(t)
        mass_row = next(key for key in reversed(replayed.selected) if isinstance(replayed.graph.nodes[key].equation, sp.Equality) and replayed.graph.nodes[key].equation.lhs == sp.diff(mass, t))
        selection['states'] += [{'quantityId': named(str(mass)), 'equationId': mass_row},
                                {'quantityId': named('U__'+owner+'(t)'), 'equationId': row}]
        selection['invariants'][named(str(mass))] = owner+'.mass'
        selection['reconstructions'].append({'quantityId': named('m_total__'+owner+'(t)'), 'equationId': 'matter.'+owner+'.total-definition'})
        for field, data in [('caloric_capacity', 'capacity'), ('T_reference', 'referenceTemperature'), ('u_reference', 'referenceEnergy')]:
            selection['parameters'][named(field+'__'+owner)] = owner+'.'+data
    selection['algebraic'] = [{'quantityId': named(name), 'equationId': row} for name, row in
        [('contactHeat(t)', first), ('contactTemperature(t)', second), ('sinkHeat(t)', sink),
         *[('T__'+o+'(t)', 'thermodynamics.'+o+'.caloric-inventory') for o in owners]]]
    for name, value, unit in parameters:
        selection['parameters'][named(name)] = datum('steady.'+name, value, unit)
    specs = [('U__'+owners[0]+'(t)', 18000, -9000, 63000, 36000, 'J'),
             ('U__'+owners[1]+'(t)', 18000, -9000, 63000, 36000, 'J'),
             ('contactHeat(t)', 90, 0, 300, 240, 'W'), ('contactTemperature(t)', 330, 290, 370, 60, 'K'),
             ('T__'+owners[0]+'(t)', 335, 290, 370, 60, 'K'), ('T__'+owners[1]+'(t)', 310, 290, 370, 60, 'K'),
             ('sinkHeat(t)', 150, 0, 300, 240, 'W')]
    variables = {}
    for name, seed, lower, upper, scale, unit in specs:
        identity = named(name); selection['unknowns'].append(identity)
        variables[identity] = {key: datum('steady.'+identity+'.'+key, value, unit) for key, value in
            [('seedDataId', seed), ('lowerDataId', lower), ('upperDataId', upper), ('scaleDataId', scale)]}
    scales = {row: datum('steady.residual.'+row, 240, 'W') for row in [*energy_rows, first, second, sink]}
    scales.update({row: datum('steady.residual.'+row, 36000, 'J') for row in ['thermodynamics.'+o+'.caloric-inventory' for o in owners]})
    selection['nonlinear'] = {'variables': variables, 'residualScales': scales, 'residualTolerance': 1e-10,
                             'stepTolerance': 1e-12, 'maxIterations': 30, 'maxBacktracks': 20}
    model['motores']['derivedExecution'] = selection
    model['estudio'] = {'tipo': 'steady', 'version': 1, 'metodoSolicitado': 'damped_newton'}
    return model


def analytic_reference(model, owners=('region_one', 'region_two')):
    """Conservation and scalar constitutive substitution; no compiler/Newton."""
    def value(key):
        declaration = model['datos'][key]['declaracion']
        from core.unidades import a_SI
        from fractions import Fraction
        return a_SI(float(Fraction(declaration['texto'])), declaration['unidad'])
    heat = value('steady.heatInput'); sink = value('steady.sinkConductance')
    second = value('steady.reservoirTemperature')+heat/sink
    contact = second+(heat+value('steady.nonlinearResistance')*heat**3)/value('steady.secondConductance')
    first = contact+heat/value('steady.firstConductance')
    return dict(zip(['U__'+owners[0]+'(t)', 'U__'+owners[1]+'(t)', 'contactHeat(t)', 'contactTemperature(t)',
                     'T__'+owners[0]+'(t)', 'T__'+owners[1]+'(t)', 'sinkHeat(t)'],
                    [value(o+'.mass')*value(o+'.capacity')*(temperature-value(o+'.referenceTemperature'))
                     for o, temperature in zip(owners, (first, second))]+[heat, contact, first, second, heat]))


class SteadyAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = thermal_case()
        output = ROOT/'.tmp/f3-steady'; output.mkdir(parents=True, exist_ok=True)
        (output/'model.json').write_text(json.dumps(cls.model, indent=2), encoding='utf-8')

    def test_common_solve_law_derived_reference(self):
        expected = analytic_reference(self.model)
        for factor in (1., .1):
            model = copy.deepcopy(self.model)
            for key in ('residualTolerance', 'stepTolerance'):
                model['motores']['derivedExecution']['nonlinear'][key] *= factor
            system = SteadySystem(model)
            from core.solvers.nonlinear import solve as newton
            with patch('core.solvers.integrar', side_effect=AssertionError('No time integration')), \
                 patch('sympy.solve', side_effect=AssertionError('No symbolic roots')), \
                 patch('core.compilador.steady.nonlinear.solve', wraps=newton) as called:
                result = system.solve()
            self.assertEqual(called.call_count, 1)
            self.assertEqual(result['estado'], 'resuelto')
            self.assertEqual(result['ejes'], [])
            values = {row['nombre']: row['valores'] for row in result['series']}
            for name, reference in expected.items():
                scale = 36000 if name.startswith('U__') else 60 if name.startswith('T__') or 'Temperature' in name else 240
                self.assertLessEqual(abs(values[name]-reference)/scale, 1e-5)
            self.assertEqual(result['procedencia']['steadyDiagnostics']['globalUniqueness'], 'not_proved')
            evidence = result['procedencia']['steadyDiagnostics']
            self.assertGreater(evidence['initialResidualNorm'], .5)
            self.assertAlmostEqual(evidence['solver']['conditionInfinity'], 35.5208333333333, places=9)
            self.assertAlmostEqual(evidence['smallestSingularValue'], .250053926386, places=10)
            self.assertLessEqual(abs(values['contactHeat(t)']-120)/240, 1e-6)
            self.assertLessEqual(abs(values['sinkHeat(t)']-120)/240, 1e-6)
            for owner, mass in [('region_one', 2), ('region_two', 3)]:
                self.assertLessEqual(abs(values['m__'+owner+'__1(t)']-mass)/mass, 1e-6)
            from core.resultados import leer_resultados
            leer_resultados(result)
            (ROOT/'.tmp/f3-steady/result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')

    def test_common_http_and_compilation(self):
        from backend.api_modelo import resolver_modelo, describe_compilation
        result = resolver_modelo({'modelo': copy.deepcopy(self.model), 'assessmentVersion': 1})
        self.assertEqual(result['estado'], 'resuelto')
        report = describe_compilation({'modelo': copy.deepcopy(self.model)})
        self.assertEqual(report['version'], 2)
        self.assertNotIn('time', report)
        self.assertEqual(result['procedencia']['assessment']['initialization']['status'], 'not_evaluated')
        (ROOT/'.tmp/f3-steady/publication.json').write_text(json.dumps({'model': self.model, 'result': result}), encoding='utf-8')

    def test_parameter_units_order_and_domain_variants(self):
        model = copy.deepcopy(self.model)
        for key, text, unit in [('steady.heatInput', '0.09', 'kW'), ('steady.firstConductance', '16000', 'mW/K'),
                               ('steady.secondConductance', '15', 'W/K'), ('steady.sinkConductance', '8', 'W/K'),
                               ('steady.nonlinearResistance', '1/90000', 'W^-2'), ('steady.reservoirTemperature', '305', 'K'),
                               ('region_one.capacity', '.4', 'kJ/(kg*K)')]:
            model['datos'][key]['declaracion'] = {'texto': text, 'unidad': unit}
        selected = model['motores']['derivedExecution']
        selected['unknowns'].reverse(); selected['states'].reverse(); selected['algebraic'].reverse()
        for settings in selected['nonlinear']['variables'].values():
            for key in settings.values():
                data = model['datos'][key]['declaracion']
                if data['unidad'] == 'J': data.update(texto=str(float(data['texto'])/1000), unidad='kJ')
        result = resolver(model); values = {s['nombre']: s['valores'] for s in result['series']}
        for name, expected in analytic_reference(model).items(): self.assertAlmostEqual(values[name], expected, places=7)
        # A narrower box containing the solution has the same root.
        qid = self.model['motores']['derivedExecution']['unknowns'][2]
        settings = selected['nonlinear']['variables'][qid]
        model['datos'][settings['lowerDataId']]['declaracion']['texto'] = '80'
        model['datos'][settings['upperDataId']]['declaracion']['texto'] = '100'
        self.assertAlmostEqual(next(s['valores'] for s in resolver(model)['series'] if s['id'] == 'steady.'+qid), 90)
        # Seeds are not a way to select a root outside the declared box.
        model['datos'][settings['lowerDataId']]['declaracion']['texto'] = '91'
        model['datos'][settings['seedDataId']]['declaracion']['texto'] = '95'
        with self.assertRaises(LoweringError) as caught: resolver(model)
        self.assertIn(caught.exception.diagnostics[0]['code'], ('nonlinear_domain', 'nonlinear_iteration_limit'))

    def test_located_admission_failures(self):
        qid = self.model['motores']['derivedExecution']['unknowns'][2]
        settings = self.model['motores']['derivedExecution']['nonlinear']['variables'][qid]
        def data(m, key, value, unit=None):
            m['datos'][key]['declaracion']['texto'] = str(value)
            if unit: m['datos'][key]['declaracion']['unidad'] = unit
        cases = [
            ('steady_invalid_selection', lambda m: m['motores']['derivedExecution']['algebraic'].pop()),
            ('steady_invalid_selection', lambda m: m['motores']['derivedExecution']['unknowns'].pop()),
            ('steady_invalid_selection', lambda m: m['motores']['derivedExecution']['nonlinear']['residualScales'].pop('operation.11')),
            ('steady_missing_data', lambda m: m['datos'].pop('region_one.mass')),
            ('steady_invalid_units', lambda m: data(m, settings['scaleDataId'], 240, 'K')),
            ('nonlinear_invalid_settings', lambda m: data(m, settings['scaleDataId'], 0)),
            ('nonlinear_invalid_settings', lambda m: data(m, settings['upperDataId'], -1)),
            ('nonlinear_invalid_seed', lambda m: data(m, settings['seedDataId'], -1)),
            ('steady_time_dependent', lambda m: data(m, 'steady.heatInput', '120+t')),
            ('steady_invalid_selection', lambda m: m['motores']['equationWorkbench'].update(cursor=1)),
            ('steady_invalid_selection', lambda m: m['motores']['derivedExecution'].update(initialValues={})),
            ('nonlinear_iteration_limit', lambda m: m['motores']['derivedExecution']['nonlinear'].update(maxIterations=1)),
            ('steady_constraint_conflict', lambda m: data(m, 'steady.sinkConductance', 0)),
        ]
        for code, mutate in cases:
            with self.subTest(code=code):
                model = copy.deepcopy(self.model); mutate(model)
                with self.assertRaises(LoweringError) as caught: resolver(model)
                row = caught.exception.diagnostics[0]
                self.assertEqual(row['code'], code)
                for key in ('path', 'stage', 'modelId', 'sourceSignature', 'formulationSignature', 'dataSignature', 'settingsSignature', 'terminationReason'):
                    self.assertIn(key, row)
                self.assertNotIn('solution', row)

    def test_renamed_closed_pair_has_no_seed_selected_energy(self):
        model = thermal_case(('alpha_store', 'omega_store'), sink_positive=False)
        model['datos']['steady.sinkConductance']['declaracion']['texto'] = '0'
        model['datos']['steady.heatInput']['declaracion']['texto'] = '0'
        for on_family in (False, True):
            if on_family:
                for settings, value in zip(model['motores']['derivedExecution']['nonlinear']['variables'].values(), [18000, 27000, 0, 330, 330, 330, 0]):
                    model['datos'][settings['seedDataId']]['declaracion']['texto'] = str(value)
            with self.assertRaises(LoweringError) as caught: resolver(model)
            self.assertEqual(caught.exception.diagnostics[0]['code'], 'steady_structure_mismatch')

    def test_postsolve_original_checks_and_reader_tampering(self):
        from core.resultados import leer_resultados
        from core.resultados.formato import ErrorResultados
        system = SteadySystem(self.model); good = system.solve()
        corrupted = np.array([r['valores'] for r in good['series'][:7]]); corrupted[0] += 1
        with patch('core.compilador.steady.nonlinear.solve', return_value=(corrupted, good['procedencia']['steadyDiagnostics']['solver'])):
            # Faulty numerical candidate/evidence: original rows must stop publication.
            with self.assertRaises(LoweringError) as caught: system.solve()
            self.assertEqual(caught.exception.diagnostics[0]['code'], 'steady_original_residual')
        original = system.final_check
        def invalid_guard(root):
            with patch.object(system, 'admissible', return_value=False): return original(root)
        with patch.object(system, 'final_check', side_effect=invalid_guard):
            with self.assertRaises(LoweringError) as caught: system.solve()
            self.assertEqual(caught.exception.diagnostics[0]['code'], 'steady_domain')
        mutations = [lambda r: r['series'][0].update(valores=999),
            lambda r: r['procedencia']['steadyDiagnostics'].update(globalUniqueness='proved'),
            lambda r: r['procedencia']['steadyDiagnostics'].update(smallestSingularValue=0),
            lambda r: r['procedencia']['steadyDiagnostics']['solver'].update(stepNorm=1),
            lambda r: r['verificaciones'][0].update(valor=1),
            lambda r: r.update(estado='parcial'),
            lambda r: r['procedencia']['compilation'].update(time={'finalTime': 1})]
        for resign in (False, True):
            for mutate in mutations:
                bad = copy.deepcopy(good); mutate(bad)
                if resign: bad['procedencia']['steadyDiagnostics']['resultSignature'] = steady_result_signature(bad)
                # A physically altered in-bounds scalar with a forged fingerprint
                # cannot be recomputed by a reader; the original fingerprint catches it.
                if resign and bad['series'][0]['valores'] == 999: continue
                with self.assertRaises(ErrorResultados): leer_resultados(bad)

    def test_invariant_binding_admission(self):
        model = copy.deepcopy(self.model); selected = model['motores']['derivedExecution']
        qid, datum = next(iter(selected['invariants'].items()))
        del selected['invariants'][qid]; selected['unknowns'].append(qid)
        selected['nonlinear']['variables'][qid] = dict.fromkeys(['seedDataId', 'lowerDataId', 'upperDataId', 'scaleDataId'], datum)
        row = next(r['equationId'] for r in selected['states'] if r['quantityId'] == qid)
        selected['nonlinear']['residualScales'][row] = datum
        with self.assertRaises(LoweringError) as caught: resolver(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'steady_unbound_invariant')
        model = copy.deepcopy(self.model); selected = model['motores']['derivedExecution']
        qid = selected['unknowns'][0]; settings = selected['nonlinear']['variables'].pop(qid)
        selected['invariants'][qid] = settings['seedDataId']; selected['unknowns'].remove(qid)
        row = next(r['equationId'] for r in selected['states'] if r['quantityId'] == qid)
        del selected['nonlinear']['residualScales'][row]
        with self.assertRaises(LoweringError) as caught: resolver(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'steady_constraint_conflict')


class GenericSteadyTests(unittest.TestCase):
    def rejection(self, code, model):
        with self.assertRaises(LoweringError) as caught: resolver(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], code)
        self.assertEqual(caught.exception.diagnostics[0]['terminationReason'], code)

    def test_nonthermal_polynomial_and_positive_root_domain(self):
        for model, expected in [(polynomial_case(), [2, 2]),
                (polynomial_case(('unrelated^2-1',), ('unrelated',), (.5,), ((.1, 2),)), [1])]:
            result = resolver(model)
            np.testing.assert_allclose([r['valores'] for r in result['series'][:len(expected)]], expected, atol=1e-12)
            self.assertEqual(result['procedencia']['steadyDiagnostics']['globalUniqueness'], 'not_proved')

    def test_inherited_rejections_through_common_solver(self):
        cases = [('nonlinear_multiple_roots', 'u^2-1', 1, (-2, 2), {}),
                 ('nonlinear_singular_jacobian', 'u^2', 0, (-1, 1), {}),
                 ('nonlinear_singular_jacobian', 'u^2-1', 0, (-2, 2), {}), # probes may not rescue this seed
                 ('nonlinear_ill_conditioned', '(u-1)^2', 2, (1, 3), {}),
                 ('nonlinear_ill_conditioned', 'u/1000000000000', 0, (-1, 1), {}),
                 ('nonlinear_iteration_limit', 'u^2-2', 1, (.1, 4), {'maxIterations': 1}),
                 ('nonlinear_stagnation', 'u^2-2', 1, (.1, 4), {'stepTolerance': 1}),
                 ('nonlinear_line_search', 'u^3-2*u+2', 1, (-3, 3), {'maxBacktracks': 1}),
                 ('nonlinear_domain', 'u-5', 4, (.1, 4), {}),
                 ('nonlinear_invalid_seed', '(u^2-1)/(u-1)', 1, (-2, 2), {})]
        for code, expression, seed, bound, settings in cases:
            with self.subTest(code=code, expression=expression):
                model = polynomial_case((expression,), ('u',), (seed,), (bound,))
                model['motores']['derivedExecution']['nonlinear'].update(settings)
                self.rejection(code, model)
        self.rejection('nonlinear_ill_conditioned', polynomial_case(('u', 'v/1000000000000'), seed=(0, 0), bounds=((-1, 1), (-1, 1))))
        for field in ('residual', 'jacobian'):
            system = SteadySystem(polynomial_case())
            with patch.object(system, field, return_value=np.full((2,) if field == 'residual' else (2, 2), float('nan'))):
                with self.assertRaises(LoweringError) as caught: system.solve()
                self.assertEqual(caught.exception.diagnostics[0]['code'], 'nonlinear_nonfinite')

    def test_structural_constraints_and_unsupported_terms(self):
        self.rejection('steady_structure_mismatch', polynomial_case(('u-v', 'u-v')))
        self.rejection('steady_constraint_conflict', polynomial_case(('u-v', 'u-v-1')))
        self.rejection('steady_unsupported_structure', polynomial_case(('u^(1/2)',), ('u',), (1,), ((.1, 4),)))

    def test_derivative_class_and_unaccounted_constraint(self):
        for order in (1, 2):
            self.rejection('steady_unsupported_structure', polynomial_case(('u^2-1',), ('u',), (1,), ((.1, 4),), derivative_order=order))
        model = polynomial_case()
        author = SharedAuthor(model); author.definition = copy.deepcopy(model['motores']['equationWorkbench']); author.refresh()
        author.relation('u', '3', 'Incompatible independently selected constraint')
        model, replayed, _ = author.finish({})
        model['motores']['derivedExecution']['sourceSignature'] = source_signature(model, replayed)
        self.rejection('steady_constraint_conflict', model)

    def test_invalid_numbers_and_invariant_ownership(self):
        model = polynomial_case()
        model['motores']['derivedExecution']['nonlinear']['stepTolerance'] = float('nan')
        self.rejection('steady_invalid_selection', model)


if __name__ == '__main__':
    if '--http' in sys.argv:
        import asyncio
        import httpx
        from fastapi import FastAPI
        from backend.api_modelo import router
        from core.resultados import leer_resultados
        async def http_regression():
            model = json.loads((ROOT/'.tmp/f3-steady/model.json').read_text(encoding='utf-8'))
            app = FastAPI(); app.include_router(router)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                response = await client.post('/modelo/resolver', json={'modelo': model, 'assessmentVersion': 1})
                assert response.status_code == 200, response.text
                leer_resultados(response.json())
                cases = [('nonlinear_multiple_roots', polynomial_case(('u^2-1',), ('u',), (1,), ((-2, 2),))),
                         ('nonlinear_singular_jacobian', polynomial_case(('u^2',), ('u',), (0,), ((-1, 1),)))]
                missing = copy.deepcopy(model); del missing['datos']['region_one.mass']
                cases.append(('steady_missing_data', missing))
                for code, candidate in cases:
                    response = await client.post('/modelo/resolver', json={'modelo': candidate, 'assessmentVersion': 1})
                    assert response.status_code == 422, response.text
                    detail = response.json()['detail']
                    assert detail['diagnostics'][0]['code'] == code, detail
                    assert 'series' not in response.json()
            print('ASGI HTTP: thermal 200 and multiple-root/singular/missing-data 422 responses verified.')
        asyncio.run(http_regression())
    else:
        unittest.main()
