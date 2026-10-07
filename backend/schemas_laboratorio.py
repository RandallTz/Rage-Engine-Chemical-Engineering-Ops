"""
Esquemas de /laboratorio/*. Forma de la peticion y de la respuesta.

POR QUE ESTAN EN UN MODULO APARTE
---------------------------------
`backend/schemas.py` ya pasa de mil lineas y describe un contrato distinto
-- el del diagrama de corrientes, con operaciones y un pool plano de
variables. El laboratorio habla de piezas, conexiones y relaciones. Son
dos vocabularios, y mezclarlos en un archivo invita a reutilizar un
esquema porque "se parece", que es como un cambio en el diagrama acaba
rompiendo el laboratorio.

LA DECISION QUE DA FORMA A ESTE MODULO: VALIDAR LA FORMA, NO LA FISICA
----------------------------------------------------------------------
Pydantic valida aqui solo lo que es cuestion de FORMA: que los tipos sean
los que son y que la peticion no sea desproporcionada. Todo lo semantico
-- que los identificadores no se repitan, que las conexiones apunten a
piezas que existen, que las especificaciones no se contradigan, que haya
exactamente una especificacion termica por volumen -- se valida en
`core/laboratorio.py` y sale como DIAGNOSTICOS.

No es pereza: es que un rechazo de Pydantic sale como un 422 con el
formato de FastAPI, y ese formato no lleva codigo estable, ni id de
bloque, ni accion sugerida. El contrato pide exactamente esas tres cosas,
y la interfaz las necesita para senalar la ficha concreta. Una peticion
sintacticamente valida y fisicamente imposible devuelve 200 con
`estado: "invalido"` y la lista de lo que le pasa; eso es mas util que un
422 que dice "value is not a valid float" sin decir donde.

Los limites de tamano SI van aqui, porque son lo unico que hay que
rechazar antes de mirar: una peticion con cien mil bloques no merece un
diagnostico, merece un no.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# Topes de la peticion. No son limites fisicos sino de servicio: la mesa
# del frontend admite ocho piezas, y estos dejan margen de sobra para que
# el tope no sea este modulo.
MAX_BLOQUES = 16
MAX_CONEXIONES = 32
MAX_ESPECIFICACIONES = 64
MAX_COMPONENTES = 8


class ValorConUnidad(BaseModel):
    valor: float
    unidad: str = Field(
        max_length=24,
        description="Obligatoria. Sin unidad habria que suponer SI, y un calor en kW "
                    "tomado por W da un resultado mil veces menor que parece "
                    "perfectamente razonable.",
    )


class BloqueLaboratorio(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    tipo: str = Field(
        max_length=40,
        description="entrada, salida, corriente, recipiente, reactor, calor o "
                    "trabajo. No se valida aqui: un tipo desconocido sale como "
                    "diagnostico con el id del bloque.",
    )
    nombre: Optional[str] = Field(None, max_length=120)
    datos: Optional[dict[str, Optional[float]]] = Field(
        None,
        description="Datos locales de la pieza, como los exporta la mesa. Las "
                    "unidades son IMPLICITAS (F mol/s, T K, p Pa, x adimensional, "
                    "**Q kW**) y por eso el camino preferente son las "
                    "'especificaciones', que llevan la unidad escrita. Una clave "
                    "ausente NO vale cero: la variable sigue siendo incognita.",
    )


class ConexionLaboratorio(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    desde: str = Field(min_length=1, max_length=120)
    hacia: str = Field(min_length=1, max_length=120)
    tipo: Optional[str] = Field(
        None, max_length=24,
        description="materia, calor o trabajo. Informativo: el motor lo deduce de "
                    "los tipos de las piezas que une, porque es la pieza la que "
                    "dice que intercambia y no la etiqueta de la flecha.",
    )


class EspecificacionLaboratorio(BaseModel):
    bloque_id: str = Field(min_length=1, max_length=120)
    variable: str = Field(
        max_length=24,
        description="F, T, p, x, Q o W. En un VOLUMEN, 'T' es la temperatura de su "
                    "corriente de SALIDA, no la de la alimentacion.",
    )
    # Opcional a proposito, aunque una especificacion sin valor no sirva de
    # nada. `JSON.stringify` de JavaScript convierte NaN e Infinity en
    # null, asi que un campo vacio en la interfaz llega aqui como null y es
    # EL caso realista -- mas que el NaN, que ni siquiera es JSON valido.
    # Si el tipo fuera `float` a secas, Pydantic devolveria un 422 sin
    # codigo estable ni id de bloque, y la interfaz no podria senalar el
    # campo. Asi llega al nucleo y sale como diagnostico con su sitio.
    valor: Optional[float] = None
    unidad: Optional[str] = Field(None, max_length=24)


class LaboratorioRequest(BaseModel):
    version: int = Field(
        1, description="Version del contrato que el cliente habla. Hoy: 1.")
    componentes: list[str] = Field(
        max_length=MAX_COMPONENTES,
        description="Identificadores del proveedor, EN ORDEN: 'x' es la fraccion del "
                    "primero. Esta entrega resuelve binarios.",
    )
    modelo_termodinamico: Optional[str] = Field(
        None, max_length=60,
        description="Explicito, o el documentado por omision ('unifac_raoult'). Un "
                    "resultado sin modelo declarado no se puede comparar con otro.",
    )
    referencia_entalpia: Optional[str] = Field(
        None, max_length=60,
        description="La referencia importa porque este calculo RESTA entalpias: dos "
                    "estados medidos contra referencias distintas no se restan.",
    )
    presion_sistema: Optional[ValorConUnidad] = Field(
        None, description="Uniforme en esta entrega. Por omision 101325 Pa.")
    bloques: list[BloqueLaboratorio] = Field(max_length=MAX_BLOQUES)
    conexiones: list[ConexionLaboratorio] = Field(max_length=MAX_CONEXIONES)
    supuestos: dict[str, Any] = Field(
        default_factory=dict,
        description="estacionario, adiabatico, sinTrabajo, sinReaccion y "
                    "sinMovimiento. Se piden los cinco: omitir uno dejaria al motor "
                    "eligiendo fisica por su cuenta. Que falte o no sea booleano sale "
                    "como diagnostico, no como 422.",
    )
    especificaciones: list[EspecificacionLaboratorio] = Field(
        default_factory=list, max_length=MAX_ESPECIFICACIONES)
    # Lo que el JSON de la mesa trae y aqui se ignora a proposito.
    relaciones: Optional[Any] = Field(
        None,
        description="Las relaciones en LaTeX que la mesa exporta para consulta. SE "
                    "IGNORAN como entrada ejecutable: el motor ensambla desde los "
                    "tipos fisicos de las piezas y emite su propio LaTeX. "
                    "Interpretar esta cadena seria ejecutar lo que un cliente "
                    "escribio.",
    )
    estado: Optional[str] = Field(None, max_length=60, description="Ignorado.")
    solver: Optional[str] = Field(None, max_length=200, description="Ignorado.")
    accion: Optional[Literal["validar", "resolver"]] = Field(
        None,
        description="Solo en /laboratorio/calcular, el endpoint unico. En "
                    "/laboratorio/validar y /laboratorio/resolver se ignora: la "
                    "ruta ya dice que se pide.",
    )


# =====================================================================
# Respuesta
# =====================================================================

class DiagnosticoLaboratorio(BaseModel):
    codigo: str = Field(
        description="Identificador estable para ramificar. El mensaje es para leer.")
    severidad: Literal["error", "advertencia", "informacion"]
    categoria: Literal["datos", "fisica", "numerica", "modelo", "informacion",
                       "desconocido"]
    mensaje: str
    accion_sugerida: Optional[str] = Field(
        None,
        description="Separado del mensaje a proposito: el mensaje dice que pasa, "
                    "esto dice que hacer, y mezclarlos da textos que no sirven para "
                    "ninguna de las dos cosas.",
    )
    bloque_ids: list[str] = Field(
        default_factory=list,
        description="Ids que EXISTEN en la peticion, para poder senalar la ficha.")
    conexion_ids: list[str] = Field(default_factory=list)
    variable_ids: list[str] = Field(default_factory=list)


class VariableLaboratorio(BaseModel):
    id: str
    bloque_ids: list[str]
    conexion_ids: list[str]
    simbolo: str
    magnitud: str
    unidad: str
    rol: Literal["impuesta", "calculada", "compartida"] = Field(
        description="'compartida' es el rol de las variables de una corriente "
                    "intermedia: las referencian los dos volumenes y son LA MISMA, "
                    "no una copia. Puede estar impuesta o calculada ademas, y eso lo "
                    "dice 'impuesta'.",
    )
    compartida: bool
    impuesta: bool
    valor: Optional[float] = Field(
        None, description="null si no se determino. Nunca un cero de relleno.")
    procedencia: Optional[str] = Field(
        None, description="De donde salio: que especificacion, o que relacion la "
                          "calculo. Dice tambien si el valor llego sin unidad "
                          "escrita (dato local).")


class TerminoDescartado(BaseModel):
    termino: str
    latex: str
    supuesto: str
    motivo: str


class EcuacionLaboratorio(BaseModel):
    id: str
    tipo: Literal["balance", "constitutiva", "condicion", "convencion", "cierre",
                  "verificacion"]
    titulo: str
    origen_bloques: list[str]
    origen_conexiones: list[str]
    variables: list[str]
    latex_general: str = Field(description="La ley completa, antes de los supuestos.")
    latex_activo: str = Field(description="Lo que queda tras aplicarlos.")
    terminos_descartados: list[TerminoDescartado] = Field(
        default_factory=list,
        description="Que se cayo y por que supuesto. Es lo que distingue 'este "
                    "termino no aplica' de 'este termino se olvido'.",
    )
    cuenta_como_ecuacion: bool = Field(
        description="Si entra en el recuento de ecuaciones independientes. Las "
                    "convenciones de signo, las especificaciones, el cierre por "
                    "parametrizacion y la verificacion global NO entran.",
    )
    ejecutada: bool = Field(
        description="Si el solver la uso en ESTE calculo. En /validar son todas "
                    "false, porque no se ejecuto nada.")
    residuo: Optional[float] = Field(
        None,
        description="null si no se midio, y eso NO es residuo cero. Una evaluacion "
                    "directa no tiene residuo: presentar el error de redondeo seria "
                    "presentarlo como una convergencia.",
    )
    escala: Optional[str] = None
    unidad: Optional[str] = None
    iteraciones: Optional[int] = None
    metodo: Optional[str] = None
    alcance: Optional[str] = Field(
        None, description="algebraico_directo, inversion_escalar o evaluacion_directa.")
    nota: Optional[str] = None


class AnalisisLaboratorio(BaseModel):
    variables_totales: int
    impuestas: int
    incognitas: int
    ecuaciones_independientes: int
    grados_libertad: int
    rango: Optional[int] = Field(
        None,
        description="Rango ESTRUCTURAL, no el de un Jacobiano en un punto. "
                    "'rango_origen' dice de donde sale.")
    rango_origen: str
    metodo: Optional[str] = Field(
        None, description="El algoritmo que de verdad corrio. null en /validar, que "
                          "no ejecuta ninguno.")
    alcance: Optional[str] = None
    nota_metodo: Optional[str] = None
    orden_resolucion: list[str]
    no_contadas: dict[str, int]
    nota_no_contadas: str


class CierreGlobal(BaseModel):
    residuo_relativo: Optional[float] = None
    escala: Optional[str] = None
    nota: Optional[str] = None


class ConvergenciaLaboratorio(BaseModel):
    metodo: str
    alcance: str
    itera: bool
    inversiones_escalares: Optional[int] = Field(
        None, description="Cuantas inversiones h(T) se hicieron. NO son iteraciones.")
    iteraciones: Optional[int] = Field(
        None,
        description="null porque no se conocen: el lazo lo lleva brentq dentro de la "
                    "inversion y no publica su contador. Poner aqui el numero de "
                    "inversiones invitaria a leer 'converge en 1 iteracion'.")
    motivo_sin_iteraciones: Optional[str] = None
    tolerancia: Optional[str] = None
    residuo_escalado: Optional[float] = None
    escala_residuo: Optional[str] = None
    convergio: Optional[bool] = Field(
        None, description="null cuando no hubo nada que converger. No es false.")
    motivo_sin_convergencia: Optional[str] = None
    cierre_global: CierreGlobal


class EstadoBloque(BaseModel):
    F: Optional[float] = None
    T: Optional[float] = None
    p: Optional[float] = None
    x: Optional[float] = None
    h: Optional[float] = None
    fase: Optional[str] = Field(
        None, description="DETERMINADA con el punto de burbuja y el de rocio, no "
                          "supuesta.")
    beta: Optional[float] = Field(None, description="Fraccion molar vaporizada.")


class LaboratorioResponse(BaseModel):
    schema_version: int
    estado: Literal["valido", "invalido", "resuelto", "no_convergente", "no_soportado"]
    modelo_id: str = Field(
        description="Identificador determinista del MONTAJE (topologia, supuestos y "
                    "especificaciones normalizadas). Dos peticiones con el mismo "
                    "modelo_id describen el mismo sistema.")
    calculo: dict[str, Any] = Field(
        description="Version y commit del motor, versiones del proveedor, instante "
                    "UTC y huella de las entradas. Ver docs/14-trazabilidad.md.")
    componentes: list[str]
    modelo_termodinamico: str
    referencia_entalpia: str
    presion_sistema: float
    variables: list[VariableLaboratorio]
    ecuaciones: list[EcuacionLaboratorio]
    diagnosticos: list[DiagnosticoLaboratorio] = Field(
        description="Ordenados por severidad: quien lea el primero ya tiene lo mas "
                    "grave.")
    resumen_diagnosticos: dict[str, Any]
    analisis: AnalisisLaboratorio
    convergencia: Optional[ConvergenciaLaboratorio] = Field(
        None,
        description="null cuando no se resolvio. En /validar siempre es null: no se "
                    "ejecuto ningun algoritmo, asi que no hay nada que declarar.")
    estados_por_bloque: dict[str, EstadoBloque]
    capacidades: dict[str, Any] = Field(
        description="Lo que el ensamblador admite, incluido lo que NO. Un cliente "
                    "que solo reciba la lista de lo admitido adivinara el resto.")


class EjemploLaboratorio(BaseModel):
    """
    Un montaje de ejemplo que ES una peticion valida de
    /laboratorio/resolver.

    `modelo` se puede reenviar tal cual al endpoint. Eso no es comodidad:
    es lo que permite que la suite de validacion compruebe que el preset
    que la interfaz ofrece de verdad se puede resolver. Un preset roto es
    un fallo que el usuario encuentra en el primer clic.

    `estado_esperado` esta a proposito, y uno de los ejemplos vale
    'invalido': la interfaz necesita poder probar su camino de error sin
    inventarse una respuesta de error.
    """
    id: str
    nombre: str
    descripcion: str
    estado_esperado: str
    modelo: LaboratorioRequest


class CapacidadesLaboratorioResponse(BaseModel):
    """Las capacidades solas, para consultarlas sin mandar un montaje."""
    schema_version: int
    motor: dict[str, Any]
    capacidades: dict[str, Any]
