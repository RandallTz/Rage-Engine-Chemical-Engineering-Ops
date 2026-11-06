"""Lower a `rage.flowsheet` v1 network through the shared connected assembly.

Each instance is replayed through the template-instance service and admitted
with its exact selected equations. Connections replace exterior boundary
bindings by the donor's recorded component flows and specific enthalpy; they
never replace a balance. The steady mode is the existing zero-accumulation
specialization of the same connected rates. Publication reuses the indexed
result metadata (instance position j is the published stage index), so the
common Results path consumes a flowsheet without another result format.
"""
from copy import deepcopy
import json
import re

import sympy as sp

from core.modelo.flowsheet import (FlowsheetError, digest, expand_flowsheet, read_layout,
                                   source_signature)
from .indexed_network import IndexedDerivedSystem, discharge, _failure
from .derived import DerivedSystem

SELECTION = 'rage.flowsheet-execution'
COMPILATION = 'rage.flowsheet-compilation'
ENGINE = 'rage.compilador.flowsheet_network'


class FlowsheetDerivedSystem(IndexedDerivedSystem):
    """General connected graph of heterogeneous replayed instances."""
    publication_engine = ENGINE

    def __init__(self, model, *, linear_solver='auto'):
        self.model = model
        self.location = 'flowsheet'
        from core.mathematics.preparation import enabled
        from .template_lowering import bind_stage, compile_template
        self.expansion, plans = expand_flowsheet(model)
        record = model['flowsheet']
        templates = {key: compile_template(source) for key, source in plans.items()}
        # Locate a missing recorded transport law before assembling the graph.
        for row in record['connections']:
            stage = self.expansion['stages'][[r['id'] for r in record['instances']].index(row['from']['instance'])]
            plan = templates[stage['template']]
            port = next(p for p in plan.model['template']['ports'] if p['id'] == row['from']['port'])
            discharge(plan, port, f"flowsheet.connections.{row['id']}.from")
        if enabled():
            self.stages = [bind_stage(templates[row['template']], row) for row in self.expansion['stages']]
        else:
            self.stages = [DerivedSystem(row['model']) for row in self.expansion['stages']]
        self.template_systems = templates
        self._assemble(linear_solver)


def read_selection(value):
    if (not isinstance(value, dict) or set(value) != {'format', 'version', 'sourceSignature', 'mode'}
            or value['format'] != SELECTION or type(value['version']) is not int or value['version'] != 1
            or value['mode'] not in ('dynamic', 'steady') or not isinstance(value['sourceSignature'], str)
            or not re.fullmatch('[a-f0-9]{64}', value['sourceSignature'])):
        raise FlowsheetError('invalid_flowsheet_execution', 'flowsheetExecution', 'Expected flowsheet execution version 1.')
    return value


def selection_for(model, mode):
    """Pins topology, templates, instance data and the study; never the layout."""
    return read_selection({'format': SELECTION, 'version': 1, 'sourceSignature': source_signature(model), 'mode': mode})


def validate_selection(model, value):
    value = read_selection(value)
    if value != selection_for(model, value['mode']):
        raise FlowsheetError('stale_flowsheet_execution', 'flowsheetExecution.sourceSignature',
                             'The flowsheet topology, templates, instance data or study changed; prepare the selection again.')
    return value


def prepare(model, mode):
    from .indexed_steady import IndexedSteadySystem
    if 'flowsheet' not in model:
        raise FlowsheetError('flowsheet_missing', 'flowsheet', 'A flowsheet record is required.')
    read_selection(selection_for(model, mode))
    dynamic = FlowsheetDerivedSystem(model)
    system = dynamic if mode == 'dynamic' else IndexedSteadySystem(model, dynamic=dynamic)
    return system, compilation(system, mode)


def resolve(model, selected):
    from .indexed_publication import dynamic_result, steady_result
    validate_selection(model, selected)
    system, report = prepare(model, selected['mode'])
    result = dynamic_result(system) if selected['mode'] == 'dynamic' else steady_result(system)
    result['procedencia']['flowsheetCompilation'] = report
    result = json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
    result['procedencia']['flowsheetResultSignature'] = digest(result)
    return read_result(result, selected)


def compilation(system, mode='dynamic'):
    dynamic = system if mode == 'dynamic' else system.dynamic
    expansion = dynamic.expansion
    stages, rates = [], []
    for j, stage in enumerate(dynamic.stages):
        row = expansion['stages'][j]
        for k, selected in enumerate(stage.selection['states']):
            rates.append({'stage': j + 1, **selected, 'expressionSI': sp.srepr(dynamic.expressions[dynamic.offsets[j] + k])})
        stages.append({'index': j + 1, 'instanceId': row['instanceId'], 'template': row['templateRef'],
                       'modelId': stage.model['id'], 'signature': row['signature'],
                       'templateId': row['provenance']['templateId'], 'templateVersion': row['provenance']['templateVersion'],
                       'ports': [{'id': source, 'portId': target} for source, target in row['provenance']['identityMap']['ports'].items()],
                       'stateCount': stage.size,
                       'dynamicReport': deepcopy(stage.report),
                       'steadyReport': None if mode == 'dynamic' else deepcopy(system.stages[j].report)})
    connections = [{'id': row['id'], 'recycle': row['recycle'], 'signature': row['signature'],
                    'from': {'stage': row['from']['stage'], 'instanceId': row['from']['instanceId'], 'port': row['from']['port']},
                    'to': {'stage': row['to']['stage'], 'instanceId': row['to']['instanceId'], 'port': row['to']['port']}}
                   for row in expansion['connections']]
    ports = [{'id': item['port']['id'], 'stage': item['endpoint']['stage'], 'instanceId': item['endpoint']['instanceId'],
              'port': item['endpoint']['port'], 'kind': item['port']['kind'], 'direction': item['port']['direction']}
             for item in expansion['ports']]
    report = {'format': COMPILATION, 'version': 1, 'sourceModelId': dynamic.model['id'],
              'flowsheetId': expansion['flowsheetId'], 'count': len(stages), 'selection': selection_for(dynamic.model, mode),
              'stages': stages, 'connections': connections, 'ports': ports, 'rateRows': rates,
              'method': dynamic.method if mode == 'dynamic' else 'damped_newton',
              'specialization': 'original_rates' if mode == 'dynamic' else 'zero_accumulation',
              'linearPolicy': deepcopy(dynamic.linear_policy)}
    report = json.loads(json.dumps(report, ensure_ascii=False, allow_nan=False))
    report['signature'] = digest(report)
    return read_compilation(report)


def read_compilation(value):
    """Structural and fingerprint validation; mathematical admission stays here in Python."""
    path = 'flowsheetCompilation'

    def bad(message, where=''):
        raise FlowsheetError('invalid_flowsheet_compilation', path + where, message)
    fields = {'format', 'version', 'sourceModelId', 'flowsheetId', 'count', 'selection', 'stages', 'connections',
              'ports', 'rateRows', 'method', 'specialization', 'linearPolicy', 'signature'}
    if not isinstance(value, dict) or set(value) != fields:
        bad('Unknown or missing fields.')
    if value['format'] != COMPILATION or type(value['version']) is not int or value['version'] != 1:
        bad('Expected flowsheet compilation version 1.', '.version')
    mode = read_selection(value['selection'])['mode']
    if (value['specialization'] != ('original_rates' if mode == 'dynamic' else 'zero_accumulation')
            or value['method'] not in (('RK45', 'BDF') if mode == 'dynamic' else ('damped_newton',))):
        bad('Mode and specialization disagree.', '.specialization')
    if type(value['count']) is not int or not isinstance(value['stages'], list) or len(value['stages']) != value['count']:
        bad('Instance count mismatch.', '.count')
    stage_fields = {'index', 'instanceId', 'template', 'modelId', 'signature', 'templateId', 'templateVersion', 'ports',
                    'stateCount', 'dynamicReport', 'steadyReport'}
    declared, models, instances, expected = {}, set(), {}, []
    for j, stage in enumerate(value['stages'], 1):
        if not isinstance(stage, dict) or set(stage) != stage_fields or stage['index'] != j:
            bad('Invalid instance row.', f'.stages[{j-1}]')
        if stage['instanceId'] in instances or stage['modelId'] in models:
            bad('Repeated instance or model identity.', f'.stages[{j-1}]')
        instances[stage['instanceId']] = j
        models.add(stage['modelId'])
        if (stage['dynamicReport'] or {}).get('sourceModelId') != stage['modelId']:
            bad('Missing instance-local dynamic compilation.', f'.stages[{j-1}].dynamicReport')
        if (mode == 'dynamic') != (stage['steadyReport'] is None):
            bad('Steady specialization presence disagrees with the mode.', f'.stages[{j-1}].steadyReport')
        for port in stage['ports']:
            declared[stage['instanceId'], port['id']] = port['portId']
        rows = stage['dynamicReport'].get('derivedExecution', {}).get('selection', {}).get('states')
        if not isinstance(rows, list) or len(rows) != stage['stateCount']:
            bad('Missing original derivative rows.', f'.stages[{j-1}]')
        expected.extend((j, row['quantityId'], row['equationId']) for row in rows)
    if [(r.get('stage'), r.get('quantityId'), r.get('equationId')) for r in value['rateRows']] != expected:
        bad('Connected rates do not retain the original ordered rows.', '.rateRows')
    used, ids = set(), set()

    def take(endpoint, where):
        key = (endpoint.get('instanceId'), endpoint.get('port'))
        if key not in declared or instances.get(key[0]) != endpoint.get('stage') or key in used:
            bad('Unknown, foreign or repeated instance port.', where)
        used.add(key)
    for i, row in enumerate(value['connections']):
        if not isinstance(row, dict) or set(row) != {'id', 'recycle', 'signature', 'from', 'to'} or row['id'] in ids:
            bad('Invalid or repeated connection.', f'.connections[{i}]')
        ids.add(row['id'])
        take(row['from'], f'.connections[{i}].from')
        take(row['to'], f'.connections[{i}].to')
        if row['from']['instanceId'] == row['to']['instanceId']:
            bad('A connection joins two different instances.', f'.connections[{i}]')
    for i, row in enumerate(value['ports']):
        if not isinstance(row, dict) or set(row) != {'id', 'stage', 'instanceId', 'port', 'kind', 'direction'} or row['id'] in ids:
            bad('Invalid exposed port.', f'.ports[{i}]')
        ids.add(row['id'])
        take(row, f'.ports[{i}]')
    if used != set(declared):
        bad('Every instance port must be connected or exposed.', '.ports')
    if value['signature'] != digest({k: v for k, v in value.items() if k != 'signature'}):
        bad('Compilation fingerprint mismatch.', '.signature')
    return value


def read_result(result, selected=None):
    from core.resultados import leer_resultados
    leer_resultados(result)
    provenance = result['procedencia']
    report = read_compilation(provenance.get('flowsheetCompilation'))
    metadata = result.get('indexedNetwork') or {}
    if (result['modeloId'] != report['sourceModelId'] or provenance.get('motor') != ENGINE
            or metadata.get('indexSetId') != report['flowsheetId'] or metadata.get('count') != report['count']
            or metadata.get('mode') != report['selection']['mode'] or provenance.get('metodo') != report['method']
            or provenance.get('firma') != report['selection']['sourceSignature']
            or selected is not None and report['selection'] != read_selection(selected)):
        raise FlowsheetError('invalid_flowsheet_result', 'procedencia.flowsheetCompilation', 'Result and flowsheet compilation disagree.')
    unsigned = deepcopy(result)
    supplied = unsigned['procedencia'].pop('flowsheetResultSignature', None)
    if supplied != digest(unsigned):
        raise FlowsheetError('invalid_flowsheet_result', 'procedencia.flowsheetResultSignature', 'Flowsheet result fingerprint mismatch.')
    return result


def validate_layout_only_change(before, after):
    """True when two documents differ only in presentation (block positions)."""
    if 'flowsheetLayout' in after:
        read_layout(after)
    return source_signature(before) == source_signature(after)
