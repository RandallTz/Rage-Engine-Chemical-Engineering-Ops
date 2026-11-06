"""Strict `rage.flowsheet` v1: separately identified recorded template instances.

A flowsheet is a common-model shell (no volumes, streams, exchanges or
journals of its own) carrying an optional `flowsheet` record and an optional,
presentation-only `flowsheetLayout` record. Each instance references one
embedded, equipment-marked recorded template, keeps its own identity and may
override declared data values of that template. Connections are explicit
endpoint pairs `instance.port -> instance.port`. Python replays every instance
through the existing template-instance service; it never appends authoring
operations. Numerical lowering lives in core/compilador/flowsheet_network.py.

Signatures: the source signature, which pins Transform/Solve selections and
results, covers the complete model except `flowsheetLayout`. Moving blocks is
therefore presentation only, while any topology, template or data edit
invalidates every downstream selection and result.
"""
from copy import deepcopy
import hashlib
import json
import math
import re
import struct
from functools import lru_cache

from .lector import ErrorModelo

FORMAT = 'rage.flowsheet'
LAYOUT_FORMAT = 'rage.flowsheet-layout'
EXPANSION_FORMAT = 'rage.flowsheet-expansion'
IDENTITY = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}')
NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?')
MAX_INSTANCES = 64


class FlowsheetError(ErrorModelo):
    """Located rejection with a stable code, shared by the TS reader."""
    def __init__(self, code, path, message):
        super().__init__(path, message)
        self.code = code
        self.diagnostics = [{'code': code, 'path': path, 'message': message}]


def fail(code, path, message):
    raise FlowsheetError(code, path, message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _portable(item):
    # Same canonicalization as core.compilador.steady.signature: every JSON
    # number is replaced by its exact binary64 bytes, so 0.0 and 0 (the
    # browser spelling after JSON.parse/JSON.stringify) sign identically.
    if isinstance(item, (int, float)) and not isinstance(item, bool):
        if not math.isfinite(item):
            raise ValueError('Nonfinite signature value.')
        return {'$binary64': struct.pack('>d', float(item)).hex()}
    if isinstance(item, dict):
        return {key: _portable(value) for key, value in item.items()}
    if isinstance(item, list):
        return [_portable(value) for value in item]
    return item


def digest(value):
    """Portable fingerprint, equal to core.compilador.steady.signature for JSON values."""
    return hashlib.sha256(canonical(_portable(value)).encode('utf-8')).hexdigest()


def source_signature(model):
    """Pins the executable source: everything except the presentation layout."""
    return digest({k: v for k, v in model.items() if k != 'flowsheetLayout'})


def _exact(value, path, fields, optional=()):
    if not isinstance(value, dict):
        fail('flowsheet_invalid', path, 'Expected an object.')
    missing = [k for k in fields if k not in value]
    extra = [k for k in value if k not in fields and k not in optional]
    if missing or extra:
        fail('flowsheet_invalid', path, 'Unknown or missing fields: ' + ', '.join(missing + extra))
    return value


def _identity(value, path):
    if not isinstance(value, str) or not IDENTITY.fullmatch(value):
        fail('flowsheet_invalid_identity', path, 'Expected an identity matching [A-Za-z][A-Za-z0-9_-]{0,63}.')


def _list(value, path):
    if not isinstance(value, list):
        fail('flowsheet_invalid', path, 'Expected a list.')
    return value


def _stream_species(template, stream_id):
    stream = next(s for s in template['corrientes'] if s['id'] == stream_id)
    chemicals = {c['id']: (c.get('identidadQuimica') or {}).get('cas') for c in template['componentes']}
    return [chemicals.get(i) for i in stream['componenteIds']]


def _thermodynamic_identity(template, volume_id):
    """Package model and energy reference of the closure that owns a port state.

    A port on a volume without its own closure (a transport path) takes the
    state of the package volume that feeds it, following the recorded streams.
    """
    seen = set()
    current = volume_id
    while current not in seen:
        seen.add(current)
        volume = next((v for v in template['volumenes'] if v['id'] == current), None)
        if volume is None:
            return None
        closure = volume.get('termodinamica') or {}
        if closure.get('tipo') == 'equilibrio':
            package = next((p for p in template['termodinamica']['paquetes'] if p['id'] == closure.get('paqueteId')), None)
            if package is None:
                return None
            energy = (volume.get('supuestos') or {}).get('energia') or {}
            return {'package': deepcopy(package['modelo']), 'formationReference': energy.get('referenciaFormacion')}
        donors = [s['desde'] for s in template['corrientes'] if s.get('hasta') == current and s.get('desde')]
        if len(donors) != 1:
            return None
        current = donors[0]
    return None


def _effective_template(template, instance, model):
    """The recorded template with this instance's data values and the shared study.

    Only declared values change. Units, roles, owners and every recorded
    operation stay as recorded, so the template signatures remain valid.
    """
    effective = deepcopy(template)
    for key, declaration in instance['data'].items():
        effective['datos'][key]['declaracion'] = deepcopy(declaration)
    study = model['estudio']
    local = effective['estudio']
    horizon = model['datos'][study['tiempoId']]['declaracion']
    effective['datos'][local['tiempoId']]['declaracion'] = deepcopy(horizon)
    for field in ('metodoSolicitado', 'muestras', 'rtol', 'atol'):
        local[field] = deepcopy(study[field])
    return effective


def read_flowsheet(model):
    """Structural, compatibility and topology admission; no replay."""
    from .lector import leer_modelo_comun
    record = _exact(model['flowsheet'], 'flowsheet',
                    ['format', 'version', 'id', 'templates', 'instances', 'connections', 'exposures', 'recycles'])
    if record['format'] != FORMAT or type(record['version']) is not int or record['version'] != 1:
        fail('flowsheet_version', 'flowsheet.version', 'Expected rage.flowsheet version 1.')
    _identity(record['id'], 'flowsheet.id')
    for field in ('volumenes', 'corrientes', 'intercambios'):
        if model[field] != []:
            fail('flowsheet_shell', field, 'A flowsheet shell owns no physical volumes, streams or exchanges; instances do.')
    if model['motores'] != {} or model['matematico'] is not None or 'template' in model or 'indexSet' in model:
        fail('flowsheet_shell', 'motores', 'A flowsheet shell carries no journals, mathematical document, template or index set.')
    study = model['estudio']
    if not isinstance(study, dict) or study.get('tipo') != 'temporal':
        fail('flowsheet_study', 'estudio', 'A flowsheet requires one temporal study shared by every instance.')
    if model['datos'][study['tiempoId']]['declaracion']['unidad'] != 's':
        fail('flowsheet_study', 'estudio.tiempoId', 'The shared horizon must be declared in seconds.')
    templates = record['templates']
    if not isinstance(templates, dict) or not templates:
        fail('flowsheet_invalid', 'flowsheet.templates', 'At least one embedded template document is required.')
    for key, source in templates.items():
        path = 'flowsheet.templates.' + str(key)
        _identity(key, path)
        if not isinstance(source, dict) or 'indexSet' in source or 'flowsheet' in source:
            fail('flowsheet_nested', path, 'Nested index sets or flowsheets are not admitted in version 1.')
        try:
            leer_modelo_comun(source)
        except FlowsheetError:
            raise
        except ErrorModelo as error:
            fail('flowsheet_template_invalid', path + '.' + error.ruta, error.mensaje)
        if not (source.get('template') or {}).get('equipment'):
            fail('flowsheet_template_unmarked', path, 'An instance requires an equipment-marked recorded template.')
        local = source.get('estudio')
        if not isinstance(local, dict) or local.get('tipo') != 'temporal' or source['datos'][local['tiempoId']]['declaracion']['unidad'] != 's':
            fail('flowsheet_study', path + '.estudio', 'Each template requires a temporal study with a horizon in seconds.')
    instances = _list(record['instances'], 'flowsheet.instances')
    if not 1 <= len(instances) <= MAX_INSTANCES:
        fail('flowsheet_invalid', 'flowsheet.instances', 'Version 1 admits one to 64 instances.')
    by_id = {}
    for i, row in enumerate(instances):
        path = f'flowsheet.instances[{i}]'
        _exact(row, path, ['id', 'template', 'data'])
        _identity(row['id'], path + '.id')
        if row['id'] in by_id:
            fail('flowsheet_duplicate_instance', path + '.id', 'Duplicate instance identity.')
        if not isinstance(row['template'], str) or row['template'] not in templates:
            fail('flowsheet_unknown_template', path + '.template', 'Unknown template reference.')
        source = templates[row['template']]
        if not isinstance(row['data'], dict):
            fail('flowsheet_invalid', path + '.data', 'Expected an object of declared data values.')
        for key, declaration in row['data'].items():
            where = path + '.data.' + str(key)
            datum = source['datos'].get(key)
            if datum is None:
                fail('flowsheet_unknown_datum', where, 'Only data declared by the template can be given instance values.')
            _exact(declaration, where, ['texto', 'unidad'])
            text = declaration['texto']
            if (not isinstance(text, str) or not NUMBER.fullmatch(text)
                    or not math.isfinite(float(text))):
                fail('flowsheet_invalid_datum', where, 'Expected a finite numeric literal.')
            if declaration['unidad'] != datum['declaracion']['unidad']:
                fail('flowsheet_datum_unit', where, 'An instance value keeps the declared unit of its template datum.')
            if key == source['estudio']['tiempoId']:
                fail('flowsheet_study', where, 'The horizon is the shared flowsheet study, not an instance datum.')
        by_id[row['id']] = row
    ports = {}
    for row in instances:
        for port in templates[row['template']]['template']['ports']:
            ports[row['id'], port['id']] = port
    used = {}
    connection_ids = set()

    def take(endpoint, path, direction):
        _exact(endpoint, path, ['instance', 'port'])
        if not isinstance(endpoint['instance'], str) or endpoint['instance'] not in by_id:
            fail('flowsheet_unknown_instance', path + '.instance', 'Unknown instance.')
        key = (endpoint['instance'], endpoint['port'])
        port = ports.get(key) if isinstance(endpoint['port'], str) else None
        if port is None:
            fail('flowsheet_unknown_port', path + '.port', 'Port does not exist on the instance template.')
        if port['direction'] != direction:
            fail('flowsheet_port_direction', path + '.port', f'Expected an {direction} port.')
        if key in used:
            fail('flowsheet_port_reused', path, 'This instance port is already bound at ' + used[key] + '.')
        used[key] = path
        return port

    connections = _list(record['connections'], 'flowsheet.connections')
    edges = []
    for i, row in enumerate(connections):
        path = f'flowsheet.connections[{i}]'
        _exact(row, path, ['id', 'from', 'to'])
        _identity(row['id'], path + '.id')
        if row['id'] in connection_ids:
            fail('flowsheet_duplicate_connection', path + '.id', 'Duplicate connection identity.')
        connection_ids.add(row['id'])
        # Once its identity is valid and unique, a connection is located by
        # identity, the same form the assembly uses (flowsheet.connections.<id>).
        path = 'flowsheet.connections.' + row['id']
        if not isinstance(row['from'], dict) or not isinstance(row['to'], dict):
            fail('flowsheet_invalid', path, 'Expected from and to endpoints.')
        origin = row['from'].get('instance')
        if isinstance(origin, str) and origin == row['to'].get('instance') and origin in by_id:
            fail('flowsheet_self_connection', path, 'A connection joins two different instances.')
        a = take(row['from'], path + '.from', 'outlet')
        b = take(row['to'], path + '.to', 'inlet')
        if a['kind'] != b['kind'] or canonical(a['variables']) != canonical(b['variables']):
            fail('flowsheet_port_kind', path, 'Connected ports require identical kinds and SI variable contracts.')
        if a['kind'] != 'material':
            fail('flowsheet_unsupported_connection', path, 'Version 1 connects material ports; heat and work ports are exposed.')
        donor = templates[by_id[row['from']['instance']]['template']]
        receiver = templates[by_id[row['to']['instance']]['template']]
        if a['boundary']['type'] != 'stream' or b['boundary']['type'] != 'stream' or b.get('exteriorState') != 'estadoExterior':
            fail('flowsheet_port_kind', path, 'A material connection joins a drawn outlet stream to an inlet with a declared exterior state.')
        species = _stream_species(donor, a['boundary']['id'])
        target = _stream_species(receiver, b['boundary']['id'])
        if (any(not s for s in species + target) or len(set(species)) != len(species)
                or len(set(target)) != len(target) or set(species) != set(target)):
            fail('flowsheet_component_mismatch', path, 'Connected streams require the same distinct chemical identities (CAS).')
        left = _thermodynamic_identity(donor, a['volumeId'])
        right = _thermodynamic_identity(receiver, b['volumeId'])
        if left is None or right is None:
            fail('flowsheet_thermodynamic_unresolved', path, 'Each connected port state must belong to a recorded package closure.')
        if left != right:
            fail('flowsheet_thermodynamic_mismatch', path, 'Connected states require the same package model and the same recorded energy reference.')
        edges.append((row['id'], row['from']['instance'], row['to']['instance']))
    exposed = []
    for i, row in enumerate(_list(record['exposures'], 'flowsheet.exposures')):
        path = f'flowsheet.exposures[{i}]'
        _exact(row, path, ['id', 'instance', 'port'])
        _identity(row['id'], path + '.id')
        if row['id'] in connection_ids or any(e['id'] == row['id'] for e in exposed):
            fail('flowsheet_duplicate_exposure', path + '.id', 'Duplicate exposed-port or connection identity.')
        if not isinstance(row['instance'], str) or row['instance'] not in by_id:
            fail('flowsheet_unknown_instance', path + '.instance', 'Unknown instance.')
        key = (row['instance'], row['port'])
        if not isinstance(row['port'], str) or key not in ports:
            fail('flowsheet_unknown_port', path + '.port', 'Port does not exist on the instance template.')
        if key in used:
            fail('flowsheet_port_reused', path, 'This instance port is already bound at ' + used[key] + '.')
        used[key] = path
        exposed.append(row)
    for key in ports:
        if key not in used:
            fail('flowsheet_dangling_port', 'flowsheet.instances[' + str(list(by_id).index(key[0])) + ']',
                 f'Port {key[1]} of instance {key[0]} must be connected or explicitly exposed.')
    recycles = _list(record['recycles'], 'flowsheet.recycles')
    if (any(not isinstance(r, str) for r in recycles) or len(set(recycles)) != len(recycles)
            or any(r not in connection_ids for r in recycles)):
        fail('flowsheet_unknown_recycle', 'flowsheet.recycles', 'Recycles list distinct existing connection identities.')
    _check_cycles(edges, set(recycles), [row['id'] for row in instances])
    return record


def _check_cycles(edges, recycles, order):
    """Every directed cycle must contain a declared recycle connection."""
    graph = {node: [] for node in order}
    full = {node: [] for node in order}
    for key, a, b in edges:
        full[a].append(b)
        if key not in recycles:
            graph[a].append((b, key))
    state, stack = {}, []

    def visit(node):
        state[node] = 1
        stack.append(node)
        for target, key in graph[node]:
            if state.get(target) == 1:
                start = stack.index(target)
                names = [k for k, a, b in edges if k not in recycles and a in stack[start:] and b in stack[start:]]
                fail('flowsheet_undeclared_cycle', 'flowsheet.recycles',
                     'The connections ' + ', '.join(names) + ' form a cycle; declare one of them as a recycle.')
            if state.get(target) is None:
                visit(target)
        stack.pop()
        state[node] = 2
    for node in order:
        if state.get(node) is None:
            visit(node)
    for key in recycles:
        a, b = next((a, b) for k, a, b in edges if k == key)
        seen, frontier = set(), [b]
        while frontier:
            node = frontier.pop()
            if node not in seen:
                seen.add(node)
                frontier.extend(full[node])
        if a not in seen:
            fail('flowsheet_recycle_not_cycle', 'flowsheet.recycles', f'Connection {key} does not close a cycle.')


def read_layout(model):
    """Presentation only: block coordinates and optional stream polylines."""
    layout = _exact(model['flowsheetLayout'], 'flowsheetLayout', ['format', 'version', 'flowsheetId', 'blocks'], ['streams'])
    if layout['format'] != LAYOUT_FORMAT or type(layout['version']) is not int or layout['version'] != 1:
        fail('flowsheet_layout_version', 'flowsheetLayout.version', 'Expected rage.flowsheet-layout version 1.')
    if 'flowsheet' not in model or layout['flowsheetId'] != model['flowsheet']['id']:
        fail('flowsheet_layout_foreign', 'flowsheetLayout.flowsheetId', 'The layout belongs to another flowsheet.')
    instances = {row['id'] for row in model['flowsheet']['instances']}
    connections = {row['id'] for row in model['flowsheet']['connections']}

    def point(value, path):
        if (not isinstance(value, list) or len(value) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value)):
            fail('flowsheet_layout_invalid', path, 'Expected a finite [x, y] point.')
    if not isinstance(layout['blocks'], dict):
        fail('flowsheet_layout_invalid', 'flowsheetLayout.blocks', 'Expected an object keyed by instance.')
    for key, block in layout['blocks'].items():
        path = 'flowsheetLayout.blocks.' + str(key)
        if key not in instances:
            fail('flowsheet_layout_foreign', path, 'Unknown instance.')
        _exact(block, path, ['position'])
        point(block['position'], path + '.position')
    streams = layout.get('streams', {})
    if not isinstance(streams, dict):
        fail('flowsheet_layout_invalid', 'flowsheetLayout.streams', 'Expected an object keyed by connection.')
    for key, stream in streams.items():
        path = 'flowsheetLayout.streams.' + str(key)
        if key not in connections:
            fail('flowsheet_layout_foreign', path, 'Unknown connection.')
        _exact(stream, path, ['points'])
        for i, value in enumerate(_list(stream['points'], path + '.points')):
            point(value, f'{path}.points[{i}]')
    return layout


@lru_cache(maxsize=32)
def _replayed(source_json, namespace):
    from .template_instance import instantiate_template
    return instantiate_template(json.loads(source_json), identity_namespace=namespace)


def plan_key(row, effective):
    """Instances with identical effective templates share one compiled plan."""
    return row['template'] + '@' + digest(effective)[:16]


def expand_flowsheet(model):
    """Replay every instance under its own deterministic identity namespace."""
    from .lector import leer_modelo_comun
    from .template_instance import TemplateInstanceError
    model = leer_modelo_comun(model)
    if 'flowsheet' not in model:
        fail('flowsheet_missing', 'flowsheet', 'A flowsheet record is required.')
    record = model['flowsheet']
    stages, plans = [], {}
    for j, row in enumerate(record['instances'], 1):
        effective = _effective_template(record['templates'][row['template']], row, model)
        key = plan_key(row, effective)
        plans[key] = effective
        # Data values and positions are not part of the identity: editing a
        # value keeps identities and still invalidates through the signature.
        namespace = json.dumps([model['id'], record['id'], row['id'], row['template']], separators=(',', ':'))
        try:
            response = deepcopy(_replayed(canonical(effective), namespace))
        except TemplateInstanceError as error:
            path = error.diagnostics[0]['path']
            raise FlowsheetError('flowsheet_replay_failed', f'flowsheet.templates.{row["template"]}.{path}',
                                 f'Instance {row["id"]}: {error}') from error
        instance_signature = digest({'template': record['templates'][row['template']], 'instance': row,
                                     'study': model['estudio'], 'horizon': model['datos'][model['estudio']['tiempoId']],
                                     'replay': response['provenance']['instanceSignature']})
        stages.append({'index': j, 'instanceId': row['id'], 'template': key, 'templateRef': row['template'],
                       'signature': instance_signature, **response})
    position = {row['instanceId']: row['index'] for row in stages}

    def endpoint(value):
        stage = stages[position[value['instance']] - 1]
        mapping = stage['provenance']['identityMap']
        port = next(p for p in stage['model']['template']['ports'] if p['id'] == mapping['ports'][value['port']])
        return {'stage': stage['index'], 'instanceId': stage['instanceId'], 'modelId': stage['model']['id'],
                'port': value['port'], 'portId': port['id'], 'volumeId': port['volumeId'], 'boundary': deepcopy(port['boundary'])}
    connections, streams = [], []
    for row in record['connections']:
        a, b = endpoint(row['from']), endpoint(row['to'])
        signature = digest({'connection': row, 'from': stages[a['stage'] - 1]['signature'], 'to': stages[b['stage'] - 1]['signature']})
        connection = {'id': row['id'], 'kind': 'material', 'from': a, 'to': b,
                      'recycle': row['id'] in record['recycles'], 'signature': signature}
        connections.append(connection)
        source = stages[a['stage'] - 1]['model']
        stream = deepcopy(next(s for s in source['corrientes'] if s['id'] == a['boundary']['id']))
        stream.update(id=record['id'] + '.' + row['id'], desde=a['volumeId'], hasta=b['volumeId'])
        stream.pop('estadoExterior', None)
        streams.append({'stream': stream, 'dataModelId': source['id'], 'replaces': [a, b]})
    ports = []
    for row in record['exposures']:
        end = endpoint(row)
        stage = stages[end['stage'] - 1]
        declaration = deepcopy(next(p for p in stage['model']['template']['ports'] if p['id'] == end['portId']))
        declaration['id'] = row['id']
        ports.append({'endpoint': end, 'port': declaration})
    return {'format': EXPANSION_FORMAT, 'version': 1, 'sourceModelId': model['id'],
            'sourceSignature': source_signature(model), 'flowsheetId': record['id'],
            # The connected publication reuses the indexed result metadata:
            # instance position j is the published stage index.
            'indexSetId': record['id'], 'count': len(stages), 'stages': stages, 'connections': connections,
            'internalStreams': streams, 'ports': ports, 'execution': 'not_lowered',
            'signatures': {'instances': {s['instanceId']: s['signature'] for s in stages},
                           'connections': {c['id']: c['signature'] for c in connections}}}, plans


def read_expansion(value, model):
    """Strict structural reader of a transmitted expansion against its source."""
    path = 'flowsheetExpansion'
    _exact(value, path, ['format', 'version', 'sourceModelId', 'sourceSignature', 'flowsheetId', 'indexSetId', 'count',
                         'stages', 'connections', 'internalStreams', 'ports', 'execution', 'signatures'])
    if value['format'] != EXPANSION_FORMAT or type(value['version']) is not int or value['version'] != 1:
        fail('flowsheet_expansion_version', path + '.version', 'Expected rage.flowsheet-expansion version 1.')
    if value['sourceModelId'] != model['id'] or value['sourceSignature'] != source_signature(model):
        fail('flowsheet_stale_expansion', path + '.sourceSignature', 'The flowsheet source changed; expand it again.')
    if value['execution'] != 'not_lowered':
        fail('flowsheet_invalid', path + '.execution', 'An expansion is not an execution.')
    record = model['flowsheet']
    if (value['flowsheetId'] != record['id'] or value['indexSetId'] != record['id']
            or value['count'] != len(record['instances']) or len(value['stages']) != value['count']):
        fail('flowsheet_invalid', path, 'The expansion does not describe this flowsheet.')
    for j, (stage, row) in enumerate(zip(value['stages'], record['instances']), 1):
        if stage.get('index') != j or stage.get('instanceId') != row['id'] or stage.get('templateRef') != row['template']:
            fail('flowsheet_invalid', f'{path}.stages[{j-1}]', 'Stage order must follow the declared instances.')
    if [c.get('id') for c in value['connections']] != [c['id'] for c in record['connections']]:
        fail('flowsheet_invalid', path + '.connections', 'Connections must follow the declared order.')
    if [p.get('port', {}).get('id') for p in value['ports']] != [e['id'] for e in record['exposures']]:
        fail('flowsheet_invalid', path + '.ports', 'Exposed ports must follow the declared order.')
    return value
