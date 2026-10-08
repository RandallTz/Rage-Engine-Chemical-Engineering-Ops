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
MAX_REACCIONES = 16


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


class LeyDeVelocidadEntrada(BaseModel):
    """
    Una ley de accion de masas: r = k(T) * prod_i a_i^(orden_i).

    DOS FORMAS DE DAR LA CONSTANTE, y la referenciada es mejor:

        k_ref + T_ref    k = k_ref exp(-Ea/R (1/T - 1/T_ref))
        A                k = A exp(-Ea/(R T))

    No es estetica. En la forma clasica A tiene magnitudes absurdas (1e13
    y mas) y el exponente vale -20 o -40, asi que la expresion resta
    numeros enormes para dar uno pequeno. En la referenciada k_ref esta a
    escala humana y el exponente ronda cero cerca de T_ref. Se admiten las
    dos --los datos de la literatura vienen en la clasica-- y la respuesta
    declara cual se uso.

    La UNIDAD de la constante declara la base de la tasa, igual que en una
    tasa dada: 'mol/s' se usa tal cual y 'mol/(m3*s)' se integra con el
    volumen del reactor.
    """
    k_ref: Optional[ValorConUnidad] = Field(
        None,
        description="La constante a T_ref (forma referenciada). Su unidad declara "
                    "la base de la tasa.")
    T_ref: Optional[ValorConUnidad] = Field(
        None, description="Obligatoria con k_ref: una constante referenciada sin "
                          "su temperatura no dice a que temperatura vale.")
    A: Optional[ValorConUnidad] = Field(
        None, description="Factor preexponencial (Arrhenius clasico). Alternativa "
                          "a k_ref; no se dan los dos.")
    Ea: Optional[float] = Field(
        None, description="Energia de activacion en J/mol. Si falta, se toma 0 y "
                          "la constante no depende de la temperatura.")
    ordenes: Optional[Any] = Field(
        None,
        description=(
            "Los ordenes de reaccion, como {componente: orden} o como lista en el "
            "orden de 'componentes'. **Un orden NO es un coeficiente "
            "estequiometrico**: la ley sale de un mecanismo y la estequiometria de "
            "un balance, y coinciden solo en una reaccion elemental. Si no se "
            "declaran se usa |nu| de los reactivos y la respuesta dice que ese fue "
            "el defecto, para que nadie crea que lo eligio. Los ordenes negativos "
            "se rechazan: modelan inhibicion y hacen que la tasa diverja cuando "
            "esa especie se agota."
        ),
    )
    # Deliberadamente `str` y no `Literal`: una base desconocida tiene que
    # salir como DIAGNOSTICO del nucleo --con su codigo, su id de bloque y
    # la explicacion de por que la concentracion no esta-- y no como un
    # 422 de Pydantic, que no lleva nada de eso. Es el mismo criterio que
    # con el resto de lo semantico.
    base_actividad: Optional[str] = Field(
        None, max_length=40,
        description="'actividad' (a = x gamma, con UNIFAC; la correcta en liquido "
                    "no ideal) o 'fraccion_molar' (a = x, ideal y mas barata). Por "
                    "omision 'actividad'. La base en concentracion NO esta: "
                    "necesitaria el volumen molar de la mezcla, que es otra "
                    "decision de modelo.")
    desde_equilibrio: Optional[bool] = Field(
        None,
        description="Solo en 'ley_inversa'. Con true, la inversa se DERIVA del "
                    "equilibrio: k_inv = k_dir / K_eq(T). Es la restriccion que "
                    "impone la termodinamica, y el unico modo en que una "
                    "reversible es consistente sin dos juegos de datos cineticos. "
                    "Necesita la energia de Gibbs de formacion de todas las "
                    "especies; consultala en /laboratorio/sustancias/buscar.")


class ReaccionLaboratorio(BaseModel):
    """
    Una reaccion de tasa especificada en un volumen.

    LAS TRES FORMAS DE DECLARAR LA TASA, Y POR QUE SON TRES
    -------------------------------------------------------
    `tasa`                              irreversible, una direccion
    `tasa_directa` + `tasa_inversa`     reversible, con las brutas
    `tasa_neta`                         solo el neto

    No son tres formas de escribir lo mismo: la tercera sabe MENOS que las
    otras dos. Con `tasa_neta` el motor no puede decir cuanto se produce y
    cuanto se consume, y lo dice -- devuelve `generacion_bruta` y
    `consumo_bruto` en null con su motivo -- en vez de rellenarlos con
    max(neto, 0).

    La razon es que un neto de cero es compatible con dos situaciones
    fisicas distintas: una reaccion PARADA (r+ = r- = 0) y un equilibrio
    DINAMICO (r+ = r- > 0), donde cada especie se esta produciendo y
    consumiendo a toda velocidad. La tasa neta no las distingue, asi que
    el motor tampoco puede.

    Dar mas de una forma es un error, no una preferencia: habria que
    elegir una y la eleccion no es del motor.
    """
    id: str = Field(min_length=1, max_length=120)
    bloque_id: str = Field(
        min_length=1, max_length=120,
        description="El volumen donde ocurre, que tiene que ser de tipo 'reactor'. "
                    "La produccion y la desaparicion quimica pertenecen al volumen "
                    "donde ocurren: no son alimentaciones ficticias.")
    nu: list[float] = Field(
        max_length=MAX_COMPONENTES,
        description="Un coeficiente por componente, EN EL MISMO ORDEN. "
                    "**Positivo producto, negativo reactivo.** Un mismo evento "
                    "produce unos componentes y consume otros, y por eso el signo va "
                    "en el coeficiente y no en la tasa. Se valida contra la matriz "
                    "elemental de 'thermo': A @ nu tiene que ser cero.")
    tasa: Optional[ValorConUnidad] = Field(
        None, description="Tasa de una reaccion irreversible, >= 0.")
    tasa_directa: Optional[ValorConUnidad] = Field(
        None, description="r+ de una reversible, >= 0. Exige tasa_inversa.")
    tasa_inversa: Optional[ValorConUnidad] = Field(
        None, description="r- de una reversible, >= 0. Exige tasa_directa. Con una "
                          "sola no se sabe si la otra es cero o si no se dio, y son "
                          "dos situaciones fisicas distintas.")
    tasa_neta: Optional[ValorConUnidad] = Field(
        None,
        description="Solo el neto, de cualquier signo. Con esta forma las brutas NO "
                    "estan disponibles y se devuelven como null.")
    # --- la tasa CALCULADA: leyes de velocidad.
    ley_directa: Optional[LeyDeVelocidadEntrada] = Field(
        None,
        description="La ley del sentido directo. Con ella la tasa se CALCULA, y el "
                    "balance del volumen pasa a ser implicito: el motor lo resuelve "
                    "como sistema y declara el algoritmo real.")
    ley_inversa: Optional[LeyDeVelocidadEntrada] = Field(
        None,
        description="La ley del sentido inverso, o {'desde_equilibrio': true} para "
                    "derivarla de K_eq(T). Con cualquiera de las dos, las tasas "
                    "brutas se conocen por construccion.")
    # Campos que el motor rechaza con nombre en vez de ignorarlos.
    cinetica: Optional[Any] = Field(
        None,
        description="No se usa. Los parametros cineticos van dentro de "
                    "'ley_directa' / 'ley_inversa'; sueltos no dicen de que ley "
                    "son parametros y se rechazan con LAB_LEY_INVALIDA.")
    A: Optional[float] = Field(
        None, description="No aqui: va dentro de la ley, con su unidad.")
    Ea: Optional[float] = Field(
        None, description="No aqui: va dentro de la ley.")


class LaboratorioRequest(BaseModel):
    version: int = Field(
        1, description="Version del contrato que el cliente habla. Hoy: 1.")
    componentes: list[str] = Field(
        max_length=MAX_COMPONENTES,
        description="Identificadores del proveedor, EN ORDEN: 'x0' es la fraccion "
                    "del primero. 'x' a secas vale como alias de 'x0' SOLO en "
                    "binarios, porque con tres especies no identifica ninguna.",
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
    reacciones: list[ReaccionLaboratorio] = Field(
        default_factory=list, max_length=MAX_REACCIONES,
        description="Las reacciones de los reactores del montaje. Vacia si no hay, "
                    "y entonces conviene marcar 'sinReaccion' para dejarlo dicho.")
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
    sistemas_implicitos: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Un sistema implicito POR VOLUMEN cinetico, con el algoritmo que de "
            "verdad corrio, su residuo escalado, la tolerancia, las evaluaciones y "
            "las restricciones. No se agregan en un solo numero: dos volumenes "
            "pueden resolverse con algoritmos distintos y promediar sus residuos "
            "no significaria nada. "
            "Con la tasa DADA esta lista esta vacia, porque no hay nada implicito "
            "que resolver."
        ),
    )
    cierre_global: CierreGlobal


class EspecieEnCorriente(BaseModel):
    componente: str
    x: Optional[float] = None
    F_i: Optional[float] = Field(
        None,
        description="Caudal molar de la especie [mol/s]. DERIVADO: F_i = F x_i. No "
                    "es una variable del sistema -- declararlo como tal anadiria n "
                    "incognitas y n ecuaciones que se cancelan -- pero es lo que "
                    "hace falta para comprobar la conservacion de elementos y masa.")
    unidad_F_i: str = "mol/s"


class EstadoBloque(BaseModel):
    F: Optional[float] = None
    T: Optional[float] = None
    p: Optional[float] = None
    x: Optional[float] = Field(
        None,
        description="La fraccion del PRIMER componente, y solo en binarios. Se "
                    "conserva por compatibilidad; en general usa 'composicion' o "
                    "'por_especie'. Es null con tres o mas componentes.")
    composicion: list[Optional[float]] = Field(
        default_factory=list,
        description="Las n fracciones en el orden de 'componentes'.")
    por_especie: list[EspecieEnCorriente] = Field(default_factory=list)
    h: Optional[float] = None
    fase: Optional[str] = Field(
        None, description="DETERMINADA con el punto de burbuja y el de rocio, no "
                          "supuesta.")
    beta: Optional[float] = Field(None, description="Fraccion molar vaporizada.")
    nota_F_i: Optional[str] = None


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
    reacciones: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Por reaccion: nu, la convencion de signo, el modo y la base de la "
            "tasa, el avance neto, los balances elemental y de masa, y la "
            "generacion y el consumo brutos POR ESPECIE. "
            "**`brutas_disponibles` es el campo que hay que mirar antes que "
            "ninguno**: si es false, `generacion_bruta` y `consumo_bruto` valen "
            "null con su motivo, y eso no es cero -- es que el dato no esta."
        ),
    )
    fuentes_por_volumen: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "G_i, C_i y la fuente neta de cada volumen reactivo, agregando sus "
            "reacciones. Si ALGUNA reaccion del volumen solo trae su tasa neta, las "
            "brutas del volumen no estan disponibles: G_i es una suma y un termino "
            "desconocido hace desconocida la suma. "
            "`descomposicion_neta` se ofrece aparte y NO es el intercambio bruto: "
            "es el signo del neto repartido en dos casillas."
        ),
    )
    conservacion: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Elementos y masa MEDIDOS sobre los caudales resueltos, por volumen. Es "
            "independiente de haber validado la estequiometria: aquello comprueba "
            "que la reaccion tenga sentido, esto que el balance se haya aplicado "
            "bien. El caudal molar total PUEDE cambiar; la masa no cambia nunca."
        ),
    )
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


# =====================================================================
# Catalogo de sustancias
# =====================================================================

class CapacidadSustancia(BaseModel):
    disponible: bool
    falta: list[str] = Field(
        default_factory=list,
        description="Que propiedad falta cuando no esta disponible.")


class SustanciaResumen(BaseModel):
    id: Optional[str] = Field(
        None, description="El id ESTABLE: el CAS. Es lo que conviene guardar, no "
                          "el nombre (que tiene sinonimos) ni la formula (que es "
                          "ambigua).")
    cas: Optional[str] = None
    nombre: Optional[str] = None
    nombre_iupac: Optional[str] = None
    formula: Optional[str] = None
    masa_molar: Optional[float] = None
    unidad_masa_molar: str = "g/mol"
    carga: Optional[int] = Field(
        None, description="Carga de la especie. Cero para una molecula neutra.")
    smiles: Optional[str] = None
    inchi_key: Optional[str] = None


class BusquedaSustanciaResponse(BaseModel):
    """
    El resultado de identificar una sustancia, con COMO se identifico.

    `identificacion_fiable` es el campo que hay que mirar: un CAS, un
    nombre, un SMILES o un InChIKey identifican una sustancia; una FORMULA
    no. 'C2H6O' resuelve a dimetil eter y el etanol tiene la misma
    formula, y hierven a 248 K y a 352 K. Cuando la identificacion no es
    fiable, `candidatos` trae las otras sustancias con esa formula para
    que el cliente pregunte en vez de que el motor adivine.
    """
    consulta: str
    encontrada: bool
    identificacion: Literal["cas", "nombre", "smiles", "inchi_key", "formula",
                            "otro", "no_encontrada"]
    identificacion_fiable: bool = Field(
        description="False cuando se resolvio por FORMULA, que no identifica una "
                    "sustancia.")
    sustancia: Optional[SustanciaResumen] = None
    candidatos: list[SustanciaResumen] = Field(
        default_factory=list,
        description="Las OTRAS sustancias con la misma formula, cuando la "
                    "identificacion no es fiable.")
    candidatos_totales: int = 0
    capacidades: Optional[dict[str, CapacidadSustancia]] = Field(
        None,
        description="Que se puede hacer con ella: elv, entalpia, reaccion, "
                    "equilibrio. Una sustancia puede tener grupos UNIFAC y no "
                    "tener entalpia de formacion -- sirve para un ELV y no para un "
                    "balance reactivo -- y por eso son cuatro capacidades y no un "
                    "unico 'apto'.")
    propiedades: Optional[dict[str, Any]] = None
    composicion_elemental: Optional[dict[str, Any]] = Field(
        None, description="Los atomos, que es lo que valida una estequiometria.")
    modelos_soportados: list[str] = Field(default_factory=list)
    fases: list[str] = Field(default_factory=list)
    referencias: Optional[dict[str, Any]] = None
    mensaje: Optional[str] = None
    aviso: Optional[str] = Field(
        None, description="Presente cuando la identificacion no es fiable.")


class CatalogoSustanciasResponse(BaseModel):
    identificadores_admitidos: list[dict[str, Any]]
    capacidades: dict[str, Any]
    id_estable: str
    max_candidatos: int
    modelos: list[str]
    referencias: dict[str, Any]
    nota: str


# =====================================================================
# Balanceo, equilibrio y lote
# =====================================================================

class BalancearRequest(BaseModel):
    """
    Que reaccion conserva los elementos entre estas especies.

    Es el unico de los tres servicios que NO necesita propiedades
    termodinamicas: solo la composicion elemental. Por eso admite especies
    que no sirven para reaccionar --sin entalpia de formacion-- y lo dice
    en vez de rechazarlas.
    """
    componentes: list[str] = Field(max_length=MAX_COMPONENTES)
    reactivos: list[str] = Field(
        default_factory=list,
        description="Opcional. Orienta el SIGNO: la conservacion de elementos no "
                    "distingue reactivo de producto, porque A@nu = 0 se cumple "
                    "igual con nu y con -nu. Sin esta pista se orienta por "
                    "convencion y la respuesta lo declara.")


class ComprobarNuRequest(BaseModel):
    """Juzga una nu dada, en vez de buscarla."""
    componentes: list[str] = Field(max_length=MAX_COMPONENTES)
    nu: list[float] = Field(
        max_length=MAX_COMPONENTES,
        description="Un coeficiente por componente, en el mismo orden.")


class CantidadInicial(BaseModel):
    componente: str = Field(min_length=1, max_length=120)
    valor: float
    unidad: str = Field(
        min_length=1, max_length=24,
        description="Cantidad ('mol', 'kmol', 'mmol') o caudal ('mol/s'...). El "
                    "lote trabaja con cantidades; el equilibrio admite las dos "
                    "porque solo le importan las proporciones.")


class ReaccionDeRed(BaseModel):
    """
    Una reaccion de la red. Para /equilibrio basta la nu; para /lote hace
    falta ademas la ley de velocidad.
    """
    id: str = Field(min_length=1, max_length=120)
    nu: list[float] = Field(max_length=MAX_COMPONENTES)
    ley_directa: Optional[LeyDeVelocidadEntrada] = Field(
        None,
        description="Obligatoria en /lote. Una tasa CONSTANTE no describe un "
                    "lote: la composicion cambia y la tasa con ella.")
    ley_inversa: Optional[LeyDeVelocidadEntrada] = Field(
        None,
        description="Con {'desde_equilibrio': true} se deriva de K_eq(T) por la "
                    "ruta RIGUROSA (Kirchhoff e integral de dCp/T). Esa es la que "
                    "hace que el final del lote coincida con /equilibrio.")


class VentanaDeTiempo(BaseModel):
    final: float = Field(gt=0.0)
    unidad: str = Field("s", max_length=8)
    muestras: int = Field(
        200, ge=2, le=2000,
        description="Puntos de la trayectoria devuelta. No cambian la precision "
                    "de la integracion, solo cuanto se devuelve de ella.")


class OpcionesIntegrador(BaseModel):
    metodo: Optional[str] = Field(
        None, max_length=24,
        description="LSODA (por omision), Radau, BDF o RK45. LSODA detecta la "
                    "rigidez sola, y una red con constantes muy distintas es "
                    "rigida sin avisar.")
    rtol: Optional[float] = Field(None, gt=0.0, le=1e-2)
    atol: Optional[float] = Field(None, gt=0.0)


class EquilibrioRequest(BaseModel):
    componentes: list[str] = Field(max_length=MAX_COMPONENTES)
    reacciones: list[ReaccionDeRed] = Field(max_length=MAX_REACCIONES)
    estado_inicial: list[CantidadInicial] = Field(max_length=MAX_COMPONENTES)
    T: ValorConUnidad
    base_actividad: Optional[str] = Field(None, max_length=40)


class LoteRequest(BaseModel):
    componentes: list[str] = Field(max_length=MAX_COMPONENTES)
    reacciones: list[ReaccionDeRed] = Field(max_length=MAX_REACCIONES)
    estado_inicial: list[CantidadInicial] = Field(max_length=MAX_COMPONENTES)
    T: ValorConUnidad
    tiempo: VentanaDeTiempo
    integrador: Optional[OpcionesIntegrador] = None
    volumen: Optional[ValorConUnidad] = Field(
        None,
        description="Del lote. Hace falta si alguna constante esta en base "
                    "volumetrica; si no se da, NO se supone 1 m3.")
    base_actividad: Optional[str] = Field(None, max_length=40)


class RespuestaReaccionesBase(BaseModel):
    """Lo comun a los tres: estado, trazabilidad y diagnosticos."""
    schema_version: int
    estado: Literal["resuelto", "invalido", "no_convergente", "no_soportado"]
    modelo_id: str
    calculo: dict[str, Any]
    diagnosticos: list[DiagnosticoLaboratorio]
    resumen_diagnosticos: dict[str, Any]


class BalancearResponse(RespuestaReaccionesBase):
    especies: list[str]
    elementos: list[str] = Field(default_factory=list)
    matriz_elemental: list[list[int]] = Field(default_factory=list)
    dimension_del_espacio: int = Field(
        0,
        description="Cuantas reacciones INDEPENDIENTES hay. Si es mayor que 1, la "
                    "conservacion de elementos no determina una reaccion: "
                    "determina un subespacio, y se devuelve la base entera.")
    reacciones: list[dict[str, Any]] = Field(default_factory=list)
    diagnostico: dict[str, Any] = Field(default_factory=dict)
    aritmetica: Optional[str] = None
    convencion_nu: Optional[str] = None
    aptas_para_termodinamica: bool = Field(
        True,
        description="Si TODAS las especies tienen grupos UNIFAC. Balancear no los "
                    "necesita --es la conservacion de los atomos-- pero "
                    "/equilibrio y /lote si. Una reaccion puede estar balanceada y "
                    "no ser calculable.")
    sin_grupos_unifac: list[str] = Field(default_factory=list)


class ComprobarNuResponse(RespuestaReaccionesBase):
    especies: list[str]
    nu: list[float]
    elementos: list[str] = Field(default_factory=list)
    residuo_elemental: dict[str, float] = Field(default_factory=dict)
    conserva: bool = False
    descuadre: dict[str, float] = Field(default_factory=dict)
    mensaje: Optional[str] = None


class EquilibrioResponse(RespuestaReaccionesBase):
    componentes: list[str] = Field(default_factory=list)
    T: Optional[float] = None
    base_actividad: Optional[str] = None
    avances: list[float] = Field(default_factory=list)
    unidad_avance: Optional[str] = None
    moles_equilibrio: list[float] = Field(default_factory=list)
    composicion_equilibrio: list[float] = Field(default_factory=list)
    propiedades_por_reaccion: list[dict[str, Any]] = Field(
        default_factory=list,
        description="dH, dS, dG y K a la T pedida, por las DOS rutas: la rigurosa "
                    "(Kirchhoff e integral de dCp/T) y van't Hoff. Se dan las dos "
                    "para que la diferencia se vea en vez de suponerse pequena.")
    comprobacion: list[dict[str, Any]] = Field(
        default_factory=list,
        description="dG_rxn de cada reaccion en la solucion. Cero es equilibrio; "
                    "el signo dice hacia donde se movería.")
    potenciales_quimicos: Optional[dict[str, Any]] = Field(
        None, description="mu_i = mu_i^0(T) + R T ln a_i, con el estado estandar "
                          "declarado. Un mu sin estado estandar no se compara.")
    estabilidad: Optional[dict[str, Any]] = Field(
        None,
        description="El hessiano de Gibbs y sus autovalores. dG = 0 dice que es "
                    "un punto ESTACIONARIO, no que sea un minimo: lo decide la "
                    "segunda derivada.")
    convergencia: Optional[dict[str, Any]] = None
    conservacion: Optional[dict[str, Any]] = None
    especies_agotadas: list[dict[str, Any]] = Field(default_factory=list)
    aviso_negativas: Optional[str] = None
    aviso_tasas: Optional[str] = Field(
        None, description="Imponer r+ = r- no demuestra equilibrio termodinamico.")


class LoteResponse(RespuestaReaccionesBase):
    componentes: list[str] = Field(default_factory=list)
    T: Optional[float] = None
    metodo: Optional[str] = None
    descripcion_metodo: Optional[str] = None
    tolerancias: Optional[dict[str, Any]] = None
    t: list[float] = Field(default_factory=list)
    unidad_tiempo: Optional[str] = None
    moles: list[list[float]] = Field(
        default_factory=list, description="Forma (especies, tiempos).")
    unidad_moles: Optional[str] = None
    trayectoria_por_especie: list[dict[str, Any]] = Field(default_factory=list)
    n_muestras: Optional[int] = None
    volumen_m3: Optional[float] = None
    evaluaciones_de_la_ley: Optional[int] = None
    pasos_del_integrador: Optional[int] = None
    agotamientos: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Localizados con un EVENTO del integrador, no mirando las "
                    "muestras: un cruce entre dos muestras se habria perdido.")
    no_negatividad: Optional[dict[str, Any]] = None
    conservacion: Optional[dict[str, Any]] = None
    equilibrio_alcanzado: Optional[dict[str, Any]] = Field(
        None,
        description="dG_rxn en el ultimo punto. Con una cinetica "
                    "termodinamicamente consistente tiende a cero y la "
                    "composicion final coincide con /laboratorio/equilibrio.")
    mensaje: Optional[str] = None


class CapacidadesReaccionesResponse(BaseModel):
    schema_version: int
    servicios: dict[str, Any]
    unidades: dict[str, Any]
    comprobacion_cruzada: str


class CapacidadesLaboratorioResponse(BaseModel):
    """Las capacidades solas, para consultarlas sin mandar un montaje."""
    schema_version: int
    motor: dict[str, Any]
    capacidades: dict[str, Any]
