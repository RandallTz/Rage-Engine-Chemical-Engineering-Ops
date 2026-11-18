"""Demo 0.3 C7: the run session (core/compilador/run_session.py and the `run-session` routes).

Plant: the closed rigid region of `test_time_inputs.heated_region` with its heater duty declared a time input.
Its energy is the exact integral U(t) = U0 + integral of P, so a run with duty changes at recorded instants is
checked against an independent piecewise-linear reference, not against the code under test.

Checked: HTTP start/status/advance/stop; a live run equals its replay bit for bit, independent of the client's
pace and with a rejected action in between; a retried `advance` returns the same rows and a different request on
the same number is refused; the session limit, idle eviction and keep-alive; concurrent identical requests;
located rejections (undeclared quantity, unit, unsupported model); the hidden-state snapshot of audit note R-1;
and `/resolver` results unchanged by the `publish_trajectory` split.
"""
import asyncio
import copy
from pathlib import Path
import sys
import threading
import unittest

import httpx
import numpy as np
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from backend.api_modelo import router
from core.compilador import resolver
from core.compilador.run_session import SessionError, SessionStore, restore, snapshot
from core.resultados.formato import leer_resultados
from test_time_inputs import POWER, HORIZON, heated_region, selection_model

app = FastAPI()
app.include_router(router)


def post(path, body):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            return await client.post('/modelo/run-session/' + path, json=body, timeout=600)
    return asyncio.run(run())


def duty(value, unit='W'):
    return [{'quantityId': 'heaterDuty', 'value': value, 'unit': unit}]


def series(result):
    return {row['id']: np.asarray(row['valores'], dtype=float) for row in result['series']}


def energy_id(result):
    return next(key for key in series(result) if key.startswith('campo.') and not key.endswith('heaterDuty')
                and series(result)[key][0] == 0.0 and series(result)[key][-1] > 0)


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        author, energy = heated_region()
        cls.model = selection_model(author, energy, inputs=['heaterDuty'])
        from backend.api_modelo import _modelo
        cls.parsed = _modelo({'modelo': cls.model})

    def store(self, **options):
        return SessionStore(**options)

    def run_live(self, store, plan, rejected=()):
        """`plan` is [(to, actions or None)]; returns the finished session's result. `rejected` are extra
        (to, actions) requests refused on the way."""
        session = store.start(copy.deepcopy(self.parsed), background=False)
        self.assertEqual(session.state, 'ready', session.error)
        seq = 0
        for to, actions in plan:
            store.advance(session.id, seq, to, actions); seq += 1
            if to in dict(rejected):
                with self.assertRaises(SessionError):
                    store.advance(session.id, seq, to, dict(rejected)[to])
        return session


class RunTests(Fixture):
    def test_live_run_matches_the_piecewise_exact_energy_and_the_published_timeline(self):
        store = self.store()
        session = self.run_live(store, [(200.0, duty(200.0)), (400.0, duty(0.0)), (HORIZON, None)])
        result = session.result
        leer_resultados(result)
        self.assertEqual(result['estado'], 'resuelto')
        timeline = result['procedencia']['runTimeline']
        self.assertEqual([(a['t'], a['value'], a['origin']) for a in timeline['actions']],
                         [(200.0, 200.0, 'operator'), (400.0, 0.0, 'operator')])
        self.assertEqual(timeline['termination'], {'reason': 'completed', 'tEnd': HORIZON})
        times = np.asarray(result['ejes'][0]['valores'])
        # An action instant carries its left then its right sample.
        for t in (200.0, 400.0):
            self.assertEqual(int(np.sum(times == t)), 2)
        U = series(result)['campo.x34b5c0f5ca']
        exact = np.array([POWER * min(t, 200.) + 200. * max(0., min(t, 400.) - 200.) for t in times])
        np.testing.assert_allclose(U, exact, rtol=1e-9, atol=1e-6)
        held = series(result)['campo.heaterDuty']
        expected = np.where(times < 200., POWER, np.where(times < 400., 200., 0.))
        # left value at the instant, right value after it
        i200 = np.flatnonzero(times == 200.)
        self.assertEqual((held[i200[0]], held[i200[1]]), (POWER, 200.))
        np.testing.assert_array_equal(np.delete(held, np.concatenate([np.flatnonzero(times == 200.), np.flatnonzero(times == 400.)])),
                                      np.delete(expected, np.concatenate([np.flatnonzero(times == 200.), np.flatnonzero(times == 400.)])))
        self.assertEqual([e['codigo'] for e in result['eventos'] if e['codigo'] == 'timeline_action'], ['timeline_action'] * 2)
        self.assertNotEqual(result['procedencia']['firma'], resolver(copy.deepcopy(self.parsed))['procedencia']['firma'])

    def test_live_equals_replay_bit_for_bit_independent_of_pace_and_with_a_rejected_action(self):
        live = self.run_live(self.store(), [(55.5, None), (200.0, duty(200.0)), (333.0, None), (400.0, duty(0.0)), (HORIZON, None)],
                             rejected={200.0: [{'quantityId': 'nothing', 'value': 1.0, 'unit': 'W'}],
                                       333.0: [{'quantityId': 'heaterDuty', 'value': 1.0, 'unit': 'K'}]}).result
        store = self.store()
        scheduled = [{'t': a['t'], 'quantityId': a['quantityId'], 'value': a['value'], 'unit': a['unit']}
                     for a in live['procedencia']['runTimeline']['actions']]
        session = store.start(copy.deepcopy(self.parsed), scheduled, background=False)
        store.advance(session.id, 0, HORIZON)
        replay = session.result
        self.assertEqual([e['codigo'] for e in live['eventos']], [e['codigo'] for e in replay['eventos']])
        self.assertEqual(live['ejes'], replay['ejes'])
        self.assertEqual(live['series'], replay['series'])
        self.assertEqual([a['origin'] for a in replay['procedencia']['runTimeline']['actions']], ['scheduled'] * 2)

    def test_idempotent_advance_sequence_and_limits_of_a_request(self):
        store = self.store()
        session = store.start(copy.deepcopy(self.parsed), background=False)
        first = store.advance(session.id, 0, 100.0)
        self.assertIs(store.advance(session.id, 0, 100.0), first)
        with self.assertRaises(SessionError) as error:
            store.advance(session.id, 0, 150.0)
        self.assertEqual(error.exception.code, 'sequence_reused')
        with self.assertRaises(SessionError) as error:
            store.advance(session.id, 5, 150.0)
        self.assertEqual((error.exception.status, error.exception.code), (409, 'sequence_mismatch'))
        with self.assertRaises(SessionError) as error:
            store.advance(session.id, 1, 50.0)
        self.assertEqual(error.exception.code, 'time_not_forward')
        # nothing was consumed by the refused requests
        self.assertEqual(store.advance(session.id, 1, 100.0)['rows']['t'], [])
        self.assertEqual(first['rows']['t'][-1], 100.0)

    def test_rejected_actions_are_located_and_change_nothing(self):
        store = self.store()
        session = store.start(copy.deepcopy(self.parsed), background=False)
        store.advance(session.id, 0, 100.0)
        for actions, code, path in [
                ([{'quantityId': 'nothing', 'value': 1.0, 'unit': 'W'}], 'time_input_not_declared', 'actions[0].quantityId'),
                (duty(5.0, 'K'), 'unit_mismatch', 'actions[0].unit'),
                ([{'quantityId': 'heaterDuty', 'value': 1.0}], 'invalid_action', 'actions[0]'),
                (duty(float('nan')), 'invalid_action', 'actions[0].value')]:
            with self.assertRaises(SessionError) as error:
                store.advance(session.id, 1, 100.0, actions)
            diagnostic = error.exception.diagnostics[0]
            self.assertEqual((diagnostic['code'], diagnostic['path']), (code, path))
        self.assertEqual(len(session.run.actions), 0)
        self.assertEqual(session.next_seq, 1)
        # the accepted one, after the refusals, in kW
        response = store.advance(session.id, 1, 100.0, duty(0.1, 'kW'))
        self.assertEqual(response['applied']['right']['heaterDuty'], 100.0)

    def test_a_refusal_by_the_state_at_the_edge_is_part_of_the_answer(self):
        from core.solvers.timeline import TimelineError
        store = self.store()
        session = store.start(copy.deepcopy(self.parsed), background=False)
        original = session.run.apply

        def refuse(updates):
            raise TimelineError('state_outside_domain', 'outside the declared box')
        session.run.apply = refuse
        response = store.advance(session.id, 0, 100.0, duty(5.0))
        session.run.apply = original
        self.assertEqual(response['rejected'][0]['code'], 'state_outside_domain')
        self.assertNotIn('applied', response)
        self.assertEqual((session.next_seq, session.run.edge, len(session.run.actions)), (1, 100.0, 0))
        self.assertEqual(response['rows']['t'][-1], 100.0)   # the stretch run is not lost
        self.assertIs(store.advance(session.id, 0, 100.0, duty(5.0)), response)

    def test_session_limit_idle_eviction_and_keep_alive(self):
        now = [0.0]
        store = self.store(clock=lambda: now[0])
        first = store.start(copy.deepcopy(self.parsed), background=False)
        second = store.start(copy.deepcopy(self.parsed), background=False)
        with self.assertRaises(SessionError) as error:
            store.start(copy.deepcopy(self.parsed), background=False)
        self.assertEqual((error.exception.status, error.exception.code), (429, 'session_limit'))
        now[0] = 29 * 60
        store.advance(first.id, 0, 0.0)                     # a zero-length advance is the keep-alive
        now[0] = 31 * 60
        with self.assertRaises(SessionError) as error:
            store.status(second.id)
        self.assertEqual((error.exception.status, error.exception.code), (410, 'session_expired'))
        self.assertEqual(store.status(first.id)['state'], 'ready')   # kept alive, 2 minutes idle
        store.stop(first.id)
        self.assertEqual(store.start(copy.deepcopy(self.parsed), background=False).state, 'ready')

    def test_concurrent_identical_requests_get_one_answer(self):
        store = self.store()
        session = store.start(copy.deepcopy(self.parsed), background=False)
        answers, errors = [], []

        def call():
            try:
                answers.append(store.advance(session.id, 0, 300.0, duty(10.0)))
            except Exception as error:  # pragma: no cover - reported below
                errors.append(error)
        threads = [threading.Thread(target=call) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertTrue(all(answer is answers[0] for answer in answers))
        self.assertEqual(len(session.run.actions), 1)

    def test_unsupported_models_are_rejected_at_start(self):
        store = self.store()
        scaled = copy.deepcopy(self.parsed)
        scaled['motores']['derivedExecution']['scaling'] = {'x': 'y'}
        for model, path in [(scaled, 'motores.derivedExecution.scaling'),
                            ({**copy.deepcopy(self.parsed), 'motores': {}}, 'motores.derivedExecution')]:
            with self.assertRaises(SessionError) as error:
                store.start(model, background=False)
            self.assertEqual((error.exception.status, error.exception.diagnostics[0]['path']), (422, path))
        self.assertEqual(store.sessions, {})

    def test_stop_publishes_a_partial_run_up_to_the_last_accepted_time(self):
        store = self.store()
        session = store.start(copy.deepcopy(self.parsed), background=False)
        store.advance(session.id, 0, 123.0, duty(75.0))
        out = store.stop(session.id)
        result = out['result']
        leer_resultados(result)
        self.assertEqual(result['estado'], 'parcial')
        self.assertEqual(result['procedencia']['runTimeline']['termination'], {'reason': 'operator_stop', 'tEnd': 123.0})
        self.assertEqual(result['ejes'][0]['valores'][-1], 123.0)
        self.assertEqual(sum(e['codigo'] == 'timeline_termination' for e in result['eventos']), 1)
        self.assertEqual(store.sessions, {})
        # the lowered system is released when the run ends
        self.assertIsNone(session.system)


    def test_status_names_the_si_unit_of_every_row_whatever_the_declared_unit(self):
        """C9-R1: rows are SI state values; status names their unit, so a client labels them without converting."""
        import test_time_inputs as ti
        original = ti.Author.append
        def append(author, kind, **fields):
            if fields.get('name') in ('heaterDuty', 'heaterPower'):
                fields['unit'] = 'kW'
            return original(author, kind, **fields)
        ti.Author.append = append
        try:
            author, energy = ti.heated_region()
        finally:
            ti.Author.append = original
        model = ti.selection_model(author, energy, inputs=['heaterDuty'])
        key = model['motores']['derivedExecution']['timeInputs']['heaterDuty']
        model['datos'][key]['declaracion'] = {'texto': '1', 'unidad': 'kW'}
        from backend.api_modelo import _modelo
        store = self.store()
        session = store.start(_modelo({'modelo': model}), background=False)
        status = store.status(session.id)
        self.assertEqual(set(status['stateUnits']), set(status['stateIds']))
        self.assertEqual(status['stateUnits']['heaterDuty'], 'W')
        self.assertEqual(sorted(status['stateUnits'].values()), ['J', 'W', 'kg'])
        out = store.advance(session.id, 0, 50.0)
        self.assertEqual(out['rows']['values']['heaterDuty'][-1], 1000.0)   # 1 kW in the stated unit W
        energy_id = next(i for i, u in status['stateUnits'].items() if u == 'J')
        self.assertAlmostEqual(out['rows']['values'][energy_id][-1], 50000.0, delta=1e-6)
        store.stop(session.id)


class NonlinearBlockTests(unittest.TestCase):
    """C7-R1 and C7-R2: the F3 index-one DAE with a held input bounded to [0, 1000] W (nonlinear algebraic block)."""

    @classmethod
    def setUpClass(cls):
        import test_f3_index1_dae as dae
        from test_f3_nonlinear_algebraic import thermal_case
        from test_time_inputs import bound_input, with_held_input
        from backend.api_modelo import _modelo
        store = {}

        def held_case(owners=('domain_one', 'domain_two')):
            model, author = thermal_case(owners)
            _, held, store['qid'] = with_held_input(model, author)
            return held, author
        original, dae.thermal_case = dae.thermal_case, held_case
        try:
            held = dae.dae_case()
        finally:
            dae.thermal_case = original
        cls.parsed, cls.qid = _modelo({'modelo': bound_input(held, store['qid'], 0, 1000)}), store['qid']

    def test_a_session_publishes_a_nonlinear_model_with_and_without_actions(self):
        store = SessionStore()
        session = store.start(copy.deepcopy(self.parsed), background=False)
        horizon = session.run.horizon
        result = store.advance(session.id, 0, horizon)['result']
        leer_resultados(result)
        self.assertEqual(result['estado'], 'resuelto')
        self.assertEqual(result['procedencia']['compilation']['signature'],
                         resolver(copy.deepcopy(self.parsed))['procedencia']['compilation']['signature'])
        self.assertNotEqual(result['procedencia']['firma'], result['procedencia']['compilation']['signature'])
        session = store.start(copy.deepcopy(self.parsed), background=False)
        store.advance(session.id, 0, horizon / 2, [{'quantityId': self.qid, 'value': 500.0, 'unit': 'W'}])
        result = store.advance(session.id, 1, horizon)['result']
        leer_resultados(result)
        self.assertEqual(len(result['procedencia']['runTimeline']['actions']), 1)

    def test_an_out_of_box_scheduled_action_is_a_located_failure_and_is_never_dropped(self):
        store = SessionStore()
        scheduled = [{'t': 1.0, 'quantityId': self.qid, 'value': 2000.0, 'unit': 'W'}]
        session = store.start(copy.deepcopy(self.parsed), scheduled, background=False)
        self.assertEqual(session.state, 'failed')
        diagnostic = session.error['diagnostics'][0]
        self.assertEqual((diagnostic['code'], diagnostic['path']), ('state_outside_domain', 'scheduled'))
        with self.assertRaises(SessionError) as error:
            store.advance(session.id, 0, 10.0)
        self.assertEqual((error.exception.status, error.exception.code), (409, 'session_failed'))
        self.assertEqual(store.status(session.id)['error']['code'], 'state_outside_domain')

    def test_a_scheduled_action_refused_while_stepping_fails_the_session_located(self):
        from core.solvers.timeline import TimelineError
        store = SessionStore()
        scheduled = [{'t': 1.0, 'quantityId': self.qid, 'value': 500.0, 'unit': 'W'}]
        session = store.start(copy.deepcopy(self.parsed), scheduled, background=False)
        self.assertEqual(session.state, 'ready')

        def refuse(t):
            raise TimelineError('state_outside_domain', 'refused at the restart')
        session.run.advance = refuse
        with self.assertRaises(SessionError) as error:
            store.advance(session.id, 0, 10.0)
        self.assertEqual((error.exception.status, error.exception.code), (422, 'state_outside_domain'))
        self.assertEqual(session.state, 'failed')
        with self.assertRaises(SessionError) as again:
            store.advance(session.id, 0, 10.0)      # the retry does not continue without the action
        self.assertEqual(again.exception.code, 'session_failed')

    def test_a_failed_publication_leaves_a_failed_session_and_stop_still_answers(self):
        import core.compilador.derived as derived
        store = SessionStore()
        session = store.start(copy.deepcopy(self.parsed), background=False)
        original = derived.publish_trajectory

        def broken(*args, **kwargs):
            raise ValueError('boom')
        derived.publish_trajectory = broken
        try:
            with self.assertRaises(SessionError) as error:
                store.advance(session.id, 0, session.run.horizon)
        finally:
            derived.publish_trajectory = original
        self.assertEqual(error.exception.code, 'publication_failed')
        self.assertEqual(session.state, 'failed')
        out = store.stop(session.id)
        self.assertEqual((out['state'], out['error']['code']), ('failed', 'publication_failed'))


class HiddenStateTests(unittest.TestCase):
    def test_snapshot_restores_what_a_refused_action_primed(self):
        class Owner:
            def __init__(self):
                self.cache, self.seed = {'a': 1}, 'seed'

        class System:
            algebraic_block = dae = None

        system = System()
        system.closures = [Owner()]
        saved = snapshot(system)
        system.closures[0].cache['b'] = 2
        system.closures[0].seed = 'primed'
        system.closures[0].late = True
        restore(saved)
        self.assertEqual((system.closures[0].cache, system.closures[0].seed), ({'a': 1}, 'seed'))
        self.assertFalse(hasattr(system.closures[0], 'late'))


class RouteTests(Fixture):
    def test_http_start_status_advance_stop(self):
        started = post('start', {'modelo': self.model})
        self.assertEqual(started.status_code, 200, started.text)
        sid = started.json()['sessionId']
        status = {}
        for _ in range(600):
            status = post('status', {'sessionId': sid}).json()
            if status['state'] != 'lowering':
                break
            threading.Event().wait(0.05)
        self.assertEqual(status['state'], 'ready', status)
        self.assertEqual((status['timeInputs'], status['horizon'], status['nextSeq']), (['heaterDuty'], HORIZON, 0))
        bad = post('advance', {'sessionId': sid, 'seq': 0, 'to': 100.0, 'actions': [{'quantityId': 'x', 'value': 1, 'unit': 'W'}]})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(bad.json()['detail']['diagnostics'][0]['code'], 'time_input_not_declared')
        body = {'sessionId': sid, 'seq': 0, 'to': 100.0, 'actions': duty(100.0)}
        one, again = post('advance', body), post('advance', body)
        self.assertEqual((one.status_code, one.json()), (200, again.json()))
        self.assertEqual(one.json()['applied']['t'], 100.0)
        done = post('advance', {'sessionId': sid, 'seq': 1, 'to': HORIZON})
        self.assertEqual(done.json()['state'], 'finished')
        self.assertEqual(done.json()['result']['estado'], 'resuelto')
        self.assertEqual(post('advance', {'sessionId': sid, 'seq': 2, 'to': HORIZON}).status_code, 409)
        stopped = post('stop', {'sessionId': sid})
        self.assertEqual(stopped.json()['result']['procedencia']['runTimeline']['termination']['reason'], 'completed')
        self.assertEqual(post('status', {'sessionId': sid}).status_code, 404)
        self.assertEqual(post('start', {'modelo': self.model, 'extra': 1}).status_code, 422)

    def test_resolver_is_unchanged_by_the_publication_split(self):
        result = resolver(copy.deepcopy(self.parsed))
        self.assertEqual(result['estado'], 'resuelto')
        self.assertNotIn('runTimeline', result['procedencia'])
        times = result['ejes'][0]['valores']
        self.assertEqual(len(times), len(set(times)))
        leer_resultados(result)


if __name__ == '__main__':
    unittest.main()
