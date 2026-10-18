"""Frontera HTTP acotada; toda la matemática pertenece al núcleo único."""
import json

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from core.adimensionalizacion import capacidades
from backend.dimensiones_adimensionalizacion import auditar_dimensiones, procesar_seguro

router = APIRouter(prefix="/api/adimensionalizacion", tags=["adimensionalizacion"])
LIMITE_BYTES = 1_000_000


@router.get("/capacidades")
def obtener_capacidades():
    return capacidades()


async def leer_json(request: Request):
    cuerpo = bytearray()
    async for parte in request.stream():
        cuerpo.extend(parte)
        if len(cuerpo) > LIMITE_BYTES:
            raise HTTPException(status_code=413, detail="La solicitud supera 1 MB.")
    try:
        dato = json.loads(cuerpo, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("número no JSON")))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Se requiere un cuerpo JSON válido.") from None
    return dato


@router.post("")
async def adimensionalizar(request: Request):
    return await run_in_threadpool(procesar_seguro, await leer_json(request))


@router.post("/dimensiones")
async def dimensiones(request: Request):
    dato = await leer_json(request)
    if not isinstance(dato, dict) or dato.get("operacion") != "analizar":
        raise HTTPException(status_code=400, detail="Esta vista requiere la operación analizar.")
    return await run_in_threadpool(auditar_dimensiones, dato)
