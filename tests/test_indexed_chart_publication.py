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
