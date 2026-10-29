"""Step (d): full frozen-request evidence through the common compatibility adapter."""
import copy
import hashlib
import asyncio
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import motor_ensamblaje_v2 as native, v2_compatibility as adapter
from core import ensamblaje_red as network
from core.resultados import leer_resultados
from core.resultados.adaptadores import desde_ensamblaje_v2
from test_common_admission import request
from v2_parity_cases import (ROOT, archives, archive_context, execution_digest,
                             RELATIVE_SERIES, event_tolerance, zero_tolerance,
                             series_limit, ZERO_REFERENCES, EVENT_REFERENCES)

EVIDENCE = ROOT/'.tmp/codex-v2-parity'


class CompatibilityTests(unittest.TestCase):
    def test_reviewed_comparison_rules_do_not_mask_nonzero_series(self):
        rows = archives()
        path, value, archived = next(row for row in rows if 'decantador-agua-butanol' in row[0].name)
        zero = {'variableId': 'red.Sgen', 'unidadSI': 'J/K', 'valores': [0, 5e-14]}
        self.assertEqual(series_limit(path, zero, value, archived['resultados'])[0], 1e-9)
        nonzero = {**zero, 'variableId': 'other.Sgen'}
        self.assertAlmostEqual(series_limit(path, nonzero, value, archived['resultados'])[0], 5e-20)
        path, value, archived = next(row for row in rows if 'unifac-red-5' in row[0].name)
        heat = next(s for s in archived['resultados']['series'] if s['variableId'] == 'calor.c.Q')
        limit, basis = series_limit(path, heat, value, archived['resultados'])
        temperatures = {s['variableId']: s['valores'] for s in archived['resultados']['series']}
        self.assertEqual(limit, .5e-6*(max(temperatures['volumen.A.T'])+max(temperatures['volumen.B.T'])))
        self.assertIn('propagated', basis)
        converted = copy.deepcopy(value)
        converted['datos']['calor.c.G']['declaracion'].update(texto='0.0005', unidad='kW/K')
        self.assertEqual(series_limit(path, heat, converted, archived['resultados'])[0], limit)

    def test_common_initialization_rejection_updates_wire_state(self):
        from core.compilador.compilador import AdmissionError
        from unittest.mock import Mock
        for state, diagnostic, status in [('pendiente','incompleto','invalido'),
                                           ('incompatible','invalido','invalido'),
                                           ('no_soportada','no_soportado','no_soportado')]:
            with self.subTest(initialization=state):
                error=AdmissionError('', '', '', diagnostics=[{'code':'initialization_test',
                    'message':'Injected unavailable common initial state.', 'path':'volumenes[0].inicial',
                    'nativeCode':'MOTOR_ENS_INICIAL_TEST','initializationStatus':state}])
                system=Mock();system.inicial.side_effect=error
                with patch.object(adapter,'compilar',return_value=system):
                    result=adapter.resolve(request(horizon='1'))
                self.assertEqual(result['estado'],status)
                self.assertIsNone(result['resultados'])
                self.assertEqual(result['validacion']['inicializacion']['estado'],state)
                initial=result['validacion']['inicializacion']['volumenes']['A']
                self.assertEqual(initial['estado'],state)
                self.assertIsNone(initial['estadoTermodinamico'])
                self.assertEqual(initial['variables'],{})
                d=result['validacion']['diagnosticos'][-1]
                self.assertEqual(d['estado'],diagnostic)
                self.assertEqual(d['origen'],{'propietarioId':'volumen:A','ruta':'/volumenes/0/inicial'})

    def test_http_boundary_and_units(self):
        import httpx
        from fastapi import FastAPI
        from backend import routes_engine
        app=FastAPI(); app.include_router(routes_engine.router)
        # Substitute the handler dependency only in this isolated app test.
        # Production routes continue dispatching to native v2 until approval.
        async def check():
            with (patch.object(routes_engine,'resolver_motor_ensamblaje',side_effect=adapter.resolve),
                  patch.object(routes_engine,'validar_motor_ensamblaje',side_effect=lambda v:(adapter.validate(v),None))):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                    baseline=request(horizon='1')
                    non_si=copy.deepcopy(baseline)
                    for key,text,unit in [('calor.q.Q','0.1','kW'),('volumen.A.T0','56.85','degC'),('volumen.A.P','1.01325','bar')]:
                        non_si['datos'][key]['declaracion'].update(texto=text,unidad=unit)
                    first=await client.post('/motor/ensamblajes/resolver',json=baseline)
                    second=await client.post('/motor/ensamblajes/resolver',json=non_si)
                    self.assertEqual(first.status_code,200); self.assertEqual(second.status_code,200)
                    a,b=first.json(),second.json()
                    self.assertEqual(a['estado'],'resuelto');self.assertEqual(b['estado'],'resuelto')
                    for x,y in zip(a['resultados']['series'],b['resultados']['series']):
                        self.assertEqual(x['unidadSI'],y['unidadSI'])
                        np.testing.assert_allclose(x['valores'],y['valores'],rtol=1e-9,atol=1e-8)
                    for field,text,unit in [('volumen.A.P','101325-200000*exp(-1e8*(t-0.125)^2)','Pa'),('calor.q.Q','0','degC')]:
                        bad=copy.deepcopy(baseline);bad['datos'][field]['declaracion'].update(texto=text,unidad=unit)
                        for endpoint in ('validar','resolver'):
                            response=await client.post('/motor/ensamblajes/'+endpoint,json=bad)
                            self.assertEqual(response.status_code,200)
                            data=response.json();validation=data.get('validacion',data)
                            self.assertTrue(validation['diagnosticos'])
                            self.assertTrue(any(field in d['variableIds'] and d['origen']==bad['datos'][field]['origen']
                                                for d in validation['diagnosticos']))
                            if endpoint=='resolver':
                                self.assertEqual(data['estado'],'invalido');self.assertIsNone(data['resultados'])
                    for method in ('bdf','euler_implicito'):
                        bad=copy.deepcopy(baseline);bad['estudio']['metodoSolicitado']=method
                        response=await client.post('/motor/ensamblajes/resolver',json=bad)
                        self.assertEqual(response.status_code,200)
                        self.assertEqual(response.json()['estado'],'no_soportado')
        asyncio.run(check())

    def test_adjunct_certification_and_events(self):
        manifest = json.loads((ROOT/'tests/reference_data/v2-parity-adjunct.json').read_text())
        evidence=EVIDENCE/'adjunct';evidence.mkdir(parents=True,exist_ok=True)
        def save(identity,value,result):
            (evidence/(identity+'.json')).write_text(json.dumps({'requestData':value,'adapter':result},ensure_ascii=True),encoding='utf-8')
        for path, digest in manifest['sources'].items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), digest, path)
        classification = manifest['classificationControl']
        self.assertEqual(network.clasificar_evento(tuple(classification['before']), tuple(classification['after'])), classification['expected'])
        for row in manifest['cases']:
            with self.subTest(control=row['id']):
                value = row['request']
                digest = hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                self.assertEqual(digest,row['inputDigest'])
                if row['id'] in ('corrupted-work', 'publication-prefix'):
                    continue  # Fault injection is exercised below, with a fresh call counter.
                result = adapter.resolve(value)
                save(row['id'],value,result)
                expected = row['expected']
                if 'status' in expected:
                    self.assertEqual(result['estado'],expected['status'])
                output = result['resultados']
                self.assertIsNotNone(output)
                leer_resultados(desde_ensamblaje_v2(result))
                if 'certification' in expected:
                    self.assertEqual(output['certificacion']['estado'],expected['certification'])
                if 'events' in expected:
                    self.assertEqual([e['codigo'] for e in output['eventos']],expected['events'])
                series = {s['variableId']:np.array(s['valores']) for s in output['series']}
                if row['id'] == 'supercritical':
                    np.testing.assert_allclose(series['volumen.A.H']-series['volumen.A.H'][0],2000*np.array(output['tiempos']),rtol=1e-6,atol=1e-3)
                    self.assertAlmostEqual(output['eventos'][0]['tiempo'],64.4210760097,delta=1e-6)
                if row['id'] == 'narrow-window':
                    for event,reference in zip(output['eventos'],(22.75493,23.39360)):
                        self.assertAlmostEqual(event['tiempo'],reference,delta=1e-3)
                if row['id'] == 'small-scale-work':
                    reference = 101325*(series['volumen.A.V'][-1]-series['volumen.A.V'][0])
                    residual = next(r for r in output['residuos'] if r['ecuacionId']=='mecanica.A.trabajo')
                    if residual['maximoEscalado'] > residual['tolerancia']:
                        self.assertEqual(output['certificacion']['estado'],'no_cumple')
                    self.assertTrue(np.isfinite(series['volumen.A.W'][-1]-reference))
        original = network.muestras
        def corrupted(red,trajectory):
            rows=copy.deepcopy(original(red,trajectory))
            rows[-1][1][network.Sistema(red).i_W]+=1000
            return rows
        with patch.object(network,'muestras',side_effect=corrupted):
            result=adapter.resolve(request(horizon='1'))
        self.assertEqual(result['estado'],'resuelto')
        self.assertEqual(result['resultados']['certificacion']['estado'],'no_cumple')
        save('corrupted-work',request(horizon='1'),result)
        evaluate=native.evaluacion_volumen
        calls=0
        def unavailable(*args):
            nonlocal calls
            from core.mezclas import FueraDeAlcance
            calls+=1
            if calls>2:
                raise FueraDeAlcance('no_convergente','Injected unavailable publication sample')
            return evaluate(*args)
        validation=adapter.validate(request(horizon='1'))
        with (patch.object(adapter,'validate',return_value=validation),
              patch.object(native,'evaluacion_volumen',side_effect=unavailable)):
            result=adapter.resolve(request(horizon='1'))
        self.assertEqual(result['estado'],'parcial')
        self.assertEqual(result['resultados']['tiempos'],[0.])
        self.assertIn('MOTOR_ENS_MUESTRA_NO_CERTIFICADA',[d['codigo'] for d in result['validacion']['diagnosticos']])
        save('publication-prefix',request(horizon='1'),result)

    def test_no_native_solver_fallback_and_aliases(self):
        with (patch.object(native, 'resolver_v2', side_effect=AssertionError('Native solver fallback')),
              patch.object(network, 'integrar', side_effect=AssertionError('Native integrator fallback'))):
            result = adapter.resolve(request(horizon='1'))
        self.assertEqual(result['estado'], 'resuelto')
        output = result['resultados']
        variables = {v['id'] for v in result['validacion']['variables']}
        for row in output['catalogoSeries']:
            self.assertEqual(row['variableEnsamblajeId'], row['variableId'] if row['variableId'] in variables else None)
        self.assertEqual(output['certificacion']['estado'], 'no_evaluable')
        leer_resultados(desde_ensamblaje_v2(result))

    def test_open_boundary_preserves_all_five_wire_codes(self):
        path, value, _ = next(row for row in archives() if 'borrador-frontera-abierta' in str(row[0]))
        actual = adapter.resolve(value)
        self.assertIsNone(actual['resultados'])
        self.assertEqual({d['codigo'] for d in actual['validacion']['diagnosticos']},
                         {'MOTOR_ENS_'+c for c in ('DONANTE_PENDIENTE', 'FRONTERA', 'INICIAL', 'MATERIA', 'MODELO')})

    def test_all_25_archives(self):
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        digest = execution_digest()
        for path, value, archived in archives():
            if os.environ.get('V2_PARITY_CASE') and os.environ['V2_PARITY_CASE'] not in path.name:
                continue
            with self.subTest(request=path.name):
                name = path.stem.removesuffix('-peticion')
                cache = EVIDENCE/(name+'.json')
                record = json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else {}
                replay = os.environ.get('V2_PARITY_REPLAY') == '1'
                if replay:
                    self.assertEqual(record.get('requestData'),value,'Replay requires evidence for the exact frozen request')
                    self.assertIn('native',record);self.assertIn('adapter',record)
                    print(json.dumps({'case':name,'replayExecutionDigest':record['executionDigest'],
                                      'currentSourceMatches':record['executionDigest']==digest}),flush=True)
                if not replay and record.get('executionDigest') != digest:
                    record = {'request': path.relative_to(ROOT).as_posix(), 'executionDigest': digest,
                              'requestData': value, 'seriesTolerance': RELATIVE_SERIES,
                              'inputDigest': hashlib.sha256(path.read_bytes()).hexdigest(),
                              'mappedDifferences': ['Method text reports common RK45 execution; no native solver fallback.']}
                with archive_context(path):
                    for label, solve in [('native', native.resolver_v2), ('adapter', adapter.resolve)]:
                        if label not in record:
                            start = time.perf_counter()
                            print(json.dumps({'case':name,'route':label,'started':True}),flush=True)
                            record[label] = solve(copy.deepcopy(value))
                            record[label+'Seconds'] = time.perf_counter()-start
                            print(json.dumps({'case': name, 'route': label, 'status': record[label]['estado'],
                                              'seconds': record[label+'Seconds']}), flush=True)
                            cache.write_text(json.dumps(record, ensure_ascii=True), encoding='utf-8')
                try:
                    self.compare(record, value, path, archived)
                    record['passed'] = True
                    record.pop('failure', None)
                except Exception as error:
                    record['passed'] = False
                    record['failure'] = str(error)
                    raise
                finally:
                    cache.write_text(json.dumps(record, ensure_ascii=True), encoding='utf-8')

    def compare(self, record, request, path, archived):
        actual, reference = record['adapter'], record['native']
        self.assertEqual(actual['estado'], reference['estado'])
        a, b = actual['validacion'], reference['validacion']
        for field in ('modeloId', 'recuento', 'variables', 'ecuaciones'):
            self.assertEqual(a[field], b[field], field)
        self.assertEqual(a['inicializacion'], b['inicializacion'])
        self.assertEqual([(d['codigo'], d['estado'], d['origen'], d['variableIds']) for d in a['diagnosticos']],
                         [(d['codigo'], d['estado'], d['origen'], d['variableIds']) for d in b['diagnosticos']])
        if archived:
            frozen_validation = archived.get('validacion', archived)
            expected_codes = {d['codigo'] for d in frozen_validation['diagnosticos'] if not d['codigo'].startswith('MOTOR_ENS_DETENIDO_')}
            self.assertTrue(expected_codes <= {d['codigo'] for d in a['diagnosticos']}, expected_codes)
        output, target = actual['resultados'], reference['resultados']
        if target is None:
            self.assertIsNone(output)
            record['maximumSeriesError'] = None
            return
        leer_resultados(desde_ensamblaje_v2(actual))
        self.assertEqual(output['certificacion']['estado'], target['certificacion']['estado'])
        self.assertEqual([(r['id'], r['estado']) for r in output['certificacion']['aspectos']],
                         [(r['id'], r['estado']) for r in target['certificacion']['aspectos']])
        self.assertEqual(output['segundaLey']['estado'], target['segundaLey']['estado'])
        self.assertEqual(output['procedenciaModelo'], target['procedenciaModelo'])
        self.assertEqual(output['catalogoSeries'], target['catalogoSeries'])
        left, right = {s['variableId']: s for s in output['series']}, {s['variableId']: s for s in target['series']}
        self.assertEqual(set(left), set(right))
        tol = event_tolerance(path, target['tiempos'][-1])
        record['eventToleranceSeconds'] = tol
        timing_failures=[]
        self.assertEqual(len(output['eventos']), len(target['eventos']))
        record['independentEventComparisons'] = []
        record['nativeFindings'] = []
        for event_index, (x, y) in enumerate(zip(output['eventos'], target['eventos'])):
            self.assertEqual(x['codigo'], y['codigo'])
            self.assertEqual(x['volumenId'], y['volumenId'])
            difference=abs(x['tiempo']-y['tiempo'])
            if path.name in EVENT_REFERENCES:
                independent = EVENT_REFERENCES[path.name][event_index]
                comparison = {'event': x['codigo'], 'referenceSeconds': independent,
                              'basis': 'H(t)=H0+Qt; PH phase-set bisection without integration',
                              'adapterErrorSeconds': abs(x['tiempo']-independent),
                              'nativeErrorSeconds': abs(y['tiempo']-independent), 'limitSeconds': tol}
                record['independentEventComparisons'].append(comparison)
                difference = comparison['adapterErrorSeconds']
                if comparison['nativeErrorSeconds'] > tol:
                    record['nativeFindings'].append(comparison)
            if difference>tol:
                timing_failures.append({'event':x['codigo'],'owner':x['volumenId'],
                                        'adapterTime':x['tiempo'],'nativeTime':y['tiempo'],
                                        'errorSeconds':difference,'limitSeconds':tol})
            for key in ('faseIdsAntes', 'faseIdsDespues'):
                self.assertEqual(x.get(key), y.get(key), key)
        # Requested points are compared directly. Event samples are compared
        # against the corresponding event side, never interpolated across it.
        pairs = []
        for j, t in enumerate(target['tiempos']):
            i = int(np.argmin(np.abs(np.array(output['tiempos'])-t)))
            if abs(output['tiempos'][i]-t)>tol and not any(e['tiempo']==t for e in target['eventos']):
                timing_failures.append({'missingRequestedSample':t})
            pairs.append((i, j))
        record['timingFailures']=timing_failures
        record['sampleCounts'] = [len(output['tiempos']), len(target['tiempos'])]
        errors, failures = {}, []
        record['seriesComparisonPolicy'] = {}
        for identity, target_series in right.items():
            series = left[identity]
            self.assertEqual(series['unidadSI'], target_series['unidadSI'])
            x = np.array([series['valores'][i] for i, j in pairs])
            y = np.array([target_series['valores'][j] for i, j in pairs])
            scale = max(abs(y))
            error = float(max(abs(x-y)))
            errors[identity] = error/scale if scale else error
            limit, basis = series_limit(path, target_series, request, target)
            record['seriesComparisonPolicy'][identity] = {'limitSI': limit, 'basis': basis}
            if (path.name, identity) in ZERO_REFERENCES:
                for values in (x, y):
                    self.assertLessEqual(float(max(abs(values))), zero_tolerance(target_series, request), basis)
            if error>limit:
                failures.append({'series':identity,'absoluteError':error,'referenceScale':float(scale),'limit':limit})
        record['maximumSeriesError'] = max(errors.values())
        record['seriesErrors'] = errors
        record['seriesFailures'] = failures
        potential_errors=[]
        for owner,states in output['estados'].items():
            for i,j in pairs:
                x,y=states[i]['potenciales'],target['estados'][owner][j]['potenciales']
                self.assertEqual(x['referencia'],y['referencia'])
                for key in ('T','P','G','A','S'):
                    error=abs(x[key]-y[key])/max(abs(y[key]),1e-300)
                    potential_errors.append(error)
                    self.assertLessEqual(error,RELATIVE_SERIES,(owner,key,i,j))
                for phase in y['fases']:
                    actual=next(p for p in x['fases'] if p['faseId']==phase['faseId'])
                    self.assertEqual(set(actual['mu']),set(phase['mu']))
                    for component,value in phase['mu'].items():
                        if value is None:
                            self.assertIsNone(actual['mu'][component])
                        else:
                            error=abs(actual['mu'][component]-value)/max(abs(value),1e-300)
                            potential_errors.append(error)
                            self.assertLessEqual(error,RELATIVE_SERIES,(owner,phase['faseId'],component))
        record['maximumPotentialError']=max(potential_errors,default=0)
        for row in output['residuos']:
            self.assertEqual(row['tolerancia'], next(r['tolerancia'] for r in target['residuos'] if r['ecuacionId']==row['ecuacionId']))
        self.assertEqual(output['certificacion']['alcance']['completa'], target['certificacion']['alcance']['completa'])
        for result in (output,target):
            if result['certificacion']['estado']=='cumple':
                self.assertTrue(all(r['maximoEscalado']<=r['tolerancia'] for r in result['residuos']))
            for owner,states in result['estados'].items():
                self.assertEqual(len(states),len(result['tiempos']),owner)
                for state in states:
                    self.assertEqual(state['potenciales']['unidades'],{'mu':'J/mol','G':'J','A':'J','S':'J/K'})
        for x,y in zip(output['certificacion']['aspectos'],target['certificacion']['aspectos']):
            self.assertEqual(x.get('primeraMuestraNoCumple'),y.get('primeraMuestraNoCumple'))
            self.assertEqual(x.get('referencias'),y.get('referencias'))
        # The immutable response is a historical baseline, not regenerated by
        # this test. Record every structural/time change separately from the
        # fresh native comparison, which includes accepted thermodynamic fixes.
        frozen=(archived or {}).get('resultados')
        historical_failures=[]
        if frozen:
            shared=[]
            for j,t in enumerate(frozen['tiempos']):
                i=int(np.argmin(abs(np.array(output['tiempos'])-t)))
                if abs(output['tiempos'][i]-t)<=tol:
                    shared.append((i,j))
            old={s['variableId']:s for s in frozen['series']}
            historical={}
            historical_policy = {}
            for identity in set(old)&set(left):
                self.assertEqual(old[identity]['unidadSI'],left[identity]['unidadSI'])
                if shared:
                    x=np.array([left[identity]['valores'][i] for i,j in shared])
                    y=np.array([old[identity]['valores'][j] for i,j in shared])
                    scale=max(abs(y));error=float(max(abs(x-y)))
                    historical[identity]=error/scale if scale else error
                    limit, basis = series_limit(path, old[identity], request, frozen)
                    historical_policy[identity] = {'limitSI': limit, 'basis': basis}
                    if (path.name, identity) in ZERO_REFERENCES:
                        for values in (x, y):
                            self.assertLessEqual(float(max(abs(values))), zero_tolerance(old[identity], request), basis)
                    if error>limit:
                        historical_failures.append({'series':identity,'absoluteError':error,
                            'referenceScale':float(scale),'limit':limit})
            record['archivedResponseComparison']={
                'sharedSamples':len(shared),'frozenSamples':len(frozen['tiempos']),
                'maximumSeriesError':max(historical.values(),default=0),
                'seriesErrors':historical,'addedSeries':sorted(set(left)-set(old)),
                'comparisonPolicy': historical_policy,
                'removedSeries':sorted(set(old)-set(left)),
                'events':[(e['codigo'],e['tiempo']) for e in frozen['eventos']],
                'currentEvents':[(e['codigo'],e['tiempo']) for e in output['eventos']],
                'certification':[frozen.get('certificacion',{}).get('estado'),output['certificacion']['estado']]}
        record['archivedSeriesFailures']=historical_failures
        record['freshNativeParity']=not failures and not timing_failures
        self.assertEqual(failures,[], 'Strict series parity findings; do not relax tolerances.')
        self.assertEqual(timing_failures,[], 'Strict event parity findings; do not relax tolerances.')
        self.assertEqual(historical_failures,[], 'Historical reference findings; do not regenerate archives.')


if __name__ == '__main__':
    unittest.main()
