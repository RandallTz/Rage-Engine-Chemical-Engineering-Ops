"""Strict indexed-template topology and replay expansion; no numerical lowering."""
from copy import deepcopy
import hashlib
import json
import re
from functools import lru_cache

@lru_cache(maxsize=32)
def _replayed_stage(source_json, namespace):
    from .template_instance import instantiate_template
    return instantiate_template(json.loads(source_json), identity_namespace=namespace)


def read_index_set(model):
    from .lector import _claves, _fallo, _texto, leer_modelo_comun
    def fail(path, message):
        _fallo('indexSet.' + path, message)
    record = _claves(model['indexSet'], 'indexSet', ['format', 'version', 'id', 'index', 'countDataId',
        'templates', 'genericStage', 'variants', 'connections', 'exposures'])
    if record['format'] != 'rage.index-set' or type(record['version']) is not int or record['version'] != 1:
        fail('version', 'Expected rage.index-set version 1.')
    for field in ('id', 'index', 'countDataId', 'genericStage'):
        _texto(record[field], 'indexSet.' + field)
    datum = model['datos'].get(record['countDataId'])
    if not datum or datum['funcion'] != 'estudio' or datum['declaracion']['unidad'] != '1':
        fail('countDataId', 'The count requires a dimensionless Solve datum (estudio, unit 1).')
    text = datum['declaracion']['texto']
    if not isinstance(text, str) or not re.fullmatch(r'[+]?[0-9]+(?:\.0*)?', text):
        fail('countDataId', 'The count must be a positive integer literal.')
    n = int(text.split('.')[0])
    if not 1 <= n <= 256:
        fail('countDataId', 'Version 1 admits one to 256 stages.')
    templates = record['templates']
    if not isinstance(templates, dict) or not templates:
        fail('templates', 'At least one embedded template document is required.')
    for key, source in templates.items():
        _texto(key, 'indexSet.templates')
        if not isinstance(source, dict) or 'indexSet' in source:
            fail('templates.' + key, 'Nested index sets are not admitted.')
        leer_modelo_comun(source)
        if not source.get('template', {}).get('equipment'):
            fail('templates.' + key, 'A stage requires an equipment-marked recorded template.')
    if record['genericStage'] not in templates:
        fail('genericStage', 'Unknown template reference.')
    generic = templates[record['genericStage']]
    for field in ('componentes', 'termodinamica', 'volumenes', 'corrientes', 'intercambios', 'matematico',
                  'motores', 'template', 'restricciones', 'observables', 'verificaciones'):
        if model.get(field) != generic.get(field):
            fail('genericStage', 'The worksheet must retain the generic template physical definition: ' + field)
    if record['countDataId'] in generic['datos'] or {k: v for k, v in model['datos'].items() if k != record['countDataId']} != generic['datos']:
        fail('countDataId', 'The worksheet data must be the generic defaults plus the separate stage-count datum.')
    for field in ('variants', 'connections', 'exposures'):
        if not isinstance(record[field], list):
            fail(field, 'Expected a list.')

    def indices(at, path):
        if at == 'each': return list(range(1, n + 1))
        if at == 'first': return [1]
        if at == 'last': return [n]
        if type(at) is int and 1 <= at <= n: return [at]
        fail(path, 'Expected first, last, each or an existing integer index.')

    stages = {j: record['genericStage'] for j in range(1, n + 1)}
    changed = set()
    for i, variant in enumerate(record['variants']):
        path = f'variants[{i}]'
        _claves(variant, 'indexSet.' + path, ['at', 'template'])
        if variant['at'] == 'each' or not isinstance(variant['template'], str) or variant['template'] not in templates:
            fail(path, 'A variant requires one index and an existing template.')
        j = indices(variant['at'], path)[0]
        if j in changed: fail(path, 'Overlapping variants.')
        changed.add(j); stages[j] = variant['template']
    ports = {(j, p['id']): p for j, key in stages.items() for p in templates[key]['template']['ports']}
    used = set(); links = []; exposed = []; ids = set()

    def take(j, port, path):
        if not isinstance(port, str) or (j, port) not in ports:
            fail(path, 'Port does not exist on the selected stage template.')
        if (j, port) in used: fail(path, 'A stage port is bound more than once.')
        used.add((j, port)); return ports[j, port]

    for i, rule in enumerate(record['connections']):
        path = f'connections[{i}]'
        _claves(rule, 'indexSet.' + path, ['outlet', 'inlet', 'offset'])
        if type(rule['offset']) is not int or rule['offset'] not in (-1, 1):
            fail(path, 'A connection offset must be -1 or +1.')
        # Even a singleton must reference real, compatible port declarations.
        for j in stages:
            for field, direction in [('outlet', 'outlet'), ('inlet', 'inlet')]:
                p = ports.get((j, rule[field])) if isinstance(rule[field], str) else None
                if p is None or p['direction'] != direction:
                    fail(path, 'Unknown port or incompatible direction.')
            a, b = ports[j, rule['outlet']], ports[j, rule['inlet']]
            if a['kind'] != b['kind'] or a['variables'] != b['variables']:
                fail(path, 'Connected ports require identical kinds and SI variable contracts.')
        for j in stages:
            k = j + rule['offset']
            if k not in stages: continue
            a, b = take(j, rule['outlet'], path), take(k, rule['inlet'], path)
            if a['kind'] != b['kind'] or a['variables'] != b['variables']:
                fail(path, 'Connected ports require identical kinds and SI variable contracts.')
            if a['kind'] == 'material' and templates[stages[j]]['componentes'] != templates[stages[k]]['componentes']:
                fail(path, 'Connected material stages require the same ordered component declarations.')
            links.append({'from': [j, rule['outlet']], 'to': [k, rule['inlet']], 'kind': a['kind']})
    for i, rule in enumerate(record['exposures']):
        path = f'exposures[{i}]'
        _claves(rule, 'indexSet.' + path, ['id', 'port', 'at'])
        _texto(rule['id'], 'indexSet.' + path + '.id')
        if rule['id'] in ids: fail(path, 'Duplicate exposed-port identity.')
        ids.add(rule['id'])
        for j in indices(rule['at'], path):
            p = take(j, rule['port'], path)
            exposed.append({'id': rule['id'] + '.' + str(j), 'stage': j, 'port': rule['port'], 'declaration': p})
    if used != set(ports): fail('connections', 'Every stage port must be connected or explicitly exposed.')
    return record, n, stages, links, exposed


def expand_index_set(model):
    from .lector import leer_modelo_comun
    from .template_instance import instantiate_template, TemplateInstanceError
    model = leer_modelo_comun(model)
    record, n, stages, links, exposed = read_index_set(model)
    instances = {}
    for j, key in stages.items():
        # n is intentionally absent: unchanged stages retain their identities on resizing.
        namespace = json.dumps([model['id'], record['id'], j, key], separators=(',', ':'))
        try:
            instances[j] = deepcopy(_replayed_stage(json.dumps(record['templates'][key], sort_keys=True, separators=(',', ':')), namespace))
        except TemplateInstanceError as error:
            path = error.diagnostics[0]['path']
            raise TemplateInstanceError(f'indexSet.templates.{key}.{path}', f'Stage {j}: {error}') from error
    def endpoint(value):
        j, port = value
        instance = instances[j]; mapping = instance['provenance']['identityMap']
        p = next(p for p in instance['model']['template']['ports'] if p['id'] == mapping['ports'][port])
        return {'stage': j, 'modelId': instance['model']['id'], 'portId': p['id'], 'volumeId': p['volumeId'], 'boundary': deepcopy(p['boundary'])}
    connections = []; streams = []
    for i, link in enumerate(links):
        a, b = endpoint(link['from']), endpoint(link['to'])
        connection = {'id': record['id'] + '.connection.' + str(i + 1), 'kind': link['kind'], 'from': a, 'to': b}
        connections.append(connection)
        if link['kind'] == 'material':
            source = instances[a['stage']]['model']
            stream = deepcopy(next(s for s in source['corrientes'] if s['id'] == a['boundary']['id']))
            stream.update(id=connection['id'], desde=a['volumeId'], hasta=b['volumeId'])
            stream.pop('estadoExterior', None)
            streams.append({'stream': stream, 'dataModelId': source['id'], 'replaces': [a, b]})
    published_ports = []
    for row in exposed:
        end = endpoint([row['stage'], row['port']])
        declaration = deepcopy(next(p for p in instances[row['stage']]['model']['template']['ports'] if p['id'] == end['portId']))
        declaration['id'] = row['id']
        published_ports.append({'endpoint': end, 'port': declaration})
    signature = hashlib.sha256(json.dumps(model, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    return {'format': 'rage.index-set-expansion', 'version': 1, 'sourceModelId': model['id'], 'sourceSignature': signature,
        'indexSetId': record['id'], 'count': n, 'stages': [{'index': j, 'template': stages[j], **response} for j, response in instances.items()],
        'connections': connections, 'internalStreams': streams, 'ports': published_ports, 'execution': 'not_lowered'}
