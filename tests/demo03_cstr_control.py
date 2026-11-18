"""Demo 0.3 C8: the accepted Demo 0.2 CSTR under a temperature loop, recorded through shared operations only.

Plant (roadmap, Demo 0.3 design section 4): the frozen Demo 0.2 continuous reactor (`tests/demo02_cstr.py`).
Its recorded history is replayed with two declarations changed from a constant symbol to a quantity of time,
`jacketTemperature` (the manipulated quantity) and `feedRate` (a disturbance Solve may hold as a time input);
every later recorded operation is the recorded one, re-pinned to its replayed inputs (the C2 and C3 replay).

Loop, recorded by the generic author `tests/control_loop.py` (C3): sensor lag on the reactor temperature, the ISA
PID root with back-calculation anti-windup, the output range 0 to 1, an instant actuator, then the PI reduction
(`apply_zero` on the derivative time). The actuator reaches the plant through one physical relation in the energy
family, the three-way jacket valve `T_j = T_c + v (T_h - T_c)`, substituted into the recorded energy balance
whose jacket heat is the Demo 0.2 conductance law. Nothing here writes a right-hand side or a final formula.

Solve data: K_c 0.2 1/K, tau_I 300 s, tau_m 30 s, tau_t 60 s (k_t = 1/60 1/s), bias 2/3 (T_j = 340 K, the accepted
jacket temperature), T_c 320 K, T_h 350 K. The start is the independent steady state of the Demo 0.2 reactor as
ordinary initial data (rounded to ten significant digits so that the document is byte-stable across platforms).
The set point and the feed rate are declared time inputs (C2); the timelines are scheduled run-session actions (C7).

Run `python tests/demo03_cstr_control.py --write` to regenerate `docs/ejemplos/demo-0.3/`.
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from control_loop import Session, author_control_loop, join_actuator, reduce_control_loop
from core.compilador.derived import source_signature
from core.mathematics.dimensions import catalog
from core.mathematics.session import replay_operations
from core.modelo.equation_workbench import _known_unit, _source_graph, build
from demo02_cstr import OWNER, frozen_model, reference_functions, simultaneous_steady_reference
from derived_closure_inputs import T as TIME, _datum

TAG = 'TC1'
LOOP = {'direction': (1., '1'), 'gain': (0.2, '1/K'), 'integralTime': (300., 's'), 'sensorTime': (30., 's'),
        'trackingGain': (1 / 60, '1/s'), 'bias': (2 / 3, '1'), 'outputMin': (0., '1'), 'outputMax': (1., '1')}
SUPPLY = {'coldSupplyTemperature': (320., 'K'), 'hotSupplyTemperature': (350., 'K')}
HORIZON, SAMPLES, RTOL = 3000., 301, 1e-8
SETPOINT_TIME, FEED_TIME = 100., 1500.
SETPOINT_STEP, FEED_FACTOR, SATURATING_STEP, SMALL_STEP = 1., 1.2, 5., 0.1
# Liquid-only premise recorded on the Demo 0.2 energy balance: the lowest-boiling azeotrope is near 343 K.
LIQUID_LIMIT = 343.
VALVE_REASON = ('Three-way jacket valve: the jacket temperature is the blend of a cold and a hot supply in the '
                'actuator proportion. Limiting case of a three-way mixing service (dec-composable-operations rules 3 '
                'and 4) under its premises: steady mixing point, adiabatic, equal heat capacities, constant total '
                'jacket flow and prescribed supply temperatures')
EXAMPLES = ROOT / 'docs/ejemplos/demo-0.3'
MODEL_FILE = EXAMPLES / 'controlled-reactor.rage-model.json'
SCHEDULE_FILE = EXAMPLES / 'controlled-reactor.schedule.json'
SHEET = ROOT / 'docs/ejemplos/demo-0.2/continuous-reactor.rage-model.json'
TEMPERATURE = sp.Function('T__' + OWNER)(TIME)


def significant(value, digits=10):
    return float(f'{float(value):.{digits - 1}e}')


def steady_start():
    """The independent steady state (`simultaneous_steady_reference`), rounded for a byte-stable document."""
    _, masses, _, _, _, _ = reference_functions()
    row = simultaneous_steady_reference(1)[0]
    return {'masses': [significant(n * m) for n, m in zip(row['amounts'], masses)],
            'temperature': significant(row['temperature']), 'flow': significant(row['flow'])}


def plant_variant():
    """The frozen Demo 0.2 history replayed with `jacketTemperature` and `feedRate` declared as quantities of time."""
    frozen = frozen_model()
    replayed = build(frozen)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    time_id = next(k for k, v in quantities.items() if str(v) == 't')
    definition = copy.deepcopy(frozen['motores']['equationWorkbench'])
    changed = []
    for op in definition['operations']:
        op.pop('sourceSignatures', None)
        if op['kind'] == 'declare_symbol' and op.get('name') in ('jacketTemperature', 'feedRate'):
            op.update(kind='declare_function', dependencies=[time_id])
            changed.append(op['name'])
    assert sorted(changed) == ['feedRate', 'jacketTemperature'], changed
    source, selected, locations, units = _source_graph(frozen)
    unsigned = replay_operations(source, selected, locations, units, definition, require_same_family=True,
                                 unit_resolver=_known_unit)
    for op, receipt in zip(definition['operations'], unsigned.receipts):
        if receipt.calculated_input_signatures:
            op['sourceSignatures'] = dict(receipt.calculated_input_signatures)
    old = {name: next(k for k, v in quantities.items() if v == replayed.introduced[name] and k != name)
           for name in ('jacketTemperature', 'feedRate')}
    return Session(frozen, definition), time_id, old


def author_controlled_cstr():
    """Record the loop, the jacket valve join and the PI reduction; return the session, names and rows."""
    session, time_id, old = plant_variant()
    jacket_function = session.result.introduced['jacketTemperature']
    # The selected state row whose rate carries the jacket temperature: the recorded first law of the reactor.
    energy, = [row['equationId'] for row in session.model['motores']['derivedExecution']['states']
               if session.result.graph.nodes[row['equationId']].equation.has(jacket_function)]
    jacket = session.quantity(jacket_function)
    with session.batch():
        names, rows = author_control_loop(session, tag=TAG, measured=session.quantity(TEMPERATURE), unit='K',
                                          time=time_id, sensor_lag=True)
        for name, (_, unit) in SUPPLY.items():
            session.append('declare_symbol', 'energy', name=name, unit=unit)
        rows['valve'], rows['energy'] = join_actuator(
            session, family='energy', balance=energy, manipulated=jacket,
            right=f"coldSupplyTemperature+{names['actuator']}*(hotSupplyTemperature-coldSupplyTemperature)",
            reason=VALVE_REASON)
        reduce_control_loop(session, names, rows, derivative=False)
    return session, names, rows, time_id, old, energy


def controlled_model(start=None):
    """The controlled reactor as a common model: recorded history, Solve selection and the steady start."""
    start = steady_start() if start is None else start
    session, names, rows, time_id, old, energy = author_controlled_cstr()
    model = copy.deepcopy(session.model)
    model['motores']['equationWorkbench'] = copy.deepcopy(session.definition)
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    qid = lambda name: next(k for k, v in quantities.items() if v == replayed.introduced[name] and k != name)
    selection = model['motores']['derivedExecution']
    jacket_datum = selection['parameters'].pop(old['jacketTemperature'])
    feed_datum = selection['parameters'].pop(old['feedRate'])
    model['datos'].pop(jacket_datum)
    for row in selection['states']:
        if row['equationId'] == energy:
            row['equationId'] = rows['energy']
    selection['states'] += [{'quantityId': names['measurement'], 'equationId': rows['sensor']},
                            {'quantityId': names['integral'], 'equationId': rows['integral']}]
    for i, key in enumerate(('cell.mass', 'cell.mass2', 'cell.mass3', 'cell.mass4')):
        model['datos'][key]['declaracion']['texto'] = repr(start['masses'][i])
    model['datos']['cell.temperature']['declaracion']['texto'] = repr(start['temperature'])
    model['datos']['solve.F0']['declaracion']['texto'] = repr(start['flow'])
    selection['initialValues'][names['measurement']] = _datum(model, 'solve.' + names['measurement'] + '0',
                                                              start['temperature'], 'K', 'inicial')
    selection['initialValues'][names['integral']] = _datum(model, 'solve.' + names['integral'] + '0', 0., 'K*s', 'inicial')
    for base, (value, unit) in LOOP.items():
        selection['parameters'][names[base]] = _datum(model, 'solve.' + names[base], value, unit)
    for name, (value, unit) in SUPPLY.items():
        selection['parameters'][name] = _datum(model, 'solve.' + name, value, unit)
    selection['timeInputs'] = {names['setpoint']: _datum(model, 'solve.' + names['setpoint'], start['temperature'], 'K'),
                               qid('feedRate'): feed_datum}
    model['datos']['solve.tf']['declaracion']['texto'] = repr(HORIZON)
    model['estudio'].update(muestras=SAMPLES, rtol=RTOL)
    model['template'] = dict(model['template'], id='demo-03-controlled-cstr')
    model.update(id='demo-0.3-controlled-reactor',
                 nombre='Demo 0.3 · Continuous jacketed liquid reactor with a temperature loop')
    selection['sourceSignature'] = source_signature(model, replayed)
    return model, {'names': names, 'rows': rows, 'feed': qid('feedRate'), 'jacket': qid('jacketTemperature'),
                   'time': time_id, 'start': start}


def schedules(model, info):
    """Run-session `scheduled` bodies (C7): set point +1 K then feed +20 %, a saturating +5 K and a small step."""
    setpoint, feed = info['names']['setpoint'], info['feed']
    base_feed = float(model['datos'][model['motores']['derivedExecution']['timeInputs'][feed]]['declaracion']['texto'])
    target = lambda step: {'t': SETPOINT_TIME, 'quantityId': setpoint, 'value': significant(info['start']['temperature'] + step), 'unit': 'K'}
    return {'setpointThenFeed': [target(SETPOINT_STEP),
                                 {'t': FEED_TIME, 'quantityId': feed, 'value': significant(base_feed * FEED_FACTOR), 'unit': 'kg/s'}],
            'saturatingSetpoint': [target(SATURATING_STEP)],
            'smallSetpoint': [target(SMALL_STEP)]}


def documents(model=None, info=None):
    """The two published documents, as text."""
    if model is None:
        model, info = controlled_model()
    sheet = json.loads(SHEET.read_text(encoding='utf-8'))['model']
    sheet = {**sheet, 'id': model['id'], 'nombre': model['nombre'], 'actualizada': '2026-11-17T00:00:00.000Z', 'commonModel': model}
    model_text = json.dumps({'format': 'rage.model-file', 'version': 1, 'model': sheet}, indent=1, ensure_ascii=False) + '\n'
    schedule = {'format': 'rage.run-session-schedule', 'version': 1, 'modelId': model['id'],
                'note': 'Each case is the body of `scheduled` for run-session/start (C7); times in s from the start.',
                'cases': schedules(model, info)}
    return {MODEL_FILE: model_text, SCHEDULE_FILE: json.dumps(schedule, indent=1, ensure_ascii=False) + '\n'}


def _loop_value(name):
    return LOOP[name][0]


class ClosedLoopReference:
    """Independent closed loop written from the design table on the Demo 0.2 reference functions.

    No compiled expression, closure bridge or model RHS is used: the liquid caloric route, kinetics and outlet
    momentum are `demo02_cstr.reference_functions` (as in `reference_train`), and the loop is the design's
    sensor lag, error, PI law with back-calculation, output range and three-way valve. States: four component
    amounts [mol], enthalpy inventory H [J], outlet flow F [kg/s], measurement y_m [K], integral I [K s].
    Inputs held between actions: the set point r [K] and the feed rate [kg/s].
    """

    def __init__(self, start, data=None):
        self.data, self.masses, self.volumes, self.enthalpy, self.temperature, self.rate = reference_functions(data)
        self.feed = np.asarray(self.data['zF'])
        self.feed_mass = float(self.feed @ self.masses)
        self.feed_specific_enthalpy = self.enthalpy(self.data['TF'], self.feed) / self.feed_mass
        amounts = np.asarray(start['masses']) / self.masses
        self.initial = np.array([*amounts, self.enthalpy(start['temperature'], amounts), start['flow'], start['temperature'], 0.])
        self.inputs = (start['temperature'], self.data['feed'])

    def command(self, x, inputs):
        error = _loop_value('direction') * (inputs[0] - x[6])
        return _loop_value('bias') + _loop_value('gain') * (error + x[7] / _loop_value('integralTime'))

    def output(self, x, inputs):
        return min(max(self.command(x, inputs), _loop_value('outputMin')), _loop_value('outputMax'))

    def rhs(self, x, inputs):
        data, nu = self.data, np.array([-1., -1., 1., 1.])
        n, H, F, measurement, integral = x[:4], x[4], x[5], x[6], x[7]
        setpoint, feed = inputs
        mass = float(n @ self.masses)
        rho = mass / float(n @ self.volumes)
        T = self.temperature(H, n)
        command = self.command(x, inputs)
        valve = min(max(command, _loop_value('outputMin')), _loop_value('outputMax'))
        cold, hot = SUPPLY['coldSupplyTemperature'][0], SUPPLY['hotSupplyTemperature'][0]
        jacket = cold + valve * (hot - cold)
        pressure = data['P'] + mass * data['g'] / data['area']
        loss = data['loss'] * F * abs(F) / (2 * rho * data['pipeArea'] ** 2)
        error = _loop_value('direction') * (setpoint - measurement)
        return np.array([*(feed * self.feed / self.feed_mass - F * n / mass + nu * self.rate(T, n)),
                         feed * self.feed_specific_enthalpy - F * H / mass + data['UA'] * (jacket - T),
                         data['pipeArea'] / data['length'] * (pressure - data['Pout'] - loss),
                         (T - measurement) / _loop_value('sensorTime'),
                         error + _loop_value('integralTime') / _loop_value('gain') * _loop_value('trackingGain') * (valve - command)])

    def run(self, times, schedule):
        """LSODA between actions (restarted at each).

        Returns T, the valve output and the states at `times`, and the times at which the command crosses an end
        of the output range (located by the integrator's root finding on the reference trajectory).
        """
        from scipy.integrate import solve_ivp
        times = np.asarray(times, dtype=float)
        breaks = sorted({float(a['t']) for a in schedule})
        x, inputs, start = self.initial.copy(), list(self.inputs), 0.
        temperature, valve = np.full(len(times), np.nan), np.full(len(times), np.nan)
        states = np.full((len(times), 8), np.nan)
        crossings = []
        limits = [lambda t, y, b=b: self.command(y, inputs) - _loop_value(b) for b in ('outputMax', 'outputMin')]
        for end in breaks + [float(times[-1])]:
            inside = (times >= start) & (times <= end)
            if end > start:
                solution = solve_ivp(lambda t, y: self.rhs(y, inputs), (start, end), x, method='LSODA', rtol=1e-10,
                                     atol=[1e-11] * 4 + [1e-6, 1e-12, 1e-9, 1e-9], max_step=10., dense_output=True,
                                     events=limits)
                if not solution.success:
                    raise RuntimeError(solution.message)
                crossings += sorted(float(t) for found in solution.t_events for t in found)
                for i in np.flatnonzero(inside):
                    if np.isnan(temperature[i]):  # the left value at an action: T and the states are continuous
                        y = solution.sol(times[i])
                        states[i], temperature[i], valve[i] = y, self.temperature(y[4], y[:4]), self.output(y, inputs)
                x = solution.y[:, -1]
            for action in schedule:
                if float(action['t']) == end:
                    inputs[0 if action['unit'] == 'K' else 1] = float(action['value'])
            start = end
        return temperature, valve, states, crossings

    def linear_setpoint_response(self, times, step, at, relative=1e-4, energy=25.):
        """Temperature deviation of the closed loop linearized at the start, for a set-point step `step` at `at`.

        The Jacobian of `rhs` and the gradient of T are central differences; the response of the 8-state
        linear system is the matrix exponential of the augmented [[A, B], [0, 0]] (exact for a held step).
        Difference steps: amounts 1e-4 relative and enthalpy 25 J (about 0.01 K). The reference enthalpy carries
        round-off from its own central difference in T, so steps of 1e-7 relative left a Jacobian error of 4e-4 of
        the step; with these steps a 0.01 K step agrees with the nonlinear reference to 8e-6 of the step.
        """
        from scipy.linalg import expm
        x0, u0 = self.initial, np.array(self.inputs)
        scale = np.array([*np.abs(x0[:4]) * relative, energy, 1e-8, 1e-4, 1e-3])
        A = np.zeros((8, 8))
        gradient = np.zeros(8)
        for j in range(8):
            h = np.zeros(8); h[j] = scale[j]
            A[:, j] = (self.rhs(x0 + h, u0) - self.rhs(x0 - h, u0)) / (2 * scale[j])
            gradient[j] = (self.temperature((x0 + h)[4], (x0 + h)[:4]) - self.temperature((x0 - h)[4], (x0 - h)[:4])) / (2 * scale[j])
        B = (self.rhs(x0, u0 + [1e-3, 0.]) - self.rhs(x0, u0 - [1e-3, 0.])) / 2e-3
        augmented = np.zeros((9, 9)); augmented[:8, :8] = A; augmented[:8, 8] = B * step
        deviations = []
        for t in np.asarray(times, dtype=float):
            deviations.append(0. if t <= at else float(gradient @ (expm(augmented * (t - at))[:8, 8])))
        return np.array(deviations), np.linalg.eigvals(A)


def published_model():
    return json.loads(MODEL_FILE.read_text(encoding='utf-8'))['model']['commonModel']


def published_schedules():
    return json.loads(SCHEDULE_FILE.read_text(encoding='utf-8'))['cases']


if __name__ == '__main__':
    texts = documents()
    if '--write' in sys.argv:
        EXAMPLES.mkdir(parents=True, exist_ok=True)
        for path, text in texts.items():
            path.write_text(text, encoding='utf-8', newline='\n')
    else:
        for path, text in texts.items():
            print(path.relative_to(ROOT), 'unchanged' if path.exists() and path.read_text(encoding='utf-8') == text else 'differs')
