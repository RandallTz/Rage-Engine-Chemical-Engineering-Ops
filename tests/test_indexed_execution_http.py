"""ASGI HTTP smoke tests of the actual connected runtime and located rejections."""
import asyncio
import copy
import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from backend.api_modelo import router
from core.compilador.indexed_contract import read_compilation, read_result, selection_for
from test_index_sets import source_model


def request(endpoint, body):
    async def run():
        app = FastAPI(); app.include_router(router)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            return await client.post('/modelo/'+endpoint, json=body)
    return asyncio.run(run())


@pytest.mark.parametrize('mode', ['dynamic', 'steady'])
def test_connected_http_result(mode):
    model = source_model()
    model['datos']['solve.stageCount']['declaracion']['texto'] = '2'
    for document in [model, *model['indexSet']['templates'].values()]:
        document['datos'][document['estudio']['tiempoId']]['declaracion']['texto'] = '1'
        document['estudio']['muestras'] = 3
        document['estudio']['metodoSolicitado'] = 'bdf'
    selected = selection_for(model, mode)
    response = request('resolver', {'modelo':model, 'indexedExecution':selected})
    assert response.status_code == 200, response.text
    result = read_result(response.json(), selected)
    assert result['estado'] == 'resuelto'
    assert result['indexedNetwork']['count'] == 2
    assert all(v['valor'] <= v['tolerancia'] for v in result['verificaciones'])
    Path('.tmp').mkdir(exist_ok=True)
    Path(f'.tmp/indexed-http-{mode}.json').write_text(json.dumps(result), encoding='utf-8')


def test_stale_and_malformed_requests_reject_before_lowering():
    model = source_model(); selected = selection_for(model, 'dynamic')
    changed = copy.deepcopy(model); changed['datos']['solve.stageCount']['declaracion']['texto'] = '2'
    for endpoint in ['resolver', 'compilation']:
        response = request(endpoint, {'modelo':changed, 'indexedExecution':selected})
        assert response.status_code == 422
        assert response.json()['detail']['diagnostics'][0]['code'] == 'stale_indexed_execution'
        response = request(endpoint, {'modelo':model, 'indexedExecution':selected, 'extra':True})
        assert response.status_code == 422
    response = request('indexed-execution', {'format':'rage.indexed-execution.request','version':1,'model':model,'mode':'unknown'})
    assert response.status_code == 422
