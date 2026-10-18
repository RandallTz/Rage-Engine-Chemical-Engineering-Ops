"""Rutas del servicio único de unidades (core/unidades, docs/SERVICIO_UNIDADES.md)."""
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from core import unidades as un
from core.unidades.servicio import dimension_json

router = APIRouter(prefix="/unidades", tags=["unidades"])
MAX_UNIDADES = 500


def _publicar(u):
    try:
        i = un.interpretar(u)
    except un.ErrorUnidad as e:
        return {"unidad": u, "valida": False, "motivo": str(e)}
    return {"unidad": u, "valida": True, "dimension": dimension_json(i["dimension"]), "unidadSI": un.unidad_SI(i["dimension"]),
            "factor": i["factor"], "desplazamiento": i["desplazamiento"], "afin": i["afin"],
            "magnitudes": un.magnitudes_de(i["dimension"])}


@router.get("/capacidades")
def capacidades():
    return {"formato": "rage.unidades.capacidades", "version": 0, "bases": un.servicio.ORDEN,
            "magnitudes": [{"id": n, "dimension": dimension_json(d), "unidadSI": un.unidad_SI(d)} for n, d in un.MAGNITUDES.items()]}


@router.post("/interpretar")
def interpretar(cuerpo: Any = Body(...)):
    if not isinstance(cuerpo, dict) or not isinstance(cuerpo.get("unidades"), list) or len(cuerpo["unidades"]) > MAX_UNIDADES \
            or not all(isinstance(u, str) for u in cuerpo["unidades"]):
        raise HTTPException(422, f"se espera {{'unidades': [texto, ...]}} con hasta {MAX_UNIDADES} unidades")
    return {"formato": "rage.unidades.interpretacion", "version": 0, "resultados": [_publicar(u) for u in cuerpo["unidades"]]}
