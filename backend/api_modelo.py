"""Rutas del modelo común (docs/CONTRATO_MODELO_COMUN.md, docs/CORTE_VERTICAL.md).

  POST /modelo/validar   {modelo} -> lectura estricta, relaciones siempre presentes y variables de la capa
  POST /modelo/resolver  {modelo} -> conjunto de resultados en el formato común (compilador + solvers propios)
  POST /modelo/termodinamica {modelo} | {solicitudV2} -> por volumen: cierre, fases candidatas, modelo de estado y
                         relaciones siempre presentes (panel Termodinámica del Engine; no calcula estados)
"""
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from core.compilador import NoSoportado, resolver
from core.modelo import ErrorModelo, leer_modelo_comun, relaciones
from core.modelo import desde_ensamblaje_v2
from core.termodinamica import NoSoportado as CapaNoSoportada, variables
from core.termodinamica.descripcion import describir

router = APIRouter(prefix="/modelo", tags=["modelo"])


@router.post('/derived-execution-source')
def derived_execution_source(body: Any = Body(...)):
    """Read-only pin for selecting the exact Transform graph in Solve."""
    from core.compilador.derived import source_signature
    try:
        model = leer_modelo_comun(desde_ensamblaje_v2(body['solicitudV2'])) if isinstance(body, dict) and set(body) == {'solicitudV2'} else _modelo(body)
        return {'format': 'rage.derived-execution-source', 'version': 1,
                'modelId': model['id'], 'sourceSignature': source_signature(model)}
    except (ErrorModelo, ValueError, KeyError, TypeError, NotImplementedError) as error:
        raise HTTPException(422, {'message': str(error)}) from error


def _modelo(cuerpo):
    if not isinstance(cuerpo, dict) or "modelo" not in cuerpo:
        raise HTTPException(422, "se espera {'modelo': <modelo común v0>}")
    try:
        return leer_modelo_comun(cuerpo["modelo"])
    except ErrorModelo as e:
        raise HTTPException(422, {"ruta": e.ruta, "mensaje": e.mensaje}) from e


@router.post("/validar")
def validar(cuerpo: Any = Body(...)):
    m = _modelo(cuerpo)
    try:
        var = variables(m)
    except CapaNoSoportada as e:
        var, aviso = [], str(e)
    else:
        aviso = None
    return {"formato": "rage.modelo.validacion", "version": 0, "relaciones": relaciones(m), "variables": var,
            **({"aviso": aviso} if aviso else {})}


@router.post("/resolver")
def resolver_modelo(cuerpo: Any = Body(...)):
    m = _modelo(cuerpo)
    try:
        return resolver(m)
    except (NoSoportado, CapaNoSoportada) as e:
        raise HTTPException(422, {"codigo": "no_soportado", "mensaje": str(e)}) from e


@router.post("/termodinamica")
def termodinamica(cuerpo: Any = Body(...)):
    if isinstance(cuerpo, dict) and "solicitudV2" in cuerpo:
        try:
            m = leer_modelo_comun(desde_ensamblaje_v2(cuerpo["solicitudV2"]))
        except (ErrorModelo, KeyError, TypeError, ValueError) as e:
            raise HTTPException(422, {"codigo": "solicitud_invalida", "mensaje": str(e)}) from e
    else:
        m = _modelo(cuerpo)
    return describir(m)
