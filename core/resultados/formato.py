"""
Conjunto de resultados v0. Genérico: no sabe de equipos ni de operaciones.

    {formato: "rage.resultados", version: 0, id, nombre, modeloId | null,
     estado: "resuelto" | "parcial" | "fallido",
     procedencia: {motor, metodo | null, firma | null, mensaje?},
     ejes:   [{id, nombre, rol, unidadSI, dimension, valores}],
     series: [{id, nombre, unidadSI, dimension, magnitudes, ejes: [ejeId...], valores,
               propietarioId?, componenteId?, faseId?}],
     eventos: [{codigo, ejeId, valor, descripcion, propietarioId?}],
     verificaciones: [{id, valor, tolerancia, descripcion}]}

- Un eje es una variable independiente: tiempo, coordenada, parámetro de una
  continuación, número de onda… (rol: tiempo | coordenada | parametro | otro).
- Una serie depende de 0, 1 o 2 ejes; `valores` es un número, una lista o una
  lista de listas con la forma de sus ejes (primer eje = índice exterior).
  Un valor no definido es null, nunca un número inventado.
- Unidades SI con su dimensión exacta, del servicio único (core/unidades).
"""

import math

from core import unidades as un
from core.unidades.servicio import dimension_json

VERSION = 0
ROLES = ["tiempo", "coordenada", "parametro", "otro"]
ESTADOS = ["resuelto", "parcial", "fallido"]


class ErrorResultados(Exception):
    def __init__(self, ruta, mensaje):
        super().__init__(f"{ruta}: {mensaje}")
        self.ruta, self.mensaje = ruta, mensaje


def _fallo(ruta, motivo):
    raise ErrorResultados(ruta, motivo)


def _dim(unidad):
    return dimension_json(un.interpretar(unidad)["dimension"])


def eje(id_, nombre, rol, unidadSI, valores):
    return {"id": id_, "nombre": nombre, "rol": rol, "unidadSI": unidadSI, "dimension": _dim(unidadSI),
            "valores": [float(x) for x in valores]}


def serie(id_, nombre, unidadSI, ejes, valores, **extra):
    d = un.interpretar(unidadSI)["dimension"]
    s = {"id": id_, "nombre": nombre, "unidadSI": unidadSI, "dimension": dimension_json(d),
         "magnitudes": un.magnitudes_de(d), "ejes": list(ejes), "valores": _limpiar(valores)}
    s.update({k: v for k, v in extra.items() if v is not None})
    return s


def evento(codigo, eje_id, valor, descripcion, propietarioId=None):
    e = {"codigo": codigo, "ejeId": eje_id, "valor": float(valor), "descripcion": descripcion}
    if propietarioId is not None:
        e["propietarioId"] = propietarioId
    return e


def conjunto(id_, nombre, estado, procedencia, ejes, series, eventos=(), verificaciones=(), modeloId=None):
    return {"formato": "rage.resultados", "version": VERSION, "id": id_, "nombre": nombre, "modeloId": modeloId,
            "estado": estado, "procedencia": procedencia, "ejes": list(ejes), "series": list(series),
            "eventos": list(eventos), "verificaciones": list(verificaciones)}


def _limpiar(v):
    if isinstance(v, (list, tuple)):
        return [_limpiar(x) for x in v]
    if v is None:
        return None
    x = float(v)
    return x if math.isfinite(x) else None


def _forma(v, dims, ruta):
    if not dims:
        if v is not None and not isinstance(v, (int, float)):
            _fallo(ruta, "se esperaba un número o null")
        return
    if not isinstance(v, list) or len(v) != dims[0]:
        _fallo(ruta, f"se esperaban {dims[0]} valores")
    for i, x in enumerate(v):
        _forma(x, dims[1:], f"{ruta}[{i}]")


def leer_resultados(dato):
    claves = ["formato", "version", "id", "nombre", "modeloId", "estado", "procedencia", "ejes", "series", "eventos", "verificaciones"]
    if not isinstance(dato, dict):
        _fallo("resultados", "se esperaba un objeto")
    faltan = [k for k in claves if k not in dato]
    sobran = [k for k in dato if k not in claves and k != 'indexedNetwork']
    if faltan or sobran:
        _fallo("resultados", ("faltan " + ", ".join(faltan) if faltan else "") + ("campos desconocidos: " + ", ".join(sobran) if sobran else ""))
    if dato["formato"] != "rage.resultados" or dato["version"] != VERSION:
        _fallo("formato", "se esperaba rage.resultados v0")
    if dato["estado"] not in ESTADOS:
        _fallo("estado", f"valor no admitido: {dato['estado']!r}")
    proc = dato["procedencia"]
    if not isinstance(proc, dict) or not isinstance(proc.get("motor"), str):
        _fallo("procedencia.motor", "texto requerido")
    largo = {}
    for i, e in enumerate(dato["ejes"]):
        r = f"ejes[{i}]"
        if e.get("rol") not in ROLES:
            _fallo(r + ".rol", "valor no admitido")
        if e["id"] in largo:
            _fallo(r + ".id", "identidad repetida")
        _unidad(e, r)
        if not isinstance(e["valores"], list) or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in e["valores"]):
            _fallo(r + ".valores", "lista de números finitos requerida")
        largo[e["id"]] = len(e["valores"])
    ids = set()
    for i, s in enumerate(dato["series"]):
        r = f"series[{i}]"
        if s["id"] in ids:
            _fallo(r + ".id", "identidad repetida")
        ids.add(s["id"])
        _unidad(s, r)
        for k in s["ejes"]:
            if k not in largo:
                _fallo(r + ".ejes", f"eje inexistente {k!r}")
        if len(s["ejes"]) > 2:
            _fallo(r + ".ejes", "una serie depende de 0, 1 o 2 ejes")
        _forma(s["valores"], [largo[k] for k in s["ejes"]], r + ".valores")
    for i, e in enumerate(dato["eventos"]):
        if e.get("ejeId") not in largo:
            _fallo(f"eventos[{i}].ejeId", "eje inexistente")
    if 'indexedNetwork' in dato:
        from .indexed_network import read_indexed_network
        read_indexed_network(dato)
    _physical_evidence(dato)
    if 'steadyDiagnostics' in proc or proc.get('motor') == 'rage.compilador.steady' or proc.get('compilation', {}).get('version') == 2:
        from core.compilador.steady import read_result
        try:
            read_result(dato)
        except (ValueError, TypeError, KeyError, ArithmeticError) as error:
            _fallo('procedencia.steadyDiagnostics', str(error))
    if 'daeDiagnostics' in proc or proc.get('compilation', {}).get('derivedExecution', {}).get('version') == 4:
        _dae_evidence(dato)
    if 'nonlinearDiagnostics' in proc:
        _nonlinear_evidence(dato)
    if 'assessment' in proc:
        from core.compilador.assessment import read_assessment
        try:
            read_assessment(proc['assessment'], result=dato)
        except (ValueError, TypeError, KeyError) as error:
            _fallo('procedencia.assessment', str(error))
    if 'runTimeline' in proc:
        from .run_timeline import read_run_timeline
        try:
            read_run_timeline(dato)
        except (ValueError, TypeError, KeyError) as error:
            _fallo('procedencia.runTimeline', str(error))
    return dato


def _dae_evidence(result):
    path = 'procedencia.daeDiagnostics'
    value = result['procedencia'].get('daeDiagnostics')
    selection = result['procedencia'].get('compilation', {}).get('derivedExecution', {}).get('selection', {})
    fields = {'version', 'method', 'acceptedChecks', 'maxResidual', 'maxConservation', 'driftTolerance', 'scope'}
    if (not isinstance(value, dict) or set(value) != fields or selection.get('version') != 4
            or 'nonlinearDiagnostics' not in result['procedencia']):
        _fallo(path, 'Expected DAE diagnostics for version 4.')
    if value['version'] != 1 or value['method'] != 'scipy_bdf_nested_newton' or not isinstance(value['scope'], str):
        _fallo(path, 'Invalid DAE evidence version or method.')
    if type(value['acceptedChecks']) is not int or value['acceptedChecks'] < 0:
        _fallo(path, 'Invalid accepted-state counter.')
    for key in ('maxResidual', 'maxConservation', 'driftTolerance'):
        if type(value[key]) not in (int, float) or not math.isfinite(value[key]) or value[key] < 0:
            _fallo(path, 'Invalid DAE numerical evidence.')
    if (value['driftTolerance'] != selection.get('dae', {}).get('driftTolerance')
            or value['maxResidual'] > value['driftTolerance'] or value['maxConservation'] > 1e-6
            or result['estado'] == 'resuelto' and value['acceptedChecks'] < 1):
        _fallo(path, 'DAE drift evidence contradicts its accepted scope.')


def _nonlinear_evidence(result):
    path = 'procedencia.nonlinearDiagnostics'
    value = result['procedencia']['nonlinearDiagnostics']
    required = {'version', 'method', 'sourceSignature', 'settings', 'evaluatedSolves',
                'lastEvaluation', 'failures', 'publishedSamples', 'scope'}
    def reject(message):
        _fallo(path, message)
    if not isinstance(value, dict) or set(value) != required or value['version'] != 1 or value['method'] != 'damped_newton':
        reject('Expected nonlinear diagnostics v1.')
    report = result['procedencia'].get('compilation', {})
    derived = report.get('derivedExecution', {})
    from core.modelo.derived_execution import read_definition
    try:
        selection = read_definition(derived.get('selection'))
    except (ValueError, TypeError, KeyError):
        reject('Missing valid nonlinear selection.')
    if (selection['version'] not in (3, 4) or value['sourceSignature'] != selection['sourceSignature']
            or value['settings'] != selection['nonlinear'] or not isinstance(value['scope'], str)
            or not isinstance(value['failures'], list)):
        reject('Nonlinear evidence disagrees with its formulation.')
    for key in ('evaluatedSolves', 'publishedSamples'):
        if type(value[key]) is not int or value[key] < 0:
            reject('Nonlinear counters must be nonnegative integers.')
    if value['publishedSamples'] != len(result['ejes'][0]['valores']):
        reject('Nonlinear evidence has a different publication scope.')
    if value['failures'] and result['estado'] == 'resuelto':
        reject('A failed nonlinear solve cannot report numerical completion.')
    allowed = {'iterations', 'evaluations', 'backtracks', 'residualNorm', 'stepNorm', 'conditionInfinity',
               'terminationReason', 'completedProbes', 'uniqueness', 'stage', 'path', 'equationIds',
               'quantityIds', 'modelId', 'sourceSignature', 'formulationSignature', 'time', 'code', 'message'}
    for row in [value['lastEvaluation'], *value['failures']]:
        if not isinstance(row, dict) or row.keys()-allowed:
            reject('Invalid nonlinear diagnostic fields.')
        if (row.get('sourceSignature') != selection['sourceSignature'] or row.get('modelId') != result['modeloId']
                or row.get('formulationSignature') != report.get('signature')
                or row.get('path') != 'motores.derivedExecution.nonlinear'
                or row.get('stage') not in ('runtime', 'initialization', 'publication')
                or row.get('equationIds') != [r['equationId'] for r in selection['algebraic']]
                or row.get('quantityIds') != [r['quantityId'] for r in selection['algebraic']]):
            reject('Nonlinear diagnostic location is stale or incompatible.')
        for key in ('iterations', 'evaluations', 'backtracks'):
            if type(row.get(key)) is not int or row[key] < 0:
                reject('Invalid nonlinear iteration counters.')
        for key in ('residualNorm', 'stepNorm', 'conditionInfinity', 'time'):
            number = row.get(key)
            if number is not None and (type(number) not in (int, float) or not math.isfinite(number) or number < 0):
                reject('Invalid nonlinear numerical evidence.')
        if not isinstance(row.get('terminationReason'), str):
            reject('A nonlinear termination reason is required.')
    for row in value['failures']:
        if not isinstance(row.get('code'), str) or not isinstance(row.get('message'), str) or row['terminationReason'] != row['code']:
            reject('Located failure codes and messages are required.')


def _physical_evidence(result):
    """Validate published evidence and scope, never infer physics from solve status."""
    provenance = result['procedencia']
    if 'physicalCertification' not in provenance:
        return
    certificate = provenance['physicalCertification']
    if certificate is None:
        if result['estado'] != 'fallido' or result['series'] or provenance.get('equilibrium'):
            _fallo('procedencia.physicalCertification', 'A missing certificate cannot describe published equilibrium samples.')
        return
    detail = provenance.get('equilibrium')
    path = 'procedencia.equilibrium'
    if not isinstance(detail, dict) or detail.get('certificacion') != certificate:
        _fallo(path, 'The physical certificate must match the published evidence.')
    times = result['ejes'][0]['valores'] if result['ejes'] else []
    if not times or detail.get('tiempos') != times:
        _fallo(path, 'Certified and common sample times must match.')
    scope = certificate.get('alcance', {})
    if (scope.get('tInicial') != times[0] or scope.get('tFinal') != times[-1] or scope.get('muestras') != len(times)
            or scope.get('completa') != (result['estado'] == 'resuelto')):
        _fallo(path, 'The certificate must describe the actual published scope.')
    aspects = certificate.get('aspectos', [])
    expected = {'estados_termodinamicos', 'conservacion', 'cierre_constitutivo', 'segunda_ley'}
    if len(aspects) != 4 or {a.get('id') for a in aspects} != expected:
        _fallo(path, 'All four certification aspects are required.')
    statuses = [a.get('estado') for a in aspects]
    if any(status not in ('cumple', 'no_cumple', 'no_evaluable') for status in statuses):
        _fallo(path, 'Invalid physical certification status.')
    aggregate = 'no_cumple' if 'no_cumple' in statuses else 'no_evaluable' if 'no_evaluable' in statuses else 'cumple'
    if certificate.get('estado') != aggregate:
        _fallo(path, 'Physical success cannot override a failed or unevaluable aspect.')
    common = {series['id']: series for series in result['series']}
    for series in detail.get('series', []):
        published = common.get(series['variableId'])
        if not published or published['valores'] != series['valores'] or published['unidadSI'] != series['unidadSI']:
            _fallo(path, 'A common series must preserve its certified source quantity.')
    for states in detail.get('estados', {}).values():
        if len(states) != len(times):
            _fallo(path, 'Certified states must align with every published sample.')
    if any(event['tiempo'] < times[0] or event['tiempo'] > times[-1] for event in detail.get('eventos', [])):
        _fallo(path, 'An event cannot lie outside the certified prefix.')


def _unidad(x, r):
    try:
        d = un.interpretar(x["unidadSI"])
    except un.ErrorUnidad as e:
        _fallo(r + ".unidadSI", str(e))
    if d["factor"] != 1.0 or d["desplazamiento"] != 0.0:
        _fallo(r + ".unidadSI", f"{x['unidadSI']!r} no es una unidad SI (factor {d['factor']}, desplazamiento {d['desplazamiento']})")
    if dimension_json(d["dimension"]) != x["dimension"]:
        _fallo(r + ".dimension", "no coincide con la unidad SI")
