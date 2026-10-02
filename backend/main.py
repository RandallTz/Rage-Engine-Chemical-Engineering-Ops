"""
API web del simulador de destilacion. Envoltura HTTP delgada sobre
core/columna_destilacion.py -- no contiene fisica ni logica de
resolucion, solo rutas y validacion de forma (ver schemas.py).

Correr localmente (desde la raiz del repo):
    uvicorn backend.main:app --reload --port 8000

Documentacion automatica interactiva en /docs una vez corriendo.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.schemas import (
    ResolverColumnaRequest, ResolverColumnaResponse, EjemploPreset,
    ResolverFlowsheetRequest, ResolverFlowsheetResponse, EjemploFlowsheet,
    ELVBinarioRequest, ELVBinarioResponse,
    ComponenteInfo, ModeloTermodinamico,
    ResolverDiagramaRequest, ResolverDiagramaResponse,
    GradosLibertadRequest, GradosLibertadResponse, TablaUnidades,
    BarridoRequest, BarridoResponse,
    MapaResidualRequest, MapaResidualResponse,
    AzeotroposRequest, AzeotroposResponse,
    PropiedadesReaccionRequest, PropiedadesReaccionResponse,
)
from backend.nucleo_componentes import buscar_componente, MODELOS
from backend.nucleo_diagrama import resolver_diagrama, grados_libertad, barrido
from backend.nucleo_unidades import tabla_unidades
from backend.ejemplos import EJEMPLOS, EJEMPLOS_POR_ID
from backend.ejemplos_flowsheet import EJEMPLOS_FLOWSHEET, EJEMPLOS_FLOWSHEET_POR_ID
from backend.nucleo import resolver_columna
from backend.nucleo_flowsheet import resolver_flowsheet
from backend.nucleo_elv import curva_elv_binaria
from backend.nucleo_termodinamica import mapa_residual, buscar_azeotropos, propiedades_reaccion

app = FastAPI(
    title="Simulador de Destilacion -- API",
    description="Frontera HTTP sobre el nucleo de simulacion (McCabe-Thiele, Ponchon-Savarit, FUG).",
    version="0.1.0",
)

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


@app.get("/componentes/buscar", response_model=ComponenteInfo)
def componentes_buscar(q: str):
    """Resuelve un nombre/formula/CAS y dice si sirve con el modelo termodinamico actual."""
    return buscar_componente(q)


@app.get("/modelos-termodinamicos", response_model=list[ModeloTermodinamico])
def modelos_termodinamicos():
    return MODELOS


@app.get("/ejemplos", response_model=list[EjemploPreset])
def listar_ejemplos():
    return EJEMPLOS


@app.get("/ejemplos/{ejemplo_id}", response_model=EjemploPreset)
def obtener_ejemplo(ejemplo_id: str):
    ejemplo = EJEMPLOS_POR_ID.get(ejemplo_id)
    if ejemplo is None:
        raise HTTPException(status_code=404, detail=f"No existe el ejemplo '{ejemplo_id}'.")
    return ejemplo


@app.post("/columna/resolver", response_model=ResolverColumnaResponse)
def resolver(request: ResolverColumnaRequest):
    try:
        return resolver_columna(request)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


OBSOLETO_FLOWSHEET = (
    "OBSOLETO. Este es el modelo ANTIGUO de flowsheet (core/diagrama_flujo.py), "
    "donde las corrientes no son objetos de primera clase y la informacion fluye en "
    "una sola direccion. Usa /diagrama/* en su lugar: ahi las variables del pool son "
    "escalares por corriente, se puede mandar cualquier subconjunto y el sistema "
    "resuelve en la direccion que haga falta. Se mantiene porque "
    "tests/validar_diagrama_flujo.py lo usa como comprobacion cruzada contra los "
    "mismos numeros por otro camino; los ejemplos de un modelo NO valen en el otro."
)


@app.get("/flowsheet/ejemplos", response_model=list[EjemploFlowsheet],
         deprecated=True, description=OBSOLETO_FLOWSHEET)
def listar_ejemplos_flowsheet():
    return EJEMPLOS_FLOWSHEET


@app.get("/flowsheet/ejemplos/{ejemplo_id}", response_model=EjemploFlowsheet,
         deprecated=True, description=OBSOLETO_FLOWSHEET)
def obtener_ejemplo_flowsheet(ejemplo_id: str):
    ejemplo = EJEMPLOS_FLOWSHEET_POR_ID.get(ejemplo_id)
    if ejemplo is None:
        raise HTTPException(status_code=404, detail=f"No existe el ejemplo de flowsheet '{ejemplo_id}'.")
    return ejemplo


@app.post("/flowsheet/resolver", response_model=ResolverFlowsheetResponse,
          deprecated=True, description=OBSOLETO_FLOWSHEET)
def resolver_flowsheet_endpoint(request: ResolverFlowsheetRequest):
    try:
        return resolver_flowsheet(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/diagrama/resolver", response_model=ResolverDiagramaResponse)
def diagrama_resolver(request: ResolverDiagramaRequest):
    """
    Flowsheet con corrientes de primera clase: manda cualquier
    subconjunto de variables y resuelve en la direccion que haga falta.

    Con 'especificaciones' resuelve la pregunta inversa ("que reflujo
    hace falta para esta pureza") mediante un lazo exterior: el objetivo
    y la variable manipulada pueden estar en equipos distintos, con un
    reciclo en medio.
    """
    try:
        return resolver_diagrama(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/diagrama/grados-libertad", response_model=GradosLibertadResponse)
def diagrama_grados_libertad(request: GradosLibertadRequest):
    """
    Conteo de grados de libertad SIN resolver, para avisar mientras se editan datos.

    Si se mandan especificaciones de diseno, cada una suma UNA ecuacion:
    un problema al que le faltaba un dato (GL = 1) queda cerrado (GL = 0).
    """
    try:
        return grados_libertad(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/diagrama/barrido", response_model=BarridoResponse)
def diagrama_barrido(request: BarridoRequest):
    """
    Mueve UNA variable y devuelve como responde el resto.

    Cada punto es una resolucion completa del diagrama, reciclos
    incluidos: por eso el numero de puntos esta acotado en el esquema.

    Un punto que no se puede resolver NO da 422 -- vuelve con su motivo
    dentro de la respuesta, porque el borde de la zona viable es parte de
    lo que se quiere ver. El 422 queda para lo que invalida el barrido
    entero: una variable que no existe, o barrer una que tambien se da
    como dato.
    """
    try:
        return barrido(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/unidades", response_model=TablaUnidades)
def unidades():
    """Tabla de conversion generada con pint; el frontend convierte en local con ella."""
    return tabla_unidades()


@app.post("/elv/binario", response_model=ELVBinarioResponse)
def elv_binario(request: ELVBinarioRequest):
    try:
        return curva_elv_binaria(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


# ---------------------------------------------------------------------
# Termodinamica avanzada: topologia de destilacion (reactiva y no).
# Son calculos CAROS (cada curva integra un ODE que, en cada paso, llama
# a UNIFAC y resuelve un punto de burbuja), del orden de segundos a
# decenas de segundos. El cliente debe llamarlos bajo demanda, nunca
# mientras el usuario escribe.
# ---------------------------------------------------------------------

@app.post("/termodinamica/mapa-residual", response_model=MapaResidualResponse)
def termodinamica_mapa_residual(request: MapaResidualRequest):
    """Mapa de curvas residuales, clasico o reactivo (segun venga 'reaccion' y Da)."""
    try:
        return mapa_residual(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/termodinamica/azeotropos", response_model=AzeotroposResponse)
def termodinamica_azeotropos(request: AzeotroposRequest):
    try:
        return buscar_azeotropos(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/termodinamica/reaccion", response_model=PropiedadesReaccionResponse)
def termodinamica_reaccion(request: PropiedadesReaccionRequest):
    """Barato: dice si la estequiometria y la cinetica tienen sentido antes de integrar un mapa entero."""
    try:
        return propiedades_reaccion(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))
