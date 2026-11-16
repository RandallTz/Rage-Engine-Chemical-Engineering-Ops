"""rage.flowsheet heat connection (F4, J-2; optional `heat` key on a v1 connection): the jacketed reactor assembled from two instances.

R (`duty-cstr`, prescribed boundary duty) and J (`jacket-service`, recorded wall
law with an exterior temperature datum) are joined by one heat connection.
The assembly replaces J's exterior temperature by R's temperature and R's duty
datum by minus J's resolved boundary heat (one duty, equal and opposite).

Independent references (no compiled expression, bridge or model RHS):
- the LSODA integration of the jacketed reactor, tests/jacketed_reactor_inputs.reference_jacketed,
  the reference the accepted single-document jacketed reactor matches (5.1e-7 K);
- the stationary balances of both volumes solved together (steady_jacketed, hybr, residual <= 1e-8), compared with
  the end of the 60000 s run (the steady mode needs the jacket holdup invariant, finding J-6).

    python -m pytest -q tests/test_flowsheet_heat.py
Writes .tmp/flowsheet_heat/{accepted,rejections,dynamic-result}.json for
frontend/verificar_flowsheet_contract.mjs.
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.modelo import leer_modelo_comun  # noqa: E402
from core.modelo.flowsheet import FlowsheetError  # noqa: E402
from core.compilador.derived_graph import LoweringError  # noqa: E402
from flowsheet_heat_inputs import authored, heat_flowsheet, CACHE  # noqa: E402
from jacketed_reactor_inputs import jacketed_data, reference_jacketed, steady_jacketed  # noqa: E402
from demo02_cstr import frozen_model as frozen_reactor  # noqa: E402

OUT = CACHE


@pytest.fixture(scope='module')
def documents():
    return authored()


@pytest.fixture(scope='module')
def model(documents):
    return leer_modelo_comun(heat_flowsheet(*documents))


def _series(result):
    return {row['id']: np.array(row['valores'], dtype=float) for row in result['series']}


# ---------------------------------------------------------------- admission

def test_heat_key_is_additive_and_rows_without_it_are_unchanged(model, documents):
    assert model['flowsheet']['version'] == 1 and 'heat' in model['flowsheet']['connections'][0]
    legacy = heat_flowsheet(*documents)
    legacy['flowsheet']['connections'][0].pop('heat')
    with pytest.raises(FlowsheetError) as caught:
        leer_modelo_comun(legacy)
    assert caught.value.code == 'flowsheet_port_direction'   # a heat-port row without the key is rejected as before


def _mutations(documents):
    base = heat_flowsheet(*documents)
    cases = []

    def case(name, edit):
        value = copy.deepcopy(base)
        edit(value)
        cases.append((name, value))
    connection = lambda m: m['flowsheet']['connections'][0]
    case('missing coupling', lambda m: connection(m).pop('heat'))
    case('coupling field', lambda m: connection(m)['heat'].update(extra=1))
    case('law endpoint', lambda m: connection(m)['heat'].update(law='both'))
    case('unknown temperature datum', lambda m: connection(m)['heat'].update(exteriorTemperature='service.nothing'))
    case('non-temperature datum', lambda m: connection(m)['heat'].update(exteriorTemperature='service.UA'))
    case('temperature on the other endpoint', lambda m: connection(m)['heat'].update(law='from'))
    case('instance value of the replaced datum', lambda m: m['flowsheet']['instances'][1]['data'].update(
        {'service.Tprocess': {'texto': '300.0', 'unidad': 'K'}}))
    case('heat recycle', lambda m: m['flowsheet']['recycles'].append('wall'))
    case('heat to material', lambda m: connection(m).update(to={'instance': 'J', 'port': 'supply'}))
    case('coupling on material', lambda m: (m['flowsheet']['exposures'].__setitem__(slice(None), [
        {'id': 'feed', 'instance': 'R', 'port': 'feed'}, {'id': 'return', 'instance': 'J', 'port': 'return'},
        {'id': 'jacketR', 'instance': 'R', 'port': 'jacket'}, {'id': 'wallJ', 'instance': 'J', 'port': 'wall'}]),
        m['flowsheet']['connections'].__setitem__(0, {'id': 'wall', 'from': {'instance': 'R', 'port': 'product'},
                                                       'to': {'instance': 'J', 'port': 'supply'}, 'heat': {'law': 'to', 'exteriorTemperature': 'service.Tprocess'}})))
    return base, cases


def test_heat_rejections_are_located_and_shared_with_the_client(documents):
    base, cases = _mutations(documents)
    expected = {'missing coupling': ('flowsheet_port_direction', 'flowsheet.connections.wall.from.port'),   # without the key, read as before
                'coupling field': ('flowsheet_invalid', 'flowsheet.connections.wall.heat'),
                'law endpoint': ('flowsheet_heat_coupling_invalid', 'flowsheet.connections.wall.heat.law'),
                'unknown temperature datum': ('flowsheet_heat_coupling_invalid', 'flowsheet.connections.wall.heat.exteriorTemperature'),
                'non-temperature datum': ('flowsheet_heat_coupling_invalid', 'flowsheet.connections.wall.heat.exteriorTemperature'),
                'temperature on the other endpoint': ('flowsheet_heat_coupling_invalid', 'flowsheet.connections.wall.heat.exteriorTemperature'),
                'instance value of the replaced datum': ('flowsheet_heat_coupling_invalid', 'flowsheet.connections.wall.heat.exteriorTemperature'),
                'heat recycle': ('flowsheet_unknown_recycle', 'flowsheet.recycles'),
                'heat to material': ('flowsheet_port_direction', 'flowsheet.connections.wall.from.port'),
                'coupling on material': ('flowsheet_invalid', 'flowsheet.connections.wall.heat')}
    rows = []
    for name, value in cases:
        with pytest.raises(FlowsheetError) as caught:
            leer_modelo_comun(value)
        assert (caught.value.code, caught.value.ruta) == expected[name], (name, caught.value.diagnostics)
        rows.append({'name': name, 'model': value, 'code': caught.value.code, 'path': caught.value.ruta})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'rejections.json').write_text(json.dumps(rows), encoding='utf-8')
    (OUT / 'accepted.json').write_text(json.dumps({'base': base}), encoding='utf-8')


def test_exactly_one_endpoint_resolves_the_duty(documents):
    """Two recorded laws (the Demo 0.2 reservoir law on R) are rejected, located at the duty endpoint."""
    from core.compilador.flowsheet_network import FlowsheetDerivedSystem
    reactor, jacket = documents
    two_laws = leer_modelo_comun(heat_flowsheet(frozen_reactor(), jacket, tf=10.0, samples=3))
    with pytest.raises(LoweringError) as caught:
        FlowsheetDerivedSystem(two_laws)
    assert caught.value.diagnostics[0]['code'] == 'index_network_heat_two_laws'
    assert caught.value.diagnostics[0]['path'] == 'flowsheet.connections.wall.from'


# ---------------------------------------------------------------- execution

@pytest.fixture(scope='module')
def dynamic(model):
    from core.compilador.flowsheet_network import resolve, selection_for
    selection = selection_for(model, 'dynamic')
    result = resolve(model, selection)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'dynamic-result.json').write_text(json.dumps({'result': result, 'selection': selection}), encoding='utf-8')
    return result


def test_the_duty_is_one_quantity_with_equal_and_opposite_terms(model):
    from core.compilador.flowsheet_network import FlowsheetDerivedSystem
    import sympy as sp
    system = FlowsheetDerivedSystem(model)
    row = system.heat_couplings[0]
    assert row['identity'] == 'equal_and_opposite'
    assert row['law']['replacedDatum'] == 'service.Tprocess' and row['law']['instanceId'] == 'J'
    assert row['duty']['instanceId'] == 'R' and row['duty']['replacedDatum'] == 'solve.Q'
    # The connected duty depends on both volumes' states, and on nothing exterior to the pair.
    duty = system.heat_duties[0][1]
    assert duty.free_symbols <= set(system.variables) | set(system.outputs) | {system.time}
    stages = {j: set(system.variables[system.offsets[j]:system.offsets[j+1]]) for j in (0, 1)}
    closures = duty.free_symbols & set(system.outputs)
    assert closures, 'the wall law uses the two temperatures from the package closures'
    # Numeric check of the identity on the initial state: R receives -Q, J receives +Q, Q = UA (T_R - T_J).
    y = system.initial()
    outputs = system.closure_values(0.0, y)
    values = dict(zip(system.variables, y)); values.update(zip(system.outputs, outputs))
    Q = float(duty.xreplace(values))
    data = jacketed_data()
    T_R, T_J = data['T0'], data['Tj0']
    assert Q == pytest.approx(data['UA'] * (T_R - T_J), rel=1e-9, abs=1e-9)
    assert sp.srepr(duty) == row['dutySI']


def test_dynamic_two_instances_match_the_jacketed_reference(dynamic):
    times = np.array(dynamic['ejes'][0]['valores'])
    sol, T_ref, Tj_ref = reference_jacketed(times)
    T, Tj = _find(dynamic, 'R'), _find(dynamic, 'J')
    assert np.max(np.abs(T - T_ref)) < 1e-5
    assert np.max(np.abs(Tj - Tj_ref)) < 1e-5
    report = dynamic['procedencia']['flowsheetCompilation']
    assert report['version'] == 1 and report['heatCouplings'][0]['connectionId'] == 'wall'
    steady = steady_jacketed()
    assert abs(T[-1] - steady['temperature']) < 1e-5
    assert abs(Tj[-1] - steady['jacketTemperature']) < 1e-5


def _find(result, instance):
    """The published closure temperature of the instance's package volume (stage 1 = R, stage 2 = J)."""
    stage = {'R': 1, 'J': 2}[instance]
    rows = [r for r in result['series'] if r['id'].startswith(f'jacketed.stage.{stage}.closure.') and r['nombre'].startswith('T__')]
    assert len(rows) == 1, (instance, [r['nombre'] for r in result['series'] if r['id'].startswith(f'jacketed.stage.{stage}.')])
    return np.array(rows[0]['valores'], dtype=float)


def test_steady_needs_the_jacket_holdup_invariant(model):
    """Finding J-6 (not a heat-connection defect): the rigid filled jacket's mass row is identically zero
    (supply = return) and its holdup enters the other rows only through H/m, so the zero-accumulation
    Jacobian has rank n - 2 and Newton stops with a located error. The stationary pair is checked
    instead on the dynamic run's end state against the joint stationary balances (test above).
    When the steady transform projects the holdup invariant (m_j = m_j0), replace this test by the
    comparison with steady_jacketed()."""
    from core.compilador.flowsheet_network import FlowsheetDerivedSystem
    from core.compilador.indexed_steady import IndexedSteadySystem
    from core.solvers.nonlinear import NonlinearError
    dynamic = FlowsheetDerivedSystem(model)
    steady = IndexedSteadySystem(model, dynamic=dynamic)
    J = steady.jacobian(steady.seed)
    zero = [k for k in range(J.shape[0]) if np.max(np.abs(J[k])) == 0.0]
    assert len(zero) == 1 and zero[0] >= dynamic.stages[0].size   # one jacket row: d m_j/dt = coolantFlow - coolantFlow
    assert np.linalg.matrix_rank(J) == J.shape[0] - 2
    with pytest.raises(NonlinearError):
        steady.solve(continuation=False)
