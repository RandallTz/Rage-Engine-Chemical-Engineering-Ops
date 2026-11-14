"""
Timeline driver: one run of the step generator with actions that change the state at recorded instants.

It knows no physics. An *action* is a set of state-vector updates `{index: value}` applied at an instant `t*`.
A time input that Solve holds as a zero-rate pseudo-state is changed by exactly such an update, and so is a
scheduled change; the model decides what the indices mean.

Rule for an action at `t*` (design: roadmap, Demo 0.3 section 3):

* the run steps until the accepted time reaches `t*`, so the last accepted step brackets `t*`; a step that
  already reached `t*` is not repeated;
* that step is truncated at `t*` (its dense output gives the state there), the updates are applied and a new step
  generator restarts from `t*`. The state before is the *left* value, the one after the *right* value;
* steps never depend on the edges a client asks for, so a replay that knows only the recorded actions takes the
  same steps and the same interpolant: live and replayed trajectories are bit-identical on one build.

Preview rows come from the bare dense output and never call the system, so they cannot disturb its closure or
warm-start state. A run ends in exactly one of three ways: it reaches the horizon (`completed`), the operator
stops it (`operator_stop`) or the integrator stops (`solver_stop`: a domain, an event policy, an exhausted step
budget). After an end no action is accepted.
"""

from dataclasses import dataclass

import numpy as np

from .integrador import DomainViolation, Trayectoria, integrar, pasos

COMPLETED, OPERATOR_STOP, SOLVER_STOP = 'completed', 'operator_stop', 'solver_stop'


class TimelineError(ValueError):
    """An action or request the run cannot accept; the run is left unchanged."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class Action:
    t: float
    updates: tuple            # ((state index, value), ...) in a fixed order
    origin: str = 'operator'  # 'operator' or 'scheduled'
    seq: int = 0


def make_action(t, updates, origin='operator'):
    """Normalise `updates` (a mapping or pairs) into an `Action` with no sequence number yet."""
    pairs = tuple(sorted((int(k), float(v)) for k, v in (updates.items() if hasattr(updates, 'items') else updates)))
    if not pairs or len({k for k, _ in pairs}) != len(pairs):
        raise TimelineError('invalid_action', 'An action needs at least one update and no repeated state index.')
    if origin not in ('operator', 'scheduled'):
        raise TimelineError('invalid_action', f'Unknown action origin {origin!r}.')
    return Action(float(t), pairs, origin)


class TimelineRun:
    def __init__(self, sistema, y0, horizon, *, start_time=0.0, rtol=1e-8, atol=1e-10, max_step=np.inf, h_min=1e-10,
                 max_pasos=200000, metodo='RK45', scheduled=()):
        horizon, start_time = float(horizon), float(start_time)
        if not horizon > start_time:
            raise TimelineError('invalid_horizon', 'The horizon must lie after the start time.')
        self.sistema, self.horizon, self.start_time = sistema, horizon, start_time
        self._options = dict(rtol=rtol, atol=atol, max_step=max_step, h_min=h_min, max_pasos=max_pasos, metodo=metodo)
        self.edge = start_time
        self.actions = []             # applied, in order
        self.jumps = []               # (t*, state before, state after) for each applied action
        self.termination = None       # {'reason', 'tEnd'} once the run has ended
        self._done = []               # closed segments (truncated trajectories)
        self._used = 0                # steps taken by closed segments (the budget is cumulative)
        self._pending = []
        for item in sorted(scheduled, key=lambda a: a.t):
            if not (start_time <= item.t < horizon):
                raise TimelineError('invalid_action', f'A scheduled action at t = {item.t} lies outside [start, horizon).')
            self._pending.append(make_action(item.t, item.updates, item.origin))
        self._y0 = np.array(y0, dtype=float)
        self._start_segment(start_time, self._y0.copy())

    # -- segments -----------------------------------------------------------------------------------------
    def _generator(self, t, y):
        opts = self._options
        return pasos(self.sistema, y, self.horizon, opts['rtol'], opts['atol'], opts['max_step'], opts['h_min'],
                     opts['max_pasos'] - self._used, opts['metodo'], start_time=t, horizon=self.horizon)

    @staticmethod
    def _prime(generator):
        """Run the generator to its first yield; (trajectory, ended) where ended means it stopped at once."""
        try:
            return next(generator), False
        except StopIteration as stop:
            return stop.value, True

    def _start_segment(self, t, y):
        generator = self._generator(t, y)
        tray, ended = self._prime(generator)
        self._install(generator, tray, ended, t)

    def _install(self, generator, tray, ended, t):
        self._gen, self._tray, self._seg_start = generator, tray, float(t)
        if ended or tray.detenida is not None:
            self._finish(SOLVER_STOP)

    def _accepted(self):
        return self._tray.tramos[-1][1] if self._tray.tramos else self._seg_start

    @property
    def finished(self):
        return self.termination is not None

    def _drain(self):
        try:
            while True:
                next(self._gen)
        except StopIteration:
            pass

    def _finish(self, reason, drain=True):
        if self.termination is not None:
            return
        if drain and reason in (COMPLETED, SOLVER_STOP):
            self._drain()
        else:
            self._gen.close()
        self._done.append(self._tray)
        self._used += self._tray.pasos
        t_end = self._tray.t_fin if reason != OPERATOR_STOP else self.edge
        self.edge = t_end
        self.termination = {'reason': reason, 'tEnd': float(t_end)}

    def _run_to(self, t):
        """Step until the accepted time reaches `t`; False when the run ended first."""
        while not self.finished and self._accepted() < t:
            try:
                tray = next(self._gen)
            except StopIteration:
                self._finish(COMPLETED if self._tray.detenida is None and self._tray.t_fin >= self.horizon else SOLVER_STOP)
                return False
            if tray.detenida is not None:
                self._finish(SOLVER_STOP)
                return False
        return not self.finished

    # -- public run control ---------------------------------------------------------------------------------
    def advance(self, t_next):
        """Run to the displayed time `t_next` (scheduled actions on the way land at their own instants)."""
        t_next = min(float(t_next), self.horizon)
        if self.finished:
            return False
        if t_next < self.edge:
            raise TimelineError('time_not_forward', 'A run only advances.')
        while self._pending and self._pending[0].t <= t_next:
            item = self._pending.pop(0)
            if not self._run_to(item.t):
                return False
            self.edge = item.t
            self._apply(item.updates, item.origin)
            if self.finished:
                return False
        if not self._run_to(t_next):
            return False
        self.edge = t_next
        if t_next >= self.horizon:
            self._finish(COMPLETED)
        return not self.finished

    def apply(self, updates):
        """An operator action at the current edge (the `t_next` of the last `advance`)."""
        if self.finished:
            raise TimelineError('run_finished', 'The run has ended; no action is accepted.')
        if self.edge >= self.horizon:
            raise TimelineError('at_horizon', 'An action at the horizon has no effect.')
        return self._apply(make_action(self.edge, updates).updates, 'operator')

    def stop(self):
        """Operator stop: the run ends at the current edge."""
        if self.finished:
            raise TimelineError('run_finished', 'The run has ended.')
        self._truncate(self.edge)
        self._finish(OPERATOR_STOP)

    # -- truncation -------------------------------------------------------------------------------------------
    def _state_at(self, t):
        """State at `t` inside the accepted part of the current segment: (index of its segment, state)."""
        tray = self._tray
        for k, (t0, t1, dense) in enumerate(tray.tramos):
            if t <= t1:
                return k, np.array(dense(max(t, t0)), dtype=float)
        if tray.tramos or t != self._seg_start:
            raise TimelineError('time_not_reached', f'The run has not reached t = {t}.')
        return None, np.array(tray.y_fin, dtype=float)

    def _truncate(self, t, k=None):
        tray = self._tray
        if k is None:
            k = next((i for i, (_, t1, _) in enumerate(tray.tramos) if t <= t1), None)
        if k is not None:
            t0, _, dense = tray.tramos[k]
            tray.tramos = tray.tramos[:k] + [(t0, t, dense)]
        tray.eventos = [event for event in tray.eventos if event[1] <= t]
        tray.event_contexts = {key: value for key, value in tray.event_contexts.items() if key <= t}
        tray.t_fin = t

    def _apply(self, updates, origin):
        t = self.edge
        try:
            k, left = self._state_at(t)
        except DomainViolation as error:
            self._stop_at_domain(error)
            raise TimelineError('run_finished', error.mensaje) from error
        right = left.copy()
        for index, value in updates:
            if not 0 <= index < len(right):
                raise TimelineError('unknown_state', f'State index {index} does not exist.')
            right[index] = value
        # Validate the restart state before the current segment is touched, so a rejected action changes nothing.
        used = self._used + self._tray.pasos
        opts = self._options
        if opts['max_pasos'] - used < 1:
            raise TimelineError('step_budget', 'The step budget is exhausted.')
        generator = pasos(self.sistema, right, self.horizon, opts['rtol'], opts['atol'], opts['max_step'], opts['h_min'],
                          opts['max_pasos'] - used, opts['metodo'], start_time=t, horizon=self.horizon)
        try:
            tray, ended = self._prime(generator)
        except ValueError as error:
            raise TimelineError('state_outside_domain', str(error)) from error
        self._gen.close()
        self._truncate(t, k)
        self._tray.y_fin = left
        self._done.append(self._tray)
        self._used = used
        action = Action(t, tuple(updates), origin, len(self.actions) + 1)
        self.actions.append(action)
        self.jumps.append((t, left, right))
        self._install(generator, tray, ended, t)
        return action

    def _stop_at_domain(self, error):
        """The interpolant left its declared domain at an action instant: stop at the last verified point."""
        tray = self._tray
        if tray.tramos:
            t0, _, _ = tray.tramos[-1]
            tray.tramos = tray.tramos[:-1]
            if tray.tramos:
                t_prev = tray.tramos[-1][1]
                tray.y_fin = np.array(tray.tramos[-1][2](t_prev), dtype=float)
            else:
                t_prev = self._seg_start
            tray.t_fin = t_prev
        tray.detenida = DomainViolation(self.sistema, error.index, tray.t_fin, abs(error.time - tray.t_fin))
        tray.eventos = [event for event in tray.eventos if event[1] <= tray.t_fin]
        tray.eventos.append((tray.detenida.codigo, tray.t_fin, None, None, tray.detenida.mensaje))
        self._finish(SOLVER_STOP, drain=False)

    # -- reading -----------------------------------------------------------------------------------------------
    def _segments(self):
        return self._done if self.finished else self._done + [self._tray]

    def preview(self, times, side='left'):
        """States at `times` (each within the accepted part of the run) from the bare dense output.

        A time equal to an action instant gives the state before (`side='left'`) or after (`'right'`) the jump.
        No system method is called, so a preview cannot change closure or warm-start state."""
        out = []
        segments = self._segments()
        for t in times:
            t = float(t)
            order = list(range(len(segments)))[::-1] if side == 'right' else range(len(segments))
            for s in order:
                tray = segments[s]
                hit = next((tr for tr in tray.tramos if tr[0] <= t <= tr[1]), None)
                if hit is not None:
                    dense = hit[2]
                    out.append(np.array(getattr(dense, 'raw', dense)(t), dtype=float))
                    break
            else:
                if t == self.start_time and not segments[0].tramos:
                    out.append(self._y0.copy())
                else:
                    raise TimelineError('time_not_reached', f'The run has not reached t = {t}.')
        return out

    def record(self):
        """The timeline in the run-timeline shape (state indices stand for quantity identities)."""
        return {'horizon': self.horizon,
                'actions': [{'seq': a.seq, 't': a.t, 'updates': [list(pair) for pair in a.updates], 'origin': a.origin}
                            for a in self.actions],
                'termination': dict(self.termination) if self.termination else None}

    def trajectory(self):
        """The concatenated trajectory of the finished run (an action instant carries both its tramos)."""
        if not self.finished:
            raise TimelineError('run_running', 'The run has not ended.')
        segments = self._done
        combined = Trayectoria(t_fin=segments[-1].t_fin, y_fin=segments[-1].y_fin, detenida=segments[-1].detenida)
        for seg in segments:
            combined.tramos += seg.tramos
            combined.eventos += seg.eventos
            combined.event_contexts.update(seg.event_contexts)
            combined.pasos += seg.pasos
            combined.rechazos += seg.rechazos
        combined._refine = self._refiner(combined)
        return combined

    def _refiner(self, combined):
        h_min, horizon = self._options['h_min'], self.horizon
        actions, termination = list(self.actions), dict(self.termination)

        def refine(index, requested, failure):
            start, end, dense = combined.tramos[index]
            initial = np.array(dense(start), dtype=float)
            step = (end - start) / 2
            if step < h_min or start + step == start:
                raise DomainViolation(self.sistema, failure.index, start, end - start)
            # Replay the recorded actions after `start`; never rebuild the suffix without them.
            later = [a for a in actions if a.t > start]
            options = dict(self._options, max_step=min(self._options['max_step'], step))
            try:
                replacement = TimelineRun(self.sistema, initial, horizon, start_time=start, scheduled=later, **options)
                replacement.advance(termination['tEnd'])
                if termination['reason'] == OPERATOR_STOP and not replacement.finished:
                    replacement.stop()
                tail = replacement.trajectory()
                value = tail.y(requested)
            except (TimelineError, ValueError) as error:
                raise DomainViolation(self.sistema, failure.index, start, step) from error
            combined.tramos = combined.tramos[:index] + tail.tramos
            combined.eventos = [e for e in combined.eventos if e[1] <= start] + tail.eventos
            combined.event_contexts = {t: v for t, v in combined.event_contexts.items() if t <= start}
            combined.event_contexts.update(tail.event_contexts)
            combined.t_fin, combined.y_fin, combined.detenida = tail.t_fin, tail.y_fin, tail.detenida
            combined.rechazos += tail.rechazos + 1
            return value

        return refine


def replay(sistema, y0, horizon, record, **options):
    """Rebuild a run from its start state and its recorded timeline; returns the finished `TimelineRun`.

    `record` is `TimelineRun.record()` (or its JSON form). The wall clock plays no part: the result equals the
    live run bit for bit on one build."""
    actions = [make_action(a['t'], [tuple(pair) for pair in a['updates']], a['origin']) for a in record['actions']]
    run = TimelineRun(sistema, y0, record['horizon'], scheduled=actions, **options)
    end = record['termination']
    run.advance(end['tEnd'])
    if end['reason'] == OPERATOR_STOP and not run.finished:
        run.stop()
    return run
