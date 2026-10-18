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
from backend.api_unidades import router as router_unidades
from backend.api_modelo import router as router_modelo

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
from backend.schemas_laboratorio import (
    LaboratorioRequest, LaboratorioResponse, CapacidadesLaboratorioResponse,
    EjemploLaboratorio, BusquedaSustanciaResponse, CatalogoSustanciasResponse,
)
from backend.nucleo_sustancias import buscar_sustancia, catalogo_sustancias
from backend.schemas_laboratorio import (
    BalancearRequest, BalancearResponse, ComprobarNuRequest, ComprobarNuResponse,
    EquilibrioRequest, EquilibrioResponse, LoteRequest, LoteResponse,
    CapacidadesReaccionesResponse,
)
from backend.nucleo_reacciones import (
    balancear as balancear_reaccion, comprobar_estequiometria,
    resolver_equilibrio, resolver_lote, capacidades_reacciones,
)
from backend.ejemplos_laboratorio import (
    EJEMPLOS_LABORATORIO, EJEMPLOS_LABORATORIO_POR_ID,
)
from backend.nucleo_laboratorio import (
    validar_laboratorio, resolver_laboratorio, calcular_laboratorio,
    capacidades_laboratorio,
)
from typing import Any
from fastapi import Body
from backend.motor_termodinamica import (
    capacidades as capacidades_motor_termodinamica,
    evaluar as evaluar_motor_termodinamica,
)
from backend.motor_ensamblaje import (
    capacidades as capacidades_motor_ensamblaje,
    validar as validar_motor_ensamblaje,
    resolver as resolver_motor_ensamblaje,
)

app = FastAPI(
    title="Simulador de Destilacion -- API",
    description="Frontera HTTP sobre el nucleo de simulacion (McCabe-Thiele, Ponchon-Savarit, FUG).",
    version="0.1.0",
)
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



# ---------------------------------------------------------------------
# Laboratorio: el ensamblador de sistemas por bloques.
#
# Tres rutas y no una, aunque el contrato permitia una sola con accion
# explicita: /validar y /resolver dicen en la URL que hacen, y eso evita
# el fallo tipico del endpoint unico -- mandar la accion equivocada y
# recibir algo que parece un resultado. /calcular existe igualmente para
# quien prefiera el camino unico, y ahi la accion SI es explicita.
#
# Ninguna de las tres devuelve 4xx por un montaje imposible. Devuelven
# 200 con `estado` y la lista de diagnosticos, porque es lo util: un 422
# con el formato de FastAPI no lleva codigo estable ni id de bloque, y la
# interfaz no puede senalar una pieza con eso. El 4xx se reserva para una
# peticion que no tiene la FORMA de un montaje, que es lo que Pydantic
# rechaza antes de llegar aqui.
# ---------------------------------------------------------------------

@app.post("/laboratorio/validar", response_model=LaboratorioResponse,
          summary="Valida un montaje SIN resolverlo")
def laboratorio_validar(request: LaboratorioRequest):
    """
    Ensambla el sistema, lo cuenta y lo diagnostica sin ejecutar el solver.

    Devuelve las variables con su rol, las relaciones con `ejecutada =
    false` -- la verdad: no se ejecuto nada -- y el analisis estructural
    con los grados de libertad. `convergencia` es null por el mismo
    motivo: no corrio ningun algoritmo, asi que no hay nada que declarar.
    """
    return validar_laboratorio(request)


@app.post("/laboratorio/resolver", response_model=LaboratorioResponse,
          summary="Valida y resuelve un montaje")
def laboratorio_resolver(request: LaboratorioRequest):
    """
    Resuelve el montaje con una marcha aguas abajo.

    `estado` dice que paso: 'resuelto', 'invalido' (el montaje o los datos
    estan mal), 'no_soportado' (el motor no sabe resolver eso, y lo dice
    en vez de aproximarlo) o 'no_convergente'. Con cualquier estado que no
    sea 'resuelto', los valores parciales NO se presentan como resultados.
    """
    return resolver_laboratorio(request)


@app.post("/laboratorio/calcular", response_model=LaboratorioResponse,
          summary="Endpoint unico con accion explicita")
def laboratorio_calcular(request: LaboratorioRequest):
    """
    El mismo servicio con la accion en el cuerpo: `accion: "validar"` o
    `"resolver"`.

    Por omision valida. El lado seguro es el que no gasta tiempo de
    calculo si el cliente se olvido de decir que queria.
    """
    return calcular_laboratorio(request)


@app.get("/laboratorio/capacidades", response_model=CapacidadesLaboratorioResponse,
         summary="Que admite el ensamblador, incluido lo que NO")
def laboratorio_capacidades():
    """
    Lo que el motor sabe hacer, para que la interfaz no ofrezca lo que no hay.

    Incluye la lista de lo NO soportado a proposito: un cliente que solo
    reciba lo admitido tiene que adivinar el resto, y adivinara que algo
    funciona.
    """
    return capacidades_laboratorio()


@app.get("/laboratorio/ejemplos", response_model=list[EjemploLaboratorio],
         summary="Montajes de ejemplo, listos para reenviar a /resolver")
def laboratorio_ejemplos():
    """
    Montajes que SON peticiones validas de /laboratorio/resolver.

    `modelo` se reenvia tal cual. Esto es lo que permite que la suite
    compruebe que cada preset de verdad se resuelve: un preset roto es un
    fallo que el usuario encuentra en el primer clic, y la unica forma de
    cazarlo antes es ejecutarlo.

    Uno de ellos espera 'invalido' a proposito, para que la interfaz pueda
    probar su camino de error contra un error de verdad.
    """
    return EJEMPLOS_LABORATORIO


@app.get("/laboratorio/ejemplos/{ejemplo_id}", response_model=EjemploLaboratorio)
def laboratorio_ejemplo(ejemplo_id: str):
    ejemplo = EJEMPLOS_LABORATORIO_POR_ID.get(ejemplo_id)
    if ejemplo is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay ejemplo de laboratorio con id {ejemplo_id!r}. "
                   f"Disponibles: {', '.join(EJEMPLOS_LABORATORIO_POR_ID)}.",
        )
    return ejemplo


# ---------------------------------------------------------------------
# Catalogo de sustancias del proveedor.
#
# Separado de /componentes/buscar, que contesta "existe y tiene grupos
# UNIFAC". Eso basta para un ELV y no para una reaccion, por dos motivos:
# una formula NO identifica una sustancia, y tener grupos UNIFAC no basta
# para reaccionar -- hace falta la entalpia de formacion, y hay sustancias
# que tienen lo primero y no lo segundo.
# ---------------------------------------------------------------------

@app.get("/laboratorio/sustancias/buscar", response_model=BusquedaSustanciaResponse,
         summary="Identifica una sustancia y dice COMO la identifico")
def laboratorio_sustancias_buscar(q: str):
    """
    Resuelve un nombre, CAS, SMILES, InChIKey o formula.

    `identificacion_fiable` es el campo que hay que mirar. Un CAS, un
    nombre, un SMILES o un InChIKey identifican una sustancia; una FORMULA
    no: 'C2H6O' resuelve a dimetil eter y el etanol tiene la misma
    formula, y hierven a 248 K y a 352 K. Cuando no es fiable, la
    respuesta trae los `candidatos` para que preguntes en vez de que el
    motor adivine.

    Y `capacidades` dice para QUE sirve, una por una: el diciclopentadieno
    tiene grupos UNIFAC pero no entalpia de formacion, asi que vale para
    un ELV y no para un balance reactivo. Enterarse de eso al resolver,
    cuando el calor de reaccion sale NaN, es tarde.
    """
    return buscar_sustancia(q)


@app.get("/laboratorio/sustancias/catalogo",
         response_model=CatalogoSustanciasResponse,
         summary="Que identificadores y capacidades admite el catalogo")
def laboratorio_sustancias_catalogo():
    """
    Como se pregunta y que se puede saber, sin preguntar nada.

    Declara los identificadores admitidos --con cuales identifican y
    cuales no-- y de que propiedad depende cada capacidad, para que el
    editor de especies pueda explicar por que una sustancia no sirve en
    vez de limitarse a no ofrecerla.
    """
    return catalogo_sustancias()


# ---------------------------------------------------------------------
# Balanceo, equilibrio quimico y lote transitorio.
#
# Tres endpoints y no uno porque contestan tres preguntas con requisitos
# distintos: balancear solo necesita atomos, el equilibrio necesita dG de
# formacion y no cinetica, y el lote necesita leyes de velocidad y no dG.
# Meterlas en uno con una bandera obligaria a declarar datos que no hacen
# falta y a devolver campos vacios.
# ---------------------------------------------------------------------

@app.post("/laboratorio/balancear", response_model=BalancearResponse,
          summary="Las reacciones que conservan los elementos, en aritmetica exacta")
def laboratorio_balancear(request: BalancearRequest):
    """
    Resuelve A @ nu = 0 con `fractions.Fraction`, no con floats.

    La respuesta correcta son enteros pequenos, y un metodo numerico los
    devuelve como 0.9999999999999998; con aritmetica exacta no hay nada
    que reconocer.

    Tres casos y los tres importan: sin reaccion posible, una reaccion
    unica, o un SUBESPACIO de reacciones independientes -- y en el tercero
    se devuelve la base entera, porque elegir una seria decidir que
    quimica ocurre.
    """
    return balancear_reaccion(request)


@app.post("/laboratorio/comprobar-estequiometria",
          response_model=ComprobarNuResponse,
          summary="Juzga una nu dada en vez de buscarla")
def laboratorio_comprobar_nu(request: ComprobarNuRequest):
    """Si una nu conserva los elementos, y cuanto descuadra si no."""
    return comprobar_estequiometria(request)


@app.post("/laboratorio/equilibrio", response_model=EquilibrioResponse,
          summary="Composicion de equilibrio, K(T), potenciales y estabilidad")
def laboratorio_equilibrio(request: EquilibrioRequest):
    """
    El equilibrio termodinamico de verdad, calculado de dG de FORMACION.

    **Imponer r+ = r- no demuestra equilibrio termodinamico**: describe un
    estado estacionario con esas dos tasas. Aqui K sale de las propiedades
    de formacion y no de ninguna cinetica.

    Se devuelven K por las DOS rutas --la rigurosa, con Kirchhoff y la
    integral de dCp/T, y van't Hoff-- para que la diferencia se vea. Y el
    criterio de estabilidad: dG = 0 dice que es un punto estacionario, no
    que sea un minimo, y eso lo decide el hessiano.
    """
    return resolver_equilibrio(request)


@app.post("/laboratorio/lote", response_model=LoteResponse,
          summary="La trayectoria de un lote isotermo")
def laboratorio_lote(request: LoteRequest):
    """
    Integra dn_i/dt = sum_r nu_ir r_r(T, x(t)) con el estado inicial dado.

    Usa las MISMAS leyes de velocidad que el CSTR: la ley es la misma
    fisica en los dos regimenes, y tener dos implementaciones seria tener
    dos fisicas que se pueden separar.

    El agotamiento se detecta con un EVENTO del integrador, no mirando las
    muestras -- un cruce entre dos muestras se habria perdido -- y la no
    negatividad se comprueba sobre la trayectoria devuelta.
    """
    return resolver_lote(request)


@app.get("/laboratorio/reacciones/capacidades",
         response_model=CapacidadesReaccionesResponse,
         summary="Que admiten los tres servicios de reaccion, y que no")
def laboratorio_reacciones_capacidades():
    return capacidades_reacciones()


# --- Motor independiente: termodinamica (contrato revision 1) ---------------
# Ver backend/motor_termodinamica.py y docs/MOTOR_TERMODINAMICA_H0_H1.md.
@app.get("/motor/termodinamica/capacidades",
         summary="Modelos termodinamicos publicados para /motor, con dominio y referencia")
def motor_termodinamica_capacidades():
    return capacidades_motor_termodinamica()


@app.get("/motor/catalogo",
         summary="Sustancias registradas, datos puros con procedencia y admision por paquete y operacion")
def motor_catalogo():
    """F2.1-F2.3: ver backend/motor_catalogo.py y docs/contratos/contratoCatalogo.ts."""
    from backend.motor_catalogo import catalogo_publico
    return catalogo_publico()


@app.get("/motor/termodinamica/diagramas/capacidades",
         summary="Trazado de diagramas binarios T-xy / P-xy: paquetes, perfiles y limites")
def motor_diagramas_capacidades():
    from backend.motor_diagramas import capacidades
    return capacidades()


@app.post("/motor/termodinamica/diagramas/trazar",
          summary="Un corte T-xy o P-xy de un binario con el paquete declarado; sin efectos")
def motor_diagramas_trazar(cuerpo: Any = Body(...)):
    """Todo rechazo conocido es una respuesta del protocolo con diagnosticos y ruta, no un 422."""
    from backend.motor_diagramas import trazar
    return trazar(cuerpo)


@app.get("/motor/termodinamica/diagrama",
         summary="Diagrama P-T del cierre de un modelo con fases solidas (curvas y triple); sin efectos")
def motor_termodinamica_diagrama(modelo: str = "agua-iapws95-hielo-ih", version: str = "1"):
    from backend.motor_hielo import diagrama
    return diagrama(modelo, version)


@app.post("/motor/termodinamica/evaluar",
          summary="Estado de equilibrio estable de una declaracion; sin efectos")
def motor_termodinamica_evaluar(cuerpo: Any = Body(...)):
    """
    Recibe el JSON sin modelo Pydantic a proposito: todo rechazo conocido
    (campo de mas, unidad, dato null, region no soportada) sale como
    respuesta del contrato con diagnosticos y evaluacion null, no como 422.
    """
    return evaluar_motor_termodinamica(cuerpo)

# --- Motor independiente: ensamblaje dinamico (protocolo de ensamblaje, revision 1) ---
# Ver backend/motor_ensamblaje.py y docs/MOTOR_ENSAMBLAJE_DINAMICO.md.
@app.get("/motor/ensamblajes/capacidades",
         summary="Alcance verificado del ensamblador dinamico independiente")
def motor_ensamblajes_capacidades(revision: int = 1):
    if revision == 2:
        from backend.motor_ensamblaje_v2 import capacidades_v2
        return capacidades_v2()
    return capacidades_motor_ensamblaje()


@app.post("/motor/ensamblajes/validar",
          summary="Ensamblaje, catalogo, recuento e inicializacion; no integra")
def motor_ensamblajes_validar(cuerpo: Any = Body(...)):
    return validar_motor_ensamblaje(cuerpo)[0]


@app.post("/motor/ensamblajes/resolver",
          summary="Validacion y, si esta lista, trayectoria de materia y energia")
def motor_ensamblajes_resolver(cuerpo: Any = Body(...)):
    return resolver_motor_ensamblaje(cuerpo)
