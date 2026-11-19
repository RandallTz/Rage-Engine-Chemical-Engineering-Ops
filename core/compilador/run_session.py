"""Demo 0.3 C7: the run session.

A session holds one lowered `DerivedSystem` and a `TimelineRun` (core/solvers/timeline.py) and steps it between the
operator's actions. It adds no physics: a declared time input is a zero-rate pseudo-state (C2), an action is a
state update at a recorded instant (C4), and the finished run is published by the shared `publish_trajectory`
with its `runTimeline` (C5). Design: roadmap, Demo 0.3 section 3 (*Server*).

* `start` answers at once with a session id; lowering (35-200 s) runs in a thread and the client polls `status`.
* `advance(seq, to, actions)` runs to the displayed time `to` and then applies the actions at that edge. `seq`
  makes a retry idempotent: the same request returns the same response, a different one with the same number is
  rejected. A zero-length advance is the keep-alive of a paused client.
* A rejected action changes nothing, not even the hidden state of the closures: the state of the system is
  snapshotted around an action and restored when the action is refused (audit note R-1).
* Limits: at most `MAX_SESSIONS` live sessions per process and idle eviction after `IDLE_SECONDS`. Sessions live in
  one process, so a reloading or multi-worker server loses them; the timeline kept by the client replays them.
* Preview rows are uncertified dense-output samples; only the final document is a result.
"""

import copy
import hashlib
import json
import math
import threading
import time
import uuid

import numpy as np

from core import unidades as un
from core.resultados.formato import leer_resultados
from core.solvers.timeline import TimelineError, make_action

MAX_SESSIONS = 2
IDLE_SECONDS = 30 * 60
UNSUPPORTED = 'run_session_unsupported'


class SessionError(Exception):
    """A request the session refuses; `diagnostics` locate the cause (code and path)."""

    def __init__(self, status, code, message, path=None, **extra):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.diagnostics = [{'code': code, 'path': path, 'message': message, **extra}]


def admit_model(model):
    """Reject at once what a session cannot run; a located `SessionError` otherwise returns the selection."""
    motores = model.get('motores', {}) if isinstance(model, dict) else {}
    selection = motores.get('derivedExecution')
    if 'indexSet' in model or 'flowsheet' in model or selection is None or selection.get('version') == 5:
        raise SessionError(422, UNSUPPORTED, 'A run session needs a derived-execution selection of an ordinary model; '
                           'indexed, flowsheet and steady runs follow later.', 'motores.derivedExecution')
    if selection.get('scaling'):
        raise SessionError(422, UNSUPPORTED, 'A run session runs the identity formulation; a scaled run follows later.',
                           'motores.derivedExecution.scaling')
    return selection


def _unit_of(system, q):
    return system._unit(q)


def snapshot(system):
    """The mutable hidden state that rhs and dominio may touch (closure caches, algebraic warm starts)."""
    owners = list(getattr(system, 'closures', None) or ())
    for name in ('algebraic_block', 'dae'):
        if getattr(system, name, None) is not None:
            owners.append(getattr(system, name))
    return [(owner, {key: copy.copy(value) if isinstance(value, (dict, list, set)) else value
                     for key, value in vars(owner).items()}) for owner in owners]


def restore(saved):
    for owner, attributes in saved:
        for key in set(vars(owner)) - set(attributes):
            delattr(owner, key)
        for key, value in attributes.items():
            setattr(owner, key, copy.copy(value) if isinstance(value, (dict, list, set)) else value)


class RunSession:
    def __init__(self, session_id, clock):
        self.id, self._clock = session_id, clock
        self.state = 'lowering'            # lowering | ready | finished | failed
        self.error = None                  # {'code', 'message', 'diagnostics'} when failed
        self.lock = threading.RLock()
        self.touched = clock()
        self.system = self.run = self.inputs = None
        self.result = None                 # the published document once the run has ended
        self.next_seq = 0
        self.answers = {}                  # seq -> (request fingerprint, response)
        self.model = self.scheduled = None

    # -- lowering --------------------------------------------------------------------------------------------
    def lower(self, model, scheduled):
        """Lower the model and start the run (blocking; the store may call it in a thread)."""
        from .derived import DerivedSystem
        from core.solvers.timeline import TimelineRun
        try:
            system = DerivedSystem(model)
            if system.scaled is not None or system.prescribed_boundary() is not None:
                raise SessionError(422, UNSUPPORTED, 'A scaled run or a run to a prescribed validity boundary follows later.',
                                   'motores.derivedExecution')
            inputs = {system.ids[q]: system.states.index(q) for q in system.time_input_quantities}
            study = model['estudio']
            horizon = system.tf
            actions = self._scheduled_actions(system, inputs, scheduled, horizon)
            run = TimelineRun(system, system.initial(), horizon, rtol=study['rtol'], atol=system.numeric.atol,
                              max_step=horizon / (study['muestras'] - 1), metodo=system.method, scheduled=actions)
        except SessionError as error:
            return self._fail(error.code, error.message, error.diagnostics)
        except TimelineError as error:
            return self._fail(error.code, error.message, [{'code': error.code, 'path': None, 'message': error.message}])
        except Exception as error:  # a located lowering diagnostic when the engine gives one
            diagnostics = getattr(error, 'diagnostics', None) or [{'code': 'lowering_failed', 'path': None, 'message': str(error)}]
            return self._fail(getattr(error, 'code', 'lowering_failed'), str(error), diagnostics)
        with self.lock:
            self.system, self.run, self.inputs, self.model = system, run, inputs, model
            self.state = 'finished' if run.finished else 'ready'
            if run.finished:
                self._publish()

    def _fail(self, code, message, diagnostics):
        with self.lock:
            self.state, self.error = 'failed', {'code': code, 'message': message, 'diagnostics': diagnostics}

    # -- actions ---------------------------------------------------------------------------------------------
    def _updates(self, requests, label='actions'):
        """Located conversion of `[{quantityId, value, unit}]` into state-index updates in SI."""
        if not isinstance(requests, list) or not requests:
            raise SessionError(422, 'invalid_action', f'{label} must be a nonempty list.', label)
        updates = {}
        for i, item in enumerate(requests):
            where = f'{label}[{i}]'
            if not isinstance(item, dict) or set(item) != {'quantityId', 'value', 'unit'}:
                raise SessionError(422, 'invalid_action', 'An action needs exactly quantityId, value and unit.', where)
            qid = item['quantityId']
            if qid not in self.inputs:
                raise SessionError(422, 'time_input_not_declared', 'Only a declared time input can be changed during a run; '
                                   'change anything else before a new run.', where + '.quantityId', quantityId=qid)
            if type(item['value']) not in (int, float) or not math.isfinite(item['value']):
                raise SessionError(422, 'invalid_action', 'The value must be a finite number.', where + '.value')
            index = self.inputs[qid]
            try:
                if not un.compatibles(item['unit'], _unit_of(self.system, self.system.states[index])):
                    raise SessionError(422, 'unit_mismatch', 'The unit does not match the quantity.', where + '.unit')
                value = float(un.a_SI(float(item['value']), item['unit']))
            except un.ErrorUnidad as error:
                raise SessionError(422, 'unit_mismatch', str(error), where + '.unit') from error
            if index in updates:
                raise SessionError(422, 'invalid_action', 'A quantity appears twice in one request.', where + '.quantityId')
            updates[index] = value
        return updates

    def _scheduled_actions(self, system, inputs, scheduled, horizon):
        if not scheduled:
            return ()
        self.system, self.inputs = system, inputs
        if not isinstance(scheduled, list):
            raise SessionError(422, 'invalid_action', 'scheduled must be a list.', 'scheduled')
        grouped = {}
        for i, item in enumerate(scheduled):
            if not isinstance(item, dict) or 't' not in item or type(item['t']) not in (int, float):
                raise SessionError(422, 'invalid_action', 'A scheduled action needs a time t.', f'scheduled[{i}]')
            body = {key: value for key, value in item.items() if key != 't'}
            grouped.setdefault(float(item['t']), []).append(body)
        out = []
        for t, items in sorted(grouped.items()):
            updates = self._updates(items, 'scheduled')
            self._check_box(updates, f'scheduled (t = {t:g})')
            out.append(make_action(t, updates, 'scheduled'))
        return out

    def _check_box(self, updates, where):
        """The pure held-input box check (no restart is primed): a value outside its declared index-one box is refused."""
        system = self.system
        if getattr(system, 'dae', None) is None:
            return
        probe = np.array(system.initial(), dtype=float)
        for index, value in updates.items():
            probe[index] = value
        try:
            system._admit_time_inputs(probe)
        except ValueError as error:
            raise SessionError(422, 'state_outside_domain', f'{where}: {error}', 'scheduled') from error

    def _apply(self, updates):
        """Apply validated state-index updates at the edge; the hidden state is restored on any rejection."""
        system = self.system
        # A pure pre-check of the held-input box, so the usual rejection never primes a restart.
        probe = np.array(self.run.preview([self.run.edge])[0], dtype=float)
        for index, value in updates.items():
            probe[index] = value
        try:
            if getattr(system, 'dae', None) is not None:
                system._admit_time_inputs(probe)
        except ValueError as error:
            raise SessionError(422, 'state_outside_domain', str(error)) from error
        saved = snapshot(system)
        try:
            return self.run.apply(updates)
        except TimelineError as error:
            restore(saved)
            raise SessionError(422 if error.code != 'run_finished' else 409, error.code, error.message) from error

    # -- stepping --------------------------------------------------------------------------------------------
    def _sample_times(self, start, end):
        study = self.model['estudio']
        grid = np.linspace(0.0, self.run.horizon, study['muestras'])
        return [float(t) for t in grid if start < t <= end]

    def _rows(self, times, jump=None):
        rows = [] if jump is None else [(jump[0], jump[2])]
        if times:
            rows += list(zip(times, self.run.preview(times)))
        ids = self.system.state_ids
        return {'t': [float(t) for t, _ in rows],
                'values': {qid: [float(state[i]) for _, state in rows] for i, qid in enumerate(ids)}}

    def advance(self, seq, to, actions=None):
        fingerprint = hashlib.sha256(json.dumps([to, actions], sort_keys=True).encode()).hexdigest()
        if seq in self.answers:
            if self.answers[seq][0] != fingerprint:
                raise SessionError(409, 'sequence_reused', 'This sequence number already carries a different request.')
            return self.answers[seq][1]
        if self.state != 'ready':
            raise SessionError(409, 'session_' + self.state, f'The session is {self.state}.')
        if seq != self.next_seq:
            raise SessionError(409, 'sequence_mismatch', f'Expected sequence number {self.next_seq}.', expected=self.next_seq)
        if type(to) not in (int, float) or not math.isfinite(to):
            raise SessionError(422, 'invalid_time', 'The target time must be a finite number.', 'to')
        if to < self.run.edge:
            raise SessionError(422, 'time_not_forward', 'A run only advances.', 'to')
        # Located validation first: a malformed or undeclared action refuses the request before any stepping.
        updates = None if actions is None else self._updates(actions)
        previous = self.run.edge
        cursor = len(self.run.actions)
        # A scheduled action on the way is a jump of its own: record the previous time to emit its right state.
        saved = snapshot(self.system)
        try:
            self.run.advance(float(to))
        except TimelineError as error:
            # A scheduled action is popped before it is applied, so the run cannot continue as if it were never
            # there: the session fails with the located cause and nothing is dropped silently.
            restore(saved)
            self._abort(error.code, error.message, 'scheduled')
            raise SessionError(422, error.code, error.message, 'scheduled') from error
        response = {'seq': seq, 'edge': self.run.edge, 'finished': self.run.finished}
        end = self.run.edge
        times = self._sample_times(previous, end)
        if end > previous and end not in times:
            times.append(end)
        scheduled = self.run.jumps[cursor:]
        rows = self._rows([t for t in times if not any(t == j[0] for j in scheduled)])
        response['rows'] = rows
        response['jumps'] = [{'t': j[0], 'left': dict(zip(self.system.state_ids, map(float, j[1]))),
                              'right': dict(zip(self.system.state_ids, map(float, j[2])))} for j in scheduled]
        if actions is not None and not self.run.finished:
            # Refused by the state at the edge (outside the declared domain): the run has advanced and nothing
            # else changed, so the refusal is part of the answer and the sequence number is consumed.
            try:
                action = self._apply(updates)
            except SessionError as error:
                response['rejected'] = error.diagnostics
            else:
                jump = self.run.jumps[-1]
                response['applied'] = {'seq': action.seq, 't': action.t,
                                       'left': dict(zip(self.system.state_ids, map(float, jump[1]))),
                                       'right': dict(zip(self.system.state_ids, map(float, jump[2])))}
        elif actions is not None:
            response['rejected'] = [{'code': 'run_finished', 'path': 'actions', 'message': 'The run has ended; no action is accepted.'}]
        if self.run.finished:
            self._publish()
            response['result'] = self.result
        response['state'] = self.state
        self.answers[seq] = (fingerprint, response)
        self.next_seq += 1
        return response

    def stop(self):
        if self.state == 'ready':
            self.run.stop()
            self._publish()
        return {'state': self.state, 'result': self.result, **({'error': self.error} if self.error else {})}

    # -- publication ----------------------------------------------------------------------------------------
    def _timeline(self):
        record, system = self.run.record(), self.system
        actions = []
        for action in self.run.actions:
            for index, value in action.updates:
                q = system.states[index]
                actions.append({'t': action.t, 'quantityId': system.state_ids[index], 'value': value,
                                'unit': _unit_of(system, q), 'origin': action.origin})
        return {'horizon': record['horizon'], 'actions': actions, 'termination': record['termination']}

    def _publish(self):
        from .derived import publish_trajectory
        run, system = self.run, self.system
        trajectory = run.trajectory()
        study = self.model['estudio']
        jumps = run.jumps
        action_times = {j[0] for j in jumps}
        times = sorted({float(t) for t in np.linspace(0.0, run.horizon, study['muestras'])
                        if t <= trajectory.t_fin and t not in action_times} | {trajectory.t_fin})
        rows = {}
        for t in times:
            rows.setdefault(t, []).append(trajectory.y(t))
        for t in action_times:
            same = [j for j in jumps if j[0] == t]
            rows[t] = [same[0][1], same[-1][2]]
        ordered = [(t, state) for t in sorted(rows) for state in rows[t]]
        try:
            result = publish_trajectory(system, trajectory, None, timeline=self._timeline(), rows=ordered)
            leer_resultados(result)
        except Exception as error:
            self._abort('publication_failed', f'The finished run could not be published: {error}', 'result')
            raise SessionError(500, 'publication_failed', self.error['message'], 'result') from error
        self.result = result
        self.state = 'finished'
        self.release()

    def _abort(self, code, message, path):
        """End the session as failed with a located error and free the lowered system."""
        self.state, self.error = 'failed', {'code': code, 'message': message, 'diagnostics': [{'code': code, 'path': path, 'message': message}]}
        if self.run is not None:
            self.release()

    def release(self):
        """Drop the lowered system (about 121 MB for the CSTR); the published result and timeline stay."""
        self.timeline = self.run.record() if self.run.finished else None
        self.system = self.run = None

    def status(self):
        out = {'sessionId': self.id, 'state': self.state}
        if self.error:
            out['error'] = self.error
        if self.state == 'ready':
            out.update(horizon=self.run.horizon, edge=self.run.edge, nextSeq=self.next_seq, timeInputs=sorted(self.inputs),
                       stateIds=list(self.system.state_ids),
                       # C9-R1: rows, jumps and applied states are SI state values; Python names their unit, so a
                       # client labels them without converting and without assuming the Model's declared unit.
                       stateUnits={qid: _unit_of(self.system, q) for qid, q in zip(self.system.state_ids, self.system.states)})
        if self.state == 'finished':
            out['result'] = self.result
        return out


class SessionStore:
    """The sessions of one process, with their limits. `clock` is injectable so that eviction is testable."""

    def __init__(self, max_sessions=MAX_SESSIONS, idle_seconds=IDLE_SECONDS, clock=time.monotonic):
        self.max_sessions, self.idle_seconds, self.clock = max_sessions, idle_seconds, clock
        self.sessions, self.evicted = {}, set()
        self.guard = threading.Lock()

    def sweep(self):
        now = self.clock()
        for key, session in list(self.sessions.items()):
            if now - session.touched > self.idle_seconds and session.lock.acquire(blocking=False):
                try:
                    del self.sessions[key]
                    self.evicted.add(key)
                finally:
                    session.lock.release()

    def start(self, model, scheduled=None, background=True):
        admit_model(model)
        with self.guard:
            self.sweep()
            live = [s for s in self.sessions.values() if s.state in ('lowering', 'ready')]
            if len(live) >= self.max_sessions:
                raise SessionError(429, 'session_limit', f'At most {self.max_sessions} run sessions can be live; stop one first.')
            session = RunSession(uuid.uuid4().hex[:16], self.clock)
            self.sessions[session.id] = session
        job = lambda: session.lower(copy.deepcopy(model), scheduled)
        if background:
            threading.Thread(target=job, daemon=True).start()
        else:
            job()
        return session

    def get(self, session_id):
        with self.guard:
            self.sweep()
            session = self.sessions.get(session_id)
        if session is None:
            if session_id in self.evicted:
                raise SessionError(410, 'session_expired', 'The session was evicted after idling; replay the recorded timeline.')
            raise SessionError(404, 'session_unknown', 'No such run session.')
        session.touched = self.clock()
        return session

    def advance(self, session_id, seq, to, actions=None):
        session = self.get(session_id)
        with session.lock:
            session.touched = self.clock()
            return session.advance(seq, to, actions)

    def stop(self, session_id):
        session = self.get(session_id)
        try:
            with session.lock:
                return session.stop()
        finally:
            with self.guard:
                self.sessions.pop(session_id, None)

    def status(self, session_id):
        return self.get(session_id).status()


SESSIONS = SessionStore()
