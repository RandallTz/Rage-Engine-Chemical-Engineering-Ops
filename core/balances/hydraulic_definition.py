"""Versioned data/geometry bindings for reduced constant-density hydraulics.

No equipment names, trajectories or terminal equations are accepted here.
Conservation and wall/pressure relations come from replayed physical journals.
"""
from core.modelo.operation_journal import JournalError, keys

FORMAT = 'rage.hydraulic-network'
PATH_DATA = {'lengthId':'m','areaId':'m2','diameterId':'m','driveId':'Pa','inletElevationId':'m','outletElevationId':'m'}
STORAGE_DATA = {'areaId':'m2','surfacePressureId':'Pa','floorElevationId':'m'}


def read_definition(value, model=None):
    keys(value, ['format','version','medium','gravityId','storages','paths'])
    if value['format']!=FORMAT or type(value['version']) is not int or value['version']!=1:
        raise JournalError('Unsupported hydraulic network version.')
    keys(value['medium'], ['densityId','viscosityId','temperatureId','minimumPressureId','reason'])
    if not isinstance(value['medium']['reason'],str) or not value['medium']['reason'].strip():
        raise JournalError('The assumed medium needs an explicit validity reason.')
    for collection in ['storages','paths']:
        if not isinstance(value[collection],list) or len(value[collection])>160:
            raise JournalError('Expected at most 160 hydraulic entities per collection.')
    if not value['paths']:raise JournalError('Declare at least one momentum flow path.')
    owners=set(); refs=[value['gravityId']]+[v for k,v in value['medium'].items() if k!='reason']
    for storage in value['storages']:
        keys(storage,['volumeId',*STORAGE_DATA])
        refs.extend(storage[k] for k in STORAGE_DATA)
    for path in value['paths']:
        keys(path,['volumeId','inletStreamId','outletStreamId',*PATH_DATA,'flow','inletPressure','outletPressure'])
        refs.extend(path[k] for k in PATH_DATA)
        flow=path['flow'];keys(flow,['kind'],['datumId','initialId'])
        if flow['kind']=='prescribed':keys(flow,['kind','datumId']);refs.append(flow['datumId'])
        elif flow['kind']=='dynamic':keys(flow,['kind','initialId']);refs.append(flow['initialId'])
        else:raise JournalError('Flow is an imposed differentiable datum or a retained dynamic unknown.')
        for end in ['inletPressure','outletPressure']:
            p=path[end];keys(p,['kind'],['datumId','volumeId'])
            if p['kind']=='datum':keys(p,['kind','datumId']);refs.append(p['datumId'])
            elif p['kind']=='storage':keys(p,['kind','volumeId'])
            elif p['kind']=='recover':keys(p,['kind'])
            else:raise JournalError('Unknown hydraulic pressure boundary.')
        recover=sum(path[k]['kind']=='recover' for k in ['inletPressure','outletPressure'])
        if recover != int(flow['kind']=='prescribed'):
            raise JournalError('An imposed flow needs exactly one recovered pressure; dynamic flow needs two declared pressure relations.')
    for entity in value['storages']+value['paths']:
        owner=entity['volumeId']
        if not isinstance(owner,str) or not owner.strip() or owner in owners:raise JournalError('Distinct hydraulic volume identities are required.')
        owners.add(owner)
    if any(not isinstance(v,str) or not v.strip() for v in refs):raise JournalError('Hydraulic quantities reference explicit datum IDs.')
    if model is not None:
        volumes={v['id']:v for v in model['volumenes']};streams={s['id']:s for s in model['corrientes']};storages={s['volumeId'] for s in value['storages']}
        if owners!=set(volumes):raise JournalError('Every volume must have exactly one declared hydraulic role; no extra volume can be ignored.')
        if any(v not in model['datos'] for v in refs):raise JournalError('A hydraulic datum binding does not exist.')
        used=set()
        for path in value['paths']:
            for end,key,incident,other in [('inletPressure','inletStreamId','hasta','desde'),('outletPressure','outletStreamId','desde','hasta')]:
                sid=path[key];stream=streams.get(sid)
                if sid in used or stream is None or stream[incident]!=path['volumeId']:raise JournalError('Each path binds distinct incident oriented material streams.')
                used.add(sid);p=path[end]
                if p['kind']=='storage' and (p['volumeId'] not in storages or stream[other]!=p['volumeId']):raise JournalError('The pressure storage must be the actual adjacent material donor/receiver.')
                if p['kind']!='storage' and stream[other] is not None:raise JournalError('A datum/recovered boundary must be external, not an ignored internal volume.')
        if used!=set(streams):raise JournalError('Every stream must belong to a hydraulic path; no prescribed stream can be silently ignored.')
    return value
