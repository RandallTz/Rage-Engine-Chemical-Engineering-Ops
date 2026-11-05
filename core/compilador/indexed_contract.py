"""Pinned network handoff: original stage selections plus connected rate rows."""
from copy import deepcopy
import json
import re

import sympy as sp

from .indexed_network import _failure
from .steady import signature


def _exact(value, fields, path):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise _failure('invalid_indexed_execution', 'Unexpected or missing fields.', path)


def read_selection(value):
    _exact(value, 'format version sourceSignature mode', 'indexedExecution')
    if (value['format'] != 'rage.indexed-execution' or type(value['version']) is not int
            or value['version'] != 1 or value['mode'] not in ('dynamic', 'steady')
            or not isinstance(value['sourceSignature'], str)
            or not re.fullmatch('[a-f0-9]{64}', value['sourceSignature'])):
        raise _failure('invalid_indexed_execution', 'Expected indexed execution version 1.', 'indexedExecution')
    return value


def selection_for(model, mode):
    # Pin the entire input, including Solve data, topology and nested recipes.
    return read_selection({'format': 'rage.indexed-execution', 'version': 1,
                           'sourceSignature': signature(model), 'mode': mode})


def validate_selection(model, value):
    value = read_selection(value)
    if value != selection_for(model, value['mode']):
        raise _failure('stale_indexed_execution', 'The indexed source or Solve data changed; prepare the selection again.', 'indexedExecution.sourceSignature')
    return value


def prepare(model, mode):
    from .indexed_network import IndexedDerivedSystem
    from .indexed_steady import IndexedSteadySystem
    read_selection(selection_for(model, mode))
    system = IndexedDerivedSystem(model) if mode == 'dynamic' else IndexedSteadySystem(model)
    return system, compilation(system, mode)


def resolve(model, selected):
    from .indexed_publication import dynamic_result, steady_result
    validate_selection(model, selected)
    system, report = prepare(model, selected['mode'])
    result = dynamic_result(system) if selected['mode'] == 'dynamic' else steady_result(system)
    result['procedencia']['indexedCompilation'] = report
    # Fingerprint the wire representation: solver evidence can contain NumPy
    # scalars or tuples, whereas HTTP exposes JSON numbers and arrays.
    result = json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
    result['procedencia']['indexedResultSignature'] = signature(result)
    return read_result(result, selected)


def read_result(result, selected=None):
    from core.resultados import leer_resultados
    leer_resultados(result)
    report = read_compilation(result['procedencia']['indexedCompilation'])
    metadata = result.get('indexedNetwork', {})
    if (result['modeloId'] != report['sourceModelId'] or metadata.get('count') != report['count']
            or metadata.get('indexSetId') != report['indexSetId']
            or metadata.get('mode') != report['selection']['mode']
            or result['procedencia']['metodo'] != report['method']
            or selected is not None and report['selection'] != read_selection(selected)):
        raise _failure('invalid_indexed_result', 'Result and indexed compilation disagree.', 'procedencia.indexedCompilation')
    unsigned = deepcopy(result)
    supplied = unsigned['procedencia'].pop('indexedResultSignature', None)
    if supplied != signature(unsigned):
        raise _failure('invalid_indexed_result', 'Indexed result fingerprint mismatch.', 'procedencia.indexedResultSignature')
    return result


def compilation(system, mode='dynamic'):
    dynamic = system if mode == 'dynamic' else system.dynamic
    expansion = dynamic.expansion
    stages, rates = [], []
    for j, stage in enumerate(dynamic.stages):
        rows = []
        for k, selected in enumerate(stage.selection['states']):
            row = {'stage': j+1, **selected,
                   'expressionSI': sp.srepr(dynamic.expressions[dynamic.offsets[j]+k])}
            rows.append(row)
        rates.extend(rows)
        stages.append({'index': j+1, 'modelId': stage.model['id'],
                       'template': expansion['stages'][j]['template'],
                       'ports': [{key: port[key] for key in ('id', 'kind', 'direction')}
                                 for port in stage.model['template']['ports']],
                       'dynamicReport': deepcopy(stage.report),
                       'steadyReport': None if mode == 'dynamic' else deepcopy(system.stages[j].report)})
    ports = []
    for item in expansion['ports']:
        ports.append({'id': item['port']['id'], 'stage': item['endpoint']['stage'],
                      'portId': item['endpoint']['portId'], 'kind': item['port']['kind'],
                      'direction': item['port']['direction']})
    connections = [{'id': row['id'], 'kind': row['kind'],
                    'from': {key: row['from'][key] for key in ('stage', 'portId')},
                    'to': {key: row['to'][key] for key in ('stage', 'portId')}}
                   for row in expansion['connections']]
    report = {'format': 'rage.indexed-compilation', 'version': 1,
              'sourceModelId': dynamic.model['id'], 'indexSetId': expansion['indexSetId'],
              'count': len(stages), 'selection': selection_for(dynamic.model, mode),
              'stages': stages, 'connections': connections, 'ports': ports,
              'rateRows': rates, 'method': dynamic.method if mode == 'dynamic' else 'damped_newton',
              'specialization': 'original_rates' if mode == 'dynamic' else 'zero_accumulation',
              'linearPolicy': deepcopy(dynamic.linear_policy)}
    report['signature'] = signature(report)
    return read_compilation(report)


def read_compilation(value):
    """Structural and fingerprint validation; mathematical admission stays server-side."""
    path = 'indexedCompilation'
    _exact(value, 'format version sourceModelId indexSetId count selection stages connections ports rateRows method specialization linearPolicy signature', path)
    def fail(message):
        raise _failure('invalid_indexed_compilation', message, path)
    if value['format'] != 'rage.indexed-compilation' or type(value['version']) is not int or value['version'] != 1:
        fail('Expected indexed compilation version 1.')
    selected = read_selection(value['selection'])
    mode = selected['mode']
    count = value['count']
    if type(count) is not int or not 1 <= count <= 256:
        fail('Invalid stage count.')
    for field in ('sourceModelId', 'indexSetId'):
        if not isinstance(value[field], str) or not value[field]:
            fail('Missing source identity.')
    for field in ('stages', 'connections', 'ports', 'rateRows'):
        if not isinstance(value[field], list):
            fail('Expected arrays.')
    if len(value['stages']) != count:
        fail('Stage count mismatch.')
    if (value['specialization'] != ('original_rates' if mode == 'dynamic' else 'zero_accumulation')
            or value['method'] not in (('RK45', 'BDF') if mode == 'dynamic' else ('damped_newton',))):
        fail('Mode and specialization disagree.')
    expected, model_ids, declared = [], set(), {}
    for j, stage in enumerate(value['stages'], 1):
        _exact(stage, 'index modelId template ports dynamicReport steadyReport', path+'.stages')
        if type(stage['index']) is not int or stage['index'] != j or not isinstance(stage['template'], str) or not stage['template']:
            fail('Invalid stage order or template reference.')
        report = stage['dynamicReport']
        if not isinstance(report, dict) or report.get('format') != 'rage.compilation' or report.get('version') != 1 or report.get('sourceModelId') != stage['modelId']:
            fail('Missing stage-local dynamic compilation.')
        required = set('format version formulation sourceModelId sourceRevision signature method closureStrategy variables equations domains conditions direct inverse eliminatedVariables auxiliaryStates time matrix'.split())
        optional = set('auxiliaryPurpose equivalence limits relations parameters groups selection materialDerivation energyDerivation thermodynamicDerivation momentumDerivation strategy systemEquations equationWorkbench derivedExecution symbolLabels'.split())
        if not required <= set(report) or set(report)-required-optional:
            fail('Unknown or missing dynamic compilation fields.')
        derived = report.get('derivedExecution')
        if not isinstance(derived, dict) or set(derived)-set('version sourceSignature selection proofConditions runtimeConditions reconstructions algebraicBlock nonlinearBlock dae thermodynamicClosures'.split()):
            fail('Invalid dynamic derivation evidence.')
        from core.modelo.derived_execution import read_definition
        read_definition(derived.get('selection'))
        if derived.get('reconstructions') != derived['selection']['reconstructions'] or derived.get('sourceSignature') != derived['selection']['sourceSignature']:
            fail('Dynamic report disagrees with its original selection.')
        if stage['modelId'] in model_ids:
            fail('Repeated stage model identity.')
        model_ids.add(stage['modelId'])
        if not isinstance(stage['ports'], list):
            fail('Missing declared stage ports.')
        for port in stage['ports']:
            _exact(port, 'id kind direction', path+'.stages.ports')
            if (not isinstance(port['id'], str) or not port['id'] or (j, port['id']) in declared
                    or port['kind'] not in ('material', 'heat', 'work') or port['direction'] not in ('inlet', 'outlet')):
                fail('Invalid declared stage port.')
            declared[j, port['id']] = port
        definition = report.get('derivedExecution', {}).get('selection', {})
        if not isinstance(definition.get('states'), list) or not definition['states']:
            fail('Missing original derivative rows.')
        expected.extend((j, row['quantityId'], row['equationId']) for row in definition['states'])
        if mode == 'steady':
            from .steady import read_report
            steady = read_report(stage['steadyReport'])
            if steady['sourceModelId'] != stage['modelId'] or steady['selection']['states'] != definition['states']:
                fail('The steady specialization changed the original derivative rows.')
        elif stage['steadyReport'] is not None:
            fail('Dynamic mode cannot include a steady specialization.')
    actual = []
    for row in value['rateRows']:
        _exact(row, 'stage quantityId equationId expressionSI', path+'.rateRows')
        if not isinstance(row['expressionSI'], str) or not row['expressionSI']:
            fail('Missing connected rate expression.')
        actual.append((row['stage'], row['quantityId'], row['equationId']))
    if actual != expected:
        fail('Connected rates do not retain the original ordered rows.')
    used, ids = set(), set()
    def endpoint(row, kind, direction):
        _exact(row, 'stage portId', path+'.endpoint')
        if type(row['stage']) is not int or not 1 <= row['stage'] <= count or not isinstance(row['portId'], str) or not row['portId']:
            fail('Invalid stage endpoint.')
        key = (row['stage'], row['portId'])
        port = declared.get(key)
        if port is None or port['kind'] != kind or port['direction'] != direction:
            fail('Unknown or incompatible stage port.')
        if key in used:
            fail('A stage port is bound more than once.')
        used.add(key)
    for row in value['connections']:
        _exact(row, 'id kind from to', path+'.connections')
        if not isinstance(row['id'], str) or not row['id'] or row['id'] in ids or row['kind'] != 'material':
            fail('Invalid or repeated connection.')
        ids.add(row['id'])
        endpoint(row['from'], row['kind'], 'outlet'); endpoint(row['to'], row['kind'], 'inlet')
        if row['from']['stage'] == row['to']['stage']:
            fail('A network connection must join different stages.')
    for row in value['ports']:
        _exact(row, 'id stage portId kind direction', path+'.ports')
        if not isinstance(row['id'], str) or not row['id'] or row['id'] in ids or row['kind'] not in ('material', 'heat', 'work') or row['direction'] not in ('inlet', 'outlet'):
            fail('Invalid exposed port.')
        ids.add(row['id']); endpoint({key: row[key] for key in ('stage', 'portId')}, row['kind'], row['direction'])
    if used != set(declared):
        fail('Every stage port must be connected or exposed.')
    policy = value['linearPolicy']
    _exact(policy, 'version requested selected size structuralNonzeros rule', path+'.linearPolicy')
    if (policy['version'] != 2 or policy['requested'] not in ('auto', 'dense', 'sparse')
            or policy['selected'] != ('dense' if policy['requested'] == 'auto' else policy['requested'])
            or type(policy['size']) is not int or policy['size'] < 1
            or type(policy['structuralNonzeros']) is not int or not 0 <= policy['structuralNonzeros'] <= policy['size']**2
            or not isinstance(policy['rule'], str) or not policy['rule']):
        fail('Invalid recorded linear solver policy.')
    if value['signature'] != signature({key: row for key, row in value.items() if key != 'signature'}):
        fail('Compilation fingerprint mismatch.')
    return value
