"""
HTTP API of the Model Engine. Thin routers over the common model, units,
nondimensionalization and the engine services; no physics here.

Correr localmente (desde la raiz del repo):
    uvicorn backend.main:app --reload --port 8000

Documentacion automatica interactiva en /docs una vez corriendo.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api_adimensionalizacion import router as router_adimensionalizacion
from backend.api_unidades import router as router_unidades
from backend.api_modelo import router as router_modelo
from backend.routes_engine import router as router_engine

app = FastAPI(
    title="Simulador de Destilacion -- API",
    description="HTTP boundary of the Model Engine (common model, units, nondimensionalization, engine services).",
    version="0.1.0",
)
app.include_router(router_adimensionalizacion)
app.include_router(router_unidades)
app.include_router(router_modelo)

# Abierto por ahora (sin lista de origenes fija) porque el frontend
# todavia no tiene un dominio de despliegue definitivo -- restringir a
# la URL real de Vercel una vez exista.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/salud")
def salud():
    return {"estado": "ok"}


# The legacy Process Simulation routes were deleted in cleanup step 4 (clean-4, 2026-10-29);
# the laboratory was deleted on 2026-10-22.
app.include_router(router_engine)
