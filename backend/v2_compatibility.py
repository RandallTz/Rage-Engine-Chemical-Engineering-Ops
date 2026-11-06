"""Revision-2 compatibility boundary backed by common compilation and Solve.

The existing strict v2 reader, catalogs, identity and initialization packaging
remain the wire authority. Initial specification dispatch is shared with the
compiler; the compiler additionally owns executable admission and integration.
No production routing is changed here, and no native solver fallback exists.
"""
import copy
import re

from backend import motor_ensamblaje_v2 as wire
from core.compilador import compilar, resolver, NoSoportado
from core.modelo import desde_ensamblaje_v2, ErrorModelo


def _reject(validation):
    return any(d['estado'] in ('invalido', 'conflicto', 'incompleto', 'no_soportado')
               for d in validation['diagnosticos'])


def _diagnostics(validation, error, request):
    rows = getattr(error, 'diagnostics', None) or [
        {'nativeCode': 'MOTOR_ENS_FORMA', 'message': str(error), 'path': getattr(error, 'ruta', '/') }]
    for row in rows:
        path = row.get('path', '/')
        match = re.match(r'volumenes\[(\d+)\]', path)
        owner = 'volumen:'+request['volumenes'][int(match[1])]['id'] if match else 'red'
        variables = []
        if path.startswith('datos.') and path[6:] in request['datos']:
            identity = path[6:]
            origin = request['datos'][identity].get('origen') or {}
            owner = origin.get('propietarioId', 'red')
            path = origin.get('ruta', '/datos/'+identity)
            variables = [identity]
        elif not path.startswith('/'):
            path = '/'+re.sub(r'\[(\d+)\]',r'/\1',path).replace('.', '/')
            if path.startswith('/intercambios/'):
                path = path.replace('/intercambios/','/intercambiosTermicos/',1)
        code = row.get('nativeCode', 'MOTOR_ENS_FORMA')
        status = 'no_soportado' if row.get('code', '').startswith('unsupported_') or row.get('code') == 'requires_discretization' else 'invalido'
        initialization = row.get('initializationStatus')
        if initialization:
            status = {'pendiente':'incompleto','no_soportada':'no_soportado','incompatible':'invalido'}[initialization]
            if match:
                identity = request['volumenes'][int(match[1])]['id']
                validation['inicializacion']['volumenes'][identity] = {
                    'estado':initialization,'variables':{},'estadoTermodinamico':None}
            states = [v['estado'] for v in validation['inicializacion']['volumenes'].values()]
            validation['inicializacion']['estado'] = next(
                state for state in ('incompatible','no_soportada','pendiente','compatible') if state in states)
        diagnostic = {'codigo': code, 'estado': status, 'mensaje': row['message'],
                      'variableIds': variables, 'origen': {'propietarioId': owner, 'ruta': path}}
        if not any(d['codigo'] == code and d['origen']['ruta'] == path for d in validation['diagnosticos']):
            validation['diagnosticos'].append(diagnostic)


def validate(request):
    # Keep all independent wire errors, including the unsupported open-boundary
    # draft's five codes, before the stricter common reader could stop at one.
    validation, context = wire.validar_v2(request)
    if context is None or _reject(validation):
        return validation
    try:
        system = compilar(desde_ensamblaje_v2(request))
        system.inicial()
    except (NoSoportado, ErrorModelo) as error:
        _diagnostics(validation, error, request)
    return validation


def _aliases(details, validation):
    """One explicit identity map for the existing common physical wire IDs."""
    variables = {v['id'] for v in validation['variables']}
    identities = variables | {e['id'] for e in validation['ecuaciones']}
    identities |= {s['variableId'] for s in details['series']}
    identities |= {r['ecuacionId'] for r in details['residuos']}
    aliases = {identity: identity for identity in identities}
    for series in details['series']:
        series['variableId'] = aliases[series['variableId']]
    for row in details['residuos']:
        row['ecuacionId'] = aliases[row['ecuacionId']]
    for row in details['catalogoSeries']:
        identity = row['variableId']
        row['variableId'] = aliases[identity]
        row['variableEnsamblajeId'] = aliases[identity] if identity in variables else None
    for aspect in details['certificacion']['aspectos']:
        aspect['referencias'] = [aliases.get(identity, identity) for identity in aspect['referencias']]


def _runtime_codes(details, validation):
    """Translate the common policy stop to its existing v2 wire meaning.

    The native result publishes the located physical transition and carries
    the policy stop in diagnostics, without a second generic event at that time.
    """
    for diagnostic in validation['diagnosticos']:
        if diagnostic['codigo'] == 'MOTOR_ENS_DETENIDO_POLITICA_INCUMPLIDA':
            diagnostic['codigo'] = 'MOTOR_ENS_DETENIDO_CAMBIO_FASE_PROHIBIDO'
    if details is not None:
        transitions = {e['tiempo'] for e in details['eventos'] if e['codigo'] in
                       ('aparicion_fase','desaparicion_fase','sustitucion_fase','cambio_denominacion')}
        details['eventos'] = [e for e in details['eventos']
                             if not (e['codigo']=='politica_incumplida' and e['tiempo'] in transitions)]


def resolve(request):
    validation = validate(request)
    if _reject(validation) or validation['recuento']['estado'] != 'listo' or validation['inicializacion']['estado'] != 'compatible':
        status = 'no_soportado' if any(d['estado']=='no_soportado' for d in validation['diagnosticos']) else 'invalido'
        return {'revision': 2, 'validacion': validation, 'estado': status, 'resultados': None}
    try:
        result = resolver(desde_ensamblaje_v2(request))
    except (NoSoportado, ErrorModelo) as error:
        _diagnostics(validation, error, request)
        status = 'no_soportado' if any(d['estado']=='no_soportado' for d in validation['diagnosticos']) else 'invalido'
        return {'revision': 2, 'validacion': validation, 'estado': status, 'resultados': None}
    details = copy.deepcopy(result['procedencia'].get('equilibrium'))
    validation['diagnosticos'].extend(result['procedencia'].get('diagnostics', []))
    status = result['estado']
    if details is not None:
        _aliases(details, validation)
    else:
        status = 'invalido' if any(d['codigo'].startswith('MOTOR_ENS_DETENIDO_') for d in validation['diagnosticos']) else 'no_convergente'
    _runtime_codes(details, validation)
    return {'revision': 2, 'validacion': validation, 'estado': status, 'resultados': details}


def capabilities():
    # Same scientific scope and water-audit gate; no additional method claims.
    return wire.capacidades_v2()
