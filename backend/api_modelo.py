"""Rutas del modelo común (docs/CONTRATO_MODELO_COMUN.md, docs/CORTE_VERTICAL.md).

  POST /modelo/validar   {modelo} -> lectura estricta, relaciones siempre presentes y variables de la capa
  POST /modelo/resolver  {modelo} -> conjunto de resultados en el formato común (compilador + solvers propios)
"""
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from core.compilador import NoSoportado, resolver
from core.modelo import ErrorModelo, leer_modelo_comun, relaciones
from core.termodinamica import NoSoportado as CapaNoSoportada, variables

router = APIRouter(prefix="/modelo", tags=["modelo"])


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
