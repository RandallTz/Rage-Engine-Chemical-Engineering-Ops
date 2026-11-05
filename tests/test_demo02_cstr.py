"""Recorded continuous reactor and its indexed train against independent physics."""
import json
from pathlib import Path

import numpy as np
import pytest

from demo02_cstr import DEMO, author_demo_cstr, frozen_model, train_model, reference_train, sequential_steady_reference, plug_flow_reference
from core.compilador.derived import DerivedSystem, resolve_system
from core.compilador.indexed_network import IndexedDerivedSystem
from core.compilador.indexed_steady import IndexedSteadySystem
from core.compilador.indexed_publication import dynamic_result, steady_result
from core.modelo.steady_transform import prepare_steady_transform
from core.compilador.steady import SteadySystem, read_result


@pytest.fixture(scope='module')
def source():
    model = frozen_model()
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
