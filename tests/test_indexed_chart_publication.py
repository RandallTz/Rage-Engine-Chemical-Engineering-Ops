"""Generate connected network results for the shared chart presentation verifier."""
import copy
import functools
import json
import subprocess

import pytest
from pathlib import Path

from core.compilador.indexed_network import IndexedDerivedSystem
from core.compilador.indexed_publication import dynamic_result, steady_result
from core.compilador.indexed_steady import IndexedSteadySystem
from core.resultados import leer_resultados
from test_index_sets import source_model


@functools.lru_cache(maxsize=None)
def publications(stages):
    model = source_model()
    model['datos']['solve.stageCount']['declaracion']['texto'] = str(stages)
    for document in [model, *model['indexSet']['templates'].values()]:
        document['datos'][document['estudio']['tiempoId']]['declaracion']['texto'] = '1'
        document['estudio']['metodoSolicitado'] = 'bdf'
        document['estudio']['muestras'] = 3
    system = IndexedDerivedSystem(model)
    return {'dynamic': dynamic_result(system),
            'steady': steady_result(IndexedSteadySystem(model, dynamic=system))}


def test_fresh_network_chart_publications(tmp_path):
    results = publications(2)
    for result in results.values():
        assert leer_resultados(result) == result
        network = result['indexedNetwork']
        assert network['version'] == 3
        assert {d['seriesId'] for d in network['display']} == {k for s in network['stages'] for k in s['seriesIds']} | {p['seriesId'] for p in network['profiles']}
        assert all('__' not in d['label'] and 'volume_' not in d['label'] and '(t)' not in d['label'] for d in network['display'])
    path = tmp_path / 'results.json'
    path.write_text(json.dumps(results), encoding='utf-8')
    subprocess.run(['node', 'frontend/motores/resultados/verificar_indexed_charts.mjs', str(path)], check=True)


def test_defaults_do_not_depend_on_the_stage_count(tmp_path):
    for count in (3,):
        results = publications(count)
        for result in results.values():
            assert leer_resultados(result) == result and result['indexedNetwork']['count'] == count
        path = tmp_path / f'results-{count}.json'
        path.write_text(json.dumps(results), encoding='utf-8')
        subprocess.run(['node', 'frontend/motores/resultados/verificar_indexed_charts.mjs', str(path)], check=True)


def test_partial_profile_for_a_quantity_of_only_some_stages():
    steady = copy.deepcopy(publications(2)['steady'])
    profile = steady['indexedNetwork']['profiles'][0]
    row = next(r for r in steady['series'] if r['id'] == profile['seriesId'])
    profile['stageSeriesIds'][0] = None
    row['valores'][0] = None
    assert leer_resultados(steady)['indexedNetwork']['profiles'][0]['stageSeriesIds'][0] is None
    row['valores'][0] = 1.0
    with pytest.raises(Exception):
        leer_resultados(steady)


def test_boundary_ports_share_a_group_and_a_steady_profile_across_stages():
    """D-2: a boundary quantity is one group over the stages that publish it, named by the template port identity."""
    results = publications(3)
    for mode, result in results.items():
        network = result['indexedNetwork']
        display = {d['seriesId']: d for d in network['display']}
        port_series = {v for p in network['endPorts'] + network['sidePorts']
                       for variable in p['variables'].values() for v in (variable if isinstance(variable, list) else [variable])}
        assert port_series and all(display[k]['rank'] == 8 and display[k]['label'].startswith('Port ') for k in port_series)
        by_group = {}
        for key in port_series:
            by_group.setdefault(display[key]['group'], []).append(key)
        assert any(len(keys) > 1 for keys in by_group.values()), 'a port quantity of several stages shares one group'
        if mode == 'steady':
            profiled = {p['seriesId']: p for p in network['profiles']}
            for group, keys in by_group.items():
                profile = next(p for p in network['profiles'] if display[p['seriesId']]['group'] == group)
                assert {k for k in profile['stageSeriesIds'] if k} == set(keys)
            assert all(display[s]['rank'] == 8 for s in profiled if display[s]['label'].startswith('Port '))


def test_flows_rank_with_amounts_and_one_rank_limit():
    """D-1/D-3: a published flow is not a secondary property, and the rank limit has one source (the client)."""
    for result in publications(3).values():
        display = result['indexedNetwork']['display']
        assert all(d['rank'] == 4 for d in display if d['label'].endswith(' flow') and not d['label'].startswith('Port'))
    import core.compilador.indexed_display as module
    assert not hasattr(module, 'DEFAULT_RANK_LIMIT')
