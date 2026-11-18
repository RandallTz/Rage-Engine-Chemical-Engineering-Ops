"""Demo 0.3 C8: the controlled CSTR, its derivation audit, its documents and the section 4 acceptance tiers.

The model is recorded by `tests/demo03_cstr_control.py` through shared operations only and run through the C7
run session with scheduled actions. References are independent of the engine:

* Independent numerical tier: `ClosedLoopReference.run`, LSODA on the Demo 0.2 reference functions with the
  loop written from the design table (no compiled expression). Temperature within 1e-3 K.
* Linear tier: the matrix exponential of that reference's 8-state Jacobian at the start, for a 0.1 K set-point
  step. Temperature deviation within 5e-4 of the step.

The exact analytic tier of section 4 (constant-capacity M1 plant) is C3's `tests/test_control_loop.py`.
"""
import copy
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pytest
import sympy as sp

import demo03_cstr_control as demo
from control_loop import SIGNAL
from core.compilador.derived import source_signature
from core.compilador.run_session import SessionStore
from core.modelo.equation_workbench import build
from demo02_cstr import frozen_model

ROOT = Path(__file__).resolve().parents[1]
SHARED = {'declare_symbol', 'declare_function', 'declare_relation', 'declare_rate', 'apply_zero', 'substitute'}
TEMPERATURE_ID = 'xe19bda88c1'
RESULTS = {}


@pytest.fixture(scope='module')
def authored():
    model, info = demo.controlled_model()
    return model, info


def run_case(model, case):
    """The scheduled case through the C7 run session, run to the horizon; the published result."""
    if case not in RESULTS:
        session = SessionStore().start(copy.deepcopy(model), demo.published_schedules()[case], background=False)
        assert session.state == 'ready', session.error
        answer = session.advance(0, demo.HORIZON)
        assert answer['finished'] and session.state == 'finished', session.error
        RESULTS[case] = session.result
    return RESULTS[case]


def temperature(result):
    times = np.asarray(result['ejes'][0]['valores'], dtype=float)
    values = next(row['valores'] for row in result['series'] if row['id'] == 'closure.cell.' + TEMPERATURE_ID)
    return times, np.asarray(values, dtype=float)


def compared(model, case):
    result = run_case(model, case)
    assert result['estado'] == 'resuelto'
    times, actual = temperature(result)
    reference = demo.ClosedLoopReference(_start(model))
    expected, valve, _, crossings = reference.run(times, demo.published_schedules()[case])
    return result, times, actual, expected, valve, crossings


def _start(model):
    data = model['datos']
    return {'masses': [float(data[k]['declaracion']['texto']) for k in ('cell.mass', 'cell.mass2', 'cell.mass3', 'cell.mass4')],
            'temperature': float(data['cell.temperature']['declaracion']['texto']),
            'flow': float(data['solve.F0']['declaracion']['texto'])}


# Documents ------------------------------------------------------------------------------------------------------

def test_published_documents_equal_fresh_authoring_byte_for_byte(authored):
    model, info = authored
    texts = demo.documents(model, info)
    for path, text in texts.items():
        assert path.read_bytes() == text.encode('utf-8'), path
    assert demo.published_model() == model


def test_start_is_the_independent_steady_state(authored):
    model, info = authored
    fresh = demo.steady_start()
    assert info['start'] == fresh == _start(model)
    reference = demo.ClosedLoopReference(fresh)
    rates = reference.rhs(reference.initial, reference.inputs)
    # Ten significant digits of the start leave component rates of about 2e-12 mol/s (2e-10 of the feed), an energy
    # rate of about 1e-7 W and a sensor rate of about 4e-10 K/s; the integral rate is exactly zero.
    assert np.max(np.abs(rates[:4])) < 1e-10 and abs(rates[4]) < 1e-5 and abs(rates[6]) < 1e-8 and rates[7] == 0, rates


# Derivation audit -----------------------------------------------------------------------------------------------

def test_history_is_the_demo02_history_plus_shared_operations(authored):
    model, info = authored
    frozen = frozen_model()['motores']['equationWorkbench']['operations']
    operations = model['motores']['equationWorkbench']['operations']
    strip = lambda op: {k: v for k, v in op.items() if k != 'sourceSignatures'}
    changed = []
    for old, new in zip(frozen, operations):
        if strip(old) != strip(new):
            # The only edits of the recorded plant: two constants become quantities of time.
            assert (old['kind'], new['kind'], old['name']) == ('declare_symbol', 'declare_function', new['name'])
            assert new['dependencies'] == [info['time']] and {k: v for k, v in strip(new).items() if k not in ('kind', 'dependencies')} == \
                {k: v for k, v in strip(old).items() if k != 'kind'}
            changed.append(new['name'])
    assert sorted(changed) == ['feedRate', 'jacketTemperature']
    appended = operations[len(frozen):]
    assert {op['kind'] for op in appended} <= SHARED
    # Every operation on input equations is pinned to the signatures its replay calculated; declarations take none.
    assert all(bool(op.get('sourceSignatures')) == ('sources' in op) for op in appended)
    assert sum('sources' in op for op in appended) == 2   # the valve substitution and the PI reduction
    rows, names = info['rows'], info['names']
    by_id = {'operation.' + str(i): op for i, op in enumerate(operations, 1)}
    for key in ('measurementJoin', 'sensor', 'error', 'integral', 'filter', 'derivative', 'law', 'limits', 'actuator', 'noDerivative'):
        assert by_id[rows[key]]['family'] == SIGNAL, key
    assert by_id[rows['valve']]['family'] == by_id[rows['energy']]['family'] == 'energy'
    assert by_id[rows['valve']]['reason'] == demo.VALVE_REASON
    assert by_id[rows['noDerivative']] == {**by_id[rows['noDerivative']], 'kind': 'apply_zero', 'symbol': names['derivativeTime']}


def test_selected_rows_are_replayed_deductions_from_the_fundamental_laws(authored):
    model, info = authored
    replayed = build(model)
    selection = model['motores']['derivedExecution']
    assert selection['sourceSignature'] == source_signature(model, replayed)
    graph, q = replayed.graph, replayed.introduced
    rows, names = info['rows'], info['names']
    for row in selection['states'] + selection['reconstructions']:
        assert row['equationId'] in graph.nodes, row
    # The selected energy row is the recorded first law with the jacket conductance law and the valve substituted.
    energy = graph.nodes[rows['energy']].equation
    assert any(row['equationId'] == rows['energy'] for row in selection['states'])
    assert energy.has(q[names['actuator']]) and not energy.has(q['jacketTemperature'])
    ancestry, frontier = set(), [rows['energy']]
    while frontier:
        key = frontier.pop()
        if key not in ancestry:
            ancestry.add(key)
            frontier += [i for i in graph.nodes[key].inputs if i in graph.nodes]
    assert any(key.startswith('energy.' + demo.OWNER + '.') for key in ancestry), sorted(ancestry)
    # Loop rows: typed as C3 records them; the PI reduction zeroes the derivative action.
    t = sp.Symbol('t', real=True)
    assert graph.nodes[rows['integral']].equation.lhs == sp.Derivative(q[names['integral']], t)
    assert graph.nodes[rows['noDerivative']].equation == sp.Eq(q[names['derivativeAction']], 0)
    assert graph.nodes[rows['measurementJoin']].equation.rhs == sp.Function('T__' + demo.OWNER)(t)
    # Solve: the set point and the feed rate are held time inputs; nothing else changes during a run.
    assert set(selection['timeInputs']) == {names['setpoint'], info['feed']}
    assert 'jacket.T' not in model['datos']


def test_recorded_premises_and_no_equipment_words(authored):
    from test_demo02_drum import recorded_texts
    model, _ = authored
    operations = model['motores']['equationWorkbench']['operations']
    premises = [op['reason'] for op in operations if op['kind'] == 'declare_domain']
    for start in ('Liquid-only premise', 'Uniform-pressure premise', 'Constant-molar-volume premise'):
        assert sum(reason.startswith(start) for reason in premises) == 1, start
    text = recorded_texts(model).replace(demo.VALVE_REASON, '')
    for word in ('drum', 'vent', 'orifice', 'pump', 'tray', 'distillation column'):
        assert re.search(r'\b' + word + r'\b', text) is None, word


AUDIT = r"""
import fs from 'node:fs';import path from 'node:path';import ts from 'typescript';import {createRequire} from 'node:module';
const directory=process.cwd(),require=createRequire(path.join(directory,'package.json')),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.css'))return {default:{}};
  if(file.endsWith('.json'))return {__esModule:true,default:JSON.parse(fs.readFileSync(file,'utf8'))};
  if(cache.has(file))return cache.get(file).exports;
  const loaded={exports:{}};cache.set(file,loaded);
  const source=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('exports','module','require','process',source)(loaded.exports,loaded,id=>id==='next/navigation'?{useRouter:()=>({push(){},replace(){}})}:id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id),{env:{}});
  return loaded.exports;
}
const document=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
const {leerModeloComun}=load(path.join(directory,'motores/modelo/lector'));
const {auditModelDerivation}=load(path.join(directory,'app/models/modelDerivationAudit'));
const read=leerModeloComun(document.model.commonModel)===document.model.commonModel;
console.log(JSON.stringify({format:document.format,read,audit:auditModelDerivation(document.model)}));
"""


def test_published_model_passes_the_frontend_reader_and_the_derivation_audit():
    out = subprocess.run(['node', '--input-type=module', '-e', AUDIT, str(demo.MODEL_FILE)], cwd=ROOT / 'frontend',
                         capture_output=True, text=True, encoding='utf-8')
    assert out.returncode == 0, out.stderr
    verdict = json.loads(out.stdout.strip().splitlines()[-1])
    assert verdict['format'] == 'rage.model-file' and verdict['read'], verdict
    assert verdict['audit']['status'] == 'recorded' and not verdict['audit']['findings'], verdict['audit']
    assert verdict['audit']['recordedSteps'] > 0


def test_no_product_library_import():
    names = ('demo-0.3', 'demo03', 'controlled-reactor')
    for folder in ('frontend/app', 'frontend/motores'):
        for path in (ROOT / folder).rglob('*'):
            if path.suffix in ('.ts', '.tsx', '.js', '.mjs', '.json') and path.is_file():
                text = path.read_text(encoding='utf-8', errors='replace')
                assert not any(name in text for name in names), path


# Section 4 tiers ------------------------------------------------------------------------------------------------

def test_setpoint_then_feed_against_the_independent_reference(authored):
    model, info = authored
    result, times, actual, expected, valve, crossings = compared(model, 'setpointThenFeed')
    timeline = result['procedencia']['runTimeline']
    assert [(a['t'], a['quantityId']) for a in timeline['actions']] == [
        (demo.SETPOINT_TIME, info['names']['setpoint']), (demo.FEED_TIME, info['feed'])]
    assert timeline['termination']['reason'] == 'completed'
    error = float(np.max(np.abs(actual - expected)))
    assert error <= 1e-3, error
    assert crossings == [] and not any(e['codigo'] == 'regime_change' for e in result['eventos'])
    assert np.all((valve > 0) & (valve < 1))
    assert float(np.max(actual)) < demo.LIQUID_LIMIT
    target = _start(model)['temperature'] + demo.SETPOINT_STEP
    late = (times > demo.FEED_TIME - 200) & (times <= demo.FEED_TIME)
    assert float(np.max(np.abs(actual[late] - target))) < 1e-2   # settled before the feed step
    print(f'\nC8 set point then feed: max |T - reference| {error:.3g} K; feed-step dip '
          f'{float(np.min(actual[times >= demo.FEED_TIME] - target)):.4g} K', flush=True)


def test_saturating_setpoint_against_the_independent_reference(authored):
    model, _ = authored
    result, times, actual, expected, valve, crossings = compared(model, 'saturatingSetpoint')
    error = float(np.max(np.abs(actual - expected)))
    assert error <= 1e-3, error
    exits = [e['valor'] for e in result['eventos'] if e['codigo'] == 'regime_change']
    # One located exit from the upper limit (the entry is the action itself, a re-baselined restart, C6).
    assert len(exits) == len(crossings) == 1
    assert abs(exits[0] - crossings[0]) <= 1e-2, (exits, crossings)
    saturated = float(np.mean(valve >= 1))
    assert 0.05 < saturated < 0.15, saturated
    assert float(np.max(actual)) < demo.LIQUID_LIMIT
    print(f'\nC8 saturating set point: max |T - reference| {error:.3g} K; exit {exits[0]:.6f} s against '
          f'{crossings[0]:.6f} s; saturated {saturated:.3f} of samples; highest T {float(np.max(actual)):.4f} K', flush=True)


def test_small_step_against_the_linearized_closed_loop(authored):
    model, _ = authored
    result, times, actual, expected, _, _ = compared(model, 'smallSetpoint')
    start = _start(model)
    deviation, eigenvalues = demo.ClosedLoopReference(start).linear_setpoint_response(times, demo.SMALL_STEP, demo.SETPOINT_TIME)
    assert np.all(eigenvalues.real < 0) and len(eigenvalues) == 8
    fraction = float(np.max(np.abs(actual - start['temperature'] - deviation))) / demo.SMALL_STEP
    assert fraction <= 5e-4, fraction
    assert float(np.max(np.abs(actual - expected))) <= 1e-3
    print(f'\nC8 linear tier: |T - T0 - linear| / step {fraction:.3g}', flush=True)
