"""Generate connected network results for the shared chart presentation verifier."""
import json
import subprocess
from pathlib import Path

from core.compilador.indexed_network import IndexedDerivedSystem
from core.compilador.indexed_publication import dynamic_result, steady_result
from core.compilador.indexed_steady import IndexedSteadySystem
from core.resultados import leer_resultados
from test_index_sets import source_model


def test_fresh_network_chart_publications(tmp_path):
    model = source_model()
    model['datos']['solve.stageCount']['declaracion']['texto'] = '2'
    for document in [model, *model['indexSet']['templates'].values()]:
        document['datos'][document['estudio']['tiempoId']]['declaracion']['texto'] = '1'
        document['estudio']['metodoSolicitado'] = 'bdf'
        document['estudio']['muestras'] = 3
    system = IndexedDerivedSystem(model)
    results = {'dynamic': dynamic_result(system),
               'steady': steady_result(IndexedSteadySystem(model, dynamic=system))}
    for result in results.values():
        assert leer_resultados(result) == result
    path = tmp_path / 'results.json'
    path.write_text(json.dumps(results), encoding='utf-8')
    subprocess.run(['node', 'frontend/motores/resultados/verificar_indexed_charts.mjs', str(path)], check=True)
