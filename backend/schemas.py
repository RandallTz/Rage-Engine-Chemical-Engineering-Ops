"""
Esquemas Pydantic de la API web -- la frontera HTTP/JSON. Traducen entre
lo que un frontend puede mandar (listas de floats, strings) y lo que el
nucleo Python espera (numpy arrays, objetos Corriente/ColumnaDestilacion).
No contienen ninguna logica de calculo -- eso vive en core/, esto solo
valida forma y tipos.
"""
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class CorrienteFeed(BaseModel):
    composicion: list[float] = Field(..., description="Fracciones molares, deben sumar 1.0, mismo orden que 'nombres' del caso.")
    flujo_molar: float = Field(..., gt=0, description="Flujo molar total de alimentacion [mol/s].")
    T: Optional[float] = Field(None, description="Temperatura [K]. Si se omite, se calcula el punto de burbuja de la mezcla (alimentacion saturada).")
    P: float = Field(..., gt=0, description="Presion del sistema [Pa].")


class CorrienteSalida(BaseModel):
    nombres: list[str]
    composicion: list[float]
    flujo_molar: float
    T: float
    P: float


class ResolverColumnaRequest(BaseModel):
    metodo: Literal["mccabe_thiele", "ponchon_savarit", "fug"]
    nombres: list[str] = Field(..., description="Nombres de componentes reconocidos por 'thermo', mismo orden que 'composicion' del feed.")
    feed: CorrienteFeed
    parametros: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "mccabe_thiele: x_D, x_B, q, y (R o N, el que se quiera dar conocido). "
            "ponchon_savarit: x_D, x_B, q, y (Qc_D o N). "
            "fug: recuperacion_LK_D, recuperacion_HK_B, R."
        ),
    )
    indice_LK: Optional[int] = Field(None, description="Solo 'fug': indice (0-based) del componente clave ligero.")
    indice_HK: Optional[int] = Field(None, description="Solo 'fug': indice (0-based) del componente clave pesado.")


class DiagramaMcCabeThiele(BaseModel):
    """Datos para dibujar la construccion grafica en el frontend (no una imagen: puntos)."""
    tipo: Literal["mccabe_thiele"] = "mccabe_thiele"
    x_equilibrio: list[float]
    y_equilibrio: list[float]
    escalones: list[list[float]] = Field(description="Polilinea [[x,y],...] del escalonamiento, de x_D a x_B.")
    interseccion_rol_q: list[float] = Field(description="[x,y] donde la recta de operacion de rectificacion corta la linea q.")
    z_F: float
    q: float
    x_D: float
    x_B: float
    R: float
    R_min: float
    N: float


class DiagramaPonchonSavarit(BaseModel):
    """
    Construccion entalpia-composicion (H vs x). A diferencia de
    McCabe-Thiele, aqui hay DOS curvas de saturacion (liquido y vapor) y
    el escalonamiento alterna entre ellas: la recta de reparto une
    (x, H_L) con su vapor en equilibrio (y, H_V), y la recta operativa
    sale del polo activo. Se mandan los segmentos ya resueltos, no una
    imagen, para que el frontend los dibuje con su propio tema.
    """
    tipo: Literal["ponchon_savarit"] = "ponchon_savarit"
    x_saturacion: list[float] = Field(description="Malla de composicion para ambas curvas de saturacion.")
    H_liquido: list[float] = Field(description="H_L(x) [J/mol] sobre esa malla.")
    H_vapor: list[float] = Field(description="H_V(x) [J/mol] sobre esa malla.")
    escalera: list[list[float]] = Field(description="Polilinea [[x,H],...] del escalonamiento completo.")
    tie_lines: list[list[float]] = Field(description="Rectas de reparto [[x,H_L,y,H_V],...].")
    lineas_operativas: list[list[float]] = Field(
        description="[[x_polo,H_polo,x,H_L,y,H_V],...]: del polo activo al punto de la etapa."
    )
    x_delta_D: float
    H_delta_D: float = Field(description="Polo de rectificacion: H_L(x_D) + Qc_D.")
    x_delta_B: float
    H_delta_B: float = Field(description="Polo de agotamiento: H_L(x_B) - QR_B.")
    z_F: float
    H_F: float
    x_D: float
    x_B: float
    Qc_D: float
    QR_B: float
    Qc_D_min: Optional[float] = Field(None, description="Minimo por debajo del cual hay pinch (busqueda numerica).")
    N: float


# Union discriminada: el frontend elige el renderizador por 'tipo' en vez
# de adivinar por que campos vienen presentes.
DiagramaColumna = Annotated[
    Union[DiagramaMcCabeThiele, DiagramaPonchonSavarit],
    Field(discriminator="tipo"),
]


class ResolverColumnaResponse(BaseModel):
    completo: bool
    incognitas_restantes: list[str]
    escalares: dict[str, float] = Field(description="N, R, R_min, N_min, Q_c, Q_R, etc. -- lo que se haya podido resolver.")
    T_feed_usada: float
    D: Optional[CorrienteSalida] = None
    B: Optional[CorrienteSalida] = None
    diagrama: Optional[DiagramaMcCabeThiele] = Field(None, description="Solo para metodo 'mccabe_thiele' resuelto por completo.")


class EjemploPreset(BaseModel):
    id: str
    titulo: str
    descripcion: str
    metodo: Literal["mccabe_thiele", "ponchon_savarit", "fug"]
    nombres: list[str]
    feed: CorrienteFeed
    parametros: dict[str, float]
    indice_LK: Optional[int] = None
    indice_HK: Optional[int] = None


# ---------------------------------------------------------------------
# Flowsheet (DiagramaFlujo): varias operaciones conectadas por Corrientes,
# con reciclos opcionales. Ver core/diagrama_flujo.py.
# ---------------------------------------------------------------------

class OperacionDef(BaseModel):
    nombre: str = Field(..., description="Nombre unico de esta operacion dentro del diagrama.")
    tipo: Literal["columna", "bomba", "mezclador", "divisor"]
    config: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "columna: metodo, nombres, P_sistema, q, indice_LK/indice_HK (solo fug), "
            "z_F_fug (solo fug -- composicion FIJA de construccion, ver nota de "
            "ColumnaDestilacion.resolver_desde_feed), variables_entrada_extra, variables_salida_extra. "
            "bomba: sin config. "
            "mezclador: nombres, puertos_entrada (lista de nombres de puerto). "
            "divisor: puertos_salida (lista de nombres de puerto), fracciones (mismo orden, suman 1.0)."
        ),
    )


class ConexionDef(BaseModel):
    origen: str
    puerto_salida: str
    destino: str
    puerto_entrada: str


class RecicloDef(BaseModel):
    conexion: ConexionDef = Field(..., description="Debe ser una de las conexiones del diagrama -- la que se rompe para iterar.")
    valor_inicial: Any = Field(..., description="Supuesto inicial: float o Corriente-like dict, segun el tipo de esa clave.")
    tolerancia: float = 1e-4
    max_iteraciones: int = 50


class ResolverFlowsheetRequest(BaseModel):
    operaciones: list[OperacionDef]
    conexiones: list[ConexionDef] = Field(default_factory=list)
    valores_conocidos: dict[str, Any] = Field(
        default_factory=dict,
        description="Claves calificadas 'operacion.variable' -> float o Corriente-like dict.",
    )
    reciclo: Optional[RecicloDef] = None


class ResolverFlowsheetResponse(BaseModel):
    completo: bool
    incognitas_restantes: list[str]
    pool: dict[str, Any] = Field(description="Claves calificadas -> float o Corriente-like dict, lo que se haya resuelto.")
    convergencia_reciclo: Optional[bool] = None
    iteraciones_reciclo: Optional[int] = None


class EjemploFlowsheet(BaseModel):
    id: str
    titulo: str
    descripcion: str
    definicion: ResolverFlowsheetRequest


# ---------------------------------------------------------------------
# Termodinamica: diagramas ELV binarios (y-x y T-x-y).
# ---------------------------------------------------------------------

class ComponenteInfo(BaseModel):
    consulta: str
    encontrado: bool
    nombre: Optional[str] = Field(None, description="Nombre canonico, el que hay que mandar al resto de la API.")
    formula: Optional[str] = None
    MW: Optional[float] = None
    CAS: Optional[str] = None
    Tb: Optional[float] = Field(None, description="Punto de ebullicion normal [K] -- util para ordenar de ligero a pesado.")
    apto_unifac: bool = False
    mensaje: Optional[str] = None


class ModeloTermodinamico(BaseModel):
    id: str
    nombre: str
    descripcion: str
    disponible: bool


class ELVBinarioRequest(BaseModel):
    nombres: list[str] = Field(..., description="Exactamente 2 nombres reconocidos por 'thermo'; el primero es el ligero.")
    P: float = Field(101325.0, gt=0, description="Presion del sistema [Pa].")
    n_puntos: int = Field(60, ge=10, le=300, description="Puntos del barrido de composicion (cada uno es un punto de burbuja completo, con UNIFAC -- subirlo cuesta tiempo).")


class PuntoAzeotropo(BaseModel):
    x: float
    T: float


class ELVBinarioResponse(BaseModel):
    nombres: list[str]
    P: float
    x: list[float]
    y: list[float]
    T: list[float]
    Tb_ligero: float
    Tb_pesado: float
    azeotropo: Optional[PuntoAzeotropo] = Field(None, description="Cruce de y(x) con la diagonal, si existe. Estimacion por interpolacion del barrido, no el calculo riguroso de core/analisis_nodos.py.")


# ---------------------------------------------------------------------
# Diagrama con CORRIENTES de primera clase (core/diagrama_corrientes.py).
# Sustituye al modelo de puertos+cables: aqui las variables del pool son
# escalares por corriente ("s1.F", "s1.x0"...), asi que el cliente puede
# mandar cualquier subconjunto y el sistema resuelve en la direccion que
# haga falta, en vez de exigir corrientes completas.
# ---------------------------------------------------------------------

class OperacionDiagrama(BaseModel):
    nombre: str
    tipo: Literal["columna", "mezclador", "divisor", "bomba", "reactor_cstr"]
    corrientes: dict[str, Any] = Field(
        description=(
            "columna: alimentacion/destilado/fondos. mezclador: entradas (lista)/salida. "
            "divisor: entrada/salidas (lista). bomba: entrada/salida. "
            "reactor_cstr: entradas (lista)/salida."
        )
    )
    metodo: Optional[Literal["mccabe_thiele", "ponchon_savarit", "fug"]] = None
    P_sistema: float = 101325.0
    q: Optional[float] = Field(None, description="ponchon_savarit y fug: q es parametro fijo, no variable de pool.")
    indice_LK: Optional[int] = Field(
        None, ge=0,
        description="Solo fug: indice (0-based) del componente clave LIGERO dentro de 'componentes'.",
    )
    indice_HK: Optional[int] = Field(
        None, ge=0,
        description="Solo fug: indice (0-based) del componente clave PESADO.",
    )
    fracciones: Optional[list[float]] = Field(None, description="Solo divisor.")
    con_balance_energia: bool = Field(
        True,
        description=(
            "Solo columna: incluir o no las cargas termicas. Separarlo permite resolver primero el "
            "balance de materia y acoplar la energia solo cuando haga falta."
        ),
    )
    reaccion: Optional["ReaccionSpec"] = Field(
        None,
        description=(
            "Solo reactor_cstr: estequiometria y cinetica. Sin ella el reactor solo resuelve "
            "balances de materia (hay que dar el avance o la conversion), que sigue siendo util."
        ),
    )
    con_cinetica: bool = Field(
        True,
        description="Solo reactor_cstr: si se incluye xi = V*r(T,x_salida) para poder dimensionar el tanque.",
    )


class ResolverDiagramaRequest(BaseModel):
    componentes: list[str]
    corrientes: list[str]
    operaciones: list[OperacionDiagrama] = Field(default_factory=list)
    valores: dict[str, float] = Field(
        default_factory=dict,
        description="Claves 'corriente.variable' (s1.F, s1.T, s1.P, s1.x0...) u 'operacion.variable' (col1.R, col1.N...).",
    )
    caudales_masicos: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Caudal de una corriente dado en MASA [kg/s], por nombre de corriente. Es otra forma de "
            "fijar la misma variable F: la conversion a moles depende de la composicion, asi que "
            "entra como restriccion y no como valor fijo."
        ),
    )


class InformeBloque(BaseModel):
    bloque: str
    incognitas: list[str]
    faltantes_para_disparar: list[str]
    puede_dispararse: bool


class Inconsistencia(BaseModel):
    bloque: str
    # Opcionales: cuando el problema lo detecta el propio bloque al
    # resolver (y no la comprobacion variable-a-variable), solo hay mensaje.
    variable: Optional[str] = None
    dado: Optional[float] = None
    implicado: Optional[float] = None
    mensaje: str


class InfoReciclo(BaseModel):
    """
    Estado del bucle de reciclo. Presente solo si el diagrama tiene lazos.
    'cortes' son las corrientes que se supusieron para romperlos.
    """
    cortes: list[str]
    convergio: bool
    ciclos: int
    error: Optional[float] = None
    mensaje: Optional[str] = None
    tolerancia: float


class ResolverDiagramaResponse(BaseModel):
    completo: bool
    inconsistencias: list[Inconsistencia] = Field(
        default_factory=list,
        description="Ecuaciones que los datos dados NO cumplen. Si hay alguna, 'completo' no significa correcto.",
    )
    pool: dict[str, Any]
    incognitas_restantes: list[str]
    resueltos_por: dict[str, str]
    diagnostico: list[InformeBloque]
    variables: list[str]
    diagramas: dict[str, DiagramaColumna] = Field(
        default_factory=dict,
        description=(
            "Construccion grafica por columna resuelta (clave = nombre de la columna). "
            "Union discriminada por 'tipo': McCabe-Thiele da y-x, Ponchon-Savarit da H-x."
        ),
    )
    masas_molares_mezcla: dict[str, float] = Field(
        default_factory=dict,
        description="MW [g/mol] de cada corriente con composicion conocida, para mostrar caudales en masa.",
    )
    reciclo: Optional[InfoReciclo] = Field(
        None, description="Solo si el diagrama tiene lazos: como fue la convergencia del reciclo."
    )


# ---------------------------------------------------------------------
# Unidades: tabla generada con pint para que el frontend convierta en
# local. El nucleo sigue trabajando siempre en SI.
# ---------------------------------------------------------------------

class UnidadInfo(BaseModel):
    simbolo: str
    etiqueta: str
    magnitud: str = Field("", description="A que magnitud pertenece: el cliente lo usa para saber si es masica.")
    factor: float = Field(description="valor_SI = valor*factor + desplazamiento")
    desplazamiento: float
    requiere_masa_molar: bool = Field(
        False,
        description=(
            "Si es true, la conversion NO es afin: pasar de masa a moles necesita la masa molar de "
            "LA MEZCLA de esa corriente, que depende de su composicion."
        ),
    )


class Magnitud(BaseModel):
    si: str
    unidades: list[UnidadInfo]
    requiere_masa_molar: bool = False


class TablaUnidades(BaseModel):
    magnitudes: dict[str, Magnitud]
    variables: dict[str, list[str]] = Field(
        description="variable -> magnitudes compatibles. Lo que no aparece es adimensional."
    )


class GradosLibertadRequest(BaseModel):
    componentes: list[str]
    corrientes: list[str]
    operaciones: list[OperacionDiagrama] = Field(default_factory=list)
    valores: dict[str, float] = Field(default_factory=dict)
    caudales_masicos: dict[str, float] = Field(default_factory=dict)


class Redundancia(BaseModel):
    bloque: str
    sobran: int
    dados: list[str]
    necesarios: int


class GradosLibertadResponse(BaseModel):
    variables: int
    dadas: int
    incognitas: int
    ecuaciones: int
    grados_de_libertad: int = Field(
        description=">0 faltan datos; 0 exactamente especificado; <0 sobran (hay que comprobar consistencia)."
    )
    redundancias: list[Redundancia] = Field(
        default_factory=list,
        description=(
            "Ecuaciones con mas datos de los necesarios. El conteo global no ve la DISTRIBUCION: "
            "se puede tener GL<0 y a la vez variables sin determinar."
        ),
    )


# ---------------------------------------------------------------------
# Termodinamica: mapas de curvas residuales (reactivas y no) y
# azeotropos. El nucleo (core/topology.py) sabe dibujar esto en
# matplotlib; aqui SOLO viajan los puntos, para que el navegador lo
# pinte con su propio tema en vez de recibir una imagen.
# ---------------------------------------------------------------------

class ReaccionSpec(BaseModel):
    """
    La reaccion, en el MISMO orden de componentes que el resto del
    request: nu negativo = reactivo, positivo = producto.
    """
    nu: list[float] = Field(description="Coeficientes estequiometricos, un float por componente.")
    A: float = Field(description="Factor preexponencial de Arrhenius, en las unidades de r.")
    Ea: float = Field(description="Energia de activacion [J/mol].")
    componente_referencia: int = Field(
        0, ge=0,
        description="Indice k del componente de referencia para la transformacion de Barbosa-Doherty.",
    )


class MapaResidualRequest(BaseModel):
    componentes: list[str] = Field(min_length=3, max_length=4)
    P_sistema: float = Field(101325.0, gt=0)
    reaccion: Optional[ReaccionSpec] = Field(
        None, description="Sin reaccion, sale el mapa de curvas residuales clasico."
    )
    Da: float = Field(0.0, ge=0, description="Numero de Damkohler. Da=0 equivale a no reactivo.")
    n_curvas: int = Field(24, ge=1, le=120)
    n_puntos: int = Field(120, ge=10, le=600)
    xi_max: float = Field(
        40.0, gt=0,
        description=(
            "Hasta donde se integra el tiempo adimensional. Con valores cortos (el default era 12) "
            "las curvas se cortan ANTES de llegar a su nodo y el mapa queda como un abanico de "
            "trayectorias colgadas, sin topologia legible."
        ),
    )
    T_referencia: float = Field(
        350.0, gt=0,
        description="T a la que se evaluan K_eq (curva de equilibrio quimico) y los saltos discretos.",
    )
    incluir_trayectorias_discretas: bool = Field(
        True,
        description="El mapeo etapa a etapa del metodo original, ademas de las curvas residuales continuas.",
    )
    max_etapas: int = Field(60, ge=2, le=400, description="Etapas del mapeo discreto.")


class CurvaResidual(BaseModel):
    inicio: list[float]
    puntos: list[list[float]] = Field(description="[[x0,x1,x2(,x3)],...] a lo largo de la curva.")
    xi: list[float]


class PoloGeometrico(BaseModel):
    """
    pi = nu/nu_tot. Todas las rectas estequiometricas pasan por el. Si la
    reaccion es equimolar (nu_tot=0) el polo se va al infinito y esas
    rectas salen PARALELAS: es un caso topologicamente distinto, por eso
    se informa la direccion en vez de inventar un punto.
    """
    equimolar: bool
    x_pi: Optional[list[float]] = None
    direccion: Optional[list[float]] = None


class MapaResidualResponse(BaseModel):
    componentes: list[str]
    curvas: list[CurvaResidual]
    # --- Los tres elementos que acompanan a las trayectorias en el metodo
    # original y que faltaban aqui: sin ellos el mapa es un abanico de
    # curvas sin marco de referencia.
    trayectorias_reactivas: list[list[list[float]]] = Field(
        default_factory=list,
        description="Mapeo DISCRETO etapa a etapa (salto fisico + salto quimico), el que dibuja el libro.",
    )
    curva_equilibrio_quimico: list[list[float]] = Field(
        default_factory=list,
        description="Lugar donde se cumple K_eq(T): separa la zona de reactivos de la de productos.",
    )
    lineas_estequiometricas: list[list[list[float]]] = Field(
        default_factory=list,
        description="Rectas de reaccion pura x(z) = (x_base + z*nu)/(1 + z*nu_tot), todas pasan por el polo.",
    )
    polo: Optional[PoloGeometrico] = None
    curvas_fallidas: int = Field(
        0, description="Semillas cuya integracion no prospero (se omiten en vez de tumbar el mapa)."
    )
    motivo_fallos: Optional[str] = Field(
        None,
        description="Por que fallo la primera curva que fallo. Un mapa a medias sin explicacion es peor que uno vacio.",
    )
    T_vertices: list[Optional[float]] = Field(description="T de ebullicion de cada componente puro [K].")
    aviso_balance: Optional[str] = Field(
        None, description="Presente si la estequiometria de la reaccion no conserva los atomos."
    )
    es_reactivo: bool
    Da: float
    P_sistema: float


class AzeotroposRequest(BaseModel):
    componentes: list[str] = Field(min_length=3, max_length=4)
    P_sistema: float = Field(101325.0, gt=0)
    reaccion: ReaccionSpec
    Da: float = Field(1.0, ge=0)
    modo: Literal["cinetico", "equilibrio"] = "cinetico"
    n_semillas: int = Field(12, ge=1, le=60)


class AzeotropoEncontrado(BaseModel):
    x: list[float]
    T: Optional[float]
    residual: float
    desde: list[float] = Field(description="Semilla desde la que se llego (util para ver la cuenca).")


class AzeotroposResponse(BaseModel):
    componentes: list[str]
    modo: str
    azeotropos: list[AzeotropoEncontrado]
    semillas_probadas: int


class PropiedadesReaccionRequest(BaseModel):
    componentes: list[str] = Field(min_length=2)
    reaccion: ReaccionSpec
    P_sistema: float = Field(101325.0, gt=0)
    Da: float = Field(0.0, ge=0)
    T_referencia: float = Field(350.0, gt=0)


class PropiedadesReaccionResponse(BaseModel):
    aviso_balance: Optional[str] = Field(
        None,
        description="Presente si la estequiometria NO conserva los atomos. Nada de lo demas es fiable si sale esto.",
    )
    dH_rxn: float = Field(description="Entalpia estandar de reaccion [J/mol].")
    dG_rxn: float = Field(description="Gibbs estandar de reaccion [J/mol].")
    K_eq_std: float
    K_eq: float
    T_referencia: float
    velocidad_equimolar: Optional[float] = Field(
        None, description="r(T_ref, x equimolar): si sale ~0 la reaccion esta practicamente en equilibrio ahi."
    )
    exotermica: bool


# OperacionDiagrama referencia a ReaccionSpec, que se define mas abajo en
# este mismo archivo (el bloque de termodinamica). La referencia va como
# string y hay que resolverla aqui, al final, cuando ya existe la clase.
OperacionDiagrama.model_rebuild()
