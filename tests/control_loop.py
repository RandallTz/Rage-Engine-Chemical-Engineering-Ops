"""Demo 0.3 C3: generic sensor, controller and actuator deduction.

One deduction, `control-loop`, recorded through the shared Model operations
only (`declare_symbol`, `declare_function`, `declare_relation`,
`declare_rate`, `apply_zero`, `substitute`). Nothing here evaluates a law or
writes a right-hand side; lowering and numbers belong to Solve.

Design (roadmap, Demo 0.3, "generic control module", accepted 10 November
2026; `dec-control-surface`):

* Family `signal`. A signal block has no control volume and conserves nothing,
  so the intrinsic-energy rule of `dec-composable-operations` does not apply
  and the signal relations have no opposite-sign entry.
* Roots. The ISA dependent PID law with derivative action on the filtered
  measurement and back-calculation anti-windup is the root. PI is the recorded
  `apply_zero` on the derivative time; no anti-windup is the recorded
  `apply_zero` on the tracking gain `k_t = 1/tau_t`. Both are reductions of the
  root, so Undo restores the PID with anti-windup.
* Sensor and actuator. A first-order sensor `tau_m dy_m/dt = y_p - y_m` and
  actuator `tau_v dv/dt = u - v` are constitutive declared rates; an instant
  sensor or actuator is the constitutive relation `y_m = y_p` or `v = u`
  recorded instead of the lag. Deducing it as the tau -> 0 limit of the lag is
  not expressible: after `multiply` by tau, `apply_zero` on tau contradicts the
  inherited premise tau != 0 (capability finding C3-F2 in the roadmap).
* Joins. The loop reaches the process through two signal relations, the
  process value `y_p` equal to the measured process quantity and the actuator
  input equal to the limited controller output `u`, plus one physical actuator
  relation supplied by the caller in the physical family (`join_actuator`).
* Generic index. Every loop quantity is named `<base>_<tag>`; a measured or
  manipulated quantity is named by its identity and unit, never by a port kind,
  so the same author serves a temperature, level, flow or pressure.
* Set point. `setpoint_<tag>` is a quantity of time, so Solve may declare it a
  time input (C2); a declared constant could not receive an action.
"""
from contextlib import contextmanager
import copy

from core.mathematics.contract import FORMAT
from core.mathematics.dimensions import catalog
from core.mathematics.session import edit_history, replay_operations
from core.modelo.equation_workbench import _known_unit, _source_graph

SIGNAL = 'signal'


class Session:
    """The Model session driver: pinned appends, Undo/Redo and replay only."""

    def __init__(self, model, definition=None):
        self.model = model
        self.source, self.selected, self.locations, self.units = _source_graph(model)
        self.definition = copy.deepcopy(definition or {'format': FORMAT, 'version': 1, 'operations': [], 'cursor': 0})
        self.refresh()

    def refresh(self):
        self.result = replay_operations(self.source, self.selected, self.locations, self.units, self.definition,
                                        require_same_family=True, unit_resolver=_known_unit)

    def edit(self, action):
        self.definition = edit_history(self.source, self.selected, self.locations, self.units, self.definition,
                                       action, require_same_family=True, unit_resolver=_known_unit)
        self.refresh()

    def append(self, kind, family=SIGNAL, **fields):
        operation = {'kind': kind, 'family': family, **fields}
        if self._pending is not None:
            self._pending.append(operation)
            return 'operation.' + str(self.definition['cursor'] + len(self._pending))
        self.edit({'kind': 'append', 'operation': operation})
        return 'operation.' + str(self.definition['cursor'])

    _pending = None

    @contextmanager
    def batch(self):
        """Record several appends with two replays instead of two per append.

        The operations are appended unsigned, replayed once, pinned to the
        input signatures that replay calculated (the signatures `edit_history`
        pins), and replayed again with the pins. A rejected operation raises
        and leaves the history unchanged. `test_control_loop` checks that the
        result equals one `edit_history` append per operation.
        """
        self._pending = []
        try:
            yield self
            operations = self._pending
        finally:
            self._pending = None
        updated = copy.deepcopy(self.definition)
        updated['operations'] = updated['operations'][:updated['cursor']] + copy.deepcopy(operations)
        updated['cursor'] += len(operations)
        unsigned = replay_operations(self.source, self.selected, self.locations, self.units, updated,
                                     require_same_family=True, unit_resolver=_known_unit)
        first = self.definition['cursor']
        for operation, receipt in zip(updated['operations'][first:], unsigned.receipts[first:]):
            if receipt.calculated_input_signatures:
                operation['sourceSignatures'] = dict(receipt.calculated_input_signatures)
        self.definition = updated
        self.refresh()

    def clone(self):
        other = Session.__new__(Session)
        other.model = copy.deepcopy(self.model)
        other.source, other.selected, other.locations, other.units = self.source, self.selected, self.locations, self.units
        other.definition = copy.deepcopy(self.definition)
        other.refresh()
        return other

    def quantities(self):
        return {**catalog(self.result.graph, self.result.units), **self.result.introduced}

    def quantity(self, expression):
        return next(key for key, value in self.quantities().items() if value == expression)


def _per(unit):
    return '1/' + unit if all(c not in unit for c in '*/') else '1/(' + unit + ')'


def _times_second(unit):
    return unit + '*s' if all(c not in unit for c in '/') else '(' + unit + ')*s'


def author_control_loop(session, *, tag, measured, unit, time, sensor_lag=False, actuator_lag=False):
    """Record the PID root with anti-windup on the measured quantity id `measured` [unit].

    `time` is the quantity id of the time coordinate. A lagged sensor or
    actuator is a declared rate; otherwise the instant relation is recorded.
    Returns the loop's quantity names and the recorded rows. PI and no
    anti-windup are recorded afterwards by `reduce_control_loop`.
    """
    name = lambda base: base + '_' + tag
    names = {}
    for base, symbol_unit, needed in [
            ('direction', '1', True), ('gain', _per(unit), True), ('integralTime', 's', True),
            ('derivativeTime', 's', True), ('filterTime', 's', True), ('trackingGain', '1/s', True),
            ('bias', '1', True), ('outputMin', '1', True), ('outputMax', '1', True),
            ('sensorTime', 's', sensor_lag), ('actuatorTime', 's', actuator_lag)]:
        if needed:
            names[base] = name(base)
            session.append('declare_symbol', name=names[base], unit=symbol_unit)
    for base, function_unit in [
            ('setpoint', unit), ('processValue', unit), ('measurement', unit), ('error', unit),
            ('integral', _times_second(unit)), ('filtered', unit), ('derivativeAction', unit),
            ('command', '1'), ('output', '1'), ('actuator', '1')]:
        names[base] = name(base)
        session.append('declare_function', name=names[base], unit=function_unit, dependencies=[time])
    n = names
    rows = {}
    rows['measurementJoin'] = session.append(
        'declare_relation', left=n['processValue'], right=measured, relationKind='constraint',
        reason='Signal join: the process value is the measured process quantity')
    if sensor_lag:
        rows['sensor'] = session.append(
            'declare_rate', symbol=n['measurement'], right=f"({n['processValue']}-{n['measurement']})/{n['sensorTime']}",
            relationKind='constitutive', reason='First-order sensor lag')
    else:
        rows['sensor'] = session.append(
            'declare_relation', left=n['measurement'], right=n['processValue'], relationKind='constitutive',
            reason='Instant sensor: the measurement equals the process value')
    rows['error'] = session.append(
        'declare_relation', left=n['error'], right=f"{n['direction']}*({n['setpoint']}-{n['measurement']})",
        reason='Control error; direction +1 reverse acting, -1 direct acting')
    rows['integral'] = session.append(
        'declare_rate', symbol=n['integral'],
        right=f"{n['error']}+({n['integralTime']}/{n['gain']})*{n['trackingGain']}*({n['output']}-{n['command']})",
        reason='Integral state with back-calculation; in saturation the command tracks the output at the tracking gain')
    rows['filter'] = session.append(
        'declare_rate', symbol=n['filtered'], right=f"({n['measurement']}-{n['filtered']})/{n['filterTime']}",
        reason='First-order filter of the measurement for the derivative action')
    rows['derivative'] = session.append(
        'declare_relation', left=n['derivativeAction'],
        right=f"-{n['direction']}*{n['derivativeTime']}*({n['measurement']}-{n['filtered']})/{n['filterTime']}",
        reason='Derivative action on the filtered measurement, not on the error')
    rows['law'] = session.append(
        'declare_relation', left=n['command'],
        right=f"{n['bias']}+{n['gain']}*({n['error']}+{n['integral']}/{n['integralTime']}+{n['derivativeAction']})",
        reason='ISA dependent PID law')
    rows['limits'] = session.append(
        'declare_relation', left=n['output'], right=f"min(max({n['command']},{n['outputMin']}),{n['outputMax']})",
        relationKind='constitutive', reason='Output range of the actuator signal')
    if actuator_lag:
        rows['actuator'] = session.append(
            'declare_rate', symbol=n['actuator'], right=f"({n['output']}-{n['actuator']})/{n['actuatorTime']}",
            relationKind='constitutive', reason='Signal join and first-order actuator lag driven by the controller output')
    else:
        rows['actuator'] = session.append(
            'declare_relation', left=n['actuator'], right=n['output'], relationKind='constitutive',
            reason='Signal join: instant actuator driven by the controller output')
    return names, rows


def reduce_control_loop(session, names, rows, *, derivative=True, anti_windup=True):
    """Recorded reductions of the PID root, appended last so Undo restores it.

    PI is `apply_zero` on the derivative time; no anti-windup is `apply_zero`
    on the tracking gain. Lowering binds each zeroed symbol to zero (C1).
    """
    if not derivative:
        rows['noDerivative'] = session.append('apply_zero', sources=[rows['derivative']], symbol=names['derivativeTime'],
                                              reason='PI controller: no derivative action')
    if not anti_windup:
        rows['noAntiWindup'] = session.append('apply_zero', sources=[rows['integral']], symbol=names['trackingGain'],
                                              reason='No anti-windup: the integral does not track the limited output')
    return rows


def join_actuator(session, *, family, balance, manipulated, right, reason):
    """The physical actuator relation and its substitution into a balance.

    It is a premise of the physical family (for example the limiting case of a
    mixing or heating service), never a signal relation. `manipulated` is the
    quantity id replaced in the balance row `balance`.
    """
    relation = session.append('declare_relation', family, left=manipulated, right=right,
                              relationKind='constraint', reason=reason)
    return relation, session.append('substitute', family, sources=[balance], relation=relation, symbol=manipulated)
