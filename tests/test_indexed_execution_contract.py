"""Network handoff pins source/data and retains every original derivative row."""
import copy
import json
from pathlib import Path

import pytest

from core.compilador.indexed_contract import compilation, read_compilation, selection_for, validate_selection
from core.compilador.indexed_network import IndexedDerivedSystem
from core.compilador.indexed_steady import IndexedSteadySystem
from core.compilador.steady import signature
from core.compilador.derived_graph import LoweringError
from test_index_sets import source_model


@pytest.fixture(scope='module')
def reports():
    model = source_model()
    model['datos']['solve.stageCount']['declaracion']['texto'] = '2'
    system = IndexedDerivedSystem(model)
    return model, {'dynamic': compilation(system),
                   'steady': compilation(IndexedSteadySystem(model, dynamic=system), 'steady')}


def test_actual_network_compilation_and_pinned_selection(reports):
    model, values = reports
    for mode, report in values.items():
        assert read_compilation(copy.deepcopy(report)) == report
        assert validate_selection(model, report['selection']) == selection_for(model, mode)
        assert report['count'] == 2
        assert len(report['rateRows']) == 8
        assert len(report['connections']) == 1
        assert len(report['ports']) == 6
    changed = copy.deepcopy(model)
    changed['datos']['solve.stageCount']['declaracion']['texto'] = '3'
    with pytest.raises(LoweringError, match='changed'):
        validate_selection(changed, values['steady']['selection'])


def test_resigned_structural_corruption_rejects(reports):
    _, values = reports
    invalid = []
    def case(name, mutate, mode='dynamic'):
        report = copy.deepcopy(values[mode]); mutate(report)
        report['signature'] = signature({k:v for k,v in report.items() if k != 'signature'})
        with pytest.raises((LoweringError, ValueError), match='.'):
            read_compilation(report)
        invalid.append({'name':name, 'report':report})
    case('unknown root', lambda r:r.update(extra=True))
    case('unknown selection', lambda r:r['selection'].update(extra=True))
    case('invalid count', lambda r:r.update(count=0))
    case('missing stage', lambda r:r['stages'].pop())
    case('reordered stages', lambda r:r['stages'].reverse())
    case('missing original row', lambda r:r['rateRows'].pop())
    case('foreign quantity', lambda r:r['rateRows'][0].update(quantityId='foreign'))
    case('missing expression', lambda r:r['rateRows'][0].update(expressionSI=''))
    case('wrong specialization', lambda r:r.update(specialization='zero_accumulation'))
    case('wrong method', lambda r:r.update(method='damped_newton'))
    case('duplicate port', lambda r:r['ports'].append(copy.deepcopy(r['ports'][0])))
    case('invalid endpoint', lambda r:r['connections'][0]['to'].update(stage=3))
    case('unknown port', lambda r:r['connections'][0]['to'].update(portId='unknown'))
    case('wrong port direction', lambda r:r['ports'][0].update(direction='outlet'))
    case('unbound port', lambda r:r['ports'].pop())
    case('unknown policy field', lambda r:r['linearPolicy'].update(extra=True))
    case('unknown stage report field', lambda r:r['stages'][0]['dynamicReport'].update(extra=True))
    case('unknown derivation evidence', lambda r:r['stages'][0]['dynamicReport']['derivedExecution'].update(extra=True))
    case('missing steady report', lambda r:r['stages'][0].update(steadyReport=None), 'steady')
    Path('.tmp/indexed-execution-contract.json').write_text(json.dumps({'valid':values,'invalid':invalid}),encoding='utf-8')
