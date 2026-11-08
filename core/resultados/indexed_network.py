"""Versioned indexed publication metadata; no physical or numerical evaluation."""
import math


def read_indexed_network(result):
    from .formato import ErrorResultados
    value = result.get('indexedNetwork')
    if 'indexedNetwork' not in result:
        return None

    def fail(path, message):
        raise ErrorResultados('indexedNetwork'+path, message)

    def obj(row, keys, path):
        if not isinstance(row, dict) or set(row) != set(keys):
            fail(path, 'Expected exactly: '+', '.join(keys))

    def text(row, path):
        if not isinstance(row, str) or not row.strip():
            fail(path, 'Expected nonempty text.')

    def array(row, path):
        if not isinstance(row, list):
            fail(path, 'Expected an array.')

    fields = ['version','indexSetId','count','mode','stageAxisId','stages','endPorts','profiles']
    if isinstance(value, dict) and value.get('version') in (2, 3):
        fields.append('sidePorts')
    if isinstance(value, dict) and value.get('version') == 3:
        fields.append('display')
    obj(value, fields, '')
    if type(value['version']) not in (int,float) or value['version'] not in (1,2,3):
        fail('.version', 'Expected version 1, 2 or 3.')
    text(value['indexSetId'], '.indexSetId')
    count = value['count']
    if type(count) not in (int,float) or not 0 < count <= 9007199254740991 or int(count) != count:
        fail('.count', 'Expected a positive safe integer.')
    count = int(count)
    if value['mode'] not in ('dynamic','steady'):
        fail('.mode', 'Expected dynamic or steady.')
    for key in ('stages','endPorts','profiles'):
        array(value[key], '.'+key)
    if value['version'] in (2, 3):
        array(value['sidePorts'], '.sidePorts')
    if len(value['stages']) != count:
        fail('.stages', 'Stage count differs from n.')
    series = {row['id']:row for row in result['series']}
    checks = {row['id']:row for row in result['verificaciones']}
    if len(checks) != len(result['verificaciones']):
        fail('.stages', 'Certificate verification identities must be unique.')
    used = set()
    def finite_values(values):
        if isinstance(values,list):
            return all(finite_values(v) for v in values)
        return values is None or type(values) in (int,float) and math.isfinite(values)
    for index, stage in enumerate(value['stages'], 1):
        path = f'.stages[{index-1}]'
        obj(stage, ['index','ownerId','seriesIds','closures'], path)
        owner = value['indexSetId']+'.stage.'+str(index)
        if type(stage['index']) not in (int,float) or stage['index'] != index or stage['ownerId'] != owner:
            fail(path, 'Expected ordered stage index and canonical stage owner.')
        array(stage['seriesIds'], path+'.seriesIds')
        if not stage['seriesIds'] or any(not isinstance(k,str) for k in stage['seriesIds']):
            fail(path+'.seriesIds', 'Expected stage series identities.')
        if len(set(stage['seriesIds'])) != len(stage['seriesIds']):
            fail(path+'.seriesIds', 'Repeated series identity.')
        for key in stage['seriesIds']:
            row = series.get(key)
            if row is None or row.get('propietarioId') != owner or not key.startswith(owner+'.') or key in used:
                fail(path+'.seriesIds', 'Missing, repeated or foreign stage series.')
            if value['mode'] == 'steady' and row['ejes']:
                fail(path+'.seriesIds', 'Steady stage values must be scalar.')
            if not finite_values(row['valores']):
                fail(path+'.seriesIds', 'Expected finite published numbers or null.')
            used.add(key)
        array(stage['closures'], path+'.closures')
        volumes = set()
        for ci, closure in enumerate(stage['closures']):
            cp = path+f'.closures[{ci}]'
            obj(closure, ['volumeId','mode','verificationId'], cp)
            volume = closure['volumeId']
            text(volume, cp+'.volumeId')
            if not volume.startswith(owner+'.volume.') or volume in volumes:
                fail(cp, 'Expected a distinct stage-local closure volume.')
            volumes.add(volume)
            if closure['mode'] not in ('equilibrium','single_phase'):
                fail(cp+'.mode', 'Unknown closure certificate mode.')
            key = 'thermodynamics.closure.'+volume
            if closure['verificationId'] != key or key not in checks:
                fail(cp, 'Missing stage-local closure certificate verification.')
            check = checks[key]
            tolerance = 1. if closure['mode'] == 'equilibrium' else 1e-9
            if (type(check['valor']) not in (int,float) or not math.isfinite(check['valor'])
                    or check['valor'] < 0 or type(check['tolerancia']) not in (int,float) or check['tolerancia'] != tolerance
                    or result['estado'] == 'resuelto' and check['valor'] > tolerance):
                fail(cp, 'Invalid or failed closure certificate summary.')
    ports = set()
    boundaries = [(f'.endPorts[{i}]', p, False) for i,p in enumerate(value['endPorts'])]
    boundaries += [(f'.sidePorts[{i}]', p, True) for i,p in enumerate(value.get('sidePorts', []))]
    for path, port, interior in boundaries:
        obj(port, ['portId','stage','kind','direction','variables'], path)
        text(port['portId'], path+'.portId')
        if port['portId'] in ports:
            fail(path, 'Repeated end-port identity.')
        ports.add(port['portId'])
        stage_index = port['stage']
        if (type(stage_index) not in (int,float) or not math.isfinite(stage_index)
                or int(stage_index) != stage_index or
                not (1 < stage_index < count if interior else stage_index in (1,count))):
            fail(path+'.stage', 'Side ports require an interior stage; end ports require stage 1 or n.')
        if port['kind'] not in ('material','heat','work') or port['direction'] not in ('inlet','outlet'):
            fail(path, 'Invalid typed end port.')
        roles = ['flow','composition','temperature','pressure','specificEnthalpy'] if port['kind']=='material' else ['power']
        obj(port['variables'], roles, path+'.variables')
        ids = []
        for role, binding in port['variables'].items():
            if role == 'composition':
                array(binding, path+'.variables.composition')
                if not binding:
                    fail(path, 'Composition requires at least one component series.')
                ids.extend(binding)
            else:
                ids.append(binding)
        stage = value['stages'][int(port['stage'])-1]
        if any(not isinstance(k,str) or k not in stage['seriesIds'] for k in ids) or len(set(ids)) != len(ids):
            fail(path+'.variables', 'End-port variables must reference distinct series of their stage.')
        units = {'temperature':('K',),'pressure':('Pa',),'specificEnthalpy':('J/kg','J/mol'),
                 'flow':('kg/s','mol/s'),'power':('W',),'composition':('1',)}
        for role,binding in port['variables'].items():
            for key in binding if role=='composition' else [binding]:
                if series[key]['unidadSI'] not in units[role]:
                    fail(path+'.variables.'+role, 'End-port variable has incompatible SI units.')
        if port['kind']=='material':
            expected = 'J/kg' if series[port['variables']['flow']]['unidadSI']=='kg/s' else 'J/mol'
            if series[port['variables']['specificEnthalpy']]['unidadSI'] != expected:
                fail(path+'.variables', 'Flow and specific enthalpy bases differ.')
    if value['mode']=='dynamic':
        if value['stageAxisId'] is not None or value['profiles']:
            fail('.profiles', 'Dynamic publication has no steady stage profiles.')
    else:
        axis = next((a for a in result['ejes'] if a['id']==value['stageAxisId']), None)
        if (axis is None or axis['rol']!='parametro' or axis['unidadSI']!='1' or axis['dimension']
                or any(type(v) not in (int,float) for v in axis['valores'])
                or axis['valores'] != list(range(1,count+1))):
            fail('.stageAxisId', 'Expected the dimensionless ordered stage axis j=1..n.')
        profiles = set()
        for index, profile in enumerate(value['profiles']):
            path = f'.profiles[{index}]'
            obj(profile, ['seriesId','stageSeriesIds'], path)
            key = profile['seriesId']
            if not isinstance(key,str) or key not in series or key in used or key in profiles:
                fail(path, 'Missing, repeated or stage-owned profile.')
            profiles.add(key)
            array(profile['stageSeriesIds'], path+'.stageSeriesIds')
            if len(profile['stageSeriesIds']) != count:
                fail(path, 'A profile requires one source per stage.')
            row = series[key]
            if row['ejes'] != [axis['id']] or row.get('propietarioId') != value['indexSetId']:
                fail(path, 'Profile owner or axis differs from the index set.')
            for stage_index, source in enumerate(profile['stageSeriesIds']):
                if source is None and value['version'] == 3:
                    if row['valores'][stage_index] is not None:
                        fail(path, 'A stage without the quantity must publish an undefined profile value.')
                    continue
                if not isinstance(source,str) or source not in value['stages'][stage_index]['seriesIds']:
                    fail(path, 'Profile sources must follow stage order.')
                original = series[source]
                if (original['unidadSI'] != row['unidadSI'] or original['dimension'] != row['dimension']
                        or original['valores'] != row['valores'][stage_index]):
                    fail(path, 'Profile must preserve each scalar source value and unit.')
    if value['version'] == 3:
        array(value['display'], '.display')
        shown = set()
        needed = set(used) | {p['seriesId'] for p in value['profiles']}
        for index, entry in enumerate(value['display']):
            path = f'.display[{index}]'
            obj(entry, ['seriesId','label','rank','group'], path)
            for key in ('seriesId','label','group'):
                text(entry[key], path+'.'+key)
            if entry['seriesId'] not in needed or entry['seriesId'] in shown:
                fail(path, 'Display entries must name each stage or profile series once.')
            if type(entry['rank']) is not int or not 0 <= entry['rank'] <= 99:
                fail(path+'.rank', 'Expected an integer rank from 0 to 99.')
            shown.add(entry['seriesId'])
        if shown != needed:
            fail('.display', 'Every stage and profile series needs a display entry.')
    return value
