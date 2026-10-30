"""Versioned, independent structure/initialization/certification assessments.

An assessment is evidence for one exact model, not permission to execute it.
Execution still uses the strict reader and existing compiler admission rules.
"""
import copy
import hashlib
import json
from typing import Literal, NotRequired, TypedDict

from core.modelo import ErrorModelo
from core.modelo.lector import leer_modelo_inspeccion
from core.termodinamica import NoSoportado as ClosureUnsupported
from .compilador import NoSoportado


class VerdictEvidence(TypedDict):
    sourceSignature: str
    scope: dict
    diagnostics: list[dict]


class StructureVerdict(VerdictEvidence):
    kind: Literal['structure']
    status: Literal['complete', 'incomplete', 'incompatible', 'unsupported', 'not_evaluated', 'invalid']
    code: Literal['STRUCTURE_COMPLETE', 'STRUCTURE_MISSING_RELATION', 'STRUCTURE_CONFLICT',
                  'STRUCTURE_UNSUPPORTED', 'STRUCTURE_NOT_EVALUATED', 'STRUCTURE_INVALID_DOCUMENT']


class InitializationVerdict(VerdictEvidence):
    kind: Literal['initialization']
    status: Literal['compatible', 'pending', 'incompatible', 'unsupported', 'not_evaluated']
    code: Literal['INITIALIZATION_COMPATIBLE', 'INITIALIZATION_MISSING_DATA', 'INITIALIZATION_CONSTRAINT_CONFLICT',
                  'INITIALIZATION_OUT_OF_DOMAIN', 'INITIALIZATION_UNSUPPORTED', 'INITIALIZATION_NOT_EVALUATED']


class CertificationVerdict(VerdictEvidence):
    kind: Literal['certification']
    status: Literal['passed', 'failed', 'not_evaluable', 'not_evaluated']
    code: Literal['CERTIFICATION_PASSED', 'CERTIFICATION_FAILED', 'CERTIFICATION_NOT_EVALUABLE', 'CERTIFICATION_NOT_EVALUATED']


class Assessment(TypedDict):
    format: Literal['rage.model-assessment']
    version: Literal[1]
    modelId: str | None
    sourceSignature: str
    structure: StructureVerdict
    initialization: InitializationVerdict
    certification: CertificationVerdict
    inspection: dict
    compilation: NotRequired[dict]
    resultSignature: NotRequired[str]


CODES = {
    'structure': {'complete': ('STRUCTURE_COMPLETE',), 'incomplete': ('STRUCTURE_MISSING_RELATION',),
                  'incompatible': ('STRUCTURE_CONFLICT',), 'unsupported': ('STRUCTURE_UNSUPPORTED',),
                  'not_evaluated': ('STRUCTURE_NOT_EVALUATED',), 'invalid': ('STRUCTURE_INVALID_DOCUMENT',)},
    'initialization': {'compatible': ('INITIALIZATION_COMPATIBLE',), 'pending': ('INITIALIZATION_MISSING_DATA',),
                       'incompatible': ('INITIALIZATION_OUT_OF_DOMAIN', 'INITIALIZATION_CONSTRAINT_CONFLICT'),
                       'unsupported': ('INITIALIZATION_UNSUPPORTED',), 'not_evaluated': ('INITIALIZATION_NOT_EVALUATED',)},
    'certification': {'passed': ('CERTIFICATION_PASSED',), 'failed': ('CERTIFICATION_FAILED',),
                      'not_evaluable': ('CERTIFICATION_NOT_EVALUABLE',), 'not_evaluated': ('CERTIFICATION_NOT_EVALUATED',)},
}


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def model_signature(model):
    from core.modelo.equation_workbench import SOURCE_REVISION
    return signature(['model-assessment-1', SOURCE_REVISION, model])


def _verdict(kind, status, source, diagnostics=(), *, code=None, scope=None):
    return {'kind': kind, 'status': status, 'code': code or CODES[kind][status][0],
            'sourceSignature': source, 'scope': scope or {}, 'diagnostics': list(diagnostics)}


def _diagnostics(error, path):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        rows = getattr(error, 'diagnostics', None)
        if rows:
            return [{**row, 'path': row.get('path') or path} for row in rows]
        if error.__cause__ is None:
            break
        error = error.__cause__
    return [{'code': 'unsupported_scope', 'message': str(error), 'path': path}]


def _pending_initial(model):
    pending = []
    def missing(path, message):
        pending.append({'code': 'INITIALIZATION_MISSING_DATA', 'path': path, 'message': message})
    def datum(identity, path):
        data = model['datos'].get(identity)
        if data is None or not data['declaracion']['texto'].strip():
            missing(path, 'An initial datum is pending: '+str(identity))
    if model['matematico'] is not None:
        from .explicito import _simbolos
        mat = model['matematico']; used = set(); constrained = set()
        for condition in mat['condiciones']:
            eq = condition['ecuacion']
            if eq['izquierda']['tipo'] == 'simbolo':
                constrained.add(eq['izquierda']['id'])
            _simbolos(eq['derecha'], used)
        for symbol in mat['simbolos']:
            if symbol['rol'] == 'campo' and symbol['id'] not in constrained:
                missing('matematico.condiciones', 'Missing initial constraint for '+symbol['id'])
            if symbol['rol'] in ('parametro', 'constante') and symbol['id'] in used:
                datum('matematico.'+symbol['id'], 'datos.matematico.'+symbol['id'])
        return pending
    for index, volume in enumerate(model['volumenes']):
        path = f'volumenes[{index}].inicial'; initial = volume.get('inicial', {})
        amounts = initial.get('cantidades')
        if not amounts:
            missing(path+'.cantidades', 'Initial component amounts are pending.')
        else:
            for component in volume['componenteIds']:
                datum(amounts['datoIds'].get(str(component)), path+'.cantidades.datoIds.'+str(component))
        if volume['balances']['energia']:
            energy = initial.get('energia')
            if not energy:
                missing(path+'.energia', 'Initial energy or temperature is pending.')
            else:
                datum(energy['datoId'], path+'.energia.datoId')
    return pending


def _structure(model):
    """Use executable admission/lowering, never a count alone or an initial flash."""
    from core.modelo.dynamic_definition import ensure_executable
    from core.balances.momentum_derivation import ensure_executable as ensure_momentum
    from core.modelo.equation_workbench import ensure_executable as ensure_equations
    from .explicito import SistemaExplicito, es_explicito
    if model['motores'].get('derivedExecution', {}).get('version') == 5:
        from .steady import SteadySystem
        report = SteadySystem(model).report
        return {'variables': report['variables'], 'equations': report['rows'],
                'scope': 'Steady residual admission and structural matching; no root, rank or global uniqueness claim.',
                'steadyCompilation': report}
    if any(model['motores'].get(key) for key in ('derivedExecution', 'hydraulicNetwork')):
        # Their constructors currently interleave reduction and initialization.
        # Do not invent a complete verdict when their independent observer is absent.
        return None
    ensure_executable(model); ensure_momentum(model); ensure_equations(model)
    if es_explicito(model):
        if model['matematico'] is None:
            from core.balances.generador import inspect_equations, NoGenerable
            try:
                model = inspect_equations(model)
            except NoGenerable as error:
                raise NoSoportado(str(error)) from error
        system = SistemaExplicito(model, _structure_only=True)
        from core.unidades import unidad_SI
        return {'variables': [{'id': field, 'unit': unidad_SI(system.dims[field])} for field in system.campos],
                'equations': copy.deepcopy(model['matematico']['ecuaciones']),
                'scope': 'explicit-first-order-ODE; initial constraints excluded; not a rank proof'}
    from .admission import validate
    from .presentation import compiled_balance_equations
    validate(model, initialization=False)
    from core.balances.energy_equations import lower_equilibrium_rate
    for volume in model['volumenes']:
        if volume['id'] in model['motores'].get('energyDerivation', {}).get('volumes', {}):
            lower_equilibrium_rate(model, volume['id'])
    variables = []
    for volume in model['volumenes']:
        variables.extend({'id': f"{volume['id']}.n.{component}", 'unit': 'mol'} for component in volume['componenteIds'])
        variables.append({'id': volume['id']+('.U' if volume['frontera']['tipo'] == 'rigida' else '.H'), 'unit': 'J'})
    return {'variables': variables, 'equations': compiled_balance_equations(model),
            'scope': 'admitted nested-equilibrium balances; no initial flash; not a rank proof'}


def assess_model(model: dict, *, initialize: bool = True) -> Assessment:
    """Inspect the draft first; evaluate initial compatibility only if requested."""
    if type(initialize) is not bool:
        raise ValueError('initialize must be boolean.')
    if not isinstance(model, dict):
        raise ValueError('A model object is required.')
    source = model_signature(model)
    result = {'format': 'rage.model-assessment', 'version': 1, 'modelId': model.get('id'),
              'sourceSignature': source, 'inspection': {'variables': [], 'equations': [], 'scope': 'not inspected'},
              **{kind: _verdict(kind, 'not_evaluated', source) for kind in CODES}}
    try:
        model = leer_modelo_inspeccion(model)
    except ErrorModelo as error:
        result['structure'] = _verdict('structure', 'invalid', source,
            [{'code': 'STRUCTURE_INVALID_DOCUMENT', 'message': error.mensaje, 'path': error.ruta}])
        return result
    try:
        inspection = _structure(model)
    except (NoSoportado, ClosureUnsupported, ValueError) as error:
        rows = _diagnostics(error, 'modelo')
        codes = {row['code'] for row in rows}
        status = ('incomplete' if codes & {'STRUCTURE_MISSING_RELATION', 'missing_data', 'missing_heat', 'missing_study'}
                  else 'incompatible' if codes & {'STRUCTURE_CONFLICT', 'conflicting_heat', 'incompatible_dimension', 'inconsistent_molar_mass'}
                  else 'unsupported')
        result['structure'] = _verdict('structure', status, source, rows)
        return result
    if inspection is not None:
        steady_report = inspection.pop('steadyCompilation', None)
        result['inspection'] = inspection
        result['structure'] = _verdict('structure', 'complete', source, scope={'description': inspection['scope']})
        if steady_report is not None:
            result['compilation'] = steady_report
            result['initialization'] = _verdict('initialization', 'not_evaluated', source,
                scope={'description': 'Steady seeds are numerical guesses, not transient initial conditions. Individual invariant bindings are audited separately.'})
            return result
    else:
        result['structure']['diagnostics'] = [{'code': 'STRUCTURE_NOT_EVALUATED', 'path': 'motores',
            'message': 'This lowering does not yet expose initialization-independent inspection.'}]
    if not initialize:
        return result
    pending = _pending_initial(model) if inspection is not None else []
    if pending:
        result['initialization'] = _verdict('initialization', 'pending', source, pending, scope={'timeSI': 0})
        return result
    from .report import compilation_report
    try:
        report = compilation_report(model)
    except (NoSoportado, ClosureUnsupported, ErrorModelo, ValueError, ArithmeticError) as error:
        rows = _diagnostics(error, 'matematico.condiciones' if model['matematico'] else 'volumenes')
        codes = {row['code'] for row in rows}
        status = ('pending' if codes & {'INITIALIZATION_MISSING_DATA', 'missing_initial_data', 'missing_data', 'dae_initial_states_required'} or
                  any(row.get('initializationStatus') == 'pendiente' for row in rows)
                  else 'unsupported' if inspection is None or any(row.get('initializationStatus') == 'no_soportada' for row in rows)
                  else 'incompatible')
        if any(row.get('stage') == 'initialization' for row in rows) and (codes & {'invalid_initialization', 'invalid_initial_domain', 'dae_domain'} or any(code.startswith('nonlinear_') for code in codes)):
            status = 'incompatible'
        code = 'INITIALIZATION_CONSTRAINT_CONFLICT' if 'INITIALIZATION_CONSTRAINT_CONFLICT' in codes else None
        result['initialization'] = _verdict('initialization', status, source, rows, code=code, scope={'timeSI': 0})
        return result
    result['compilation'] = report
    result['initialization'] = _verdict('initialization', 'compatible', source, scope={'timeSI': 0})
    if inspection is None:
        result['structure'] = _verdict('structure', 'complete', source,
            scope={'description': 'Validated by full compilation; no independent draft inspection for this lowering.'})
        result['inspection'] = {'variables': report['variables'], 'equations': report.get('equations', []),
                                'scope': result['structure']['scope']['description']}
    return result


def certification(result, source):
    physical = result['procedencia'].get('physicalCertification')
    status = {'cumple': 'passed', 'no_cumple': 'failed', 'no_evaluable': 'not_evaluable'}.get(
        (physical or {}).get('estado'), 'not_evaluable')
    rows = []
    if physical:
        for aspect in physical['aspectos']:
            if aspect['estado'] != 'cumple':
                rows.append({'code': 'CERTIFICATION_FAILED' if aspect['estado'] == 'no_cumple' else 'CERTIFICATION_NOT_EVALUABLE',
                             'path': 'procedencia.physicalCertification.aspectos.'+aspect['id'],
                             'message': 'Physical aspect: '+aspect['id'], 'nativeStatus': aspect['estado']})
    else:
        rows.append({'code': 'CERTIFICATION_NOT_EVALUABLE', 'path': 'procedencia.physicalCertification',
                     'message': 'No physical certificate is published; initialization and numerical completion are not certification.'})
        for index, check in enumerate(result['verificaciones']):
            if check['valor'] > check['tolerancia']:
                status = 'failed'
                rows.append({'code': 'CERTIFICATION_FAILED', 'path': f'verificaciones[{index}]',
                             'message': 'Published numerical verification failed: '+check['id']})
    times = next((axis['valores'] for axis in result['ejes'] if axis['rol'] == 'tiempo'), [])
    scope = {'numericalStatus': result['estado'], 'complete': result['estado'] == 'resuelto',
             'samples': len(times), 'startSI': times[0] if times else None, 'endSI': times[-1] if times else None}
    return _verdict('certification', status, source, rows, scope=scope)


def result_signature(result):
    return signature({**result, 'procedencia': {k: v for k, v in result['procedencia'].items() if k != 'assessment'}})


def attach_result(assessment, result):
    evidence = copy.deepcopy(assessment)
    evidence['certification'] = certification(result, evidence['sourceSignature'])
    evidence['resultSignature'] = result_signature(result)
    read_assessment(evidence, result=result)
    result['procedencia']['assessment'] = evidence
    return result


def read_assessment(value, *, model=None, result=None):
    """Fail closed on unknown versions, status/code mismatch and stale evidence."""
    required = {'format', 'version', 'modelId', 'sourceSignature', 'structure', 'initialization', 'certification', 'inspection'}
    if (not isinstance(value, dict) or not required <= value.keys() or
            value.keys() - required - {'compilation', 'resultSignature'} or value['format'] != 'rage.model-assessment' or
            type(value['version']) is not int or value['version'] != 1):
        raise ValueError('Expected rage.model-assessment v1.')
    source = value['sourceSignature']
    if not isinstance(source, str) or len(source) != 64 or any(c not in '0123456789abcdef' for c in source):
        raise ValueError('A SHA-256 model signature is required.')
    if model is not None and (model_signature(model) != source or model.get('id') != value['modelId']):
        raise ValueError('Stale assessment: model identity or signature differs.')
    for kind, statuses in CODES.items():
        verdict = value[kind]
        if (not isinstance(verdict, dict) or set(verdict) != {'kind', 'status', 'code', 'sourceSignature', 'scope', 'diagnostics'} or
                verdict['kind'] != kind or not isinstance(verdict['status'], str) or
                verdict['code'] not in statuses.get(verdict['status'], ()) or verdict['sourceSignature'] != source or
                not isinstance(verdict['scope'], dict) or not isinstance(verdict['diagnostics'], list)):
            raise ValueError('Invalid '+kind+' verdict.')
        for diagnostic in verdict['diagnostics']:
            if not isinstance(diagnostic, dict) or any(not isinstance(diagnostic.get(k), str) or not diagnostic[k]
                                                       for k in ('code', 'message', 'path')):
                raise ValueError('Located typed diagnostics are required.')
    if (not isinstance(value['modelId'], str) or not value['modelId']) and value['structure']['status'] != 'invalid':
        raise ValueError('A model identity is required.')
    inspection = value['inspection']
    if (not isinstance(inspection, dict) or set(inspection) != {'variables', 'equations', 'scope'} or
            not isinstance(inspection['variables'], list) or not isinstance(inspection['equations'], list) or
            not isinstance(inspection['scope'], str)):
        raise ValueError('Invalid partial structural inspection.')
    if result is not None:
        if (value['modelId'] != result['modeloId'] or value.get('resultSignature') != result_signature(result) or
                value['certification'] != certification(result, source)):
            raise ValueError('Assessment does not match the published result or certification evidence.')
    elif 'resultSignature' not in value and value['certification']['status'] != 'not_evaluated':
        raise ValueError('Certification requires published-result evidence.')
    if value['initialization']['status'] == 'compatible' and value['structure']['status'] != 'complete':
        raise ValueError('Compatible initialization requires an admitted structure.')
    if 'resultSignature' in value:
        digest = value['resultSignature']
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('A SHA-256 result signature is required.')
    # Reject non-finite JSON anywhere, including diagnostic SI values.
    signature(value)
    return value
