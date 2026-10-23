"""Legacy Process Simulation routes, moved unchanged from backend/main.py (cleanup phase 3).

Column (McCabe-Thiele, Ponchon-Savarit, FUG), old and stream flowsheets, the unit table
and the thermodynamic topology tools. Decision D6 deletes this side in cleanup phase 4;
its validated outputs are frozen in tests/reference_data/legacy-distillation/. /elv/binario
and /termodinamica/* (residue maps, azeotropes, reaction properties) are rescue items: they are
reconnected to the common thermodynamic layer before deletion.
"""
from fastapi import APIRouter
from fastapi import HTTPException
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

router = APIRouter()


@router.get("/componentes/buscar", response_model=ComponenteInfo)
def componentes_buscar(q: str):
    """Resuelve un nombre/formula/CAS y dice si sirve con el modelo termodinamico actual."""
    return buscar_componente(q)


@router.get("/modelos-termodinamicos", response_model=list[ModeloTermodinamico])
def modelos_termodinamicos():
    return MODELOS


@router.get("/ejemplos", response_model=list[EjemploPreset])
def listar_ejemplos():
    return EJEMPLOS


@router.get("/ejemplos/{ejemplo_id}", response_model=EjemploPreset)
def obtener_ejemplo(ejemplo_id: str):
    ejemplo = EJEMPLOS_POR_ID.get(ejemplo_id)
    if ejemplo is None:
        raise HTTPException(status_code=404, detail=f"No existe el ejemplo '{ejemplo_id}'.")
    return ejemplo


@router.post("/columna/resolver", response_model=ResolverColumnaResponse)
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


@router.get("/flowsheet/ejemplos", response_model=list[EjemploFlowsheet],
         deprecated=True, description=OBSOLETO_FLOWSHEET)
def listar_ejemplos_flowsheet():
    return EJEMPLOS_FLOWSHEET


@router.get("/flowsheet/ejemplos/{ejemplo_id}", response_model=EjemploFlowsheet,
         deprecated=True, description=OBSOLETO_FLOWSHEET)
def obtener_ejemplo_flowsheet(ejemplo_id: str):
    ejemplo = EJEMPLOS_FLOWSHEET_POR_ID.get(ejemplo_id)
    if ejemplo is None:
        raise HTTPException(status_code=404, detail=f"No existe el ejemplo de flowsheet '{ejemplo_id}'.")
    return ejemplo


@router.post("/flowsheet/resolver", response_model=ResolverFlowsheetResponse,
          deprecated=True, description=OBSOLETO_FLOWSHEET)
def resolver_flowsheet_endpoint(request: ResolverFlowsheetRequest):
    try:
        return resolver_flowsheet(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/diagrama/resolver", response_model=ResolverDiagramaResponse)
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


@router.post("/diagrama/grados-libertad", response_model=GradosLibertadResponse)
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


@router.post("/diagrama/barrido", response_model=BarridoResponse)
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


@router.get("/unidades", response_model=TablaUnidades)
def unidades():
    """Tabla de conversion generada con pint; el frontend convierte en local con ella."""
    return tabla_unidades()


@router.post("/elv/binario", response_model=ELVBinarioResponse)
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

@router.post("/termodinamica/mapa-residual", response_model=MapaResidualResponse)
def termodinamica_mapa_residual(request: MapaResidualRequest):
    """Mapa de curvas residuales, clasico o reactivo (segun venga 'reaccion' y Da)."""
    try:
        return mapa_residual(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/termodinamica/azeotropos", response_model=AzeotroposResponse)
def termodinamica_azeotropos(request: AzeotroposRequest):
    try:
        return buscar_azeotropos(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/termodinamica/reaccion", response_model=PropiedadesReaccionResponse)
def termodinamica_reaccion(request: PropiedadesReaccionRequest):
    """Barato: dice si la estequiometria y la cinetica tienen sentido antes de integrar un mapa entero."""
    try:
        return propiedades_reaccion(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e))
