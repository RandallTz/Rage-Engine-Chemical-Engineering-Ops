"""rage.flowsheet v1: heterogeneous instances, typed connections, lowering and publication.

Network: continuous reactor R1 -> heated liquid drum D1 -> continuous reactor R2
(two recorded templates, three identities, R2 with its own jacket data).

The independent reference is written here: simultaneous component, energy and
outlet-momentum balances of the three vessels, with the liquid caloric route of
core.reactions.PackagePhase (chemical potentials, formation-anchored), solved
with scipy (DOP853 and a simultaneous root). No compiled expression, bridge,
closure runtime or model RHS is used by the reference.

    python -m pytest -q tests/test_flowsheet_network.py
Writes .tmp/flowsheet/{publication,rejections}.json for frontend/verificar_flowsheet_contract.mjs.
"""
import copy
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.modelo import leer_modelo_comun, ErrorModelo  # noqa: E402
from core.modelo.flowsheet import FlowsheetError, expand_flowsheet, read_expansion, source_signature  # noqa: E402
from flowsheet_inputs import chain_data, drum4_model, flowsheet_model, OWNER  # noqa: E402
from demo02_cstr import frozen_model as frozen_reactor  # noqa: E402

OUT = ROOT / '.tmp' / 'flowsheet'
TIMES = {}
NU = np.array([-1., -1., 1., 1.])


def browser_round_trip(value):
    """JSON.parse/JSON.stringify in Node: the spelling a browser client sends back (0.0 -> 0)."""
    script = 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>process.stdout.write(JSON.stringify(JSON.parse(s))))'
    run = subprocess.run(['node', '-e', script], input=json.dumps(value, ensure_ascii=False), capture_output=True,
                         text=True, encoding='utf-8', check=True)
    return json.loads(run.stdout)


@pytest.fixture(scope='module')
def documents():
    started = time.time()
    reactor, drum = frozen_reactor(), drum4_model()
    TIMES['documents'] = time.time() - started
    return reactor, drum


@pytest.fixture(scope='module')
def model(documents):
    return leer_modelo_comun(flowsheet_model(*documents))


# ---------------------------------------------------------------- reference

def reference(documents):
    """Independent physics of the chain from the documents' declared numbers."""
    from demo02_cstr import reference_functions, demo_data
    rows = chain_data(*documents)
    functions = []
    for row in rows:
        data = dict(demo_data(), P=row['P'])
        for key in ('kf', 'kr', 'E', 'Er', 'Tref'):
            if key in row:
                data[key] = row[key]
        functions.append(reference_functions(data))
    _, masses, volumes, enthalpy, temperature, _ = functions[0]
    feed = rows[0]
    z = np.asarray(feed['zF'])
    feed_molar = feed['solve.F'] * z / float(z @ masses)
    feed_energy = feed['solve.F'] * enthalpy(feed['TF'], z) / float(z @ masses)

    def vessel(row, state, rate, inlet, inlet_energy):
        n, H, F = state[:4], state[4], state[5]
        mass = float(n @ masses)
        rho = mass / float(n @ volumes)
        T = temperature(H, n)
        out, out_energy = F * n / mass, F * H / mass
        pressure = row['P'] + mass * row['solve.g'] / row['solve.A']
        loss = row['solve.K'] * F * abs(F) / (2 * rho * row['solve.pipeArea'] ** 2)
        heat = row['UA'] * (row['Tj'] - T) if 'UA' in row else row['Q']
        source = NU * rate(T, n) if rate is not None else 0.
        derivative = [*(inlet - out + source), inlet_energy - out_energy + heat,
                      row['solve.pipeArea'] / row['solve.length'] * (pressure - row['solve.Pout'] - loss)]
        return derivative, out, out_energy, T, heat

    rates = [functions[0][5], None, functions[2][5]]

    def rhs(_, values):
        inlet, energy, result = feed_molar, feed_energy, []
        for row, state, rate in zip(rows, np.asarray(values).reshape(3, 6), rates):
            derivative, inlet, energy, _, _ = vessel(row, state, rate, inlet, energy)
            result.extend(derivative)
        return result

    initial = []
    for row in rows:
        n0 = np.asarray(row['m0']) / masses
        initial.extend([*n0, enthalpy(row['T0'], n0), row['solve.F0']])
    return {'rows': rows, 'masses': masses, 'enthalpy': enthalpy, 'temperature': temperature, 'rhs': rhs,
            'initial': np.asarray(initial), 'vessel': vessel, 'rates': rates, 'feed': (feed_molar, feed_energy)}


def reference_trajectory(ref, times):
    from scipy.integrate import solve_ivp
    solution = solve_ivp(ref['rhs'], (0., float(times[-1])), ref['initial'], method='DOP853', t_eval=times,
                         rtol=2e-10, atol=([1e-11] * 4 + [1e-6, 1e-12]) * 3)
    assert solution.success, solution.message
    return solution


def reference_steady(ref):
    """Stationary balances of each vessel, solved simultaneously in (amounts, T).

    Unknowns per vessel: the four amounts and T, at the outlet flow F. The four
    component balances, the energy balance and the outlet momentum balance are
    solved together (scipy least squares, one redundant row: the mass-weighted
    component sum). The chain has no recycle, so vessels are solved in flow order.
    """
    from scipy.optimize import least_squares
    masses, enthalpy = ref['masses'], ref['enthalpy']
    from demo02_cstr import reference_functions, demo_data
    volumes = reference_functions(demo_data())[2]
    inlet, energy = ref['feed']
    states, temperatures = [], []
    guess_T = ref['rows'][0]['TF']
    for row, rate in zip(ref['rows'], ref['rates']):
        F = float(inlet @ masses)
        z = inlet / inlet.sum()

        def residual(x):
            n, T = x[:4] * 10.0, x[4] * 300.0
            mass = float(n @ masses)
            rho = mass / float(n @ volumes)
            H = enthalpy(T, n)
            heat = row['UA'] * (row['Tj'] - T) if 'UA' in row else row['Q']
            source = NU * rate(T, n) if rate is not None else np.zeros(4)
            pressure = row['P'] + mass * row['solve.g'] / row['solve.A']
            loss = row['solve.K'] * F * F / (2 * rho * row['solve.pipeArea'] ** 2)
            return np.concatenate([(inlet - F * n / mass + source) / 1e-6, [(energy - F * H / mass + heat) / 1e-3,
                                   (pressure - row['solve.Pout'] - loss) / 1e-3]])
        mass0 = row['solve.A'] / row['solve.g'] * row['solve.K'] * F ** 2 / (2 * 900. * row['solve.pipeArea'] ** 2)
        seed = np.concatenate([z * mass0 / float(z @ masses) / 10.0, [guess_T / 300.0]])
        fit = least_squares(residual, seed, method='lm', xtol=1e-15, ftol=1e-15, gtol=1e-15, max_nfev=4000)
        assert np.max(np.abs(residual(fit.x))) < 1e-4, np.max(np.abs(residual(fit.x)))
        n, T = fit.x[:4] * 10.0, fit.x[4] * 300.0
        H = enthalpy(T, n)
        mass = float(n @ masses)
        states.extend([*n, H, F])
        temperatures.append(T)
        inlet, energy, guess_T = F * n / mass, F * H / mass, T
    return np.asarray(states), temperatures


def to_mass_basis(ref, values):
    """Reference amounts (mol) to the compiled state basis (component masses, H, F)."""
    rows = []
    for state in np.asarray(values).reshape(-1, 6):
        rows.append([*(state[:4] * ref['masses']), state[4], state[5]])
    return np.asarray(rows)


# ---------------------------------------------------------------- admission

def test_reader_accepts_and_expands_heterogeneous_instances(model):
    started = time.time()
    expansion, plans = expand_flowsheet(model)
    TIMES['expansion'] = time.time() - started
    stages = expansion['stages']
    assert [s['instanceId'] for s in stages] == ['R1', 'D1', 'R2']
    assert [s['templateRef'] for s in stages] == ['reactor', 'drum', 'reactor']
    assert len({s['model']['id'] for s in stages}) == 3
    assert len(plans) == 3   # R2 data differ from R1: its own effective template
    # Identity is per instance: same template, different namespaces, no shared volume identity.
    volumes = [{v['id'] for v in s['model']['volumenes']} for s in stages]
    assert not (volumes[0] & volumes[2])
    r2 = stages[2]['model']['datos']
    assert r2['jacket.T']['declaracion']['texto'] == '345.0' and stages[0]['model']['datos']['jacket.T']['declaracion']['texto'] == '340.0'
    assert all(s['model']['datos'][s['model']['estudio']['tiempoId']]['declaracion']['texto'] == '20000.0' for s in stages)
    assert [c['id'] for c in expansion['connections']] == ['s1', 's2']
    assert expansion['connections'][0]['from']['stage'] == 1 and expansion['connections'][0]['to']['stage'] == 2
    assert len(expansion['ports']) == 5 and len(expansion['signatures']['instances']) == 3
    read_expansion(json.loads(json.dumps(expansion)), model)
    # Replayed instances keep their signed provenance.
    for stage in stages:
        assert stage['model']['procedencia']['templateInstance']['sourceSignature'] == stage['provenance']['sourceSignature']


def _mutations(documents):
    base = flowsheet_model(*documents)

    def case(name, edit):
        value = copy.deepcopy(base)
        edit(value)
        return name, value
    f = lambda m: m['flowsheet']
    cases = [
        case('version', lambda m: f(m).update(version=2)),
        case('extra field', lambda m: f(m).update(extra=1)),
        case('bad identity', lambda m: f(m)['instances'][0].update(id='R.1')),
        case('shell journal', lambda m: m['motores'].update(materialDerivation=copy.deepcopy(f(m)['templates']['drum']['motores']['materialDerivation']))),
        case('unknown template', lambda m: f(m)['instances'][1].update(template='column')),
        case('duplicate instance', lambda m: f(m)['instances'][2].update(id='R1')),
        case('unmarked template', lambda m: f(m)['templates']['drum']['template'].update(equipment=False)),
        case('nested flowsheet', lambda m: f(m)['templates']['drum'].update(flowsheet={})),
        case('unknown datum', lambda m: f(m)['instances'][2]['data'].update({'jacket.missing': {'texto': '1', 'unidad': 'K'}})),
        case('datum unit', lambda m: f(m)['instances'][2]['data']['jacket.T'].update(unidad='degC')),
        case('datum literal', lambda m: f(m)['instances'][2]['data']['jacket.T'].update(texto='hot')),
        case('instance horizon', lambda m: f(m)['instances'][0]['data'].update({'solve.tf': {'texto': '5', 'unidad': 's'}})),
        case('duplicate connection', lambda m: f(m)['connections'][1].update(id='s1')),
        case('unknown instance', lambda m: f(m)['connections'][0]['to'].update(instance='X9')),
        case('unknown port', lambda m: f(m)['connections'][0]['from'].update(port='bottoms')),
        case('direction', lambda m: f(m)['connections'][0].update({'from': {'instance': 'R1', 'port': 'feed'}})),
        case('kind', lambda m: f(m)['connections'][0].update({'to': {'instance': 'D1', 'port': 'heat'}})),
        case('self connection', lambda m: f(m)['connections'][0].update({'to': {'instance': 'R1', 'port': 'feed'}})),
        case('duplicate port', lambda m: f(m)['exposures'].append({'id': 'again', 'instance': 'R1', 'port': 'product'})),
        case('dangling port', lambda m: f(m)['exposures'].pop()),
        case('duplicate exposure', lambda m: f(m)['exposures'][1].update(id='feed')),
        case('component mismatch', lambda m: f(m)['templates']['drum']['componentes'][3]['identidadQuimica'].update(cas='71-43-2')),
        case('tampered closure', lambda m: f(m)['templates']['drum']['termodinamica']['paquetes'][0]['modelo'].update(version='2')),
        case('undeclared cycle', lambda m: (f(m)['exposures'].pop(0), f(m)['exposures'].pop(),
             f(m)['connections'].append({'id': 's3', 'from': {'instance': 'R2', 'port': 'product'}, 'to': {'instance': 'R1', 'port': 'feed'}}))),
        case('recycle not cycle', lambda m: f(m).update(recycles=['s1'])),
        case('unknown recycle', lambda m: f(m).update(recycles=['s9'])),
        case('layout foreign block', lambda m: m['flowsheetLayout']['blocks'].update(Z9={'position': [0, 0]})),
        case('layout foreign flowsheet', lambda m: m['flowsheetLayout'].update(flowsheetId='other')),
        case('layout point', lambda m: m['flowsheetLayout']['blocks']['R1'].update(position=[0])),
        case('layout without flowsheet', lambda m: m.pop('flowsheet')),
        case('study unit', lambda m: m['datos']['flowsheet.tf']['declaracion'].update(unidad='min')),
        # Non-string references are located, never an unhashable TypeError (review F2).
        case('list endpoint instance', lambda m: f(m)['connections'][0]['from'].update(instance=['R1'])),
        case('object exposure instance', lambda m: f(m)['exposures'][0].update(instance={'id': 'R1'})),
        case('list template reference', lambda m: f(m)['instances'][0].update(template=['reactor'])),
        case('list recycle', lambda m: f(m).update(recycles=[['s1']])),
        # A prototype key is not a declared datum on either reader (review F3).
        case('prototype datum', lambda m: f(m)['instances'][2]['data'].update({'constructor': {'texto': '1', 'unidad': 'K'}})),
    ]
    declared = copy.deepcopy(cases[[n for n, _ in cases].index('undeclared cycle')][1])
    declared['flowsheet']['recycles'] = ['s3']
    return base, cases, declared


def test_rejections_are_located_and_shared_with_the_client(documents):
    base, cases, declared = _mutations(documents)
    expected = {'version': 'flowsheet_version', 'extra field': 'flowsheet_invalid', 'bad identity': 'flowsheet_invalid_identity',
                'shell journal': 'flowsheet_shell', 'unknown template': 'flowsheet_unknown_template',
                'duplicate instance': 'flowsheet_duplicate_instance', 'unmarked template': 'flowsheet_template_unmarked',
                'nested flowsheet': 'flowsheet_nested', 'unknown datum': 'flowsheet_unknown_datum', 'datum unit': 'flowsheet_datum_unit',
                'datum literal': 'flowsheet_invalid_datum', 'instance horizon': 'flowsheet_study',
                'duplicate connection': 'flowsheet_duplicate_connection', 'unknown instance': 'flowsheet_unknown_instance',
                'unknown port': 'flowsheet_unknown_port', 'direction': 'flowsheet_port_direction', 'kind': 'flowsheet_port_kind',
                'self connection': 'flowsheet_self_connection', 'duplicate port': 'flowsheet_port_reused',
                'dangling port': 'flowsheet_dangling_port', 'duplicate exposure': 'flowsheet_duplicate_exposure',
                'component mismatch': 'flowsheet_component_mismatch', 'tampered closure': 'flowsheet_template_invalid',
                'undeclared cycle': 'flowsheet_undeclared_cycle', 'recycle not cycle': 'flowsheet_recycle_not_cycle',
                'unknown recycle': 'flowsheet_unknown_recycle', 'layout foreign block': 'flowsheet_layout_foreign',
                'layout foreign flowsheet': 'flowsheet_layout_foreign', 'layout point': 'flowsheet_layout_invalid',
                'layout without flowsheet': 'flowsheet_layout_foreign', 'study unit': 'flowsheet_study',
                'list endpoint instance': 'flowsheet_unknown_instance', 'object exposure instance': 'flowsheet_unknown_instance',
                'list template reference': 'flowsheet_unknown_template', 'list recycle': 'flowsheet_unknown_recycle',
                'prototype datum': 'flowsheet_unknown_datum'}
    paths = {'list endpoint instance': 'flowsheet.connections.s1.from.instance',
             'object exposure instance': 'flowsheet.exposures[0].instance',
             'list template reference': 'flowsheet.instances[0].template', 'list recycle': 'flowsheet.recycles',
             'prototype datum': 'flowsheet.instances[2].data.constructor',
             'kind': 'flowsheet.connections.s1', 'unknown instance': 'flowsheet.connections.s1.to.instance',
             'duplicate connection': 'flowsheet.connections[1].id'}
    rows = []
    for name, value in cases:
        with pytest.raises(FlowsheetError) as caught:
            leer_modelo_comun(value)
        assert caught.value.code == expected[name], (name, caught.value.diagnostics)
        assert caught.value.diagnostics[0]['path'].startswith(('flowsheet', 'motores', 'estudio')), name
        if name in paths:
            assert caught.value.ruta == paths[name], (name, caught.value.ruta)
        rows.append({'name': name, 'model': value, 'code': caught.value.code, 'path': caught.value.ruta})
    leer_modelo_comun(declared)   # a declared recycle closes the same cycle and is admitted
    # The energy reference enters the same comparison. An edited reference
    # fails the template's own journal check first, so test the identity directly.
    from core.modelo.flowsheet import _thermodynamic_identity
    drum = base['flowsheet']['templates']['drum']
    assert _thermodynamic_identity(drum, 'pipe') == _thermodynamic_identity(base['flowsheet']['templates']['reactor'], 'cell')
    assert _thermodynamic_identity(drum, 'pipe')['formationReference'] == 'liquido'
    edited = copy.deepcopy(drum)
    edited['volumenes'][0]['supuestos']['energia'].pop('referenciaFormacion')
    assert _thermodynamic_identity(edited, 'pipe') != _thermodynamic_identity(drum, 'pipe')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'rejections.json').write_text(json.dumps(rows), encoding='utf-8')
    (OUT / 'accepted.json').write_text(json.dumps({'base': base, 'declaredRecycle': declared}), encoding='utf-8')


def test_persistence_layout_invariance_and_stale_sources(model):
    from core.compilador.flowsheet_network import selection_for, validate_selection
    stored = json.loads(json.dumps(model, ensure_ascii=False))
    assert leer_modelo_comun(stored) == model and source_signature(stored) == source_signature(model)
    selection = selection_for(model, 'steady')
    moved = copy.deepcopy(model)
    moved['flowsheetLayout']['blocks']['D1']['position'] = [220.5, -40]
    moved['flowsheetLayout']['streams'] = {}
    leer_modelo_comun(moved)
    validate_selection(moved, selection)                    # presentation only
    without = copy.deepcopy(model)
    without.pop('flowsheetLayout')
    validate_selection(without, selection)
    for edit in (lambda m: m['flowsheet']['instances'][2]['data']['jacket.T'].update(texto='350.0'),
                 lambda m: m['datos']['flowsheet.tf']['declaracion'].update(texto='100.0'),
                 lambda m: m['flowsheet']['instances'].reverse(),
                 lambda m: m['flowsheet']['templates']['drum']['datos']['solve.Q']['declaracion'].update(texto='30.0')):
        changed = copy.deepcopy(model)
        edit(changed)
        with pytest.raises(FlowsheetError) as caught:
            validate_selection(changed, selection)
        assert caught.value.code == 'stale_flowsheet_execution'
    expansion, _ = expand_flowsheet(model)
    changed = copy.deepcopy(model)
    changed['flowsheet']['instances'][1]['data'] = {'solve.Q': {'texto': '30.0', 'unidad': 'W'}}
    with pytest.raises(FlowsheetError) as caught:
        read_expansion(expansion, changed)
    assert caught.value.code == 'flowsheet_stale_expansion'
    read_expansion(expansion, moved)
    # Review F1: a browser JSON round trip respells numbers (0.0 -> 0). It must
    # keep the selection and the expansion, like the client's invalidatedByEdit.
    from core.compilador.steady import signature
    browser = browser_round_trip(model)
    assert json.dumps(browser, sort_keys=True) != json.dumps(model, sort_keys=True)   # the spelling really differs
    browser['flowsheetLayout']['blocks']['R1']['position'] = [7, 7]
    leer_modelo_comun(browser)
    assert source_signature(browser) == source_signature(model)
    validate_selection(browser, selection)
    validate_selection(browser, browser_round_trip(selection))
    read_expansion(browser_round_trip(expansion), browser)
    from core.modelo.flowsheet import digest
    assert digest(model['flowsheet']) == signature(model['flowsheet'])   # the repository's binary64 canonical form
    browser['flowsheet']['instances'][2]['data']['jacket.T']['texto'] = '350.0'
    with pytest.raises(FlowsheetError) as caught:
        validate_selection(browser, selection)
    assert caught.value.code == 'stale_flowsheet_execution'


def test_pressure_rule_rejects_unequal_connected_pressures(documents):
    from core.compilador.flowsheet_network import FlowsheetDerivedSystem
    from core.compilador.derived_graph import LoweringError
    value = flowsheet_model(*documents)
    value['flowsheet']['instances'][1]['data'] = {OWNER + '.pressure': {'texto': '200000.0', 'unidad': 'Pa'}}
    with pytest.raises(LoweringError) as caught:
        FlowsheetDerivedSystem(leer_modelo_comun(value))
    assert caught.value.diagnostics[0]['code'] == 'index_network_pressure_mismatch'
    assert caught.value.diagnostics[0]['path'] == 'flowsheet.connections.s1'


# ---------------------------------------------------------------- execution

def _stage_values(result, stage, count):
    series = {row['id']: row for row in result['series']}
    keys = result['indexedNetwork']['stages'][stage]['seriesIds'][:count]
    return np.asarray([series[k]['valores'] for k in keys])


def _temperature(result, stage):
    series = {row['id']: row for row in result['series']}
    keys = [k for k in result['indexedNetwork']['stages'][stage]['seriesIds'] if '.closure.' in k and series[k]['nombre'].startswith('T__')]
    assert len(keys) == 1
    return np.asarray(series[keys[0]]['valores'])


def _port(result, port_id):
    ports = result['indexedNetwork']['endPorts'] + result['indexedNetwork']['sidePorts']
    series = {row['id']: row for row in result['series']}
    port = next(p for p in ports if p['portId'] == port_id)
    get = lambda key: np.asarray(series[key]['valores'], dtype=float)
    return {role: ([get(k) for k in key] if role == 'composition' else get(key)) for role, key in port['variables'].items()}


ELEMENTS = np.array([[2, 2, 4, 0], [6, 4, 8, 2], [1, 2, 2, 1]], dtype=float)


def _global_checks(result, ref):
    """Exposed-port element and energy budgets at the stationary point."""
    masses = ref['masses']
    ports = {p['portId'] for p in result['indexedNetwork']['endPorts'] + result['indexedNetwork']['sidePorts']}
    assert ports == {'feed', 'jacket1', 'heater', 'jacket2', 'product'}
    out = _port(result, 'product')
    flow = float(np.atleast_1d(out['flow'])[-1])
    fractions = np.asarray([float(np.atleast_1d(c)[-1]) for c in out['composition']])
    feed_molar, feed_energy = ref['feed']
    out_molar = flow * fractions / masses
    elements_in, elements_out = ELEMENTS @ feed_molar, ELEMENTS @ out_molar
    assert np.max(np.abs(elements_out - elements_in) / elements_in) < 1e-8
    assert abs(flow - float(feed_molar @ masses)) / flow < 1e-9
    heat = sum(float(np.atleast_1d(_port(result, key)['power'])[-1]) for key in ('jacket1', 'heater', 'jacket2'))
    enthalpy = float(np.atleast_1d(out['specificEnthalpy'])[-1]) * flow
    assert abs(feed_energy + heat - enthalpy) / abs(enthalpy) < 1e-7
    return {'elements': float(np.max(np.abs(elements_out - elements_in) / elements_in)),
            'energy': abs(feed_energy + heat - enthalpy) / abs(enthalpy)}


def test_steady_network_matches_simultaneous_reference(model, documents):
    from core.compilador.flowsheet_network import prepare, resolve, selection_for, read_result
    started = time.time()
    selection = selection_for(model, 'steady')
    result = resolve(model, selection)
    TIMES['steady'] = time.time() - started
    assert result['estado'] == 'resuelto' and result['procedencia']['motor'] == 'rage.compilador.flowsheet_network'
    assert all(row['valor'] <= row['tolerancia'] for row in result['verificaciones'] if not row['id'].startswith('reactions.'))
    ref = reference(documents)
    started = time.time()
    root, temperatures = reference_steady(ref)
    TIMES['steadyReferenceSeconds'] = time.time() - started
    expected = to_mass_basis(ref, root)
    for j in range(3):
        actual = _stage_values(result, j, 6).reshape(-1)
        np.testing.assert_allclose(actual, expected[j], rtol=2e-7, atol=1e-10)
        T = float(np.atleast_1d(_temperature(result, j))[0])
        assert abs(T - temperatures[j]) < 1e-5
    checks = _global_checks(result, ref)
    stored = json.loads(json.dumps(result))
    read_result(stored, selection)
    browser = browser_round_trip(stored)        # review F1: a result stored by the client
    assert json.dumps(browser, sort_keys=True) != json.dumps(stored, sort_keys=True)
    read_result(browser, browser_round_trip(selection))
    tampered = copy.deepcopy(stored)
    tampered['series'][0]['valores'] = 1.0 + float(np.atleast_1d(tampered['series'][0]['valores'])[0])
    with pytest.raises(FlowsheetError):
        read_result(tampered, selection)
    conversions = [1 - root[6 * j] / (root[6 * j] + root[6 * j + 2]) for j in (0, 2)]
    TIMES['steadyReference'] = {'conversionR1': conversions[0], 'conversionR2': conversions[1],
                                'temperatures': temperatures,
                                'globalChecks': checks}
    assert conversions[1] > conversions[0]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'steady-result.json').write_text(json.dumps({'source': model, 'selection': selection, 'result': stored}), encoding='utf-8')


def test_dynamic_network_matches_independent_integration(model, documents):
    from core.compilador.flowsheet_network import resolve, selection_for
    started = time.time()
    selection = selection_for(model, 'dynamic')
    result = resolve(model, selection)
    TIMES['dynamic'] = time.time() - started
    assert result['estado'] == 'resuelto'
    conservation = [row for row in result['verificaciones'] if '.conservation.' in row['id']]
    assert len(conservation) == 3 and all(row['valor'] <= 1e-9 for row in conservation)
    times = np.asarray(next(a for a in result['ejes'] if a['id'] == 't')['valores'])
    ref = reference(documents)
    solution = reference_trajectory(ref, times)
    errors = []
    for j in range(3):
        actual = _stage_values(result, j, 6).T
        expected = np.asarray([to_mass_basis(ref, y)[j] for y in solution.y.T])
        scale = np.maximum(np.max(np.abs(expected), axis=0), 1e-12)
        errors.append(float(np.max(np.abs(actual - expected) / scale)))
        temperatures = _temperature(result, j)
        reference_t = [ref['temperature'](y[6 * j + 4], y[6 * j:6 * j + 4]) for y in solution.y.T]
        assert np.max(np.abs(temperatures - reference_t)) < 2e-4
    assert max(errors) < 2e-6, errors
    TIMES['dynamicMaxRelativeError'] = errors
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'dynamic-result.json').write_text(json.dumps({'source': model, 'selection': selection, 'result': json.loads(json.dumps(result))}), encoding='utf-8')


def test_http_routes_and_guards(model):
    import asyncio
    import httpx
    from backend.main import app

    class Client:
        """In-process ASGI transport; no socket or server process."""
        def post(self, route, json):
            async def send():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    return await client.post(route, json=json)
            return asyncio.run(send())
    client = Client()
    response = client.post('/modelo/flowsheet-expansion', json={'format': 'rage.flowsheet-expansion.request', 'version': 1, 'model': model})
    assert response.status_code == 200 and response.json()['count'] == 3
    bad = copy.deepcopy(model)
    bad['flowsheet']['exposures'].pop()
    response = client.post('/modelo/flowsheet-expansion', json={'format': 'rage.flowsheet-expansion.request', 'version': 1, 'model': bad})
    assert response.status_code == 422
    assert response.json()['detail']['diagnostics'][0]['code'] == 'flowsheet_dangling_port'
    for route in ('/modelo/resolver', '/modelo/compilation'):
        response = client.post(route, json={'modelo': model})
        assert response.status_code == 422 and response.json()['detail']['diagnostics'][0]['code'] == 'flowsheet_not_lowered'
    from core.compilador.flowsheet_network import selection_for
    stale = selection_for(model, 'steady')
    changed = copy.deepcopy(model)
    changed['flowsheet']['instances'][2]['data']['jacket.T']['texto'] = '350.0'
    response = client.post('/modelo/resolver', json={'modelo': changed, 'flowsheetExecution': stale})
    assert response.status_code == 422 and response.json()['detail']['diagnostics'][0]['code'] == 'stale_flowsheet_execution'
    response = client.post('/modelo/steady-transform', json={'format': 'rage.steady-transform.request', 'version': 1, 'model': model})
    assert response.status_code == 422 and response.json()['detail']['diagnostics'][0]['code'] == 'flowsheet_not_lowered'


def test_zz_record_timings():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'timings.json').write_text(json.dumps(TIMES, indent=1, default=float), encoding='utf-8')
    print(json.dumps(TIMES, default=float))
