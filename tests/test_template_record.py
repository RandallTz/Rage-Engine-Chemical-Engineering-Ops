"""Shared Python/TypeScript acceptance and rejection corpus; no product templates."""
import copy
import json
import sys
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo01_flash import frozen_model
from core.modelo.lector import leer_modelo_comun, leer_modelo_inspeccion, ErrorModelo


def cases():
    model = frozen_model()
    model['motores']['momentumDerivation'] = dict(format='rage.momentum-derivation', version=1, volumes={'drum': dict(origin='recorded', operations=[dict(id='stress', title='Retain pressure stress', changes=dict(pressureStress=True))])})
    model['volumenes'][0]['balances']['momento'] = True
    units = dict(flow='kg/s', composition='1', temperature='K', pressure='Pa', specificEnthalpy='J/kg')
    port = dict(id='feed', volumeId='drum', direction='inlet', kind='material',
                boundary=dict(type='stream', id='feed'), exteriorState='estadoExterior',
                variables={key: dict(unitSI=unit) for key, unit in units.items()})
    model['template'] = dict(format='rage.model-template', version=1, id='reader-test', templateVersion='1.0',
                             equipment=True, recipe=dict(journals=['materialDerivation', 'energyDerivation', 'momentumDerivation', 'thermodynamicDerivation', 'equationWorkbench']), ports=[port])
    rows = [('valid inlet', True, copy.deepcopy(model)), ('legacy absent', True, frozen_model())]
    def variant(label, valid, edit):
        value = copy.deepcopy(model); edit(value); rows.append((label, valid, value))
    def set_path(path, value):
        def edit(m):
            for key in path[:-1]: m = m[key]
            m[path[-1]] = value
        return edit
    def delete_path(path):
        def edit(m):
            for key in path[:-1]: m = m[key]
            del m[path[-1]]
        return edit
    root=['template']; pr=root+['ports',0]
    for path in [root,root+['recipe'],pr,pr+['boundary'],pr+['variables']]+[pr+['variables',key] for key in units]:
        variant('unknown '+str(path), False, set_path(path+['extra'],1))
        original=model
        for key in path: original=original[key]
        for key in original:
            variant('missing '+str(path+[key]), False, delete_path(path+[key]))
    for path,value in [(root+['format'],'other'),(root+['version'],2),(root+['version'],True),(root+['id'],''),(root+['templateVersion'],1),(root+['equipment'],1),(root+['recipe','journals'],[]),(root+['recipe','journals'],['equationWorkbench','equationWorkbench']),(root+['recipe','journals'],['derivedExecution']),(root+['recipe','journals'],['momentumDerivation']),(root+['ports'],[]),(pr+['id'],''),(pr+['volumeId'],'missing'),(pr+['kind'],'other'),(pr+['direction'],'other'),(pr+['direction'],'outlet'),(pr+['boundary','id'],'missing'),(pr+['boundary','type'],'term'),(pr+['donorPhase'],None),(pr+['exteriorState'],'other'),(pr+['variables','flow','unitSI'],'g/s'),(pr+['variables','specificEnthalpy','unitSI'],'J/mol')]:
        variant('invalid '+str(path)+repr(value),False,set_path(path,value))
    for journal in model['template']['recipe']['journals']:
        for value in [None, [], 'journal', 1, {}]:
            variant('invalid journal '+journal+repr(value),False,set_path(['motores',journal],value))
        variant('equipment missing recipe '+journal,journal=='equationWorkbench',lambda m,j=journal:m['template']['recipe']['journals'].remove(j))
    for value in [None, [], 'state', {'temperaturaId':'missing'}, {}]:
        variant('invalid exterior '+repr(value),False,set_path(['corrientes',0,'estadoExterior'],value))
    for value in [None, [], 'extraction', {'missing':{}}]:
        variant('invalid extraction '+repr(value),False,set_path(['corrientes',1,'extraccion'],value))
    for journal in ['materialDerivation','energyDerivation','momentumDerivation','thermodynamicDerivation']:
        variant('equipment empty journal '+journal,False,set_path(['motores',journal,'volumes'],{}))
        variant('equipment missing entry '+journal,False,delete_path(['motores',journal,'volumes','drum']))
        if journal!='thermodynamicDerivation':
            variant('equipment no operations '+journal,False,set_path(['motores',journal,'volumes','drum','operations'],[]))
    for flag in ['materia','energia','momento']:
        variant('equipment inactive balance '+flag,False,set_path(['volumenes',0,'balances',flag],False))
    def pipe(m):
        v=copy.deepcopy(m['volumenes'][0]);v['id']='pipe';v['balances']=dict(materia=False,energia=False,momento=True);v['termodinamica']=dict(motivo='Donor phase state; no separate closure',supuesto='fase_no_evaluada',tipo='supuesto')
        m['volumenes'].append(v)
        m['motores']['momentumDerivation']['volumes']['pipe']=copy.deepcopy(m['motores']['momentumDerivation']['volumes']['drum'])
    variant('equipment momentum-only pipe volume',True,pipe)
    variant('invalid stream base',False,set_path(['corrientes',0,'materia','base'],'x'))
    variant('invalid stream base without template',False,lambda m:(m.pop('template'),m['corrientes'][0]['materia'].update(base='x')))
    variant('byte-order-mark template id is text',True,set_path(['template','id'],'﻿'))
    variant('no exterior state',False,delete_path(['corrientes',0,'estadoExterior']))
    variant('duplicate port',False,lambda m:m['template']['ports'].append(copy.deepcopy(m['template']['ports'][0])))
    def duplicate_boundary(m):
        other=copy.deepcopy(m['template']['ports'][0]);other['id']='other';m['template']['ports'].append(other)
    variant('duplicate boundary',False,duplicate_boundary)
    variant('general template without ports',True,lambda m:m['template'].update(equipment=False,ports=[]))
    def outlet(m):
        p=m['template']['ports'][0];p.update(direction='outlet',boundary=dict(type='stream',id='liquid'),donorPhase=None);del p['exteriorState']
    variant('homogeneous outlet',True,outlet)
    def phase(m):
        outlet(m);m['corrientes'][1]['extraccion']={'drum':dict(tipo='fase',fase='liquido')};m['template']['ports'][0]['donorPhase']='liquido'
    variant('phase outlet',True,phase)
    variant('null extraction on homogeneous outlet',False,lambda m:(outlet(m),m['corrientes'][1].update(extraccion=None)))
    variant('wrong phase outlet',False,lambda m:(phase(m),m['template']['ports'][0].update(donorPhase='vapor')))
    variant('missing phase',False,lambda m:(outlet(m),m['template']['ports'][0].pop('donorPhase')))
    variant('outlet exterior state',False,lambda m:(outlet(m),m['template']['ports'][0].update(exteriorState='estadoExterior')))
    variant('internal stream',False,lambda m:m['corrientes'][0].update(desde='drum'))
    def term(m,kind):
        key='calor' if kind=='heat' else 'trabajo_viscoso'
        m['volumenes'][0]['terminos']={key:'feed.P'}
        m['template']['ports']=[dict(id=kind,volumeId='drum',kind=kind,direction='inlet',boundary=dict(type='term',id=key),variables=dict(power=dict(unitSI='W')))]
    for kind in ['heat','work']:
        variant(kind+' term',True,lambda m,k=kind:term(m,k))
        variant(kind+' outlet term',True,lambda m,k=kind:(term(m,k),m['template']['ports'][0].update(direction='outlet')))
        variant(kind+' missing term',kind=='heat',lambda m,k=kind:(term(m,k),m['volumenes'][0].pop('terminos')))
        variant(kind+' invalid material field',False,lambda m,k=kind:(term(m,k),m['template']['ports'][0].update(donorPhase=None)))
        variant(kind+' wrong unit',False,lambda m,k=kind:(term(m,k),m['template']['ports'][0]['variables']['power'].update(unitSI='J')))
    def exchange(m):
        term(m,'heat');m['template']['ports'][0]['boundary']=dict(type='exchange',id='heat')
        m['intercambios']=[dict(id='heat',desde=None,hasta='drum',ley=dict(tipo='impuesto',potenciaId='feed.P'))]
    variant('heat exchange',True,exchange)
    variant('wrong exchange direction',False,lambda m:(exchange(m),m['template']['ports'][0].update(direction='outlet')))
    variant('internal exchange',False,lambda m:(exchange(m),m['intercambios'][0].update(desde='drum')))
    variant('unknown exchange',False,lambda m:(exchange(m),m.update(intercambios=[])))
    variant('work exchange',False,lambda m:(exchange(m),m['template']['ports'][0].update(kind='work')))
    return rows


@pytest.mark.parametrize('label,valid,model', cases(), ids=[row[0] for row in cases()])
@pytest.mark.parametrize('reader', [leer_modelo_comun, leer_modelo_inspeccion], ids=['runnable', 'inspection'])
def test_template_record(label, valid, model, reader):
    if valid:
        assert reader(model) is model, label
    else:
        with pytest.raises(ErrorModelo) as caught:
            reader(model)
        assert caught.value.ruta, label


@pytest.mark.parametrize('reader', [leer_modelo_comun, leer_modelo_inspeccion], ids=['runnable', 'inspection'])
def test_template_version_requires_integer(reader):
    model = cases()[0][2]
    model['template']['version'] = 1.0
    with pytest.raises(ErrorModelo) as caught:
        reader(model)
    assert caught.value.ruta == 'template'


if __name__ == '__main__':
    rows = cases()
    if '--cases' in sys.argv:
        print(json.dumps(rows)); sys.exit()
    for label, valid, model in rows:
        for reader in (leer_modelo_comun, leer_modelo_inspeccion):
            test_template_record(label, valid, model, reader)
    print(f'{2*len(rows)} template reader checks passed ({len(rows)} cases, runnable and inspection readers)')
