"""rage.flowsheet heat connection (F4, J-2; optional `heat` key on a v1 connection): the jacketed reactor assembled from two instances.

R (`duty-cstr`, prescribed boundary duty) and J (`jacket-service`, recorded wall
law with an exterior temperature datum) are joined by one heat connection.
The assembly replaces J's exterior temperature by R's temperature and R's duty
datum by minus J's resolved boundary heat (one duty, equal and opposite).

Independent references (no compiled expression, bridge or model RHS):
- the LSODA integration of the jacketed reactor, tests/jacketed_reactor_inputs.reference_jacketed,
  the reference the accepted single-document jacketed reactor matches (5.1e-7 K);
- the stationary balances of both volumes solved together (steady_jacketed, hybr, residual <= 1e-8), compared with
  the end of the 60000 s run and with the connected steady mode (the jacket holdup projected as an exact invariant, J-6).

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
    case('premise kind', lambda m: m['flowsheet']['templates']['jacket']['template']['momentumPremise'].update(kind='pumped'))
    case('premise reason', lambda m: m['flowsheet']['templates']['jacket']['template']['momentumPremise'].update(reason=' '))
    case('premise field', lambda m: m['flowsheet']['templates']['jacket']['template']['momentumPremise'].update(extra=1))
    case('premise null', lambda m: m['flowsheet']['templates']['jacket']['template'].update(momentumPremise=None))   # review J1R-1
    case('premise with momentum', lambda m: m['flowsheet']['templates']['jacket']['volumenes'][0]['balances'].update(momento=True))
    case('no premise, no momentum', lambda m: m['flowsheet']['templates']['jacket']['template'].pop('momentumPremise'))
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
                'premise kind': ('flowsheet_template_invalid', 'flowsheet.templates.jacket.template.momentumPremise.kind'),
                'premise reason': ('flowsheet_template_invalid', 'flowsheet.templates.jacket.template.momentumPremise.reason'),
                'premise field': ('flowsheet_template_invalid', 'flowsheet.templates.jacket.template.momentumPremise'),
                'premise null': ('flowsheet_template_invalid', 'flowsheet.templates.jacket.template.momentumPremise'),
                'premise with momentum': ('flowsheet_template_invalid', 'flowsheet.templates.jacket.template.momentumPremise'),
                'no premise, no momentum': ('flowsheet_template_invalid', 'flowsheet.templates.jacket.template.recipe.journals'),
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
    # T0 = Tj0 makes the check above 0 = 0 (review J2R-2): repeat it where the temperatures differ, with
    # both temperatures from the independent package functions of the LSODA reference (no engine closure).
    import demo02_cstr
    from jacketed_reactor_inputs import water_enthalpy_functions
    masses, temperature = demo02_cstr.reference_functions(data)[1], demo02_cstr.reference_functions(data)[4]
    Tj_of = water_enthalpy_functions(data['Pj'])[1]
    j = system.offsets[1]
    for k, factor in ((0, 1.002), (4, 0.998), (j, 1.002), (j + 1, 0.998)):
        y = np.array(system.initial(), dtype=float); y[k] *= factor
        values = dict(zip(system.variables, y)); values.update(zip(system.outputs, system.closure_values(0.0, y)))
        expected = data['UA'] * (temperature(y[4], y[:4] / masses) - Tj_of(y[j + 1] / y[j]))
        assert abs(expected) > 5.0
        assert float(duty.xreplace(values)) == pytest.approx(expected, rel=1e-6)


def test_dynamic_two_instances_match_the_jacketed_reference(dynamic):
    times = np.array(dynamic['ejes'][0]['valores'])
    sol, T_ref, Tj_ref = reference_jacketed(times)
    T, Tj = _find(dynamic, 'R'), _find(dynamic, 'J')
    assert np.max(np.abs(T - T_ref)) < 1e-5
    assert np.max(np.abs(Tj - Tj_ref)) < 1e-5
    report = dynamic['procedencia']['flowsheetCompilation']
    assert report['version'] == 2 and report['heatCouplings'][0]['connectionId'] == 'wall'
    steady = steady_jacketed()
    assert abs(T[-1] - steady['temperature']) < 1e-5
    assert abs(Tj[-1] - steady['jacketTemperature']) < 1e-5


def test_compilation_rows_name_their_kind(dynamic):
    """J2R-4: a heat row without its coupling is rejected structurally, even when re-signed."""
    from core.compilador.flowsheet_network import read_compilation
    from core.modelo.flowsheet import digest
    report = copy.deepcopy(dynamic['procedencia']['flowsheetCompilation'])
    assert [(row['id'], row['kind']) for row in report['connections']] == [('wall', 'heat')]

    def signed(value):
        value = copy.deepcopy(value)
        value.pop('signature')
        value['signature'] = digest(value)
        return value
    read_compilation(signed(report))
    for mutate in (lambda r: r.update(heatCouplings=[]), lambda r: r.pop('heatCouplings'),
                   lambda r: r['connections'][0].update(kind='material'), lambda r: r['connections'][0].pop('kind')):
        bad = copy.deepcopy(report)
        mutate(bad)
        with pytest.raises(FlowsheetError) as caught:
            read_compilation(signed(bad))
        assert caught.value.code == 'invalid_flowsheet_compilation'
    # A version 1 compilation (rows without kind) is still read.
    legacy = copy.deepcopy(report)
    legacy['version'] = 1
    for row in legacy['connections']:
        row.pop('kind')
    read_compilation(signed(legacy))


def _find(result, instance):
    """The published closure temperature of the instance's package volume (stage 1 = R, stage 2 = J)."""
    stage = {'R': 1, 'J': 2}[instance]
    rows = [r for r in result['series'] if r['id'].startswith(f'jacketed.stage.{stage}.closure.') and r['nombre'].startswith('T__')]
    assert len(rows) == 1, (instance, [r['nombre'] for r in result['series'] if r['id'].startswith(f'jacketed.stage.{stage}.')])
    return np.atleast_1d(np.array(rows[0]['valores'], dtype=float))   # a steady series is one value


def test_jacket_holdup_is_an_exact_invariant_of_the_connected_rates(model):
    """J-6: with the single-species phase molar mass substituted (M_L = M_1 x_1), the jacket mass rate is identically
    zero in the connected system, so the connected steady path projects the holdup m_j = m_j0 out."""
    import sympy as sp
    from core.compilador.flowsheet_network import FlowsheetDerivedSystem
    from core.compilador.indexed_steady import IndexedSteadySystem
    dynamic = FlowsheetDerivedSystem(model)
    jacket = dynamic.stages[1]
    mass = dynamic.offsets[1] + [str(q) for q in jacket.states].index(next(str(q) for q in jacket.states if str(q).startswith('m__')))
    assert sp.cancel(dynamic.expressions[mass]) == 0
    steady = IndexedSteadySystem(model, dynamic=dynamic)
    assert mass not in steady.indices and len(steady.indices) == dynamic.stages[0].size + jacket.size - 1
    [record] = steady.invariant_records
    assert record['stage'] == 2 and record['value'] == pytest.approx(jacketed_data()['mj0'], rel=1e-12)


def test_steady_two_instances_match_the_joint_stationary_balances(model):
    from core.compilador.flowsheet_network import resolve, selection_for
    selection = selection_for(model, 'steady')
    result = resolve(model, selection)
    (OUT / 'steady-result.json').write_text(json.dumps({'result': result, 'selection': selection}), encoding='utf-8')
    steady = steady_jacketed()
    assert abs(_find(result, 'R')[-1] - steady['temperature']) < 1e-6
    assert abs(_find(result, 'J')[-1] - steady['jacketTemperature']) < 1e-6
    report = result['procedencia']['flowsheetCompilation']
    assert report['version'] == 2 and report['heatCouplings'][0]['connectionId'] == 'wall'


def test_momentum_premise_admits_the_jacket_without_a_momentum_balance(documents):
    """J-1: the jacket template records the prescribed-flow premise instead of a hydrostatic momentum journal."""
    from flowsheet_heat_inputs import MOMENTUM_PREMISE
    _, jacket = documents
    assert jacket['template']['momentumPremise'] == MOMENTUM_PREMISE
    assert all(v['balances'].get('momento') is not True for v in jacket['volumenes'])
    assert 'momentumDerivation' not in jacket['template']['recipe']['journals']
    leer_modelo_comun(jacket)
