"""`procedencia.runTimeline` v1: the operator actions of a run and how it ended.

    {format: "rage.run-timeline", version: 1, horizon,
     actions: [{seq, t, quantityId, value, unit, origin: "scheduled" | "operator"}],
     termination: {reason: "completed" | "operator_stop" | "solver_stop", tEnd}}

Optional and additive: a result without the key is read exactly as before. Python
produces every value (`run_timeline`); the reader only validates. Its rules:

- Actions are numbered 0..n-1 and sorted by time. An action is a truncation at
  the recorded float `t`, so several actions may share one time.
- Each action is also an event `timeline_action` on the time axis at `t`. A run
  that did not complete also carries one event `timeline_termination` at `tEnd`.
- The time axis never decreases. A time may repeat only at an action: the left
  value, then the right value (one more sample per action at that time).
- `completed` requires `resuelto` and `tEnd == horizon`. Any other reason
  requires `parcial`: an exhausted step budget or a stop never reads as solved.
- The sampled times end at `tEnd` (a stop publishes up to the last accepted time).
"""

import math

from core import unidades as un

FORMAT = 'rage.run-timeline'
VERSION = 1
REASONS = ('completed', 'operator_stop', 'solver_stop')
ORIGINS = ('scheduled', 'operator')
ACTION_EVENT = 'timeline_action'
TERMINATION_EVENT = 'timeline_termination'
_TOP = {'format', 'version', 'horizon', 'actions', 'termination'}
_ACTION = {'seq', 't', 'quantityId', 'value', 'unit', 'origin'}
_END = {'reason', 'tEnd'}
_TOL = 1e-9


def _number(x):
    return type(x) in (int, float) and math.isfinite(x)


def run_timeline(horizon, actions, reason, t_end):
    """Build the document; `actions` are dicts with t, quantityId, value, unit, origin (seq is assigned)."""
    return {'format': FORMAT, 'version': VERSION, 'horizon': float(horizon),
            'actions': [{'seq': i, 't': float(a['t']), 'quantityId': a['quantityId'], 'value': float(a['value']),
                         'unit': a['unit'], 'origin': a['origin']} for i, a in enumerate(actions)],
            'termination': {'reason': reason, 'tEnd': float(t_end)}}


def timeline_events(timeline, time_axis_id):
    """The events a result must publish for this timeline (publication helper)."""
    events = [{'codigo': ACTION_EVENT, 'ejeId': time_axis_id, 'valor': a['t'],
               'descripcion': f"{a['origin']} action {a['seq']}: {a['quantityId']} = {a['value']} {a['unit']}"}
              for a in timeline['actions']]
    end = timeline['termination']
    if end['reason'] != 'completed':
        events.append({'codigo': TERMINATION_EVENT, 'ejeId': time_axis_id, 'valor': end['tEnd'],
                       'descripcion': f"Run ended early: {end['reason']}"})
    return events


def read_run_timeline(result):
    """Validate `result['procedencia']['runTimeline']` against the whole result; raise ValueError."""
    def reject(message):
        raise ValueError(message)
    value = result['procedencia']['runTimeline']
    if not isinstance(value, dict) or set(value) != _TOP or value['format'] != FORMAT \
            or type(value['version']) is not int or value['version'] != VERSION:
        reject('Expected rage.run-timeline version 1 with exactly its fields.')
    horizon = value['horizon']
    if not _number(horizon) or horizon <= 0:
        reject('The horizon must be a positive finite number.')
    end = value['termination']
    if not isinstance(end, dict) or set(end) != _END or end['reason'] not in REASONS:
        reject('A termination with a known reason is required.')
    t_end = end['tEnd']
    if not _number(t_end) or t_end < 0 or t_end > horizon * (1 + _TOL):
        reject('The termination time must lie within [0, horizon].')
    actions = value['actions']
    if not isinstance(actions, list):
        reject('Actions must be a list.')
    previous = 0.0
    for i, action in enumerate(actions):
        if not isinstance(action, dict) or set(action) != _ACTION:
            reject(f'Action {i} needs exactly seq, t, quantityId, value, unit and origin.')
        if type(action['seq']) is not int or action['seq'] != i:
            reject(f'Action {i} must carry seq {i}.')
        if not _number(action['t']) or action['t'] < previous or action['t'] > t_end * (1 + _TOL):
            reject(f'Action {i} time must be finite, not decrease and not exceed the termination time.')
        previous = action['t']
        if not isinstance(action['quantityId'], str) or not action['quantityId'] or not _number(action['value']):
            reject(f'Action {i} needs a quantity identity and a finite value.')
        if action['origin'] not in ORIGINS:
            reject(f'Action {i} origin must be scheduled or operator.')
        try:
            un.interpretar(action['unit'])
        except (un.ErrorUnidad, TypeError, AttributeError, KeyError) as error:
            reject(f'Action {i} unit is not readable: {error}')
    estado = result['estado']
    if estado == 'fallido':
        reject('A failed result carries no run timeline.')
    if end['reason'] == 'completed':
        if estado != 'resuelto' or abs(t_end - horizon) > _TOL * horizon:
            reject('A completed run is solved and ends at the horizon.')
    elif estado != 'parcial':
        reject('A run that stopped early must be published as partial, never as solved.')
    axes = [e for e in result['ejes'] if e['rol'] == 'tiempo']
    if not axes:
        reject('A run timeline needs a time axis.')
    axis = axes[0]
    times = axis['valores']
    if not times or any(b < a for a, b in zip(times, times[1:])):
        reject('The time axis of a timed run must not decrease.')
    if abs(times[-1] - t_end) > _TOL * max(horizon, 1.0):
        reject('The sampled times must end at the termination time.')
    allowed = {}
    for action in actions:
        allowed[action['t']] = allowed.get(action['t'], 0) + 1
    seen = {}
    for time in times:
        seen[time] = seen.get(time, 0) + 1
    for time, count in seen.items():
        if count > 1 and count > 1 + allowed.get(time, 0):
            reject('A time may repeat only at an action.')
    marks = [e for e in result['eventos'] if e['codigo'] == ACTION_EVENT]
    if [(e['ejeId'], e['valor']) for e in marks] != [(axis['id'], a['t']) for a in actions]:
        reject('Every action must be published as an event on the time axis, in order.')
    stops = [e for e in result['eventos'] if e['codigo'] == TERMINATION_EVENT]
    expected = [] if end['reason'] == 'completed' else [(axis['id'], t_end)]
    if [(e['ejeId'], e['valor']) for e in stops] != expected:
        reject('An early stop must be published as one termination event at its time.')
