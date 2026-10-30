"""F3 slice 5: inverse specifications on the common steady solve; independent references."""
import copy
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))
from m1_acceptance import SharedAuthor
from test_f3_steady_state import thermal_case
from core import mezclas as mz
from core import coexistencia_lv as lv
from core.compilador.derived import source_signature
from core.compilador.steady import SteadySystem, LoweringError
from core.mathematics.dimensions import catalog
from core.solvers import inverse_spec, nonlinear
from core.solvers.inverse_steady import InverseSteadySystem

WORST = {}


def worst(case, error):
    WORST[case] = max(WORST.get(case, 0.), float(error))


def code(error):
    return error.diagnostics[0]['code']


def datum(model, key, value, unit):
    model['datos'][key] = {'magnitud': key, 'funcion': 'parametro', 'declaracion': {'texto': repr(value) if isinstance(value, float) else str(value), 'unidad': unit},
                           'origen': {'propietarioId': 'estudio', 'ruta': key}}
    return key


def parameter_case(rows, unknowns, parameters, model_id='inverse-control'):
    """Internal steady control authored with generic declaration operations.

    rows: [(expression, unit)] declared as expression = 0; unknowns: {name: (unit, seed, lo, hi, scale)};
    parameters: {name: (unit, value)}.
    """
    model = {'formato': 'rage.modelo', 'version': 0, 'id': model_id, 'nombre': 'Inverse specification control',
             'componentes': [], 'termodinamica': {'paquetes': []}, 'volumenes': [], 'corrientes': [],
             'intercambios': [], 'datos': {}, 'matematico': None, 'estudio': None, 'motores': {}, 'procedencia': {'tipo': 'nuevo'}}
    author = SharedAuthor(model)
    author.append('declare_symbol', name='clock', unit='s')
    for name, spec in [*unknowns.items(), *parameters.items()]:
        author.append('declare_symbol', name=name, unit=spec[0])
    keys = [author.relation(expression, '0', 'Internal inverse-specification control', kind='constitutive') for expression, _ in rows]
    model, replayed, _ = author.finish({})
    named = lambda name: author.quantity(sp.Symbol(name, real=True))
    variables = {named(name): {key: datum(model, name+'.'+key, value, unit) for key, value in
                 [('seedDataId', seed), ('lowerDataId', lo), ('upperDataId', hi), ('scaleDataId', scale)]}
                 for name, (unit, seed, lo, hi, scale) in unknowns.items()}
    model['motores']['derivedExecution'] = {'format': 'rage.derived-execution', 'version': 5,
        'sourceSignature': source_signature(model, replayed), 'timeId': named('clock'), 'states': [],
        'algebraic': [{'quantityId': named(name), 'equationId': key} for name, key in zip(unknowns, keys)],
        'unknowns': list(variables), 'invariants': {}, 'reconstructions': [], 'checks': [],
        'parameters': {named(name): datum(model, 'input.'+name, value, unit) for name, (unit, value) in parameters.items()},
        'nonlinear': {'variables': variables, 'residualScales': {key: datum(model, key+'.scale', 1, unit) for key, (_, unit) in zip(keys, rows)},
                      'residualTolerance': 1e-10, 'stepTolerance': 1e-12, 'maxIterations': 30, 'maxBacktracks': 20}}
    model['estudio'] = {'tipo': 'steady', 'version': 1, 'metodoSolicitado': 'damped_newton'}
    return model, named


def specification(model, outputs, freed):
    """outputs: [(id, quantityId, target, unit, scale)]; freed: [(quantityId, seed, lo, hi, scale, unit)]."""
    record = {'format': inverse_spec.FORMAT, 'version': 1, 'specifications': [], 'freedInputs': []}
    for sid, qid, target, unit, scale in outputs:
        record['specifications'].append({'id': sid, 'quantityId': qid, 'targetDataId': datum(model, 'spec.'+sid+'.target', target, unit),
                                         'residualScaleDataId': datum(model, 'spec.'+sid+'.scale', scale, unit)})
    for qid, seed, lo, hi, scale, unit in freed:
        record['freedInputs'].append({'quantityId': qid, **{key: datum(model, 'free.'+qid+'.'+key, value, unit) for key, value in
                                      [('seedDataId', seed), ('lowerDataId', lo), ('upperDataId', hi), ('scaleDataId', scale)]}})
    return record


def series_value(result, qid):
    return float(next(s['valores'] for s in result['series'] if s['id'] == 'steady.'+qid))


def mixer(F2=3, x1=0.8, x2=0.2):
    return parameter_case([('F1+F2-F3', 'mol/s'), ('F1*x1+F2*x2-F3*x3', 'mol/s')],
                          {'F3': ('mol/s', 4, .01, 100, 1), 'x3': ('1', .5, 0, 1, .1)},
                          {'F1': ('mol/s', 1), 'F2': ('mol/s', F2), 'x1': ('1', x1), 'x2': ('1', x2)}, 'inverse-mixer')


class LinearMixer(unittest.TestCase):
    """(a) Fix the outlet mole fraction, free one feed flow: F1 = F2 (x3 - x2) / (x1 - x3)."""

    def test_outlet_composition_frees_feed_flow(self):
        for target in (.3, .6, .75):
            model, named = mixer()
            record = specification(model, [('outlet-fraction', named('x3'), target, '1', .1)],
                                   [(named('F1'), 1, .01, 50, 1, 'mol/s')])
            result = InverseSteadySystem(model, record).solve()
            analytic = 3*(target-.2)/(.8-target)
            F1 = series_value(result, named('F1'))
            worst('a.mixer.F1.relative', abs(F1-analytic)/analytic)
            self.assertLess(abs(F1-analytic)/analytic, 1e-10)
            self.assertLess(abs(series_value(result, named('x3'))-target), 1e-12)
            self.assertLess(abs(series_value(result, named('F3'))-(F1+3)), 1e-9)
            diagnostics = result['procedencia']['steadyDiagnostics']
            self.assertEqual(diagnostics['verdict'], 'local_regular_root')
            self.assertEqual(diagnostics['inverseSpecification']['freedInputs'], [named('F1')])
            self.assertIn('specification.outlet-fraction', diagnostics['equationIds'])

    def test_specification_invalidates_solve_not_model_or_transform(self):
        model, named = mixer()
        forward = SteadySystem(copy.deepcopy(model)).report
        reports = []
        for target in (.6, .7):
            case = copy.deepcopy(model)
            record = specification(case, [('outlet-fraction', named('x3'), target, '1', .1)], [(named('F1'), 1, .01, 50, 1, 'mol/s')])
            reports.append(InverseSteadySystem(case, record).report)
        for report in reports:
            self.assertEqual(report['sourceSignature'], forward['sourceSignature'])
            self.assertEqual(report['formulationSignature'], forward['formulationSignature'])
            self.assertEqual(report['inverseSpecification']['invalidates'], ['solve', 'results'])
        self.assertNotEqual(reports[0]['specificationSignature'], reports[1]['specificationSignature'])
        self.assertNotEqual(reports[0]['signature'], reports[1]['signature'])


def thermal_ids(model):
    selection = model['motores']['derivedExecution']
    heat = next(q for q, d in selection['parameters'].items() if d == 'steady.heatInput')
    temperature = next(r['quantityId'] for r in selection['algebraic'] if r['equationId'] == 'thermodynamics.region_one.caloric-inventory')
    return heat, temperature


def analytic_heat(T1):
    # T1 = 300 + Q/3 + Q^3/691200 from the declared laws (slice-4 hand reference).
    roots = np.roots([1/691200, 0, 1/3, 300-T1])
    return float(next(r.real for r in roots if abs(r.imag) < 1e-12))


class Heater(unittest.TestCase):
    """(b) Fix the heated-region temperature, free the heat input; round trip through the forward solve."""

    @classmethod
    def setUpClass(cls):
        cls.base = thermal_case()

    def test_outlet_temperature_frees_heat_input(self):
        model = copy.deepcopy(self.base)
        heat, temperature = thermal_ids(model)
        record = specification(model, [('heated-temperature', temperature, 350, 'K', 60)], [(heat, 120, 0, 300, 240, 'W')])
        result = InverseSteadySystem(model, record).solve()
        Q = series_value(result, heat)
        worst('b.heater.Q_vs_analytic.W', abs(Q-analytic_heat(350)))
        self.assertLess(abs(Q-analytic_heat(350)), 1e-8)
        forward = copy.deepcopy(self.base)
        forward['datos']['steady.heatInput']['declaracion']['texto'] = repr(Q)
        T1 = series_value(SteadySystem(forward).solve(), temperature)
        worst('b.heater.roundtrip_T.K', abs(T1-350))
        self.assertLess(abs(T1-350), 1e-8)

    def test_unattainable_temperature_reports_bound(self):
        model = copy.deepcopy(self.base)
        heat, temperature = thermal_ids(model)
        record = specification(model, [('heated-temperature', temperature, 360, 'K', 60)], [(heat, 120, 0, 150, 240, 'W')])
        with self.assertRaises(LoweringError) as caught:
            InverseSteadySystem(model, record).solve()
        self.assertEqual(code(caught.exception), 'inverse_target_unattainable')
        evidence = caught.exception.diagnostics[0]['reachability']
        self.assertEqual(evidence['kind'], 'bound')
        self.assertAlmostEqual(evidence['sampledRange'][1], 300+150/3+150**3/691200, delta=1e-7)
        self.assertEqual(evidence['extremumInput'], 150)


class TurningPointAndRank(unittest.TestCase):
    """(d) unattainable targets and rank/structure rejections on internal controls."""

    def case(self, rows, target, freed, unknowns=None, parameters=None):
        model, named = parameter_case(rows, unknowns or {'u': ('1', 1, -10, 10, 1)}, parameters or {'b': ('1', 1)})
        record = specification(model, [('target', named('u'), target, '1', 1)], [(named(freed[0]), *freed[1:], '1')])
        return model, record, named

    def test_target_beyond_turning_point(self):
        model, record, _ = self.case([('u-b*(4-b)', '1')], 5, ('b', 1, 0, 4, 1))
        with self.assertRaises(LoweringError) as caught:
            InverseSteadySystem(model, record).solve()
        self.assertEqual(code(caught.exception), 'inverse_target_unattainable')
        evidence = caught.exception.diagnostics[0]['reachability']
        self.assertEqual(evidence['kind'], 'turning_point')
        self.assertAlmostEqual(evidence['extremumInput'], 2, delta=4/32)
        self.assertAlmostEqual(evidence['sampledRange'][1], 4, delta=1e-12)

    def test_two_branches_are_not_chosen_silently(self):
        model, record, named = self.case([('u-b*(4-b)', '1')], 3, ('b', 1.5, 0, 4, 1))
        with self.assertRaises(LoweringError) as caught:
            InverseSteadySystem(model, record).solve()
        self.assertEqual(code(caught.exception), 'nonlinear_multiple_roots')
        model, record, named = self.case([('u-b*(4-b)', '1')], 3, ('b', 1.5, 0, 1.9, 1))
        self.assertAlmostEqual(series_value(InverseSteadySystem(model, record).solve(), named('b')), 1, delta=1e-12)

    def test_unreachable_input_rejected_structurally(self):
        rows = [('u-a', '1'), ('v-b', '1')]
        model, named = parameter_case(rows, {'u': ('1', 1, -10, 10, 1), 'v': ('1', 1, -10, 10, 1)}, {'a': ('1', 1), 'b': ('1', 1)})
        record = specification(model, [('target', named('u'), 2, '1', 1)], [(named('b'), 1, -5, 5, 1, '1')])
        with patch.object(nonlinear, 'solve', side_effect=AssertionError('no solve before admission')):
            with self.assertRaises(LoweringError) as caught:
                InverseSteadySystem(model, record)
        self.assertEqual(code(caught.exception), 'inverse_unreachable')

    def test_locally_insensitive_seed_rejected_then_regular_seed_solves(self):
        model, record, named = self.case([('u-(b-1)^2', '1')], 2, ('b', 1, .5, 4, 1))
        with self.assertRaises(LoweringError) as caught:
            InverseSteadySystem(model, record)
        self.assertEqual(code(caught.exception), 'inverse_rank_deficient')
        self.assertIsNotNone(caught.exception.diagnostics[0]['regularity']['sensitivitySigmaMin'])
        model, record, named = self.case([('u-(b-1)^2', '1')], 2, ('b', 2, 1.2, 4, 1))
        b = series_value(InverseSteadySystem(model, record).solve(), named('b'))
        worst('d.sqrt2.b', abs(b-(1+math.sqrt(2))))
        self.assertLess(abs(b-(1+math.sqrt(2))), 1e-12)

    def test_failed_forward_samples_never_declare_unattainable(self):
        # Review F-1: x^3 - x - p = 0, u - x^2 = 0, x in [0, 2], u = 0.1, p freed in [-1, 1]. The unique admissible
        # root is x = sqrt(0.1), p = 0.1^1.5 - 0.1^0.5; from seed x = 1.9 Newton fails and the forward scan fails
        # wherever x^3 - x = p has several roots, so the sampled range is inconclusive and Newton's failure stands.
        exact = .1**1.5-.1**.5
        for seed_x in (1.9, 1.2):
            model, named = parameter_case([('x^3-x-p', '1'), ('u-x^2', '1')],
                                          {'x': ('1', seed_x, 0, 2, 1), 'u': ('1', seed_x**2, 0, 4, 1)}, {'p': ('1', .5)}, 'inverse-f1')
            record = specification(model, [('target', named('u'), .1, '1', 1)], [(named('p'), .5, -1, 1, 1, '1')])
            if seed_x == 1.9:
                with self.assertRaises(LoweringError) as caught:
                    InverseSteadySystem(model, record).solve()
                self.assertNotEqual(code(caught.exception), 'inverse_target_unattainable')
                self.assertTrue(code(caught.exception).startswith('nonlinear_'))
                evidence = caught.exception.diagnostics[0]['reachability']
                self.assertEqual(evidence['kind'], 'inconclusive')
                self.assertGreater(evidence['failedSamples'], 0)
            else:
                p = series_value(InverseSteadySystem(model, record).solve(), named('p'))
                worst('d.f1.p', abs(p-exact))
                self.assertLess(abs(p-exact), 1e-12)

    def test_kernel_passes_multiple_roots_through(self):
        residual = lambda w: np.array([w[0]**3-w[0]-w[2], w[1]-w[0]**2, w[1]-.1])
        jacobian = lambda w: np.array([[3*w[0]**2-1, 0, -1], [-2*w[0], 1, 0], [0, 1, 0]])
        problem = inverse_spec.InverseProblem(residual, jacobian, 2, [.1], [1.2, 1.44, .5], [[-2, 2], [0, 4], [-1, 1]],
                                              [1, 1, 1], [1, 1, 1], [[1, 0, 1], [1, 1, 0], [0, 1, 0]])
        two_roots = nonlinear.NonlinearError('nonlinear_multiple_roots', 'Two admissible roots.')
        with patch.object(nonlinear, 'solve', side_effect=two_roots),              patch.object(inverse_spec, 'reachable_scan', side_effect=AssertionError('no scan for two roots')):
            with self.assertRaises(inverse_spec.InverseError) as caught:
                problem.solve()
        self.assertEqual(caught.exception.code, 'nonlinear_multiple_roots')


class NonSquareAndInvalid(unittest.TestCase):
    """(e) rejected before solving."""

    def test_rejections_before_solving(self):
        model, named = mixer()
        F = lambda q, seed=1: (named(q), seed, .01, 50, 1, 'mol/s')
        cases = [('inverse_not_square', [('x', named('x3'), .6, '1', .1)], []),
                 ('inverse_not_square', [], [F('F1')]),
                 ('inverse_not_square', [('x', named('x3'), .6, '1', .1)], [F('F1'), F('F2', 3)]),
                 ('inverse_invalid_input', [('x', named('x3'), .6, '1', .1)], [F('F3')]),
                 ('inverse_invalid_output', [('x', named('x1'), .6, '1', .1)], [F('F1')])]
        for expected, outputs, freed in cases:
            case = copy.deepcopy(model)
            record = specification(case, outputs, freed)
            with self.subTest(expected=expected, outputs=len(outputs), freed=len(freed)),                     patch.object(nonlinear, 'solve', side_effect=AssertionError('solved before admission')):
                with self.assertRaises(LoweringError) as caught:
                    InverseSteadySystem(case, record)
                self.assertEqual(code(caught.exception), expected)
        with self.assertRaises(inverse_spec.InverseError):
            inverse_spec.read_specification({'format': inverse_spec.FORMAT, 'version': 2, 'specifications': [], 'freedInputs': []})

    def test_wrong_target_units_rejected(self):
        model, named = mixer()
        record = specification(model, [('x', named('x3'), .6, 'K', .1)], [(named('F1'), 1, .01, 50, 1, 'mol/s')])
        with self.assertRaises(LoweringError) as caught:
            InverseSteadySystem(model, record)
        self.assertEqual(code(caught.exception), 'steady_invalid_units')


ETHANOL, WATER = '64-17-5', '7732-18-5'
P = 101325.


class FlashVaporFraction(unittest.TestCase):
    """(c) Fixed vapor fraction, free T at fixed P, through the common package potentials.

    Forward rows: mu_i^L(T, P, x) = mu_i^V(T, P, y) for both species and the component-1 balance
    z1 = (1 - beta) x1 + beta y1 (species 2 is the dependent total). Specification: beta - target = 0.
    """

    @classmethod
    def setUpClass(cls):
        cls.system = mz.Sistema('unifac-original-public', [ETHANOL, WATER])
        cls.z1 = .4

    def problem(self, target, seed_T=355.):
        s, z1 = self.system, self.z1
        def residual(w):
            x1, y1, beta, T = map(float, w)
            try:
                mL = s.mu('liquido', T, P, np.array([x1, 1-x1]), [0, 1])
                mV = s.mu('vapor', T, P, np.array([y1, 1-y1]), [0, 1])
            except mz.FueraDeAlcance as error:
                raise ValueError(str(error))
            return np.array([*((mL-mV)/(mz.R*T)), z1-(1-beta)*x1-beta*y1, beta-target])
        scales = np.array([.05, .05, .1, 5.])
        def jacobian(w):
            w = np.asarray(w, float); columns = []
            for j, h in enumerate(1e-6*scales):
                d = np.zeros(4); d[j] = h
                columns.append((residual(w+d)-residual(w-d))/(2*h))
            return np.array(columns).T
        incidence = [[1, 1, 0, 1], [1, 1, 0, 1], [1, 1, 1, 0], [0, 0, 1, 0]]
        bounds = [[1e-3, 1-1e-3], [1e-3, 1-1e-3], [-.05, 1.05], [330, 400]]
        return inverse_spec.InverseProblem(residual, jacobian, 3, [target], [.3, .55, .5, seed_T], bounds, scales,
                                           [1, 1, .1, .1], incidence, ['mu.ethanol', 'mu.water', 'balance.ethanol', 'spec.beta'],
                                           settings={'residual_tolerance': 1e-10, 'step_tolerance': 1e-9})

    def vapor_fraction(self, T):
        state = self.system.equilibrio_TP(T, P, np.array([self.z1, 1-self.z1]))
        return sum(f.n for f in state.fases if f.tipo == 'vapor')/sum(f.n for f in state.fases), state

    def test_bubble_matches_existing_coexistence_solver(self):
        root, evidence = self.problem(0.).solve()
        T_b = root[3]
        reference, y_ref = lv.resolver_punto(self.system, 'Txy', P, self.z1, (T_b+.5, root[1]))
        worst('c.bubble.T.K', abs(T_b-reference)); worst('c.bubble.y1', abs(root[1]-y_ref))
        self.assertLess(abs(T_b-reference), 1e-7)
        self.assertLess(abs(root[1]-y_ref), 1e-7)
        self.assertEqual(self.vapor_fraction(T_b-.01)[0], 0.)
        self.assertGreater(self.vapor_fraction(T_b+.01)[0], 0.)
        self.assertEqual(evidence['verdict'], 'local_regular_root')

    def test_interior_vapor_fraction_round_trip_with_gibbs_flash(self):
        for target in (.25, .5, .75):
            root, _ = self.problem(target).solve()
            beta, state = self.vapor_fraction(root[3])
            liquid = next(f for f in state.fases if f.tipo == 'liquido'); vapor = next(f for f in state.fases if f.tipo == 'vapor')
            worst('c.flash.beta', abs(beta-target))
            worst('c.flash.x1', abs(liquid.x[0]-root[0])); worst('c.flash.y1', abs(vapor.x[0]-root[1]))
            self.assertLess(abs(beta-target), 1e-6)
            self.assertLess(abs(liquid.x[0]-root[0]), 1e-6)
            self.assertLess(abs(vapor.x[0]-root[1]), 1e-6)

    def test_dew_brackets_gibbs_flash(self):
        root, _ = self.problem(1.).solve()
        T_d = root[3]
        self.assertLess(self.vapor_fraction(T_d-.01)[0], 1.)
        self.assertEqual(self.vapor_fraction(T_d+.01)[0], 1.)
        self.assertLess(abs(root[1]-self.z1), 1e-10)
        # Independent coexistence solve at the incipient liquid: it must return T_d and y = z.
        reference, y_ref = lv.resolver_punto(self.system, 'Txy', P, root[0], (T_d+.5, self.z1))
        worst('c.dew.T.K', abs(T_d-reference)); worst('c.dew.y1', abs(y_ref-self.z1))
        self.assertLess(abs(T_d-reference), 1e-7)
        self.assertLess(abs(y_ref-self.z1), 1e-7)

    def test_superheated_target_is_not_labelled_bound(self):
        # Review F-1: beta = 1.2 has no two-phase root, but forward samples fail beyond the dew point, so the scan is
        # inconclusive and Newton's failure is re-raised; the interior sampled extremum is never called a bound.
        with self.assertRaises(inverse_spec.InverseError) as caught:
            self.problem(1.2).solve()
        self.assertNotEqual(caught.exception.code, 'inverse_target_unattainable')
        evidence = caught.exception.diagnostic['reachability']
        self.assertEqual(evidence['kind'], 'inconclusive')
        self.assertGreater(evidence['failedSamples'], 0)
        self.assertNotIn('extremumInput', evidence)


def tearDownModule():
    for key, error in sorted(WORST.items()):
        print(f'WORST {key}: {error:.3e}')


if __name__ == '__main__':
    unittest.main()
