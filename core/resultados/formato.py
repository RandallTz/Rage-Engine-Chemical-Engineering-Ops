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
    sobran = [k for k in dato if k not in claves]
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
    return dato


def _unidad(x, r):
    try:
        d = un.interpretar(x["unidadSI"])
    except un.ErrorUnidad as e:
        _fallo(r + ".unidadSI", str(e))
    if d["factor"] != 1.0 or d["desplazamiento"] != 0.0:
        _fallo(r + ".unidadSI", f"{x['unidadSI']!r} no es una unidad SI (factor {d['factor']}, desplazamiento {d['desplazamiento']})")
    if dimension_json(d["dimension"]) != x["dimension"]:
        _fallo(r + ".dimension", "no coincide con la unidad SI")
