"""runTimeline v1 (Demo 0.3 C5): one validator rule set in both readers, plus the chart path."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.modelo.result_charts import chart_data
from core.resultados import ErrorResultados, leer_resultados
from core.resultados.formato import conjunto, eje, serie
from core.resultados.run_timeline import run_timeline, timeline_events

ROOT = Path(__file__).resolve().parent.parent
VERIFIER = ROOT / 'frontend' / 'motores' / 'resultados' / 'verificar_run_timeline.mjs'
ACTIONS = [
    {'t': 2.0, 'quantityId': 'setpoint', 'value': 341.0, 'unit': 'K', 'origin': 'scheduled'},
    {'t': 3.0, 'quantityId': 'feedRate', 'value': 0.02, 'unit': 'kg/s', 'origin': 'operator'},
]


def timed_result(reason='completed', horizon=4.0, t_end=None, actions=ACTIONS, estado=None, repeat=True):
    t_end = horizon if t_end is None else t_end
    times = [0.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0] if repeat else [0.0, 1.0, 2.0, 3.0, 4.0]
    times = [t for t in times if t <= t_end]
    if t_end not in times:
        times.append(t_end)
    kept = [a for a in actions if a['t'] <= t_end]
    timeline = run_timeline(horizon, kept, reason, t_end)
    axis = eje('t', 'Time', 'tiempo', 's', times)
    values = [330.0 + 0.5 * i for i in range(len(times))]
    estado = estado or ('resuelto' if reason == 'completed' else 'parcial')
    return conjunto('timed', 'Timed run', estado,
                    {'motor': 'test', 'metodo': None, 'firma': None, 'runTimeline': timeline},
                    [axis], [serie('T', 'Temperature', 'K', ['t'], values)],
                    timeline_events(timeline, 't'))


def cases():
    out = {}

    def add(name, result, python, ts=None):
        out[name] = {'result': result, 'python': python, 'ts': python if ts is None else ts}
    add('completed', timed_result(), True)
    add('operator_stop', timed_result('operator_stop', t_end=2.5), True)
    add('solver_stop', timed_result('solver_stop', t_end=3.0), True)  # also an exhausted step budget
    add('no_actions', timed_result(actions=[], repeat=False), True)
    v0 = timed_result()
    del v0['procedencia']['runTimeline']
    v0['eventos'] = []
    add('v0_without_key', v0, True)
    add('completed_but_partial', timed_result(estado='parcial'), False)
    add('step_budget_read_as_solved', timed_result('solver_stop', t_end=3.0, estado='resuelto'), False)
    add('stop_read_as_solved', timed_result('operator_stop', t_end=2.5, estado='resuelto'), False)
    add('failed_with_timeline', timed_result(estado='fallido'), False)

    def mutate(name, change, python=False, ts=None):
        r = timed_result()
        change(r)
        add(name, r, python, ts)
    mutate('extra_field', lambda r: r['procedencia']['runTimeline'].update(extra=1))
    mutate('version_2', lambda r: r['procedencia']['runTimeline'].update(version=2))
    mutate('bad_reason', lambda r: r['procedencia']['runTimeline']['termination'].update(reason='paused'))
    mutate('bad_origin', lambda r: r['procedencia']['runTimeline']['actions'][0].update(origin='script'))
    mutate('bad_seq', lambda r: r['procedencia']['runTimeline']['actions'][1].update(seq=5))
    mutate('non_numeric_value', lambda r: r['procedencia']['runTimeline']['actions'][0].update(value='341'))
    mutate('unreadable_unit', lambda r: r['procedencia']['runTimeline']['actions'][0].update(unit='bogus_unit'), False, True)
    mutate('actions_out_of_order', lambda r: r['procedencia']['runTimeline']['actions'].reverse())
    mutate('action_after_end', lambda r: r['procedencia']['runTimeline']['actions'][1].update(t=9.0))
    mutate('horizon_mismatch', lambda r: r['procedencia']['runTimeline']['termination'].update(tEnd=3.0))
    mutate('time_decreases', lambda r: r['ejes'][0]['valores'].__setitem__(1, 5.0))
    mutate('repeat_not_at_action', lambda r: r['ejes'][0]['valores'].__setitem__(1, 0.0))
    mutate('missing_action_event', lambda r: r['eventos'].pop(0))
    mutate('stray_termination_event', lambda r: r['eventos'].append(
        {'codigo': 'timeline_termination', 'ejeId': 't', 'valor': 4.0, 'descripcion': 'x'}))
    mutate('no_time_axis', lambda r: r['ejes'][0].update(rol='otro'))
    early = timed_result('operator_stop', t_end=2.5)
    early['eventos'] = [e for e in early['eventos'] if e['codigo'] != 'timeline_termination']
    add('stop_without_event', early, False)
    return out


@pytest.mark.parametrize('name,case', cases().items())
def test_python_reader(name, case):
    if case['python']:
        leer_resultados(copy.deepcopy(case['result']))
    else:
        with pytest.raises(ErrorResultados):
            leer_resultados(copy.deepcopy(case['result']))


def test_repeated_time_is_published_and_converted_by_the_chart_path():
    result = leer_resultados(timed_result())
    axis, row = result['ejes'][0], result['series'][0]
    assert axis['valores'].count(2.0) == 2 and axis['valores'].count(3.0) == 2
    response = chart_data({'format': 'rage.chart-data.request', 'version': 1, 'resultId': result['id'], 'requests': [
        {'kind': 'axis', 'id': 't', 'unit': 'min', 'sourceUnit': 's', 'values': axis['valores'],
         'events': [e for e in result['eventos'] if e['ejeId'] == 't']},
        {'kind': 'series', 'id': 'T', 'unit': 'K', 'sourceUnit': 'K', 'values': row['valores'], 'events': []}]})
    x, y = response['rows'][0], response['rows'][1]
    assert x['values'] == pytest.approx([t / 60 for t in axis['valores']])
    assert y['values'] == row['valores']
    assert len(x['events']) == 2 and [e['codigo'] for e in x['events']] == ['timeline_action'] * 2


def test_typescript_reader_agrees_and_charts_the_repeated_time(tmp_path):
    path = tmp_path / 'cases.json'
    path.write_text(json.dumps(cases()), encoding='utf-8')
    done = subprocess.run(['node', str(VERIFIER), str(path)], capture_output=True, text=True, cwd=ROOT)
    assert done.returncode == 0, done.stdout + done.stderr
    assert 'run-timeline checks passed' in done.stdout


if __name__ == '__main__':
    sys.exit(pytest.main([__file__]))
