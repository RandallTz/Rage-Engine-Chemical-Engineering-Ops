"""Actual connected-network samples through the existing strict result contract."""
import copy
import json
from pathlib import Path

from core.compilador.indexed_network import IndexedDerivedSystem
from core.compilador.indexed_publication import dynamic_result, steady_result
from core.compilador.indexed_steady import IndexedSteadySystem
from core.resultados import leer_resultados
from test_index_sets import source_model


def test_connected_dynamic_publication_has_stage_certificates_and_exposed_ports():
    model = source_model()
    model['datos']['solve.stageCount']['declaracion']['texto'] = '3'
    for document in [model,*model['indexSet']['templates'].values()]:
        document['datos'][document['estudio']['tiempoId']]['declaracion']['texto'] = '1'
        document['estudio']['metodoSolicitado'] = 'bdf'
        document['estudio']['muestras'] = 3
    before = copy.deepcopy(model)
    result = dynamic_result(IndexedDerivedSystem(model))
    assert model == before
    assert leer_resultados(copy.deepcopy(result)) == result
    metadata = result['indexedNetwork']
    assert metadata['count'] == 3
    assert len(metadata['endPorts']) == 6
    assert len(metadata['sidePorts']) == 2
    assert all(len(stage['closures']) == 1 for stage in metadata['stages'])
    assert all(row['valor'] <= row['tolerancia'] for row in result['verificaciones'])
    assert result['procedencia']['networkEvidence']['unresolvedPortSeries'] == [
        'cascade.stage.3.port.liquid.3.temperature','cascade.stage.3.port.liquid.3.pressure']
    Path('.tmp').mkdir(exist_ok=True)
    Path('.tmp/indexed-dynamic-result.json').write_text(json.dumps(result),encoding='utf-8')


def test_connected_steady_publication_has_profiles_from_actual_stage_roots():
    model = source_model()
    model['datos']['solve.stageCount']['declaracion']['texto'] = '2'
    result = steady_result(IndexedSteadySystem(model))
    assert result['estado'] == 'resuelto'
    assert leer_resultados(copy.deepcopy(result)) == result
    metadata = result['indexedNetwork']
    assert metadata['mode'] == 'steady'
    assert metadata['profiles']
    assert result['ejes'][0]['valores'] == [1.,2.]
    assert all(row['valor'] <= row['tolerancia'] for row in result['verificaciones'])
    by_id = {row['id']:row for row in result['series']}
    for profile in metadata['profiles']:
        assert by_id[profile['seriesId']]['valores'] == [by_id[key]['valores'] if key else None for key in profile['stageSeriesIds']]
    assert any(by_id[row['seriesId']]['unidadSI'] == 'K' for row in metadata['profiles'])
    Path('.tmp').mkdir(exist_ok=True)
    Path('.tmp/indexed-steady-result.json').write_text(json.dumps(result),encoding='utf-8')
