"""Demo 0.3 C1 control kernel and kernel-audit A-2 regressions.

C1: the shared `declare_rate` operation, `min`/`max` with a same-dimension
check and their lowering, the recorded-zero and inactive-rate lowering rules
(amendment CR-1 included) and the rejection of a constant joined to a
time-dependent expression. The control loop is authored from the energy law of
one closed rigid region through the same pinned operations as Model; the PI
reference is the matrix exponential of the hand-derived closed loop, not a
value computed by the engine.

A-2: a declared identity or contradiction is a located, coded rejection, and a
Boolean relation never reaches `.lhs` (HTTP 422, not 500).
"""
import asyncio
import copy
from pathlib import Path
import sys
import unittest

import httpx
import numpy as np
import sympy as sp
from fastapi import FastAPI
from scipy.linalg import expm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from m1_acceptance import thermal_source
from core.compilador.derived import DerivedSystem, LoweringError, resolve_system, source_signature
from core.mathematics.contract import FORMAT
from core.mathematics.dimensions import catalog, dimension, parse_expression
from core.mathematics.domains import DomainPremise, select_polynomial_branch
from core.mathematics.errors import MathematicsError
from core.mathematics.graph import solve_unique
from core.mathematics.session import edit_history, replay_operations
from core.modelo.equation_workbench import _known_unit, _source_graph, build

OWNER = 'region_a'
t = sp.Symbol('t', real=True)
T = sp.Function('T__' + OWNER)(t)
U = sp.Function('U__' + OWNER)(t)
Q = sp.Function('energy_heat_rate__' + OWNER)(t)
MASS = sp.Function('m__' + OWNER + '__1')(t)
# Closed loop data: m c = 2 kg * 500 J/(kg K) (thermal_source); T(0) = 320 K.
LOOP = {'setpoint': (330, 'K'), 'gain': (0.05, '1/K'), 'integralTime': (50, 's'), 'bias': (0, '1'),
        'commandMin': (-1, '1'), 'commandMax': (1, '1'), 'heaterPower': (1000, 'W')}
HEAT_CAPACITY, T0, HORIZON = 2 * 500, 320, 600


class Author:
    """The Model session driver: pinned appends, Undo and replay only."""

    def __init__(self):
        self.model = thermal_source((OWNER,))
        self.source, self.selected, self.locations, self.units = _source_graph(self.model)
        self.definition = {'format': FORMAT, 'version': 1, 'operations': [], 'cursor': 0}
        self.refresh()

    def refresh(self):
        self.result = replay_operations(self.source, self.selected, self.locations, self.units, self.definition,
                                        require_same_family=True, unit_resolver=_known_unit)

    def edit(self, action):
        self.definition = edit_history(self.source, self.selected, self.locations, self.units, self.definition,
                                       action, require_same_family=True, unit_resolver=_known_unit)
        self.refresh()

    def append(self, kind, family='energy', **fields):
        self.edit({'kind': 'append', 'operation': {'kind': kind, 'family': family, **fields}})
        return 'operation.' + str(self.definition['cursor'])

    def clone(self):
        other = Author.__new__(Author)
        other.model = copy.deepcopy(self.model)
        other.source, other.selected, other.locations, other.units = self.source, self.selected, self.locations, self.units
        other.definition = copy.deepcopy(self.definition)
        other.refresh()
        return other

    def quantity(self, expression):
        return next(key for key, value in {**catalog(self.result.graph, self.result.units),
                                          **self.result.introduced}.items() if value == expression)


def author_pid():
    """PID root on the region temperature, its actuator join, then the PI reduction."""
    author = Author(); rows = {}
    for name, unit in [('setpoint', 'K'), ('gain', '1/K'), ('integralTime', 's'), ('derivativeTime', 's'),
                       ('filterTime', 's'), ('bias', '1'), ('commandMin', '1'), ('commandMax', '1'), ('heaterPower', 'W')]:
        author.append('declare_symbol', name=name, unit=unit)
    for name, unit in [('error', 'K'), ('integral', 'K*s'), ('filtered', 'K'), ('derivativeAction', 'K'),
                       ('command', '1'), ('valve', '1')]:
        author.append('declare_function', name=name, unit=unit, dependencies=[author.quantity(t)])
    temperature = author.quantity(T)
    rows['error'] = author.append('declare_relation', left='error', right=f'setpoint-{temperature}',
                                  reason='Reverse-acting control error on the measured temperature')
    rows['integral'] = author.append('declare_rate', symbol='integral', right='error',
                                     reason='Integral state of the controller')
    rows['filter'] = author.append('declare_rate', symbol='filtered', right=f'({temperature}-filtered)/filterTime',
                                   reason='First-order filter of the measurement for the derivative action')
    rows['derivative'] = author.append('declare_relation', left='derivativeAction',
                                       right=f'-derivativeTime*({temperature}-filtered)/filterTime',
                                       reason='Derivative action on the filtered measurement')
    rows['law'] = author.append('declare_relation', left='command',
                                right='bias+gain*(error+integral/integralTime+derivativeAction)',
                                reason='ISA dependent PID law')
    rows['valve'] = author.append('declare_relation', left='valve', right='min(max(command,commandMin),commandMax)',
                                  relationKind='constitutive', reason='Valve signal range of the actuator')
    rows['heat'] = author.append('declare_relation', left=author.quantity(Q), right='heaterPower*valve',
                                 relationKind='constraint',
                                 reason='Heater duty proportional to the valve signal; the only heat exchange of the region')
    balance = next(key for key in author.selected if key.startswith('energy.' + OWNER + '.')
                   and author.source.nodes[key].equation.lhs == sp.diff(U, t))
    rows['energy'] = author.append('substitute', sources=[balance], relation=rows['heat'], symbol=author.quantity(Q))
    rows['zero'] = author.append('apply_zero', sources=[rows['derivative']], symbol='derivativeTime',
                                 reason='PI controller: no derivative action')
    return author, rows


def lowered_model(author, rows, data=None, filter_state=False):
    """Bind numerical data in Solve; no equation is added here."""
    model = copy.deepcopy(author.model)
    model['motores']['equationWorkbench'] = copy.deepcopy(author.definition)
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    named = lambda name: next(key for key, value in quantities.items() if str(value) == name)
    def datum(key, value, unit, role='parametro'):
        model['datos'][key] = {'magnitud': key, 'funcion': role, 'declaracion': {'texto': str(value), 'unidad': unit},
                               'origen': {'propietarioId': 'estudio', 'ruta': key}}
        return key
    volume = model['volumenes'][0]
    selection = {'format': 'rage.derived-execution', 'version': 1, 'sourceSignature': source_signature(model, replayed),
                 'timeId': named('t'), 'states': [], 'parameters': {}, 'initialValues': {}, 'initialEquations': [],
                 'reconstructions': [], 'checks': []}
    mass_row = next(key for key in replayed.selected if isinstance(replayed.graph.nodes[key].equation, sp.Equality)
                    and replayed.graph.nodes[key].equation.lhs == sp.diff(MASS, t))
    selection['states'] = [{'quantityId': named(str(MASS)), 'equationId': mass_row},
                           {'quantityId': named(str(U)), 'equationId': rows['energy']},
                           {'quantityId': 'integral', 'equationId': rows['integral']}]
    selection['initialValues'] = {named(str(MASS)): volume['inicial']['cantidades']['datoIds']['1'],
                                  'integral': datum('solve.integral0', 0, 'K*s'),
                                  named(str(T)): volume['inicial']['energia']['datoId']}
    if filter_state:
        selection['states'].append({'quantityId': 'filtered', 'equationId': rows['filter']})
        selection['initialValues']['filtered'] = datum('solve.filtered0', T0, 'K')
    caloric = 'thermodynamics.' + OWNER + '.caloric-inventory'
    selection['reconstructions'] = [{'quantityId': named(str(T)), 'equationId': caloric},
                                    {'quantityId': named('m_total__' + OWNER + '(t)'), 'equationId': 'matter.' + OWNER + '.total-definition'}]
    selection['initialEquations'] = [caloric]
    for prefix, key in [('caloric_capacity', 'cId'), ('T_reference', 'TRefId'), ('u_reference', 'uRefId')]:
        selection['parameters'][named(prefix + '__' + OWNER)] = volume['termodinamica']['parametros'][key]
    for name, (value, unit) in {**LOOP, **(data or {})}.items():
        selection['parameters'][name] = datum('solve.' + name, value, unit)
    model['datos'][volume['inicial']['energia']['datoId']]['declaracion']['texto'] = str(T0)
    horizon = datum('solve.finalTime', HORIZON, 's', 'estudio')
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': horizon, 'metodoSolicitado': 'rk45', 'muestras': 121,
                        'rtol': 1e-10, 'atol': {'cantidad': 1e-11, 'energia': 1e-6}}
    model['motores']['derivedExecution'] = selection
    return model


def pi_reference(times):
    """Hand-derived PI loop: x = T - r, m c x' = P K_c (-x + I/tau_I), I' = -x."""
    a = LOOP['heaterPower'][0] * LOOP['gain'][0] / HEAT_CAPACITY
    matrix = np.array([[-a, a / LOOP['integralTime'][0]], [-1., 0.]])
    start = np.array([T0 - LOOP['setpoint'][0], 0.])
    return np.array([LOOP['setpoint'][0] + (expm(matrix * x) @ start)[0] for x in times])


def rejected(test, code, function, *args):
    with test.assertRaises(LoweringError) as caught:
        function(*args)
    test.assertEqual(caught.exception.diagnostics[0]['code'], code, caught.exception.diagnostics)
    return caught.exception.diagnostics[0]


class DeclaredRateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.author, cls.rows = author_pid()

    def test_declared_rate_is_a_typed_root_with_units_and_reversible_history(self):
        graph = self.author.result.graph
        node = graph.nodes[self.rows['integral']]
        integral = self.author.result.introduced['integral']
        self.assertEqual(node.equation.lhs, sp.Derivative(integral, t))
        self.assertEqual(node.equation.rhs, self.author.result.introduced['error'])
        self.assertEqual((node.kind, node.rule, node.dependent), ('definition', 'declared_rate', False))
        units = self.author.result.units
        self.assertEqual(dimension(node.equation.lhs, units, _known_unit), {'Theta': 1})
        self.assertIn(sp.Ne(sp.Symbol('filterTime', real=True), 0, evaluate=False),
                      graph.nodes[self.rows['filter']].predicates)
        # Undo, redo and a fresh replay reproduce the same graph.
        before = {key: node.equation for key, node in graph.nodes.items()}
        cursor = self.author.definition['cursor']
        author = self.author.clone()
        for _ in range(cursor - int(self.rows['integral'].split('.')[1]) + 1):
            author.edit({'kind': 'undo'})
        self.assertNotIn(self.rows['integral'], author.result.graph.nodes)
        for _ in range(cursor - author.definition['cursor']):
            author.edit({'kind': 'redo'})
        self.assertEqual({key: node.equation for key, node in author.result.graph.nodes.items()}, before)
        model = copy.deepcopy(self.author.model); model['motores']['equationWorkbench'] = self.author.definition
        self.assertEqual({key: node.equation for key, node in build(model).graph.nodes.items()}, before)

    def test_declared_rate_rejections(self):
        author = self.author.clone()
        derivative = author.quantity(sp.Derivative(author.result.introduced['integral'], t))
        for fields, code in [({'symbol': 'gain', 'right': '0'}, 'rate_of_constant'),
                             ({'symbol': derivative, 'right': 'error'}, 'higher_order_rate'),
                             ({'symbol': 'command', 'right': 'error'}, 'incompatible_rate_units'),
                             ({'symbol': 'command', 'right': 'error/integralTime'}, 'incompatible_rate_units'),
                             ({'symbol': author.quantity(T), 'right': 'error/integralTime'}, 'undeclared_rate_quantity')]:
            with self.subTest(code=code, fields=fields):
                with self.assertRaises(MathematicsError) as caught:
                    author.append('declare_rate', reason='Probe', **fields)
                self.assertEqual(caught.exception.code, code)
                self.assertTrue(str(caught.exception).startswith('operation.' + str(author.definition['cursor'] + 1) + ': '))
        with self.assertRaises(MathematicsError):
            author.append('declare_rate', symbol='command', right='1/integralTime', relationKind='constraint', reason='Probe')
        # A rejected append leaves the history unchanged.
        self.assertEqual(author.definition, self.author.definition)

    def test_min_and_max_parse_with_one_dimension_and_evaluate_directly(self):
        units = self.author.result.units
        quantities = {**catalog(self.author.result.graph, units), **self.author.result.introduced}
        with self.assertRaises(MathematicsError):
            parse_expression('min(setpoint,gain)', quantities, [], units, _known_unit)
        with self.assertRaises(MathematicsError):
            parse_expression('max(heaterPower,setpoint,commandMax)', quantities, [], units, _known_unit)
        expression = parse_expression('min(max(command,commandMin),commandMax)', quantities, [], units, _known_unit)
        self.assertEqual(dimension(expression, units, _known_unit), {})
        symbols = [quantities[name] for name in ('command', 'commandMin', 'commandMax')]
        for values in [(0.3, -1, 1), (1.7, -1, 1), (-2.5, -1, 1), (0.2, 0.2, 0.9), (5, 0, 0.25)]:
            value = expression.xreplace(dict(zip(symbols, map(sp.Float, values))))
            self.assertEqual(float(value), min(max(values[0], values[1]), values[2]))


class ControlLoweringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.author, cls.rows = author_pid()
        cls.pi = lowered_model(cls.author, cls.rows)
        cls.system = DerivedSystem(copy.deepcopy(cls.pi))

    def test_pid_reduced_to_pi_lowers_without_derivative_or_filter_data(self):
        selection = self.pi['motores']['derivedExecution']
        self.assertNotIn('derivativeTime', selection['parameters'])
        self.assertNotIn('filterTime', selection['parameters'])
        self.assertNotIn('filtered', [row['quantityId'] for row in selection['states']])
        branches = self.system.report['derivedExecution']['inactiveBranches']
        self.assertEqual(branches['zeroBindings'], [{'equationId': self.rows['zero'], 'quantity': 'derivativeTime'}])
        # CR-1 decision: predicates of inactive rows and of rows reduced away are
        # excluded from enforcement and listed; their data are not required.
        kinds = {(row['equationId'], row['kind']) for row in branches['rows']}
        self.assertIn((self.rows['filter'], 'inactive_rate'), kinds)
        self.assertTrue(any(row['kind'] == 'inactive_premise' and 'filterTime' in row['latex'] for row in branches['rows']))
        self.assertFalse(any('filterTime' in row['latex'] for row in self.system.report['derivedExecution']['runtimeConditions']))
        self.assertEqual(len(self.system.states), 3)

    def test_pi_matches_the_closed_form_within_1e_6_kelvin(self):
        temperature = next(row['quantityId'] for row in self.pi['motores']['derivedExecution']['reconstructions']
                           if str(self.system.quantities[row['quantityId']]) == str(T))
        for method in ('RK45', 'BDF'):
            with self.subTest(method=method):
                system = DerivedSystem(copy.deepcopy(self.pi))
                system.method = method; system.model['estudio']['metodoSolicitado'] = method.lower()
                system.report = system._report()
                result = resolve_system(system)
                self.assertEqual(result['estado'], 'resuelto')
                times = np.array(result['ejes'][0]['valores'])
                self.assertAlmostEqual(times[-1], HORIZON)
                values = np.array(next(row for row in result['series'] if row['id'] == 'observable.' + temperature)['valores'])
                self.assertLessEqual(float(np.max(np.abs(values - pi_reference(times)))), 1e-6)

    def test_saturated_valve_lowers_min_max_against_direct_evaluation(self):
        system = DerivedSystem(lowered_model(self.author, self.rows, {'commandMax': (0.2, '1'), 'commandMin': (-0.1, '1')}))
        self.assertIn("'nombre': 'min'", str(system.lowered['matematico']['ecuaciones']))
        self.assertIn("'nombre': 'max'", str(system.lowered['matematico']['ecuaciones']))
        mass, energy, integral = (system.states.index(q) for q in (MASS, U, system.quantities['integral']))
        gain, setpoint, integral_time, power = 0.05, 330., 50., 1000.
        for temperature, accumulated in [(320, 0), (329.9, 10), (335, -400), (300, 2000), (330, 0)]:
            state = np.zeros(len(system.states)); state[mass] = 2.
            state[energy] = 2. * 500. * (temperature - 300.)  # U = m (u_ref + c (T - T_ref)), u_ref = 0
            state[integral] = accumulated
            command = gain * (setpoint - temperature + accumulated / integral_time)
            expected = power * min(max(command, -0.1), 0.2)
            rates = system.rhs(0., state)
            self.assertAlmostEqual(float(rates[energy]), expected, delta=1e-9 * max(1., abs(expected)))
            self.assertAlmostEqual(float(rates[integral]), setpoint - temperature, delta=1e-9)

    def test_nonzero_datum_after_a_recorded_zero_is_rejected(self):
        row = rejected(self, 'zero_datum_conflict', DerivedSystem,
                       lowered_model(self.author, self.rows, {'derivativeTime': (2, 's')}))
        self.assertEqual(row['equationId'], self.rows['zero'])
        system = DerivedSystem(lowered_model(self.author, self.rows, {'derivativeTime': (0, 's')}))
        self.assertEqual(len(system.states), 3)

    def test_unreduced_pid_requires_its_filter_state(self):
        author = self.author.clone()
        author.edit({'kind': 'undo'})  # remove the PI reduction; the PID root remains
        self.assertNotIn(self.rows['zero'], author.result.graph.nodes)
        data = {'derivativeTime': (5, 's'), 'filterTime': (1, 's')}
        row = rejected(self, 'unselected_rate', DerivedSystem, lowered_model(author, self.rows, data))
        self.assertEqual(row['equationId'], self.rows['filter'])
        system = DerivedSystem(lowered_model(author, self.rows, data, filter_state=True))
        self.assertEqual(len(system.states), 4)
        self.assertNotIn('inactiveBranches', system.report['derivedExecution'])

    def test_constant_joined_to_a_time_dependent_expression_is_rejected_at_the_join(self):
        author = self.author.clone()
        join = author.append('declare_relation', left='setpoint', right=author.quantity(T),
                             reason='Probe: a constant set point receiving the measured temperature')
        row = rejected(self, 'constant_time_join', DerivedSystem, lowered_model(author, self.rows))
        self.assertEqual(row['equationId'], join)


app = FastAPI()
from backend.api_modelo import router  # noqa: E402
app.include_router(router)


def post(path, body):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            return await client.post(path, json=body, timeout=600)
    return asyncio.run(run())


class DegenerateRelationTests(unittest.TestCase):
    """Kernel audit A-2 reproducers K4a-K4c and K17."""

    def setUp(self):
        self.author = Author()
        self.author.append('declare_symbol', name='qa', unit='1')
        self.author.append('declare_symbol', name='xb', unit='1')
        self.author.append('declare_function', name='yc', unit='1', dependencies=[self.author.quantity(t)])

    def declare(self, left, right, code):
        cursor = self.author.definition['cursor']
        with self.assertRaises(MathematicsError) as caught:
            self.author.append('declare_relation', left=left, right=right, reason='Audit reproducer')
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.location, 'operation.' + str(cursor + 1))
        self.assertEqual(self.author.definition['cursor'], cursor)

    def test_k4a_k4b_identity_and_contradiction_are_located_rejections(self):
        self.declare('1', '2', 'contradictory_relation')                  # K4a
        self.declare('qa', 'qa+1', 'contradictory_relation')                # K4b
        self.declare('qa', 'qa', 'identity_relation')
        self.declare('2*(qa+xb)', '2*qa+2*xb', 'identity_relation')

    def test_k4c_combination_cannot_reach_the_contradiction(self):
        legitimate = self.author.append('declare_relation', left='qa', right='2*qa', reason='Audit reproducer: qa = 0')
        self.assertEqual(self.author.result.graph.nodes[legitimate].equation, sp.Eq(sp.Symbol('qa', real=True), 2*sp.Symbol('qa', real=True)))
        self.declare('qa', 'qa+1', 'contradictory_relation')

    def test_k17_boolean_relation_never_reaches_lhs(self):
        xb = sp.Symbol('xb', real=True)
        for relation, code in [(sp.Eq(xb, xb + 1, evaluate=False), 'contradictory_relation'),
                               (sp.Eq(xb, xb, evaluate=False), 'identity_relation')]:
            with self.assertRaises(MathematicsError) as caught:
                solve_unique(relation, xb)
            self.assertEqual(caught.exception.code, code)
        premise = DomainPremise(xb, 'positive')
        for relation in (sp.S.true, sp.S.false):
            with self.assertRaises(MathematicsError):
                select_polynomial_branch(relation, xb, [premise])
        self.declare('xb', 'xb+1', 'contradictory_relation')
        relation = self.author.append('declare_relation', left='xb', right='3*qa', reason='Valid definition')
        self.author.append('declare_relation', left='yc', right='2*xb', reason='Valid definition')
        substituted = self.author.append('substitute', sources=['operation.' + str(self.author.definition['cursor'])],
                                         relation=relation, symbol='xb')
        self.assertEqual(self.author.result.graph.nodes[substituted].equation.rhs, 6*sp.Symbol('qa', real=True))

    def test_valid_definition_and_constitutive_relation_still_pass(self):
        definition = self.author.append('declare_relation', left='yc', right='qa+xb', reason='Valid definition')
        constitutive = self.author.append('declare_relation', left='xb', right='2*qa', relationKind='constitutive',
                                          reason='Valid constitutive relation',
                                          source={'kind': 'correlation', 'citation': 'Test premise', 'validRange': 'qa > 0'})
        self.assertEqual(self.author.result.graph.nodes[definition].kind, 'definition')
        self.assertEqual(self.author.result.graph.nodes[constitutive].kind, 'constitutive')

    def test_route_answers_422_for_identity_and_contradiction(self):
        model = copy.deepcopy(self.author.model)
        model['motores']['equationWorkbench'] = self.author.definition
        for left, right in [('1', '2'), ('qa', 'qa+1'), ('qa', 'qa')]:
            with self.subTest(relation=left + ' = ' + right):
                response = post('/modelo/equation-workbench', {'modelo': model, 'action': {'kind': 'append', 'operation': {
                    'kind': 'declare_relation', 'family': 'energy', 'left': left, 'right': right, 'reason': 'Audit reproducer'}}})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn('operation.' + str(self.author.definition['cursor'] + 1), response.json()['detail']['message'])
        response = post('/modelo/equation-workbench', {'modelo': model, 'action': {'kind': 'append', 'operation': {
            'kind': 'declare_relation', 'family': 'energy', 'left': 'xb', 'right': '2*qa', 'reason': 'Valid definition'}}})
        self.assertEqual(response.status_code, 200, response.text)


if __name__ == '__main__':
    unittest.main()
