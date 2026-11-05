"""Indexed result contract over real shared-author thermal-chain publications."""
import copy
from functools import lru_cache
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.resultados.formato import conjunto, eje, serie, leer_resultados, ErrorResultados


@lru_cache(maxsize=1)
def publications():
    from sparse_chain_inputs import thermal_chain
    from core.compilador.derived import DerivedSystem, resolve_system
    from core.compilador.steady import SteadySystem
    from core.modelo.steady_transform import prepare_steady_transform
    model=thermal_chain(3)
    sources={'dynamic':resolve_system(DerivedSystem(model)),
             'steady':SteadySystem(prepare_steady_transform(model)['model']).solve()}
    outputs={}
    for mode,source in sources.items():
        leer_resultados(source)
        stages=[];rows=[]
        for j in range(1,4):
            owner='thermal.stage.'+str(j)
            temperature=next(s for s in source['series'] if s['unidadSI']=='K' and 'region_'+str(j-1) in s['nombre'])
            row={**copy.deepcopy(temperature),'id':owner+'.temperature','propietarioId':owner}
            rows.append(row)
            stages.append({'index':j,'ownerId':owner,'seriesIds':[row['id']],'closures':[]})
        axes=copy.deepcopy(source['ejes']);profiles=[]
        if mode=='steady':
            axes.append(eje('stage-index','Stage j','parametro','1',[1,2,3]))
            profile=serie('thermal.temperature','Temperature by stage','K',['stage-index'],
                          [r['valores'] for r in rows],propietarioId='thermal')
            profiles=[{'seriesId':profile['id'],'stageSeriesIds':[r['id'] for r in rows]}]
            rows.append(profile)
        output=conjunto('indexed-'+mode,'Indexed thermal publication',source['estado'],
            {'motor':'rage.indexed-publication.contract-test','metodo':source['procedencia']['metodo'],
             'firma':source['procedencia'].get('firma')},axes,rows,
            verificaciones=copy.deepcopy(source['verificaciones']),modeloId=model['id'])
        output['indexedNetwork']={'version':1,'indexSetId':'thermal','count':3,'mode':mode,
            'stageAxisId':'stage-index' if mode=='steady' else None,
            'stages':stages,'endPorts':[],'profiles':profiles}
        leer_resultados(output);outputs[mode]=output
    return outputs


def malformed_cases():
    reference=publications()['steady']
    mutations=[
        ('unknown root',lambda x:x['indexedNetwork'].update(extra=True)),
        ('version',lambda x:x['indexedNetwork'].update(version=2)),
        ('boolean version',lambda x:x['indexedNetwork'].update(version=True)),
        ('count',lambda x:x['indexedNetwork'].update(count=2)),
        ('fractional count',lambda x:x['indexedNetwork'].update(count=3.5)),
        ('zero count',lambda x:x['indexedNetwork'].update(count=0)),
        ('stage order',lambda x:x['indexedNetwork']['stages'][0].update(index=2)),
        ('stage owner',lambda x:x['indexedNetwork']['stages'][0].update(ownerId='thermal.stage.2')),
        ('missing series',lambda x:x['indexedNetwork']['stages'][0].update(seriesIds=['missing'])),
        ('repeated series',lambda x:x['indexedNetwork']['stages'][0]['seriesIds'].append(x['indexedNetwork']['stages'][0]['seriesIds'][0])),
        ('foreign series',lambda x:x['series'][0].update(propietarioId='thermal.stage.2')),
        ('axis order',lambda x:x['ejes'][0].update(valores=[3,2,1])),
        ('axis role',lambda x:x['ejes'][0].update(rol='coordenada')),
        ('boolean stage axis',lambda x:x['ejes'][0].update(valores=[True,2,3])),
        ('profile value',lambda x:x['series'][-1]['valores'].__setitem__(0,999)),
        ('profile order',lambda x:x['indexedNetwork']['profiles'][0]['stageSeriesIds'].reverse()),
        ('profile duplicate',lambda x:x['indexedNetwork']['profiles'].append(copy.deepcopy(x['indexedNetwork']['profiles'][0]))),
        ('unknown closure',lambda x:x['indexedNetwork']['stages'][0]['closures'].append({'volumeId':'thermal.stage.1.volume.v','mode':'equilibrium','verificationId':'missing'})),
        ('port interior',lambda x:x['indexedNetwork']['endPorts'].append({'portId':'heat','stage':2,'kind':'heat','direction':'inlet','variables':{'power':x['series'][0]['id']}})),
        ('port units',lambda x:x['indexedNetwork']['endPorts'].append({'portId':'heat','stage':1,'kind':'heat','direction':'inlet','variables':{'power':x['series'][0]['id']}})),
    ]
    rows=[]
    for name,change in mutations:
        altered=copy.deepcopy(reference);change(altered);rows.append({'name':name,'result':altered})
    return rows


def boundary_contract_fixture():
    """Wire-only fixture for strict type checks, not a physical simulation."""
    owner='wire.stage.1';volume=owner+'.volume.v'
    definitions=[('flow','kg/s',2.),('fraction','1',1.),('temperature','K',300.),
                 ('pressure','Pa',101325.),('enthalpy','J/kg',100.),('power','W',20.)]
    rows=[serie(owner+'.'+key,key,unit,[],number,propietarioId=owner) for key,unit,number in definitions]
    verification='thermodynamics.closure.'+volume
    result=conjunto('wire-contract','Wire contract fixture','resuelto',
        {'motor':'contract-fixture','metodo':None,'firma':None},[eje('j','j','parametro','1',[1])],rows,
        verificaciones=[{'id':verification,'valor':0.,'tolerancia':1.,'descripcion':'Wire-only certificate summary fixture'}])
    result['indexedNetwork']={'version':1,'indexSetId':'wire','count':1,'mode':'steady','stageAxisId':'j',
        'stages':[{'index':1,'ownerId':owner,'seriesIds':[s['id'] for s in rows],
                   'closures':[{'volumeId':volume,'mode':'equilibrium','verificationId':verification}]}],
        'endPorts':[{'portId':'feed','stage':1,'kind':'material','direction':'inlet',
                     'variables':{'flow':owner+'.flow','composition':[owner+'.fraction'],'temperature':owner+'.temperature',
                                  'pressure':owner+'.pressure','specificEnthalpy':owner+'.enthalpy'}},
                    {'portId':'heat','stage':1,'kind':'heat','direction':'inlet','variables':{'power':owner+'.power'}}],
        'profiles':[]}
    return result


def boundary_rejections():
    mutations=[
        ('certificate failure',lambda x:x['verificaciones'][0].update(valor=2.)),
        ('certificate tolerance',lambda x:x['verificaciones'][0].update(tolerancia=2.)),
        ('boolean certificate tolerance',lambda x:x['verificaciones'][0].update(tolerancia=True)),
        ('certificate foreign volume',lambda x:x['indexedNetwork']['stages'][0]['closures'][0].update(volumeId='wire.stage.2.volume.v')),
        ('unknown certificate field',lambda x:x['indexedNetwork']['stages'][0]['closures'][0].update(extra=1)),
        ('duplicate closure',lambda x:x['indexedNetwork']['stages'][0]['closures'].append(copy.deepcopy(x['indexedNetwork']['stages'][0]['closures'][0]))),
        ('empty composition',lambda x:x['indexedNetwork']['endPorts'][0]['variables'].update(composition=[])),
        ('missing material state',lambda x:x['indexedNetwork']['endPorts'][0]['variables'].pop('pressure')),
        ('unknown port field',lambda x:x['indexedNetwork']['endPorts'][0].update(extra=1)),
        ('invalid direction',lambda x:x['indexedNetwork']['endPorts'][0].update(direction='both')),
        ('duplicate port',lambda x:x['indexedNetwork']['endPorts'].append(copy.deepcopy(x['indexedNetwork']['endPorts'][0]))),
        ('foreign binding',lambda x:x['indexedNetwork']['endPorts'][0]['variables'].update(flow='missing')),
        ('enthalpy basis',lambda x:x['series'][4].update(unidadSI='J/mol',dimension={'M':{'n':1,'d':1},'L':{'n':2,'d':1},'T':{'n':-2,'d':1},'N':{'n':-1,'d':1}})),
    ]
    rows=[]
    for name,change in mutations:
        result=boundary_contract_fixture();change(result);rows.append({'name':name,'result':result})
    return rows


def test_actual_chain_dynamic_and_steady_stage_profile():
    for result in publications().values():
        assert leer_resultados(result) is result
    assert publications()['steady']['series'][-1]['valores']==pytest.approx([300]*3,abs=1e-6)


def test_shared_rejections():
    for case in malformed_cases()+boundary_rejections():
        with pytest.raises(ErrorResultados,match='indexedNetwork'):
            leer_resultados(case['result'])


def test_boundary_and_certificate_wire_contract():
    result=boundary_contract_fixture()
    assert leer_resultados(result) is result
    result['indexedNetwork']['endPorts'][1]['kind']='work'
    assert leer_resultados(result) is result
    result['indexedNetwork']['stages'][0]['closures'][0]['mode']='single_phase'
    result['verificaciones'][0]['tolerancia']=1e-9
    assert leer_resultados(result) is result


def test_explicit_null_extension_is_not_absence():
    result=copy.deepcopy(publications()['dynamic']);result['indexedNetwork']=None
    with pytest.raises(ErrorResultados):leer_resultados(result)
    del result['indexedNetwork']
    assert leer_resultados(result) is result


def side_port_fixture():
    result = copy.deepcopy(publications()['steady'])
    record = result['indexedNetwork']
    record.update(version=2, sidePorts=[])
    for j, field in [(1, 'endPorts'), (2, 'sidePorts')]:
        owner = 'thermal.stage.' + str(j)
        identity = owner + '.power'
        result['series'].append(serie(identity, 'Boundary heat', 'W', [], 10., propietarioId=owner))
        record['stages'][j-1]['seriesIds'].append(identity)
        record[field].append({'portId':'heat.'+str(j), 'stage':j, 'kind':'heat',
                              'direction':'inlet', 'variables':{'power':identity}})
    return result


def side_port_rejections():
    mutations = [
        ('v1 side ports', lambda x:x['indexedNetwork'].update(version=1)),
        ('v2 missing side ports', lambda x:x['indexedNetwork'].pop('sidePorts')),
        ('side at end', lambda x:x['indexedNetwork']['sidePorts'][0].update(stage=1)),
        ('fractional side stage', lambda x:x['indexedNetwork']['sidePorts'][0].update(stage=1.5)),
        ('side foreign stage', lambda x:x['indexedNetwork']['sidePorts'][0].update(stage=4)),
        ('side boolean stage', lambda x:x['indexedNetwork']['sidePorts'][0].update(stage=True)),
        ('end at interior', lambda x:x['indexedNetwork']['endPorts'][0].update(stage=2)),
        ('duplicate exposed identity', lambda x:x['indexedNetwork']['sidePorts'][0].update(portId='heat.1')),
        ('foreign side variable', lambda x:x['indexedNetwork']['sidePorts'][0]['variables'].update(power='thermal.stage.1.power')),
        ('unknown side field', lambda x:x['indexedNetwork']['sidePorts'][0].update(extra=1)),
    ]
    cases = []
    for name, change in mutations:
        result = side_port_fixture()
        change(result)
        cases.append({'name':name, 'result':result})
    return cases


def test_version_two_side_ports_preserve_version_one():
    assert leer_resultados(side_port_fixture())['indexedNetwork']['version'] == 2
    assert leer_resultados(boundary_contract_fixture())['indexedNetwork']['version'] == 1
    for case in side_port_rejections():
        with pytest.raises(ErrorResultados, match='indexedNetwork'):
            leer_resultados(case['result'])


if __name__=='__main__':
    destination=Path(sys.argv[1]);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps({'valid':{**publications(),'typedPorts':boundary_contract_fixture(), 'sidePorts':side_port_fixture()},
        'invalid':malformed_cases()+boundary_rejections()+side_port_rejections()}),encoding='utf8')
