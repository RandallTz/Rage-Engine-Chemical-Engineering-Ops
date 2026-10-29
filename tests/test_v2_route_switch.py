"""Real ASGI HTTP dispatch and frozen-request parity; never rewrites archives."""
import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from fastapi import FastAPI
from backend import routes_engine, v2_compatibility as adapter, motor_ensamblaje_v2 as native
from backend.v2_dispatch import EXECUTOR_ENV
from test_common_admission import request
import test_v2_compatibility as parity
from v2_parity_cases import archives, archive_context, execution_digest

EVIDENCE = ROOT/'.tmp/codex-v2-http'
APP = FastAPI()
APP.include_router(routes_engine.router)


def without_provenance(value):
    return {k: v for k, v in value.items() if k != 'executionProvenance'}


async def post(client, endpoint, value):
    response = await client.post('/motor/ensamblajes/'+endpoint, json=value)
    assert response.status_code == 200, response.text
    return response.json()


class RouteSwitchTests(unittest.TestCase):
    def test_selection_capabilities_rejections_and_no_fallback(self):
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=APP), base_url='http://test') as client:
                with patch.dict(os.environ):
                    os.environ.pop(EXECUTOR_ENV, None)
                    caps = (await client.get('/motor/ensamblajes/capacidades?revision=2')).json()
                    self.assertEqual(without_provenance(caps), adapter.capabilities())
                    self.assertEqual(caps['executionProvenance']['path'], 'common-compiler')
                    EVIDENCE.mkdir(parents=True, exist_ok=True)
                    (EVIDENCE/'capabilities.json').write_text(json.dumps(caps), encoding='utf8')
                    retired = (await client.get('/motor/ensamblajes/capacidades')).json()
                    self.assertNotIn('executionProvenance', retired)
                    value = request(horizon='1')
                    with patch.object(native, 'resolver_v2', side_effect=AssertionError('Silent fallback')):
                        result = await post(client, 'resolver', value)
                        self.assertEqual(result['estado'], 'resuelto')
                        self.assertEqual(without_provenance(result), adapter.resolve(value))
                        for method in ('bdf', 'euler_implicito'):
                            bad = copy.deepcopy(value); bad['estudio']['metodoSolicitado'] = method
                            result = await post(client, 'resolver', bad)
                            self.assertEqual(result['estado'], 'no_soportado')
                            self.assertIsNone(result['resultados'])
                            self.assertEqual(result['executionProvenance']['path'], 'common-compiler')
                        with patch.object(adapter, 'resolve', side_effect=RuntimeError('Unexpected failure')):
                            with self.assertRaisesRegex(RuntimeError, 'Unexpected failure'):
                                await post(client, 'resolver', value)
                    os.environ[EXECUTOR_ENV] = 'native'
                    with patch.object(adapter, 'resolve', side_effect=AssertionError('Unexpected common path')):
                        native_caps = (await client.get('/motor/ensamblajes/capacidades?revision=2')).json()
                        self.assertEqual(without_provenance(native_caps), native.capacidades_v2())
                        result = await post(client, 'resolver', value)
                        self.assertEqual(result['executionProvenance'], {'version': 1, 'path': 'native-v2', 'selection': 'server-override'})
                        self.assertEqual(without_provenance(result), native.resolver_v2(value))
                    os.environ[EXECUTOR_ENV] = 'common'
                    overridden = (await client.get('/motor/ensamblajes/capacidades?revision=2')).json()
                    self.assertEqual(overridden['executionProvenance']['selection'], 'server-override')
                    os.environ[EXECUTOR_ENV] = 'typo'
                    with self.assertRaisesRegex(RuntimeError, 'must be common or native'):
                        await client.get('/motor/ensamblajes/capacidades?revision=2')
        asyncio.run(check())

    def test_25_requests_through_http(self):
        shard = int(os.environ.get('V2_HTTP_SHARD', '0'))
        count = int(os.environ.get('V2_HTTP_SHARDS', '1'))
        digest = execution_digest()
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        comparator = parity.CompatibilityTests()
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=APP), base_url='http://test') as client:
                for index, (path, value, archived) in enumerate(archives()):
                    if index % count != shard:
                        continue
                    name = path.stem.removesuffix('-peticion')
                    record = {'requestData': value, 'executionDigest': digest, 'request': path.relative_to(ROOT).as_posix()}
                    with archive_context(path), patch.dict(os.environ):
                        for mode, label in [('common', 'adapter'), ('native', 'native')]:
                            if mode == 'common': os.environ.pop(EXECUTOR_ENV, None)
                            else: os.environ[EXECUTOR_ENV] = mode
                            start = time.perf_counter()
                            print(json.dumps({'case': name, 'httpPath': mode, 'started': True}), flush=True)
                            record[label] = await post(client, 'resolver', value)
                            record[label+'Seconds'] = time.perf_counter()-start
                            self.assertEqual(record[label]['executionProvenance']['path'], 'common-compiler' if mode=='common' else 'native-v2')
                            validation = await post(client, 'validar', value)
                            expected = adapter.validate(value) if mode=='common' else native.validar_v2(value)[0]
                            self.assertEqual(without_provenance(validation), expected)
                            record[label+'Validation'] = validation
                            print(json.dumps({'case': name, 'httpPath': mode, 'seconds': record[label+'Seconds'], 'status': record[label]['estado']}), flush=True)
                        try:
                            comparator.compare(record, value, path, archived)
                            record['passed'] = True
                        finally:
                            (EVIDENCE/(name+'.json')).write_text(json.dumps(record), encoding='utf8')
        asyncio.run(check())


if __name__ == '__main__':
    unittest.main()
