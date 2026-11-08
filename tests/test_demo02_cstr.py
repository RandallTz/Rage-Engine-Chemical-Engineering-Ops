"""Recorded continuous reactor and its indexed train against independent physics."""
import copy
import json
import re
from pathlib import Path

import numpy as np
import pytest

from demo02_cstr import (DEMO, OWNER, author_demo_cstr, frozen_model, train_model, reference_train, sequential_steady_reference,
                         simultaneous_steady_reference, plug_flow_reference)
from core.compilador.derived import DerivedSystem, resolve_system
from core.compilador.indexed_network import IndexedDerivedSystem
from core.compilador.indexed_steady import IndexedSteadySystem
from core.compilador.indexed_publication import dynamic_result, steady_result
from core.modelo.steady_transform import prepare_steady_transform
from core.compilador.steady import SteadySystem, read_result


@pytest.fixture(scope='module')
def source():
    model = frozen_model()
    Path('.tmp').mkdir(exist_ok=True)
    Path('.tmp/cstr-authored-test.json').write_text(json.dumps(model),encoding='utf-8')
    return model


def test_fixture_matches_fresh_shared_authoring(source):
    model,_=author_demo_cstr()
    assert model==source


def test_jacket_publication_follows_the_recorded_heat_law():
    model=frozen_model()
    model['datos'][model['estudio']['tiempoId']]['declaracion']['texto']='1'
    model['estudio']['muestras']=3
    result=dynamic_result(IndexedDerivedSystem(train_model(model,1)))
    assert result['estado']=='resuelto'
    temperature=next(r['valores'] for r in result['series'] if '.closure.' in r['id'] and r['unidadSI']=='K')
    power=next(r['valores'] for r in result['series'] if '.port.jacket.' in r['id'] and r['unidadSI']=='W')
    np.testing.assert_allclose(power,DEMO['UA']*(DEMO['Tj']-np.asarray(temperature)),rtol=1e-12,atol=1e-10)
    assert power[-1]!=power[0]


def test_single_dynamic_and_steady_against_independent_reference(source):
    system = DerivedSystem(source)
    result = resolve_system(system)
    assert result['estado']=='resuelto'
    times = np.asarray(result['ejes'][0]['valores'])
    reference_times=times[times<=6000.]
    reference,temperature = reference_train(reference_times)
    assert reference.success,reference.message
    values = {r['id']:r['valores'] for r in result['series']}
    masses = np.asarray(system.closures[0].molar_masses)
    expected = reference.y.T.copy();expected[:,:4]*=masses
    actual = np.column_stack([values['campo.'+qid] for qid in system.state_ids])
    np.testing.assert_allclose(actual[:len(reference_times)],expected,rtol=3e-6,atol=1e-7)
    closure = system.closures[0]
    np.testing.assert_allclose(values['closure.'+closure.owner+'.'+system.ids[closure.T]][:len(reference_times)],temperature[:,0],rtol=0,atol=3e-4)
    for row in result['verificaciones']:
        if 'conservation' in row['id'] or row['id'].startswith('thermodynamics.closure.'):
            assert row['valor']<=row['tolerancia']
    steady = SteadySystem(prepare_steady_transform(source)['model'])
    solved = steady.solve();read_result(solved)
    stationary = {r['id']:r['valores'] for r in solved['series']}
    root = np.asarray([stationary['steady.'+q] for q in system.state_ids])
    np.testing.assert_allclose(root,actual[-1],rtol=2e-4,atol=1e-7)
    independent = sequential_steady_reference(1)[0]
    np.testing.assert_allclose(root[:4]/masses,independent['amounts'],rtol=3e-6,atol=1e-8)
    assert any(r['id'].startswith('reactions.equilibrium_limit.') for r in solved['verificaciones'])


@pytest.mark.parametrize('count',[1,2,3,5])
def test_indexed_reactor_train_dynamic_steady_and_conversion(source,count):
    model = train_model(source,count)
    dynamic = IndexedDerivedSystem(model)
    if count==1:
        single = DerivedSystem(source)
        np.testing.assert_array_equal(dynamic.initial(),single.initial())
        np.testing.assert_allclose(dynamic.rhs(0.,dynamic.initial()),single.rhs(0.,single.initial()),rtol=1e-14,atol=1e-12)
    transient = dynamic_result(dynamic)
    assert transient['estado']=='resuelto'
    steady = IndexedSteadySystem(model,dynamic=dynamic)
    root,evidence = steady.solve()
    assert evidence['residualNorm']<1e-9
    publication = steady_result(steady)
    assert publication['estado']=='resuelto'
    references = sequential_steady_reference(count)
    conversions = []
    for j,stage in enumerate(dynamic.stages):
        local = root[sum(s.size for s in dynamic.stages[:j]):sum(s.size for s in dynamic.stages[:j+1])]
        amounts = local[:4]/np.asarray(stage.closures[0].molar_masses)
        conversion = 1-2*amounts[0]/sum(amounts)
        conversions.append(conversion)
        np.testing.assert_allclose(amounts,references[j]['amounts'],rtol=3e-6,atol=1e-8)
    assert all(b>a for a,b in zip(conversions,conversions[1:]))
    assert conversions[-1]<plug_flow_reference(count)
    values = {r['id']:r for r in transient['series']}
    stationary = {r['id']:r for r in publication['series']}
    for key,row in stationary.items():
        if key in values and '.state.' in key:
            np.testing.assert_allclose(row['valores'],values[key]['valores'][-1],rtol=3e-4,atol=1e-7)
    for result in (transient,publication):
        for check in result['verificaciones']:
            if 'conservation' in check['id'] or check['id'].startswith('thermodynamics.closure.'):
                assert check['valor']<=check['tolerancia']
    if count in (2,3):
        times = np.asarray(transient['ejes'][0]['valores'])
        times=times[times<=6000.]
        reference,_ = reference_train(times,count)
        assert reference.success,reference.message
        for j,stage in enumerate(dynamic.stages):
            mapping = dynamic.expansion['stages'][j]['provenance']['identityMap']['quantities']
            inverse = {v:k for k,v in mapping.items()}
            for k,qid in enumerate(stage.state_ids):
                actual = values[f'reactorTrain.stage.{j+1}.state.'+inverse[qid]]['valores']
                expected = reference.y[6*j+k]*(stage.closures[0].molar_masses[k] if k<4 else 1.)
                np.testing.assert_allclose(actual[:len(times)],expected,rtol=3e-6,atol=1e-7)


def test_recorded_premises_and_no_equipment_words(source):
    from test_demo02_drum import recorded_texts
    text = recorded_texts(source)
    for word in ('drum', 'valve', 'vent', 'orifice', 'pump', 'tray', 'distillation column'):
        assert re.search(r'\b' + word + r'\b', text) is None, word
    operations = source['motores']['equationWorkbench']['operations']
    # CR-3: the jacket port names the retained heat-rate term; no numeric copy of the conductance law.
    reactor = next(v for v in source['volumenes'] if v['id'] == OWNER)
    assert 'terminos' not in reactor and 'jacket.initialHeat' not in source['datos']
    # CR-4: liquid-only, uniform-pressure and constant-molar-volume premises are recorded on their quantities.
    premises = [op['reason'] for op in operations if op['kind'] == 'declare_domain']
    for start in ('Liquid-only premise', 'Uniform-pressure premise', 'Constant-molar-volume premise'):
        assert sum(reason.startswith(start) for reason in premises) == 1, start
    # CR-1: distributed friction is a recorded premise with its validity bound, and the bound holds for the data.
    friction = next(op for op in operations if op['kind'] == 'declare_relation' and op.get('source') and op['right'] == '0')
    assert friction['source'] == DEMO['friction']['source']
    mu, F = 8e-4, DEMO['feed']
    assert 16 * np.pi * mu * DEMO['length'] / F <= 0.013 * DEMO['loss']
    assert abs(DEMO['loss'] / DEMO['pipeArea']**2 - 8e12) <= 1e-9 * 8e12


def test_simultaneous_reference_reproduces_the_sequential_stage_solution():
    sequential = sequential_steady_reference(3)
    simultaneous = simultaneous_steady_reference(3)
    for a, b in zip(sequential, simultaneous):
        np.testing.assert_allclose(b['amounts'], a['amounts'], rtol=1e-8)
        assert b['residual'] < 1e-7   # scaled rows (component flow / feed, W / 10 UA, kPa)


def test_unequal_stage_pressures_couple_each_discharge_to_the_next_stage(source):
    # Review PR-6/CR-2: stage 2 at +1 kPa. Its pressure is the discharge pressure of stage 1, so the
    # stage-1 holdup rises by A/g * 1 kPa; the exposed last discharge stays at Pout.
    pressures = [101325., 102325.]
    short = copy.deepcopy(source)
    short['datos'][short['estudio']['tiempoId']]['declaracion']['texto'] = '2000.0'
    model = train_model(short, 2, pressures)
    dynamic = IndexedDerivedSystem(model)
    assert [(row['from']['stage'], row['to']['stage']) for row in dynamic.pressure_couplings] == [(1, 2)]
    transient = dynamic_result(dynamic)
    assert transient['estado'] == 'resuelto'
    times = np.asarray(transient['ejes'][0]['valores'])
    reference, _ = reference_train(times, 2, pressures=pressures)
    assert reference.success, reference.message
    values = {r['id']: r['valores'] for r in transient['series']}
    for j, stage in enumerate(dynamic.stages):
        mapping = dynamic.expansion['stages'][j]['provenance']['identityMap']['quantities']
        inverse = {v: k for k, v in mapping.items()}
        for k, qid in enumerate(stage.state_ids):
            actual = values[f'reactorTrain.stage.{j+1}.state.' + inverse[qid]]
            expected = reference.y[6*j+k]*(stage.closures[0].molar_masses[k] if k < 4 else 1.)
            np.testing.assert_allclose(actual, expected, rtol=3e-6, atol=1e-7)
    full = train_model(source, 2, pressures)
    steady = IndexedSteadySystem(full, dynamic=IndexedDerivedSystem(full))
    root, evidence = steady.solve()
    assert evidence['residualNorm'] < 1e-9
    coupled = simultaneous_steady_reference(2, pressures=pressures)
    uniform = simultaneous_steady_reference(2)
    masses = np.asarray(dynamic.stages[0].closures[0].molar_masses)
    holdups = []
    for j, stage in enumerate(steady.dynamic.stages):
        local = root[sum(s.size for s in steady.dynamic.stages[:j]):sum(s.size for s in steady.dynamic.stages[:j+1])]
        np.testing.assert_allclose(local[:4]/masses, coupled[j]['amounts'], rtol=3e-6, atol=1e-8)
        holdups.append(float(local[:4].sum()))
    rise = DEMO['area']/DEMO['g']*(pressures[1]-pressures[0])
    uniform_holdup = float(uniform[0]['amounts'] @ masses)
    # The head balance moves by A/g dP; the loss density changes slightly with the higher conversion.
    assert abs(holdups[0] - uniform_holdup - rise) < 0.1 * rise
    assert coupled[0]['conversion'] > uniform[0]['conversion']
