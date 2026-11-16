"""Demo 0.3 C3: the generic control deduction and the Signal family.

The loop is recorded by `tests/control_loop.py` through the shared operations
only, on the frozen M1-A constant-capacity mixing model (design section 4,
exact analytic tier). The supplied heat of M1-A is replayed as a quantity of
time (every later recorded operation unchanged and re-pinned, as in C2) and
joined to the actuator by one physical relation in the energy family.

Plant, from the frozen data: M = 10 kg, c = 1000 J/(kg K), F = 0.1 kg/s,
T_F = 330 K, so M c dT/dt = F c (T_F - T) + Q (the equal flow-work offsets
cancel), K = 1/(F c), tau = M/F = 100 s. Q = P v with P = 4000 W.

The reference is hand-derived and independent of the engine: the closed loop
is affine in each regime of the output limits, integrated by matrix
exponentials, with the regime changes located by root finding on that exact
solution. Acceptance: temperature within 1e-6 K at rtol 1e-9.
"""
import copy
import json
from pathlib import Path
import sys
import time as clock
import unittest

import numpy as np
import sympy as sp
from scipy.linalg import expm
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from control_loop import SIGNAL, Session, author_control_loop, join_actuator, reduce_control_loop
from core.compilador.derived import DerivedSystem, LoweringError, resolve_system, source_signature
from core.compilador.presentation import formulation_summary
from core.mathematics.dimensions import catalog
from core.mathematics.session import replay_operations
from core.modelo.equation_workbench import _known_unit, _source_graph, build, describe, read_definition
from core.modelo.operation_journal import JournalError

t = sp.Symbol('t', real=True)
T = sp.Function('T__mixture')(t)
U = sp.Function('U__mixture')(t)
DOCUMENT = json.loads((ROOT / 'tests/reference_data/m1-a.json').read_text(encoding='utf8'))
REFERENCE = DOCUMENT['reference']
SELECTED = DOCUMENT['selectedEquations']
MASS = sum(REFERENCE['initialMass'])
CAPACITY, FLOW, FEED_T = REFERENCE['specificCapacity'], REFERENCE['massFlow'], REFERENCE['feedTemperature']
POWER, T0, HORIZON, RTOL = 4000., 340., 600., 1e-9
LOOP = {'direction': (1, '1'), 'gain': (0.05, '1/K'), 'integralTime': (100, 's'), 'bias': (0.25, '1'),
        'outputMin': (0, '1'), 'outputMax': (1, '1'), 'trackingGain': (1 / 60, '1/s'),
        'derivativeTime': (20, 's'), 'filterTime': (5, 's'), 'sensorTime': (30, 's'), 'actuatorTime': (10, 's')}
SETPOINT = 345.
# Saturates the heater at the start and stays inside the recorded caloric interval (T <= 360 K).
SATURATED_SETPOINT = 357.


_VARIANT = {}


def mixing_variant():
    """M1-A with `suppliedHeat` declared as a quantity of time, re-pinned by replay."""
    if not _VARIANT:
        model = copy.deepcopy(DOCUMENT['model'])
        replayed = build(model)
        quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
        time_id = next(k for k, v in quantities.items() if str(v) == 't')
        definition = copy.deepcopy(model['motores']['equationWorkbench'])
        for op in definition['operations']:
            op.pop('sourceSignatures', None)
            if op.get('name') == 'suppliedHeat':
                op.update(kind='declare_function', dependencies=[time_id])
        source, selected, locations, units = _source_graph(model)
        unsigned = replay_operations(source, selected, locations, units, definition,
                                     require_same_family=True, unit_resolver=_known_unit)
        for op, receipt in zip(definition['operations'], unsigned.receipts):
            if receipt.calculated_input_signatures:
                op['sourceSignatures'] = dict(receipt.calculated_input_signatures)
        _VARIANT.update(session=Session(model, definition), time=time_id)
    return _VARIANT['session'].clone(), _VARIANT['time']


def controlled_mixing(tag='TC1', derivative=True, anti_windup=True, **lags):
    """Record the loop, its heater join, then its reductions on the M1-A variant; no RHS here."""
    session, time_id = mixing_variant()
    with session.batch():
        names, rows = author_control_loop(session, tag=tag, measured=session.quantity(T), unit='K', time=time_id, **lags)
        session.append('declare_symbol', 'energy', name='heaterPower', unit='W')
        rows['heat'], rows['energy'] = join_actuator(
            session, family='energy', balance=SELECTED['energy'], manipulated=session.quantity(session.result.introduced['suppliedHeat']),
            right='heaterPower*' + names['actuator'],
            reason='Heater duty proportional to the actuator signal; the only heat input of the mixture')
        reduce_control_loop(session, names, rows, derivative=derivative, anti_windup=anti_windup)
    return session, names, rows


def lowered(session, names, rows, *, sensor_lag=False, actuator_lag=False, filter_state=False, data=None,
            omit=(), setpoint=SETPOINT, method='rk45'):
    """Numerical bindings in Solve; the set point is a declared time input (C2)."""
    model = copy.deepcopy(session.model)
    model['motores']['equationWorkbench'] = copy.deepcopy(session.definition)
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    named = lambda name: next(key for key, value in quantities.items() if str(value) == name)
    def datum(key, value, unit, role='parametro'):
        model['datos'][key] = {'magnitud': key, 'funcion': role, 'declaracion': {'texto': repr(float(value)), 'unidad': unit},
                               'origen': {'propietarioId': 'estudio', 'ruta': key}}
        return key
    volume = model['volumenes'][0]
    selection = {'format': 'rage.derived-execution', 'version': 1, 'sourceSignature': source_signature(model, replayed),
                 'timeId': named('t'), 'states': [], 'parameters': {}, 'initialValues': {}, 'initialEquations': [],
                 'reconstructions': [], 'checks': []}
    for component in (1, 2):
        mass = 'm__mixture__' + str(component) + '(t)'
        selection['states'].append({'quantityId': named(mass), 'equationId': SELECTED['mass.' + str(component)]})
        selection['initialValues'][named(mass)] = volume['inicial']['cantidades']['datoIds'][str(component)]
    selection['states'].append({'quantityId': named(str(U)), 'equationId': rows['energy']})
    signal_states = [('integral', 'integral', 0., 'K*s')]
    if sensor_lag:
        signal_states.append(('measurement', 'sensor', T0, 'K'))
    if filter_state:
        signal_states.append(('filtered', 'filter', T0, 'K'))
    if actuator_lag:
        signal_states.append(('actuator', 'actuator', LOOP['bias'][0], '1'))
    for base, row, value, unit in signal_states:
        selection['states'].append({'quantityId': names[base], 'equationId': rows[row]})
        selection['initialValues'][names[base]] = datum('solve.' + base + '0', value, unit)
    caloric = 'thermodynamics.mixture.caloric-inventory'
    selection['reconstructions'] = [{'quantityId': named(str(T)), 'equationId': caloric},
                                    {'quantityId': named('m_total__mixture(t)'), 'equationId': 'matter.mixture.total-definition'}]
    selection['initialEquations'] = [caloric]
    selection['initialValues'][named(str(T))] = volume['inicial']['energia']['datoId']
    model['datos'][volume['inicial']['energia']['datoId']]['declaracion']['texto'] = repr(T0)
    for prefix, key in [('caloric_capacity', 'cId'), ('T_reference', 'TRefId'), ('u_reference', 'uRefId')]:
        selection['parameters'][named(prefix + '__mixture')] = volume['termodinamica']['parametros'][key]
    for key, value, unit in [('feedRate', FLOW, 'kg/s'), ('feedFraction', REFERENCE['feedMassFraction'], '1'),
                             ('feedTemperature', FEED_T, 'K'), ('specificFlowWork', REFERENCE['specificFlowWork'], 'J/kg'),
                             ('molarMass1', REFERENCE['molarMass'][0], 'kg/mol'), ('molarMass2', REFERENCE['molarMass'][1], 'kg/mol'),
                             ('heaterPower', POWER, 'W')]:
        selection['parameters'][key] = datum('solve.' + key, value, unit)
    # Data of a quantity reduced away by a recorded zero are not bound (C1 rule).
    current = lambda key: key in rows and rows[key] in session.result.graph.nodes
    reduced = ({'derivativeTime', 'filterTime'} if current('noDerivative') else set()) | (
        {'trackingGain'} if current('noAntiWindup') else set())
    for base, (value, unit) in {**{k: v for k, v in LOOP.items() if k not in reduced}, **(data or {})}.items():
        if base in names and base not in omit:
            selection['parameters'][names[base]] = datum('solve.' + names[base], value, unit)
    selection['timeInputs'] = {names['setpoint']: datum('solve.' + names['setpoint'], setpoint, 'K')}
    horizon = datum('solve.finalTime', HORIZON, 's', 'estudio')
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': horizon, 'metodoSolicitado': method, 'muestras': 121,
                        'rtol': RTOL, 'atol': {'cantidad': 1e-11, 'energia': 1e-6}}
    model['motores']['derivedExecution'] = selection
    return model


def reference(times, *, derivative=False, anti_windup=True, sensor_lag=False, actuator_lag=False, setpoint=SETPOINT, data=None):
    """Hand-derived closed loop, affine in each output regime, solved exactly.

    Returns T(times) and the regime changes. States: T, I, then y_m, z, v when
    present. Every quantity is a row vector over [states, 1].
    """
    p = {k: v for k, (v, _) in {**LOOP, **(data or {})}.items()}
    order = ['T', 'I'] + (['ym'] if sensor_lag else []) + (['z'] if derivative else []) + (['v'] if actuator_lag else [])
    n = len(order)
    state = lambda name: np.eye(n + 1)[order.index(name)]
    one = np.eye(n + 1)[n]
    measured = state('ym') if sensor_lag else state('T')
    error = p['direction'] * (setpoint * one - measured)
    action = -p['direction'] * p['derivativeTime'] * (measured - state('z')) / p['filterTime'] if derivative else 0 * one
    command = p['bias'] * one + p['gain'] * (error + state('I') / p['integralTime'] + action)
    tracking = p['trackingGain'] if anti_windup else 0.

    def system(regime):
        output = command if regime == 'linear' else p['outputMax' if regime == 'high' else 'outputMin'] * one
        valve = state('v') if actuator_lag else output
        rates = {'T': lambda: FLOW / MASS * (FEED_T * one - state('T')) + POWER / (MASS * CAPACITY) * valve,
                 'I': lambda: error + p['integralTime'] / p['gain'] * tracking * (output - command),
                 'ym': lambda: (state('T') - measured) / p['sensorTime'],
                 'z': lambda: (measured - state('z')) / p['filterTime'],
                 'v': lambda: (output - state('v')) / p['actuatorTime']}
        matrix = np.zeros((n + 1, n + 1))
        for index, name in enumerate(order):
            matrix[index] = rates[name]()
        return matrix

    def regime_of(x):
        value = command @ x
        return 'high' if value > p['outputMax'] else 'low' if value < p['outputMin'] else 'linear'

    x = np.array([T0, 0.] + ([T0] if sensor_lag else []) + ([T0] if derivative else []) + ([p['bias']] if actuator_lag else []) + [1.])
    low, high = p['outputMin'], p['outputMax']
    start, regime, switches = 0., regime_of(x), []
    values = np.full(len(times), np.nan)
    grid = np.linspace(0., HORIZON, 6001)
    while True:
        matrix, x0, s0 = system(regime), x, start
        flow = lambda s: expm(matrix * (s - s0)) @ x0
        def leaving(s):
            """Positive once the exact solution has left the current regime."""
            value = command @ flow(s)
            return max(value - high, low - value) if regime == 'linear' else (high - value if regime == 'high' else value - low)
        crossing, previous = None, start
        for right in grid[grid > start]:
            if leaving(right) > 0:
                assert previous > start, 'a regime is left at once; refine the reference grid'
                crossing = brentq(leaving, previous, right, xtol=1e-13, rtol=1e-15)
                break
            previous = right
        end = HORIZON if crossing is None else crossing
        segment = (times >= start) & (times <= end)
        values[segment] = [flow(s)[0] for s in times[segment]]
        if crossing is None:
            return values, switches
        x, start = flow(crossing), crossing
        switches.append((crossing, regime))
        regime = 'linear' if regime != 'linear' else ('high' if command @ x > (low + high) / 2 else 'low')


def temperature_error(test, model, label, **options):
    system = DerivedSystem(copy.deepcopy(model))
    result = resolve_system(system)
    test.assertEqual(result['estado'], 'resuelto', label)
    times = np.array(result['ejes'][0]['valores'])
    quantity = next(row['quantityId'] for row in model['motores']['derivedExecution']['reconstructions']
                    if str(system.quantities[row['quantityId']]) == str(T))
    values = np.array(next(row for row in result['series'] if row['id'] == 'observable.' + quantity)['valores'])
    expected, switches = reference(times, **options)
    return float(np.max(np.abs(values - expected))), switches, system


def rejected(test, code, model):
    with test.assertRaises(LoweringError) as caught:
        DerivedSystem(model)
    test.assertEqual(caught.exception.diagnostics[0]['code'], code, caught.exception.diagnostics)
    return caught.exception.diagnostics[0]


def equations(session):
    return {key: node.equation for key, node in session.result.graph.nodes.items()}


TIMINGS = {}


class ControlLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        start = clock.perf_counter()
        cls.pi = controlled_mixing(derivative=False)
        TIMINGS['author PI'] = clock.perf_counter() - start
        start = clock.perf_counter()
        cls.pid = controlled_mixing(sensor_lag=True, actuator_lag=True)
        TIMINGS['author PID with lags'] = clock.perf_counter() - start
        cls.windup = controlled_mixing(derivative=False, anti_windup=False)

    @classmethod
    def tearDownClass(cls):
        print('\nC3 timings (s) and errors (K): ' + ', '.join(f'{k} {v:.3g}' if isinstance(v, float) else f'{k} {v}'
                                                          for k, v in TIMINGS.items()), flush=True)

    # Graph: typed Signal rows, reductions, Undo and a renamed index.
    def test_signal_rows_are_typed_and_the_physical_join_stays_in_energy(self):
        session, names, rows = self.pid
        graph = session.result.graph
        node = lambda key: graph.nodes[rows[key]]
        expected = {'measurementJoin': ('constraint', 'declared_relation'), 'sensor': ('constitutive', 'declared_rate'),
                    'error': ('definition', 'declared_relation'), 'integral': ('definition', 'declared_rate'),
                    'filter': ('definition', 'declared_rate'), 'derivative': ('definition', 'declared_relation'),
                    'law': ('definition', 'declared_relation'), 'limits': ('constitutive', 'declared_relation'),
                    'actuator': ('constitutive', 'declared_rate')}
        for key, (kind, rule) in expected.items():
            with self.subTest(row=key):
                self.assertEqual((node(key).family, node(key).kind, node(key).rule), (SIGNAL, kind, rule))
                self.assertFalse(node(key).dependent)
        self.assertEqual((node('heat').family, node('energy').family), ('energy', 'energy'))
        q = session.result.introduced
        self.assertEqual(node('integral').equation.lhs, sp.Derivative(q[names['integral']], t))
        self.assertEqual(node('measurementJoin').equation, sp.Eq(q[names['processValue']], T))
        self.assertTrue(node('energy').equation.rhs.has(q[names['actuator']]))
        self.assertFalse(node('energy').equation.rhs.has(session.result.introduced['suppliedHeat']))
        # The Signal family is accepted by the workspace reader and nothing else is.
        read_definition(session.definition)
        bad = copy.deepcopy(session.definition); bad['operations'][-1]['family'] = 'control'
        with self.assertRaises(JournalError):
            read_definition(bad)

    def test_pid_to_pi_and_no_anti_windup_are_recorded_zero_reductions(self):
        session, names, rows = self.windup
        graph = session.result.graph
        q = session.result.introduced
        self.assertEqual(graph.nodes[rows['noDerivative']].equation, sp.Eq(q[names['derivativeAction']], 0))
        self.assertEqual(graph.nodes[rows['noAntiWindup']].equation,
                         sp.Eq(sp.Derivative(q[names['integral']], t), q[names['error']]))
        for key in ('noDerivative', 'noAntiWindup'):
            self.assertEqual(graph.nodes[rows[key]].family, SIGNAL)
        system = DerivedSystem(lowered(session, names, rows))
        branches = system.report['derivedExecution']['inactiveBranches']
        self.assertEqual(sorted((row['quantity'], row['equationId']) for row in branches['zeroBindings']),
                         sorted([(names['derivativeTime'], rows['noDerivative']), (names['trackingGain'], rows['noAntiWindup'])]))
        self.assertIn((rows['filter'], 'inactive_rate'), {(row['equationId'], row['kind']) for row in branches['rows']})

    def test_undo_restores_each_reduction_and_the_pid_root(self):
        session, names, rows = self.windup
        undone = session.clone(); undone.edit({'kind': 'undo'})
        self.assertNotIn(rows['noAntiWindup'], undone.result.graph.nodes)
        self.assertEqual(equations(undone), equations(self.pi[0]))  # exactly the PI with anti-windup
        undone.edit({'kind': 'undo'})
        self.assertNotIn(rows['noDerivative'], undone.result.graph.nodes)
        # The PID root asks for its filter state again; redo restores both reductions.
        rejected(self, 'unselected_rate', lowered(undone, names, rows, data={'derivativeTime': (20, 's')}))
        for _ in range(2):
            undone.edit({'kind': 'redo'})
        self.assertEqual(equations(undone), equations(session))

    def test_no_lag_records_instant_relations_instead_of_rates(self):
        pid, pi = self.pid, self.pi
        for (session, names, rows), lag in [(pid, True), (pi, False)]:
            graph = session.result.graph
            q = session.result.introduced
            for key, left, right in [('sensor', 'measurement', 'processValue'), ('actuator', 'actuator', 'output')]:
                equation = graph.nodes[rows[key]].equation
                if lag:
                    self.assertEqual(equation.lhs, sp.Derivative(q[names[left]], t))
                else:
                    self.assertEqual(equation, sp.Eq(q[names[left]], q[names[right]]))
        self.assertNotIn('sensorTime', pi[1])
        self.assertNotIn('actuatorTime', pi[1])

    def test_a_renamed_index_renames_every_loop_quantity_and_nothing_else(self):
        session, names, rows = self.pi
        other, other_names, other_rows = controlled_mixing(tag='TC2', derivative=False)
        self.assertEqual(rows, other_rows)
        mapping = {}
        for base, name in names.items():
            new = other.result.introduced[other_names[base]]
            old = session.result.introduced[name]
            mapping[old.func if isinstance(old, sp.core.function.AppliedUndef) else old] = (
                new.func if isinstance(new, sp.core.function.AppliedUndef) else new)
        functions = {k: v for k, v in mapping.items() if not isinstance(k, sp.Symbol)}
        symbols = {k: v for k, v in mapping.items() if isinstance(k, sp.Symbol)}
        renamed = {key: equation.xreplace(symbols).replace(lambda e: isinstance(e, sp.core.function.AppliedUndef) and e.func in functions,
                                                           lambda e: functions[e.func](*e.args))
                   for key, equation in equations(session).items()}
        self.assertEqual(renamed, equations(other))
        self.assertTrue(all(name.endswith('_TC2') for name in other_names.values()))

    # Solve: data, blocking, and the exact analytic tier.
    def test_a_missing_datum_blocks(self):
        session, names, rows = self.pi
        # A divisor blocks at the nonzero premise of the row that divides by it;
        # any other datum blocks naming its quantity. The wording is finding C3-F1.
        for base, code, located in [('gain', 'unsupported_condition', rows['integral']),
                                    ('integralTime', 'unsupported_condition', rows['law']),
                                    ('outputMax', 'unsupported_expression', None), ('bias', 'unsupported_expression', None),
                                    ('direction', 'unsupported_expression', None)]:
            with self.subTest(datum=base):
                diagnostic = rejected(self, code, lowered(session, names, rows, omit=(base,)))
                if located:
                    self.assertEqual(diagnostic['equationId'], located)
                else:
                    self.assertIn(names[base], diagnostic['message'])

    def test_pi_matches_the_closed_loop_within_1e_6_kelvin(self):
        session, names, rows = self.pi
        for method in ('rk45', 'bdf'):
            with self.subTest(method=method):
                start = clock.perf_counter()
                error, switches, system = temperature_error(self, lowered(session, names, rows, method=method), 'PI ' + method)
                TIMINGS['PI ' + method] = clock.perf_counter() - start
                self.assertEqual(switches, [])
                self.assertEqual(len(system.states), 4 + 1)  # two masses, U, I and the held set point
                self.assertLessEqual(error, 1e-6, error)
                TIMINGS['PI ' + method + ' error K'] = error

    def test_pid_with_sensor_and_actuator_lags_matches_the_matrix_exponential(self):
        session, names, rows = self.pid
        start = clock.perf_counter()
        error, switches, system = temperature_error(
            self, lowered(session, names, rows, sensor_lag=True, actuator_lag=True, filter_state=True), 'PID',
            derivative=True, sensor_lag=True, actuator_lag=True)
        TIMINGS['PID lags rk45'] = clock.perf_counter() - start
        TIMINGS['PID lags error K'] = error
        self.assertEqual(switches, [])
        self.assertEqual(len(system.states), 3 + 4 + 1)
        self.assertLessEqual(error, 1e-6, error)

    def test_saturation_with_and_without_anti_windup(self):
        for (session, names, rows), anti_windup in [(self.pi, True), (self.windup, False)]:
            with self.subTest(anti_windup=anti_windup):
                start = clock.perf_counter()
                error, switches, _ = temperature_error(self, lowered(session, names, rows, setpoint=SATURATED_SETPOINT),
                                                       'saturated', anti_windup=anti_windup, setpoint=SATURATED_SETPOINT)
                label = 'saturated ' + ('anti-windup' if anti_windup else 'no anti-windup')
                TIMINGS[label + ' rk45'] = clock.perf_counter() - start
                TIMINGS[label + ' error K'] = error
                TIMINGS[label + ' exits s'] = [round(s, 3) for s, _ in switches]
                self.assertTrue(switches and switches[0][1] == 'high', switches)
                self.assertLessEqual(error, 1e-6, error)

    # Presentation: the Signal family reaches the workbench report and the summary.
    def test_report_and_summary_carry_the_signal_family(self):
        session, names, rows = self.pi
        model = copy.deepcopy(session.model)
        model['motores']['equationWorkbench'] = copy.deepcopy(session.definition)
        report = describe(model)
        signal = {row['id'] for row in report['equations'] if row['family'] == SIGNAL}
        self.assertTrue({rows[key] for key in ('error', 'integral', 'law', 'limits', 'measurementJoin')} <= signal)
        summary = formulation_summary(model)
        self.assertEqual([family['id'] for family in summary['families']],
                         ['matter', 'energy', 'momentum', 'thermodynamics', SIGNAL])
        steps = {row['id'] for volume in next(f for f in summary['families'] if f['id'] == SIGNAL)['volumes'] for row in volume['steps']}
        self.assertTrue({rows['law'], rows['integral']} <= steps)
        # A model without signal rows keeps the four physical families.
        plain = copy.deepcopy(DOCUMENT['model'])
        self.assertEqual([family['id'] for family in formulation_summary(plain)['families']],
                         ['matter', 'energy', 'momentum', 'thermodynamics'])


class BatchRecordingTests(unittest.TestCase):
    def test_batch_equals_one_pinned_append_per_operation(self):
        from m1_acceptance import thermal_source
        owner = 'region_a'
        temperature = sp.Function('T__' + owner)(t)
        def record(batched):
            session = Session(thermal_source((owner,)))
            time_id = session.quantity(t)
            def record_loop():
                names, rows = author_control_loop(session, tag='k', measured=session.quantity(temperature), unit='K',
                                                  time=time_id, sensor_lag=True)
                reduce_control_loop(session, names, rows, derivative=False, anti_windup=False)
            if batched:
                with session.batch():
                    record_loop()
            else:
                record_loop()
            return session
        batched, sequential = record(True), record(False)
        self.assertEqual(batched.definition, sequential.definition)
        self.assertEqual(equations(batched), equations(sequential))


if __name__ == '__main__':
    unittest.main()
