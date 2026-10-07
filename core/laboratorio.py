"""
Ensamblador del laboratorio: de un grafo de piezas a un sistema resuelto.

QUE PROBLEMA RESUELVE
---------------------
La mesa del laboratorio deja dibujar piezas fisicas (alimentacion,
volumen de control, fuente de calor, corriente intermedia, salida) y
conectarlas. Hasta ahora el frontend podia FORMULAR ese montaje -- escribir
los balances en LaTeX y marcar que terminos anulan los supuestos -- pero
solo habia adaptadores para dos montajes concretos: un calentador y un CSTR
isotermo. Dos volumenes en serie no se podian resolver.

Este modulo toma el grafo y construye el sistema de verdad: variables con
identidad, relaciones con origen, y una resolucion cuyo algoritmo se
declara tal como es.

LAS TRES DECISIONES QUE DAN FORMA AL MODULO
-------------------------------------------

**1. Una corriente intermedia es UN estado, no dos.**

Es el requisito central. Si el volumen 1 escribe su salida en un sitio y el
volumen 2 lee su entrada de otro, hay que anadir ecuaciones de igualdad
(F_sal = F_ent, T_sal = T_ent, ...) y el sistema crece con incognitas que no
son incognitas. Aqui el estado PERTENECE al bloque corriente: los dos
volumenes referencian las mismas variables, y por eso no hay nada que
igualar. En la respuesta, esas variables salen con rol 'compartida' y con
los dos volumenes y las dos conexiones en su procedencia.

**2. El LaTeX se genera, nunca se interpreta.**

El JSON de la mesa trae relaciones en LaTeX para que el usuario las lea. Son
descriptivas. El motor ensambla desde los TIPOS FISICOS de las piezas y
emite su propio LaTeX como salida. Interpretar la cadena del cliente seria
ejecutar lo que un cliente escribio.

**3. El metodo se declara, no se adorna.**

Para esta topologia el sistema es TRIANGULAR: el estado de salida de cada
volumen depende solo de lo que esta aguas arriba. Asi que se resuelve con
una marcha aguas abajo, y cada volumen es:

    T de salida impuesta  ->  Q = F (h_sal - h_ent)        algebraico directo
    Q impuesto            ->  h_sal = h_ent + Q/F, y T     inversion escalar

No hay sistema acoplado, no hay Newton y no hay lazo global. Decir "Newton"
porque suena a motor seria la misma clase de mentira que fabricar un
residuo: el contrato lo prohibe expresamente, y con razon -- quien lea
"Newton, 1 iteracion" concluira cosas falsas sobre el coste y sobre el
condicionamiento del problema.

LO QUE NO HACE
--------------
Un volumen con dos alimentaciones, reaccion, trabajo de eje o un ciclo se
RECHAZAN con diagnostico, no se aproximan. El contrato lo permite en esta
entrega, y es lo correcto: un montaje que el motor no sabe resolver tiene
que decirlo en vez de devolver numeros de otro problema.

Tampoco se infiere adiabaticidad por ausencia de una pieza. Que no haya
fuente de calor dibujada no significa Q=0: significa que el montaje no
declara intercambio termico, y entonces el balance de energia le falta un
termino. Son cosas distintas y la diferencia se nota: con Q=0 supuesto, un
volumen al que se le pide subir 10 K daria un sistema incompatible sin
explicacion; declarandolo indeterminado, el diagnostico dice que falta
conectar una fuente o marcar el supuesto.

Zona libre de pint: las unidades se convierten en la frontera de este
modulo (ver UNIDADES) y todo lo de dentro esta en SI.
"""

import math

import numpy as np

from core import errores as codigos
from core.errores import ErrorDeDatos, ErrorFisico, ErrorNumerico
from core.flash import EvaluadorFlash
from thermodynamics.elv import CalculadoraELV
from thermodynamics.proveedor import ProveedorTermodinamico

# ---------------------------------------------------------------------
# Version del contrato del laboratorio. Es independiente de la version
# del motor: el motor puede mejorar sin que la forma del JSON cambie, y
# si la forma cambia de manera incompatible esto sube a 2.
# ---------------------------------------------------------------------
SCHEMA_VERSION = 1

# El unico modelo termodinamico implementado. Se exige explicito en la
# peticion (o se declara este por omision) porque un resultado sin
# modelo declarado no se puede comparar con otro.
MODELO_POR_OMISION = "unifac_raoult"
MODELOS_DISPONIBLES = (MODELO_POR_OMISION,)

# Referencia de entalpia. No es un detalle: dos estados medidos contra
# referencias distintas no se pueden restar, y la diferencia h(310)-h(300)
# es justo lo que este modulo calcula.
REFERENCIA_POR_OMISION = "sensible_liquido_298.15K"
REFERENCIAS_DISPONIBLES = (REFERENCIA_POR_OMISION,)

# Tolerancia del residuo relativo de la inversion h(T).
#
# brentq para cuando la TEMPERATURA deja de moverse mas de su xtol, y eso
# no es lo mismo que que la ENTALPIA haya cuadrado. Donde h(T) es muy
# empinada -- dentro de la laguna bifasica, donde casi toda la energia va
# a calor latente y 1 MW mueve la temperatura dos grados -- una T correcta
# hasta 1e-10 K puede dejar un residuo apreciable en h. Asi que el residuo
# se comprueba contra esto, y si lo excede el estado es 'no_convergente'.
TOLERANCIA_INVERSION = 1e-9

# Tolerancia del cierre global de energia.
#
# Mas holgada que la de la inversion porque es una SUMA de resultados: con
# dos volumenes acumula el redondeo de los dos balances. Que la exceda no
# significa que los datos esten mal -- significa que el ensamblador tiene
# un fallo, y por eso es un error y no una advertencia.
TOLERANCIA_CIERRE = 1e-8

PRESION_POR_OMISION = 101325.0

# Tipos de pieza que el ensamblador entiende, con el papel de cada una.
PIEZAS = {
    "entrada": "Alimentacion: estado impuesto que entra al sistema.",
    "salida": "Salida: estado que abandona el sistema.",
    "corriente": "Corriente intermedia: UN estado compartido por dos volumenes.",
    "recipiente": "Volumen de control: aporta balances, no propiedades.",
    "reactor": "Reactor mezclado: balances mas estequiometria y cinetica.",
    "calor": "Fuente de calor: aporta Q al balance del volumen conectado.",
    "trabajo": "Trabajo de eje: aporta W al balance del volumen conectado.",
}

# Las que llevan un estado material propio (F, T, p, x, h).
PIEZAS_CON_ESTADO = ("entrada", "salida", "corriente")
PIEZAS_VOLUMEN = ("recipiente", "reactor")
PIEZAS_FUENTE = ("calor", "trabajo")

SUPUESTOS = ("estacionario", "adiabatico", "sinTrabajo", "sinReaccion", "sinMovimiento")

# ---------------------------------------------------------------------
# Unidades admitidas en las especificaciones.
#
# Se exige la unidad en cada especificacion y se convierte aqui. No se
# acepta una unidad desconocida con un factor adivinado: un factor
# equivocado da un numero plausible y mal, que es el peor fallo posible.
#
# La temperatura va aparte porque es AFIN: degC tiene desplazamiento y
# las demas no. Es el mismo problema que la LMTD destapo en el informe
# (ver docs/11-unidades.md): tratar una diferencia de temperatura como
# una temperatura resta 273.15 donde no toca.
# ---------------------------------------------------------------------
UNIDADES = {
    "F": {"mol/s": 1.0, "mol/h": 1.0 / 3600.0, "kmol/h": 1000.0 / 3600.0,
          "kmol/s": 1000.0},
    "p": {"Pa": 1.0, "kPa": 1000.0, "bar": 1e5, "MPa": 1e6, "atm": 101325.0},
    "x": {"mol/mol": 1.0, "-": 1.0, "fraccion": 1.0},
    "Q": {"W": 1.0, "J/s": 1.0, "kW": 1000.0, "MW": 1e6},
}
UNIDADES_TEMPERATURA = {"K": 0.0, "degC": 273.15, "C": 273.15, "°C": 273.15}

# La unidad canonica de cada variable, que es la que viaja en la respuesta.
UNIDAD_SI = {"F": "mol/s", "T": "K", "p": "Pa", "x": "mol/mol",
             "h": "J/mol", "Q": "W", "W": "W"}

# ---------------------------------------------------------------------
# Unidades de `bloques[].datos`.
#
# La mesa del laboratorio edita valores dentro de cada pieza y los exporta
# ahi, SIN unidad, con las que su propia documentacion fija: F en mol/s,
# T en K, p en Pa, x adimensional y **Q en kW**.
#
# Esa Q en kW es el detalle peligroso de todo este modulo: la misma letra
# significa W en una especificacion explicita (donde la unidad es
# obligatoria) y kW en un dato local (donde es implicita). Tomar un dato
# local por watts da un calor mil veces menor, que no se parece a un
# error -- se parece a un resultado. Por eso la tabla esta aqui, con
# nombre, y la respuesta dice de donde salio cada valor.
#
# Las especificaciones explicitas son el camino preferente justamente
# porque llevan su unidad escrita; los datos locales se admiten para que
# el frontend actual pueda consumir el servicio sin reescribirse primero.
# ---------------------------------------------------------------------
UNIDADES_DATOS_LOCALES = {"F": "mol/s", "T": "K", "p": "Pa", "x": "mol/mol",
                          "Q": "kW"}

# Variables que una especificacion puede fijar, y sobre que pieza.
VARIABLES_DE_ESTADO = ("F", "T", "p", "x")
VARIABLES_POR_PIEZA = {
    "entrada": ("F", "T", "p", "x"),
    "salida": ("p",),
    "corriente": ("p",),
    # En un volumen, 'T' significa la temperatura de SU SALIDA. No es la
    # de la alimentacion: el contrato lo subraya porque confundirlas
    # convierte un calentamiento en una identidad.
    "recipiente": ("T",),
    "reactor": ("T",),
    "calor": ("Q",),
    "trabajo": ("W",),
}

# Dominio fisico de cada variable. Fuera de esto no se calcula: no son
# limites del adaptador sino del significado (un caudal negativo no es un
# caudal pequeno).
DOMINIO = {
    "F": (0.0, None, "estrictamente positivo"),
    "T": (0.0, None, "estrictamente positivo en kelvin"),
    "p": (0.0, None, "presion absoluta estrictamente positiva"),
    "x": (0.0, 1.0, "fraccion molar en [0, 1]"),
    "Q": (None, None, "cualquier signo; positivo hacia el volumen"),
    "W": (None, None, "cualquier signo; positivo hacia el exterior"),
}


# =====================================================================
# Piezas de la respuesta
# =====================================================================

class Diagnostico:
    """
    Una incidencia del montaje, atada a las piezas que la provocan.

    `bloque_ids`, `conexion_ids` y `variable_ids` son lo que permite a la
    interfaz senalar la ficha concreta en vez de mostrar un mensaje
    suelto, y el contrato exige que esos identificadores EXISTAN en la
    peticion. `accion_sugerida` esta separada del mensaje a proposito:
    el mensaje dice que pasa, la accion dice que hacer, y mezclarlos
    produce textos que no sirven para ninguna de las dos cosas.
    """

    def __init__(self, codigo, severidad, mensaje, accion_sugerida=None,
                 categoria="datos", bloque_ids=(), conexion_ids=(), variable_ids=()):
        self.codigo = codigo
        self.severidad = severidad
        self.categoria = categoria
        self.mensaje = mensaje
        self.accion_sugerida = accion_sugerida
        self.bloque_ids = list(bloque_ids)
        self.conexion_ids = list(conexion_ids)
        self.variable_ids = list(variable_ids)

    def como_diccionario(self):
        return {
            "codigo": self.codigo,
            "severidad": self.severidad,
            "categoria": self.categoria,
            "mensaje": self.mensaje,
            "accion_sugerida": self.accion_sugerida,
            "bloque_ids": list(self.bloque_ids),
            "conexion_ids": list(self.conexion_ids),
            "variable_ids": list(self.variable_ids),
        }


class Variable:
    """
    Una variable canonica del sistema, con identidad propia.

    `rol` son los tres valores que el contrato pide:

        impuesta    la fija una especificacion
        calculada   la determina el motor
        compartida  pertenece a una corriente intermedia y la referencian
                    dos volumenes -- no es una copia, es la misma

    Los tres no son ortogonales, y por eso hay ademas una bandera
    `impuesta`. Una variable de corriente intermedia puede estar impuesta
    (la T que viene de la especificacion del volumen aguas arriba) o
    calculada, y en los dos casos su rol es 'compartida': es lo que la
    distingue en el contrato, porque es lo que garantiza que no haya dos
    estados donde hay uno. La bandera conserva la otra mitad de la
    informacion en vez de que el rol tenga que elegir cual contar.
    """

    def __init__(self, id, simbolo, magnitud, bloque_ids, conexion_ids=(),
                 compartida=False):
        self.id = id
        self.simbolo = simbolo
        self.magnitud = magnitud
        self.unidad = UNIDAD_SI[magnitud]
        self.bloque_ids = list(bloque_ids)
        self.conexion_ids = list(conexion_ids)
        self.compartida = compartida
        self.valor = None
        self.impuesta = False
        self.procedencia = None

    @property
    def rol(self):
        if self.compartida:
            return "compartida"
        return "impuesta" if self.impuesta else "calculada"

    def imponer(self, valor, procedencia):
        self.valor = float(valor)
        self.impuesta = True
        self.procedencia = procedencia

    def como_diccionario(self):
        return {
            "id": self.id,
            "bloque_ids": list(self.bloque_ids),
            "conexion_ids": list(self.conexion_ids),
            "simbolo": self.simbolo,
            "magnitud": self.magnitud,
            "unidad": self.unidad,
            "rol": self.rol,
            "compartida": self.compartida,
            "impuesta": self.impuesta,
            "valor": self.valor,
            "procedencia": self.procedencia,
        }


class Relacion:
    """
    Una relacion del sistema, con su origen y su estado de ejecucion.

    `tipo` separa lo que cuenta de lo que no:

        balance       conservacion; cuenta como ecuacion independiente
        constitutiva  propiedad del modelo (h = h(T,p,x)); cuenta
        condicion     especificacion impuesta; NO es una ecuacion extra
        convencion    signo de Q o W; NO es una ecuacion
        cierre        se satisface por la parametrizacion; NO cuenta
        verificacion  combinacion lineal de otras; NO cuenta, pero SI se
                      mide -- es la unica forma de comprobar el resultado

    Esa separacion es la razon de que exista `cuenta_como_ecuacion`. El
    contrato lo dice sin rodeos: "Convenciones de signo y especificaciones
    de entrada no se cuentan automaticamente como ecuaciones
    independientes". Contarlas infla el numero de ecuaciones y los grados
    de libertad salen negativos en un sistema que esta bien planteado.

    `latex_general` y `latex_activo` son la ley completa y la que queda
    tras los supuestos; `terminos_descartados` dice que se cayo y por que
    supuesto. Sin los tres, la interfaz no puede explicar la diferencia
    entre "este termino no aplica" y "este termino se olvido".
    """

    def __init__(self, id, tipo, titulo, latex_general, latex_activo=None,
                 terminos_descartados=(), origen_bloques=(), origen_conexiones=(),
                 variables=(), unidad=None, escala=None, cuenta_como_ecuacion=False,
                 metodo=None, alcance=None, nota=None):
        self.id = id
        self.tipo = tipo
        self.titulo = titulo
        self.latex_general = latex_general
        self.latex_activo = latex_activo if latex_activo is not None else latex_general
        self.terminos_descartados = list(terminos_descartados)
        self.origen_bloques = list(origen_bloques)
        self.origen_conexiones = list(origen_conexiones)
        self.variables = list(variables)
        self.unidad = unidad
        self.escala = escala
        self.cuenta_como_ecuacion = bool(cuenta_como_ecuacion)
        self.metodo = metodo
        self.alcance = alcance
        self.nota = nota
        # Estado de ejecucion. 'ejecutada' es False hasta que el solver la
        # usa de verdad, y el residuo se queda en None salvo que se MIDA.
        self.ejecutada = False
        self.residuo = None
        self.iteraciones = None

    def ejecutar(self, residuo=None, iteraciones=None, nota=None):
        self.ejecutada = True
        if residuo is not None:
            self.residuo = float(residuo)
        if iteraciones is not None:
            self.iteraciones = int(iteraciones)
        if nota is not None:
            self.nota = nota

    def como_diccionario(self):
        return {
            "id": self.id,
            "tipo": self.tipo,
            "titulo": self.titulo,
            "origen_bloques": list(self.origen_bloques),
            "origen_conexiones": list(self.origen_conexiones),
            "variables": list(self.variables),
            "latex_general": self.latex_general,
            "latex_activo": self.latex_activo,
            "terminos_descartados": list(self.terminos_descartados),
            "cuenta_como_ecuacion": self.cuenta_como_ecuacion,
            "ejecutada": self.ejecutada,
            # Nunca un cero de exito: si no se midio, es None.
            "residuo": self.residuo,
            "escala": self.escala,
            "unidad": self.unidad,
            "iteraciones": self.iteraciones,
            "metodo": self.metodo,
            "alcance": self.alcance,
            "nota": self.nota,
        }


# =====================================================================
# Conversion de unidades en la frontera
# =====================================================================

def convertir(magnitud, valor, unidad):
    """
    Un valor de la peticion en SI, o un ValueError con las unidades que si.

    La unidad es OBLIGATORIA. Aceptar una especificacion sin unidad
    obligaria a suponer SI, y una Q en kW tomada por W da un resultado
    mil veces menor que parece perfectamente razonable.
    """
    if valor is None:
        # Este es el caso que llega de verdad desde una interfaz web:
        # `JSON.stringify` convierte NaN e Infinity en null, asi que un
        # campo vacio o un calculo que se fue a infinito llegan aqui como
        # null y no como NaN.
        raise ErrorDeDatos(
            f"Falta el valor de {magnitud}. Un campo vacio llega como null, y null "
            "no es cero: la variable se queda sin determinar.",
            codigo=codigos.LAB_FALTA_ESPECIFICACION,
        )
    if unidad is None:
        raise ErrorDeDatos(
            f"Falta la unidad de {magnitud}. Es obligatoria: sin ella habria que "
            "suponer SI, y un calor en kW tomado por W da un resultado mil veces "
            "menor que parece perfectamente razonable.",
            codigo=codigos.LAB_UNIDAD_INCOMPATIBLE,
        )
    valor = float(valor)
    if not math.isfinite(valor):
        raise ErrorDeDatos(
            f"El valor de {magnitud} no es un numero finito ({valor!r}).",
            codigo=codigos.LAB_VALOR_NO_FINITO,
        )
    if magnitud == "T":
        if unidad not in UNIDADES_TEMPERATURA:
            raise ErrorDeDatos(
                f"Unidad de temperatura no admitida: {unidad!r}. "
                f"Admitidas: {', '.join(sorted(UNIDADES_TEMPERATURA))}.",
                codigo=codigos.LAB_UNIDAD_INCOMPATIBLE,
            )
        # Afin: factor 1 y desplazamiento. Por eso no esta en UNIDADES.
        return valor + UNIDADES_TEMPERATURA[unidad]
    tabla = UNIDADES.get("W" if magnitud == "W" else magnitud)
    if magnitud == "W":
        tabla = UNIDADES["Q"]
    if tabla is None:
        raise ErrorDeDatos(f"Magnitud sin tabla de unidades: {magnitud!r}.",
                           codigo=codigos.LAB_VARIABLE_DESCONOCIDA)
    if unidad not in tabla:
        raise ErrorDeDatos(
            f"Unidad no admitida para {magnitud}: {unidad!r}. "
            f"Admitidas: {', '.join(sorted(tabla))}.",
            codigo=codigos.LAB_UNIDAD_INCOMPATIBLE,
        )
    return valor * tabla[unidad]


def _en_dominio(magnitud, valor):
    """None si el valor es admisible, o el motivo de que no lo sea."""
    minimo, maximo, descripcion = DOMINIO[magnitud]
    if minimo is not None and valor <= minimo:
        return descripcion
    if maximo is not None and valor > maximo:
        return descripcion
    return None


# =====================================================================
# Ensamblaje: del grafo al sistema
# =====================================================================

class Montaje:
    """
    El sistema ensamblado: variables, relaciones, orden y diagnosticos.

    Se construye SIN resolver nada, que es lo que permite que
    /laboratorio/validar funcione sin llamar al solver. El proveedor
    termodinamico si se crea, porque "este componente no existe en el
    modelo" es una validacion y no un calculo.
    """

    def __init__(self, peticion):
        self.peticion = peticion
        self.diagnosticos = []
        self.variables = {}
        self.relaciones = []
        self.orden = []
        self.estados = {}        # bloque_id de pieza con estado -> dict de variables
        self.volumenes = []      # en orden de resolucion
        self.soportado = True
        self.proveedor = None
        self.flash = None
        self.presion = PRESION_POR_OMISION
        self.componentes = []
        self.modelo = MODELO_POR_OMISION
        self.referencia = REFERENCIA_POR_OMISION
        self._numero = {}

    # -- utilidades -------------------------------------------------
    def avisar(self, codigo, severidad, mensaje, accion=None, categoria="datos",
               bloques=(), conexiones=(), variables=()):
        self.diagnosticos.append(Diagnostico(
            codigo, severidad, mensaje, accion, categoria,
            bloques, conexiones, variables))

    @property
    def hay_errores(self):
        return any(d.severidad == "error" for d in self.diagnosticos)

    def variable(self, id):
        return self.variables.get(id)

    def _nueva_variable(self, bloque_id, magnitud, bloque_ids=None,
                        conexion_ids=(), compartida=False, simbolo=None):
        vid = f"{bloque_id}.{magnitud}"
        numero = self._numero.get(bloque_id, "?")
        v = Variable(
            vid,
            simbolo or f"{magnitud}_{{{numero}}}",
            magnitud,
            bloque_ids if bloque_ids is not None else [bloque_id],
            conexion_ids,
            compartida,
        )
        self.variables[vid] = v
        return v


def _indexar(peticion):
    """
    Los bloques y conexiones por id, comprobando que los ids sean unicos.

    Los duplicados se detectan ANTES de cualquier otra cosa porque con
    dos bloques del mismo id todo lo demas es ambiguo: una conexion que
    apunte a ese id no se sabe a cual de los dos va, y el diagnostico
    posterior senalaria una pieza al azar.
    """
    bloques, conexiones, problemas = {}, {}, []
    for b in peticion.get("bloques") or []:
        bid = b.get("id")
        if bid in bloques:
            problemas.append(("bloque", bid))
            continue
        bloques[bid] = b
    for c in peticion.get("conexiones") or []:
        cid = c.get("id")
        if cid in conexiones:
            problemas.append(("conexion", cid))
            continue
        conexiones[cid] = c
    return bloques, conexiones, problemas


def _conexion_admitida(tipo_origen, tipo_destino):
    """
    Si una conexion entre dos tipos de pieza representa algo fisico.

    La tabla no es arbitraria: una fuente de calor entra a un volumen y no
    sale de el, una corriente intermedia sale de un volumen y entra a
    otro, y una alimentacion no se conecta a una salida sin pasar por un
    volumen de control (sin volumen no hay balance que escribir).
    """
    if tipo_origen in ("entrada", "corriente", "calor", "trabajo"):
        return tipo_destino in PIEZAS_VOLUMEN
    if tipo_origen in PIEZAS_VOLUMEN:
        return tipo_destino in ("salida", "corriente")
    return False


def _buscar_ciclo(salidas_de):
    """
    Un ciclo del grafo de materia como lista de bloques, o None.

    Recorrido en profundidad con tres colores: blanco sin visitar, gris en
    la pila actual, negro terminado. Un arco a un nodo GRIS es un ciclo, y
    el camino se reconstruye desde la pila -- devolver "hay un ciclo" sin
    decir por donde pasa obliga al usuario a buscarlo a mano.
    """
    gris, negro, pila = set(), set(), []

    def bajar(nodo):
        gris.add(nodo)
        pila.append(nodo)
        for conexion in salidas_de.get(nodo, ()):
            siguiente = conexion["hacia"]
            if siguiente in gris:
                return pila[pila.index(siguiente):] + [siguiente]
            if siguiente not in negro:
                encontrado = bajar(siguiente)
                if encontrado:
                    return encontrado
        pila.pop()
        gris.discard(nodo)
        negro.add(nodo)
        return None

    for nodo in salidas_de:
        if nodo not in negro:
            encontrado = bajar(nodo)
            if encontrado:
                return encontrado
    return None


def ensamblar(peticion):
    """
    Construye el Montaje a partir de la peticion ya validada en forma.

    El orden de las comprobaciones es deliberado: primero lo que hace
    ambiguo el resto (ids, referencias), luego la topologia, luego las
    especificaciones, y al final los valores. Comprobar los valores de un
    grafo cuyas referencias no resuelven produce diagnosticos sobre piezas
    que no existen.
    """
    m = Montaje(peticion)

    # --- 0. componentes y modelo -----------------------------------
    componentes = list(peticion.get("componentes") or [])
    if len(componentes) != 2:
        m.avisar(
            codigos.LAB_NUMERO_DE_COMPONENTES, "error",
            f"Esta entrega resuelve mezclas binarias y se dieron {len(componentes)} "
            "componente(s).",
            "Declara exactamente dos componentes; 'x' es la fraccion del primero.",
            categoria="modelo",
        )
        m.soportado = False
    m.componentes = componentes

    modelo = peticion.get("modelo_termodinamico") or MODELO_POR_OMISION
    if modelo not in MODELOS_DISPONIBLES:
        m.avisar(
            codigos.LAB_MODELO_NO_DISPONIBLE, "error",
            f"Modelo termodinamico no disponible: {modelo!r}. "
            f"Disponibles: {', '.join(MODELOS_DISPONIBLES)}.",
            "Usa uno de los modelos que el motor declara en /laboratorio/capacidades.",
            categoria="modelo",
        )
        m.soportado = False
    m.modelo = modelo

    referencia = peticion.get("referencia_entalpia") or REFERENCIA_POR_OMISION
    if referencia not in REFERENCIAS_DISPONIBLES:
        m.avisar(
            codigos.LAB_MODELO_NO_DISPONIBLE, "error",
            f"Referencia de entalpia no disponible: {referencia!r}. "
            f"Disponibles: {', '.join(REFERENCIAS_DISPONIBLES)}.",
            "La referencia importa: dos estados medidos contra referencias distintas "
            "no se pueden restar, y este calculo resta entalpias.",
            categoria="modelo",
        )
        m.soportado = False
    m.referencia = referencia

    # La presion del sistema. Uniforme e impuesta en esta entrega.
    presion = peticion.get("presion_sistema")
    if presion is None:
        m.presion = PRESION_POR_OMISION
    else:
        try:
            m.presion = convertir("p", presion.get("valor"), presion.get("unidad"))
        except ErrorDeDatos as e:
            m.avisar(e.codigo, "error", str(e),
                     "Da la presion del sistema con su unidad.")
            m.soportado = False
    if m.presion is not None and _en_dominio("p", m.presion):
        m.avisar(codigos.LAB_VALOR_FUERA_DE_DOMINIO, "error",
                 f"Presion del sistema no fisica: {m.presion} Pa.",
                 "La presion es absoluta y estrictamente positiva.")
        m.soportado = False

    # El proveedor se crea aqui, en la validacion: "este componente no
    # existe para este modelo" es un problema de datos y no un calculo.
    if componentes and not m.hay_errores:
        try:
            m.proveedor = ProveedorTermodinamico(componentes)
            m.flash = EvaluadorFlash(CalculadoraELV(m.proveedor), P_sistema=m.presion)
        except Exception as e:
            m.avisar(
                codigos.LAB_COMPONENTE_NO_DISPONIBLE, "error",
                f"El modelo no admite estos componentes: {e}",
                "Comprueba los identificadores con /componentes/buscar.",
                categoria="modelo",
            )
            m.soportado = False

    # --- 1. ids y referencias --------------------------------------
    bloques, conexiones, duplicados = _indexar(peticion)
    for clase, id_repetido in duplicados:
        m.avisar(
            codigos.LAB_ID_DUPLICADO, "error",
            f"Hay mas de un {clase} con el identificador {id_repetido!r}.",
            "Cada pieza y cada conexion necesitan un identificador unico: con dos "
            "iguales, una conexion que apunte ahi es ambigua.",
            bloques=[id_repetido] if clase == "bloque" else [],
            conexiones=[id_repetido] if clase == "conexion" else [],
        )

    for bid, b in bloques.items():
        if b.get("tipo") not in PIEZAS:
            m.avisar(
                codigos.LAB_TOPOLOGIA_NO_SOPORTADA, "error",
                f"Tipo de pieza desconocido en {bid!r}: {b.get('tipo')!r}.",
                f"Tipos admitidos: {', '.join(sorted(PIEZAS))}.",
                categoria="modelo", bloques=[bid],
            )
            m.soportado = False

    conexiones_validas = {}
    for cid, c in conexiones.items():
        desde, hacia = c.get("desde"), c.get("hacia")
        faltantes = [r for r in (desde, hacia) if r not in bloques]
        if faltantes:
            m.avisar(
                codigos.LAB_REFERENCIA_INEXISTENTE, "error",
                f"La conexion {cid!r} referencia bloques que no existen: "
                f"{', '.join(repr(f) for f in faltantes)}.",
                "Revisa los extremos de la conexion o anade las piezas que faltan.",
                conexiones=[cid],
            )
            continue
        if desde == hacia:
            m.avisar(
                codigos.LAB_PUERTO_INCOMPATIBLE, "error",
                f"La conexion {cid!r} une la pieza {desde!r} consigo misma.",
                "Una pieza no intercambia con ella misma.",
                bloques=[desde], conexiones=[cid],
            )
            continue
        t_desde, t_hacia = bloques[desde].get("tipo"), bloques[hacia].get("tipo")
        if not _conexion_admitida(t_desde, t_hacia):
            m.avisar(
                codigos.LAB_PUERTO_INCOMPATIBLE, "error",
                f"La conexion {cid!r} va de {t_desde!r} a {t_hacia!r}, y eso no "
                "representa una entrada ni una salida admitida.",
                "Una alimentacion o una corriente entran a un volumen; un volumen "
                "descarga a una salida o a una corriente; calor y trabajo entran a "
                "un volumen.",
                bloques=[desde, hacia], conexiones=[cid],
            )
            continue
        conexiones_validas[cid] = c

    if m.hay_errores:
        # Sin un grafo bien referenciado, lo que viene despues produciria
        # diagnosticos sobre piezas inexistentes.
        return m

    # Numeracion estable para los simbolos del LaTeX, en el orden en que
    # las piezas llegan. Los subindices identifican PIEZAS, no
    # componentes -- el frontend ya usa esa convencion.
    for i, bid in enumerate(bloques, start=1):
        m._numero[bid] = i

    # --- 2. piezas aisladas y topologia ----------------------------
    conectados = set()
    for c in conexiones_validas.values():
        conectados.add(c["desde"])
        conectados.add(c["hacia"])
    for bid in bloques:
        if bid not in conectados:
            m.avisar(
                codigos.LAB_PIEZA_AISLADA, "error",
                f"La pieza {bid!r} ({bloques[bid]['tipo']}) no esta conectada a nada.",
                "Conectala o retirala: una pieza aislada no aporta terminos a ningun "
                "balance, asi que su presencia no define nada.",
                bloques=[bid],
            )

    supuestos = dict(peticion.get("supuestos") or {})
    for s in SUPUESTOS:
        if not isinstance(supuestos.get(s), bool):
            m.avisar(
                codigos.LAB_SUPUESTO_NO_SOPORTADO, "error",
                f"Falta el supuesto {s!r} o no es booleano.",
                f"Declara los cinco supuestos: {', '.join(SUPUESTOS)}. Omitir uno "
                "dejaria al motor eligiendo fisica por tu cuenta.",
            )
    if m.hay_errores:
        return m

    # Lo que esta entrega no resuelve. Se rechaza con diagnostico en vez
    # de aproximarse: un montaje que el motor no sabe resolver tiene que
    # decirlo, no devolver numeros de otro problema.
    if not supuestos["estacionario"]:
        m.avisar(
            codigos.LAB_SUPUESTO_NO_SOPORTADO, "error",
            "El regimen transitorio no esta implementado: haria falta integrar "
            "dE/dt y dn_i/dt en el tiempo.",
            "Marca 'estacionario'. La formulacion transitoria se muestra, no se calcula.",
            categoria="modelo",
        )
        m.soportado = False
    if not supuestos["sinTrabajo"]:
        m.avisar(
            codigos.LAB_SUPUESTO_NO_SOPORTADO, "error",
            "El trabajo de eje no esta implementado en el ensamblador.",
            "Marca 'sinTrabajo'. Calcularlo necesita un modelo de maquina, no solo "
            "el termino del balance.",
            categoria="modelo",
        )
        m.soportado = False
    if not supuestos["sinReaccion"]:
        m.avisar(
            codigos.LAB_SUPUESTO_NO_SOPORTADO, "error",
            "La reaccion no esta implementada en el ensamblador de varios volumenes.",
            "Marca 'sinReaccion'. El CSTR de un solo volumen sigue disponible en "
            "/diagrama/resolver.",
            categoria="modelo",
        )
        m.soportado = False
    if not supuestos["sinMovimiento"]:
        m.avisar(
            codigos.LAB_SUPUESTO_NO_SOPORTADO, "error",
            "Las energias cinetica y potencial no estan implementadas.",
            "Marca 'sinMovimiento': haria falta velocidad y altura de cada corriente.",
            categoria="modelo",
        )
        m.soportado = False

    volumenes = [bid for bid, b in bloques.items() if b["tipo"] in PIEZAS_VOLUMEN]
    if not volumenes:
        m.avisar(
            codigos.LAB_TOPOLOGIA_NO_SOPORTADA, "error",
            "No hay ningun volumen de control.",
            "Sin un volumen no hay balance que escribir: las corrientes solas no "
            "definen un sistema.",
            categoria="modelo",
        )
        m.soportado = False
    if len(volumenes) > 2:
        m.avisar(
            codigos.LAB_TOPOLOGIA_NO_SOPORTADA, "error",
            f"Esta entrega resuelve uno o dos volumenes en serie, y hay {len(volumenes)}.",
            "Reduce el montaje o espera la ampliacion del ensamblador.",
            categoria="modelo", bloques=volumenes,
        )
        m.soportado = False
    for bid in volumenes:
        if bloques[bid]["tipo"] == "reactor":
            m.avisar(
                codigos.LAB_TOPOLOGIA_NO_SOPORTADA, "error",
                f"El reactor {bid!r} no lo resuelve este ensamblador.",
                "El CSTR demostrativo sigue en /diagrama/resolver, con su balance de "
                "energia desactivado. Acoplarlo aqui exige resolver ese balance, no "
                "solo escribirlo.",
                categoria="modelo", bloques=[bid],
            )
            m.soportado = False

    if m.hay_errores:
        return m

    # --- 3. el grafo de materia, y su orden ------------------------
    materia = [c for c in conexiones_validas.values()
               if bloques[c["desde"]]["tipo"] in PIEZAS_CON_ESTADO + PIEZAS_VOLUMEN
               and bloques[c["hacia"]]["tipo"] in PIEZAS_CON_ESTADO + PIEZAS_VOLUMEN]
    fuentes = [c for c in conexiones_validas.values()
               if bloques[c["desde"]]["tipo"] in PIEZAS_FUENTE]

    entradas_de = {bid: [] for bid in bloques}
    salidas_de = {bid: [] for bid in bloques}
    for c in materia:
        salidas_de[c["desde"]].append(c)
        entradas_de[c["hacia"]].append(c)

    # Una corriente intermedia tiene que tener exactamente un volumen
    # aguas arriba y uno aguas abajo. Con uno solo no es intermedia: es
    # una salida o una entrada disfrazada, y su estado no estaria
    # determinado por nada.
    for bid, b in bloques.items():
        if b["tipo"] != "corriente":
            continue
        if len(entradas_de[bid]) != 1 or len(salidas_de[bid]) != 1:
            m.avisar(
                codigos.LAB_CORRIENTE_MAL_CONECTADA, "error",
                f"La corriente intermedia {bid!r} tiene {len(entradas_de[bid])} "
                f"entrada(s) y {len(salidas_de[bid])} salida(s).",
                "Una corriente intermedia conecta exactamente un volumen aguas "
                "arriba con uno aguas abajo; es un unico estado compartido.",
                bloques=[bid],
                conexiones=[c["id"] for c in entradas_de[bid] + salidas_de[bid]],
            )

    # Los ciclos, antes de contar entradas y salidas. Un lazo que pase por
    # un volumen le da ademas una segunda entrada, y la comprobacion de
    # "una entrada por volumen" lo cazaria primero diciendo "este volumen
    # tiene 2 entradas". Es verdad y no es el problema: el problema es el
    # lazo. Un diagnostico que describe el sintoma manda a arreglar lo que
    # no esta roto.
    ciclo = _buscar_ciclo(salidas_de)
    if ciclo:
        m.avisar(
            codigos.LAB_CICLO, "error",
            "El montaje tiene un ciclo de materia: "
            + " -> ".join(ciclo) + ".",
            "Un reciclo necesita cortar el lazo e iterar hasta que cierre; esta "
            "entrega resuelve cadenas abiertas con una marcha aguas abajo. "
            "/diagrama/resolver si admite reciclos.",
            categoria="modelo", bloques=list(dict.fromkeys(ciclo)),
        )
        m.soportado = False
        return m

    for bid in volumenes:
        n_ent = len(entradas_de[bid])
        n_sal = len(salidas_de[bid])
        if n_ent == 0:
            m.avisar(
                codigos.LAB_VOLUMEN_SIN_ENTRADA, "error",
                f"El volumen {bid!r} no recibe ninguna corriente de materia.",
                "Conecta una alimentacion o una corriente intermedia a su entrada.",
                bloques=[bid],
            )
        elif n_ent > 1:
            m.avisar(
                codigos.LAB_TOPOLOGIA_NO_SOPORTADA, "error",
                f"El volumen {bid!r} recibe {n_ent} corrientes de materia.",
                "Esta entrega admite una sola entrada por volumen: con dos, la "
                "composicion y la temperatura de salida salen de un mezclado que "
                "necesita sus propios datos independientes.",
                categoria="modelo", bloques=[bid],
                conexiones=[c["id"] for c in entradas_de[bid]],
            )
            m.soportado = False
        if n_sal == 0:
            m.avisar(
                codigos.LAB_VOLUMEN_SIN_SALIDA, "error",
                f"El volumen {bid!r} no descarga a ninguna corriente.",
                "Conecta su salida a una salida final o a una corriente intermedia. "
                "Sin salida no hay estado al que aplicar su temperatura.",
                bloques=[bid],
            )
        elif n_sal > 1:
            m.avisar(
                codigos.LAB_TOPOLOGIA_NO_SOPORTADA, "error",
                f"El volumen {bid!r} descarga a {n_sal} corrientes.",
                "Un divisor necesita su propia especificacion de reparto; esta "
                "entrega no lo incluye.",
                categoria="modelo", bloques=[bid],
                conexiones=[c["id"] for c in salidas_de[bid]],
            )
            m.soportado = False

    if m.hay_errores:
        return m

    # Orden aguas abajo. Se hace por recorrido desde la alimentacion y no
    # por el orden en que llegaron las piezas: el cliente puede mandarlas
    # en cualquier orden y el resultado no debe depender de eso.
    alimentaciones = [bid for bid, b in bloques.items() if b["tipo"] == "entrada"]
    if len(alimentaciones) != 1:
        m.avisar(
            codigos.LAB_TOPOLOGIA_NO_SOPORTADA, "error",
            f"Esta entrega admite exactamente una alimentacion y hay {len(alimentaciones)}.",
            "Con dos alimentaciones hay un mezclado que necesita datos propios.",
            categoria="modelo", bloques=alimentaciones,
        )
        m.soportado = False
        return m

    orden_volumenes, visitados = [], set()
    actual = alimentaciones[0]
    while True:
        siguientes = salidas_de[actual]
        if not siguientes:
            break
        destino = siguientes[0]["hacia"]
        if destino in visitados:
            # Inalcanzable si _buscar_ciclo hizo su trabajo. Se queda como
            # red de seguridad: un bucle infinito aqui colgaria el
            # servicio, y una guarda muda es peor que una que explica.
            m.avisar(
                codigos.LAB_CICLO, "error",
                f"El recorrido aguas abajo vuelve a pasar por {destino!r}.",
                "Hay un lazo en el montaje. Esta entrega resuelve cadenas abiertas.",
                categoria="modelo", bloques=sorted(visitados | {destino}),
            )
            m.soportado = False
            return m
        visitados.add(destino)
        if bloques[destino]["tipo"] in PIEZAS_VOLUMEN:
            orden_volumenes.append(destino)
        actual = destino

    no_alcanzados = [bid for bid in volumenes if bid not in orden_volumenes]
    if no_alcanzados:
        m.avisar(
            codigos.LAB_TOPOLOGIA_NO_SOPORTADA, "error",
            f"Estos volumenes no estan en la cadena que sale de la alimentacion: "
            f"{', '.join(sorted(no_alcanzados))}.",
            "Esta entrega resuelve una sola cadena en serie.",
            categoria="modelo", bloques=sorted(no_alcanzados),
        )
        m.soportado = False
        return m

    m.volumenes = orden_volumenes

    # --- 4. las variables, con la identidad compartida -------------
    for bid, b in bloques.items():
        if b["tipo"] not in PIEZAS_CON_ESTADO:
            continue
        compartida = b["tipo"] == "corriente"
        # Los dos volumenes que ven este estado, y las dos conexiones.
        vecinos = [c["desde"] for c in entradas_de[bid]] + [c["hacia"] for c in salidas_de[bid]]
        cxs = [c["id"] for c in entradas_de[bid] + salidas_de[bid]]
        duenos = [bid] + [v for v in vecinos if bloques[v]["tipo"] in PIEZAS_VOLUMEN]
        estado = {}
        for magnitud in ("F", "T", "p", "x", "h"):
            estado[magnitud] = m._nueva_variable(
                bid, magnitud, bloque_ids=duenos, conexion_ids=cxs,
                compartida=compartida,
            )
        m.estados[bid] = estado

    # Q de cada fuente de calor conectada.
    for c in fuentes:
        origen, destino = c["desde"], c["hacia"]
        tipo = bloques[origen]["tipo"]
        magnitud = "Q" if tipo == "calor" else "W"
        m._nueva_variable(origen, magnitud, bloque_ids=[origen, destino],
                          conexion_ids=[c["id"]])

    # Una fuente termica conectada con el supuesto adiabatico es una
    # contradiccion del montaje, no un detalle estetico: el supuesto
    # anula el termino que la pieza existe para aportar.
    for c in fuentes:
        origen = c["desde"]
        if bloques[origen]["tipo"] == "calor" and supuestos["adiabatico"]:
            m.avisar(
                codigos.LAB_SUPUESTO_INCOHERENTE, "error",
                f"La fuente de calor {origen!r} esta conectada y el supuesto "
                "adiabatico anula su contribucion.",
                "Quita el supuesto adiabatico o retira la fuente: tal como esta, el "
                "montaje declara dos cosas incompatibles.",
                bloques=[origen, c["hacia"]], conexiones=[c["id"]],
                variables=[f"{origen}.Q"],
            )

    m._bloques = bloques
    m._conexiones = conexiones_validas
    m._entradas_de = entradas_de
    m._salidas_de = salidas_de
    m._fuentes = fuentes
    m._supuestos = supuestos

    # --- 5. las especificaciones -----------------------------------
    _aplicar_especificaciones(m, peticion, bloques)
    if m.hay_errores:
        return m

    # --- 6. las relaciones -----------------------------------------
    _construir_relaciones(m, bloques)

    # --- 7. modos excluyentes por volumen --------------------------
    _comprobar_modos(m, bloques)

    return m


def _especificaciones_de_datos_locales(m, peticion, bloques):
    """
    Convierte `bloques[].datos` en especificaciones canonicas.

    El contrato es explicito en los dos sentidos: "no uses valores
    ausentes como ceros" y "no ignores datos locales contradictorios". Lo
    primero significa que una clave que no esta no vale cero -- vale
    nada, y la variable sigue siendo incognita. Lo segundo, que un dato
    local y una especificacion explicita sobre la misma variable son una
    contradiccion que hay que denunciar, no un empate que resolver por
    orden de llegada.

    Las que vienen de aqui se marcan en su procedencia, porque su unidad
    es IMPLICITA (ver UNIDADES_DATOS_LOCALES) y quien lea el resultado
    tiene derecho a saber que ese valor llego sin unidad escrita.
    """
    derivadas = []
    for bid, b in bloques.items():
        datos = b.get("datos")
        if not datos:
            continue
        tipo = b.get("tipo")
        for clave, valor in sorted(datos.items()):
            if clave not in UNIDADES_DATOS_LOCALES:
                m.avisar(
                    codigos.LAB_VARIABLE_DESCONOCIDA, "error",
                    f"{bid!r}: el dato local {clave!r} no es una variable conocida.",
                    f"Datos locales admitidos: "
                    f"{', '.join(sorted(UNIDADES_DATOS_LOCALES))}.",
                    bloques=[bid],
                )
                continue
            if clave not in VARIABLES_POR_PIEZA.get(tipo, ()):
                m.avisar(
                    codigos.LAB_VARIABLE_DESCONOCIDA, "error",
                    f"{bid!r}: lleva un dato local {clave!r} y una pieza de tipo "
                    f"{tipo!r} no tiene esa variable.",
                    f"En {tipo!r} se puede fijar: "
                    f"{', '.join(VARIABLES_POR_PIEZA.get(tipo, ())) or 'nada'}. "
                    "Un dato que no corresponde a la pieza se perderia en silencio.",
                    bloques=[bid],
                )
                continue
            derivadas.append({
                "bloque_id": bid,
                "variable": clave,
                "valor": valor,
                "unidad": UNIDADES_DATOS_LOCALES[clave],
                "_origen": "datos locales del bloque",
            })
    return derivadas


def _aplicar_especificaciones(m, peticion, bloques):
    """
    Pasa las especificaciones a variables impuestas, en SI.

    Reglas que se comprueban aqui, y el motivo de cada una:

    - una variable se fija UNA vez. Dos especificaciones sobre la misma
      variable son datos contradictorios aunque coincidan, porque la
      segunda no aporta nada y si coinciden por casualidad el usuario
      cree haber fijado dos cosas.
    - la variable tiene que existir para ese tipo de pieza. 'T' en una
      fuente de calor no significa nada, y aceptarla en silencio la
      perderia.
    - la 'T' de un volumen es la de SU SALIDA. El contrato lo subraya:
      interpretarla como la de la alimentacion convierte el calentamiento
      en una identidad y Q saldria cero.
    """
    explicitas = list(peticion.get("especificaciones") or [])
    # Las explicitas van PRIMERO a proposito. No para que ganen -- una
    # colision es un error y ninguna gana -- sino para que el mensaje diga
    # "la explicita y luego el dato local" y no al reves, que es el orden
    # en que el usuario las escribio.
    especificaciones = explicitas + _especificaciones_de_datos_locales(
        m, peticion, bloques)
    vistas = {}

    for i, e in enumerate(especificaciones):
        bid = e.get("bloque_id")
        variable = e.get("variable")
        etiqueta = (e["_origen"] + f" en {bid!r}" if e.get("_origen")
                    else f"especificaciones[{i}]")

        if bid not in bloques:
            m.avisar(
                codigos.LAB_REFERENCIA_INEXISTENTE, "error",
                f"{etiqueta}: el bloque {bid!r} no existe.",
                "Una especificacion pertenece a una pieza del montaje.",
                bloques=[bid] if bid else [],
            )
            continue
        tipo = bloques[bid]["tipo"]
        admitidas = VARIABLES_POR_PIEZA.get(tipo, ())
        if variable not in admitidas:
            m.avisar(
                codigos.LAB_VARIABLE_DESCONOCIDA, "error",
                f"{etiqueta}: {variable!r} no es una variable que se pueda fijar en "
                f"una pieza de tipo {tipo!r}.",
                f"En {tipo!r} se puede fijar: {', '.join(admitidas) or 'nada'}.",
                bloques=[bid],
            )
            continue

        try:
            valor = convertir(variable, e.get("valor"), e.get("unidad"))
        except ErrorDeDatos as err:
            m.avisar(err.codigo, "error", f"{etiqueta}: {err}",
                     "Da el valor con una unidad admitida.", bloques=[bid])
            continue

        motivo = _en_dominio(variable, valor)
        if motivo:
            m.avisar(
                codigos.LAB_FRACCION_INVALIDA if variable == "x"
                else codigos.LAB_VALOR_FUERA_DE_DOMINIO,
                "error",
                f"{etiqueta}: {variable} = {valor:g} {UNIDAD_SI[variable]} esta fuera "
                f"del dominio fisico ({motivo}).",
                "No es un limite del adaptador sino del significado de la magnitud.",
                bloques=[bid],
            )
            continue

        # A que variable canonica apunta. La unica traduccion no trivial
        # es la 'T' de un volumen, que es la de su corriente de salida.
        fuente = (f"dato local de {bid!r} (unidad implicita "
                  f"{UNIDADES_DATOS_LOCALES.get(variable)})"
                  if e.get("_origen") else f"especificacion explicita en {bid!r} "
                  f"({e.get('unidad')})")
        if tipo in PIEZAS_VOLUMEN and variable == "T":
            salidas = m._salidas_de[bid]
            destino = salidas[0]["hacia"]
            vid = f"{destino}.T"
            procedencia = (
                f"{fuente}: temperatura de su corriente de salida ({destino!r}). "
                "No es la temperatura de la alimentacion."
            )
        else:
            vid = f"{bid}.{variable}"
            procedencia = fuente

        v = m.variable(vid)
        if v is None:
            m.avisar(
                codigos.LAB_VARIABLE_DESCONOCIDA, "error",
                f"{etiqueta}: la variable {vid!r} no existe en este montaje.",
                "Revisa que la pieza tenga el estado o la conexion que esa variable "
                "necesita.",
                bloques=[bid],
            )
            continue

        if vid in vistas:
            anterior, valor_anterior = vistas[vid]
            coinciden = abs(valor_anterior - valor) <= 1e-12 * max(
                abs(valor_anterior), abs(valor), 1.0)
            m.avisar(
                codigos.LAB_ESPECIFICACION_DUPLICADA, "error",
                f"La variable {vid!r} se fija dos veces: {valor_anterior:g} "
                f"{UNIDAD_SI[variable]} desde {anterior}, y {valor:g} "
                f"{UNIDAD_SI[variable]} desde {etiqueta}."
                + ("" if coinciden else " Y los dos valores no coinciden."),
                "Una especificacion pertenece a una variable canonica y se fija una "
                "sola vez. " + (
                    "Aunque coincidan, la segunda no aporta nada y esconde cual "
                    "manda; si manana una cambia, el conflicto aparece sin que nadie "
                    "haya tocado la que creia que mandaba."
                    if coinciden else
                    "Elige cual vale y retira la otra."
                ),
                bloques=[bid], variables=[vid],
            )
            continue

        v.imponer(valor, procedencia)
        vistas[vid] = (etiqueta, valor)

    # La presion uniforme. Se impone en todos los estados, y si alguien
    # la fijo distinta en una pieza concreta, eso es una contradiccion.
    for bid, estado in m.estados.items():
        v = estado["p"]
        if v.rol in ("impuesta", "compartida") and v.valor is not None:
            if abs(v.valor - m.presion) > 1e-9 * max(abs(m.presion), 1.0):
                m.avisar(
                    codigos.LAB_ESPECIFICACION_EXCLUYENTE, "error",
                    f"{bid!r} fija p = {v.valor:g} Pa y el sistema declara "
                    f"{m.presion:g} Pa.",
                    "Esta entrega supone presion uniforme: iguala los valores o "
                    "espera el modelo de caida de presion.",
                    bloques=[bid], variables=[v.id],
                )
            continue
        v.imponer(m.presion, "presion uniforme del sistema")


def _construir_relaciones(m, bloques):
    """
    Las relaciones del sistema: balances, constitutivas, condiciones y
    convenciones, cada una con su origen y su LaTeX general y activo.

    Lo que NO se hace aqui: contar. `cuenta_como_ecuacion` lo decide el
    tipo de relacion, y el recuento se hace en `analizar()`. Mezclar las
    dos cosas es como se llega a contar una convencion de signo como una
    ecuacion independiente.
    """
    s = m._supuestos
    numero = m._numero

    def sim(bid, magnitud):
        return f"{magnitud}_{{{numero[bid]}}}"

    # --- condiciones de la alimentacion y presiones ----------------
    for bid, b in bloques.items():
        if b["tipo"] not in PIEZAS_CON_ESTADO:
            continue
        estado = m.estados[bid]
        j = numero[bid]

        impuestas = [mag for mag in ("F", "T", "p", "x")
                     if estado[mag].impuesta]
        if impuestas:
            m.relaciones.append(Relacion(
                id=f"{bid}:condiciones",
                tipo="condicion",
                titulo=f"Condiciones impuestas en {b.get('nombre') or bid}",
                latex_general=", \\quad ".join(
                    f"{sim(bid, mag)} = {sim(bid, mag)}^{{dado}}" for mag in impuestas),
                origen_bloques=[bid],
                variables=[estado[mag].id for mag in impuestas],
                # Una especificacion NO es una ecuacion independiente: es
                # un dato. Contarla inflaria el numero de ecuaciones y los
                # grados de libertad saldrian negativos en un sistema bien
                # planteado.
                cuenta_como_ecuacion=False,
                nota="Datos, no leyes de conservacion. Reducen las incognitas, no "
                     "aumentan las ecuaciones.",
            ))

        # El cierre de composicion. Se satisface por la PARAMETRIZACION:
        # el estado se describe con x y la segunda fraccion es 1-x, asi
        # que no hay ecuacion que resolver ni residuo que medir.
        m.relaciones.append(Relacion(
            id=f"{bid}:cierre",
            tipo="cierre",
            titulo=f"Cierre de composicion en {b.get('nombre') or bid}",
            latex_general=r"\sum_i x_{i," + str(j) + "} = 1",
            latex_activo=f"x_{{2,{j}}} = 1 - x_{{1,{j}}}",
            origen_bloques=[bid],
            variables=[estado["x"].id],
            cuenta_como_ecuacion=False,
            nota="Se satisface por construccion: el estado binario se parametriza "
                 "con la fraccion del primer componente. No es una ecuacion que el "
                 "solver resuelva, asi que no tiene residuo.",
        ))

        # La propiedad. ESTA si se evalua, y es donde entra el modelo.
        m.relaciones.append(Relacion(
            id=f"{bid}:entalpia",
            tipo="constitutiva",
            titulo=f"Entalpia molar de {b.get('nombre') or bid}",
            latex_general=(f"h_{{{j}}} = h(T_{{{j}}}, p_{{{j}}}, "
                           f"\\mathbf{{x}}_{{{j}}}; \\mathcal{{M}})"),
            origen_bloques=[bid],
            origen_conexiones=[c["id"] for c in
                               m._entradas_de[bid] + m._salidas_de[bid]],
            variables=[estado[k].id for k in ("T", "p", "x", "h")],
            unidad="J/mol",
            cuenta_como_ecuacion=True,
            metodo=f"{m.modelo}: flash isotermico para determinar la fase, y "
                   "h = (1-beta) h_L + beta h_V",
            alcance="evaluacion_directa",
            nota="La fase se DETERMINA con el punto de burbuja y el de rocio a "
                 "(T, p, x); no se supone liquida. Por eso el resultado trae beta y "
                 "la fase medida.",
        ))

    # --- convenciones de signo de las fuentes ----------------------
    for c in m._fuentes:
        origen, destino = c["desde"], c["hacia"]
        tipo = bloques[origen]["tipo"]
        j = numero[origen]
        if tipo == "calor":
            activo = (r"\dot Q_{" + str(j) + "} = 0" if s["adiabatico"]
                      else r"\dot Q_{" + str(j) + r"} > 0 \ \text{hacia el volumen}")
            m.relaciones.append(Relacion(
                id=f"{origen}:convencion",
                tipo="convencion",
                titulo=f"Signo del calor de {bloques[origen].get('nombre') or origen}",
                latex_general=r"\dot Q_{" + str(j) + r"} > 0 \ \text{hacia el volumen}",
                latex_activo=activo,
                origen_bloques=[origen, destino],
                origen_conexiones=[c["id"]],
                variables=[f"{origen}.Q"],
                unidad="W",
                cuenta_como_ecuacion=False,
                nota="Convencion de signo, no una ley de transferencia. No se supone "
                     "Q = U A dT: aqui Q sale del balance de energia o se impone.",
            ))

    # --- balances por volumen --------------------------------------
    for bid in m.volumenes:
        b = bloques[bid]
        nombre = b.get("nombre") or bid
        entrada = m._entradas_de[bid][0]["desde"]
        salida = m._salidas_de[bid][0]["hacia"]
        cx = [m._entradas_de[bid][0]["id"], m._salidas_de[bid][0]["id"]]
        e_in, e_out = m.estados[entrada], m.estados[salida]
        ji, jo = numero[entrada], numero[salida]

        descartados_materia = []
        if s["estacionario"]:
            descartados_materia.append({
                "termino": "acumulacion",
                "latex": r"\frac{dn_i}{dt}",
                "supuesto": "estacionario",
                "motivo": "En estado estacionario no hay acumulacion de materia.",
            })
        if s["sinReaccion"]:
            descartados_materia.append({
                "termino": "generacion por reaccion",
                "latex": r"\sum_r \nu_{ir}\dot\xi_r",
                "supuesto": "sinReaccion",
                "motivo": "Sin reaccion no hay transformacion de especies.",
            })

        m.relaciones.append(Relacion(
            id=f"{bid}:materia_total",
            tipo="balance",
            titulo=f"Conservacion de materia · {nombre}",
            latex_general=(r"\frac{dn}{dt} = \sum_{in} F - \sum_{out} F "
                           r"+ \sum_r \sum_i \nu_{ir}\dot\xi_r"),
            latex_activo=f"F_{{{jo}}} = F_{{{ji}}}",
            terminos_descartados=descartados_materia,
            origen_bloques=[bid, entrada, salida],
            origen_conexiones=cx,
            variables=[e_in["F"].id, e_out["F"].id],
            unidad="mol/s",
            cuenta_como_ecuacion=True,
            metodo="propagacion algebraica",
            alcance="algebraico_directo",
        ))
        m.relaciones.append(Relacion(
            id=f"{bid}:materia_especie",
            tipo="balance",
            titulo=f"Conservacion por especie · {nombre}",
            latex_general=(r"\frac{dn_i}{dt} = \sum_{in} F x_i - \sum_{out} F x_i "
                           r"+ \sum_r \nu_{ir}\dot\xi_r"),
            latex_activo=f"F_{{{jo}}} x_{{1,{jo}}} = F_{{{ji}}} x_{{1,{ji}}}",
            terminos_descartados=descartados_materia,
            origen_bloques=[bid, entrada, salida],
            origen_conexiones=cx,
            variables=[e_in["F"].id, e_in["x"].id, e_out["F"].id, e_out["x"].id],
            unidad="mol/s",
            cuenta_como_ecuacion=True,
            metodo="propagacion algebraica",
            alcance="algebraico_directo",
            nota="Una relacion por especie independiente. En un binario sin reaccion, "
                 "junto con el balance total, da x de salida igual a x de entrada.",
        ))

        # Energia. Aqui esta el termino que de verdad decide el problema.
        calores = [c for c in m._fuentes
                   if c["hacia"] == bid and bloques[c["desde"]]["tipo"] == "calor"]
        descartados_energia = []
        if s["estacionario"]:
            descartados_energia.append({
                "termino": "acumulacion",
                "latex": r"\frac{dE_{CV}}{dt}",
                "supuesto": "estacionario",
                "motivo": "En estado estacionario la energia del volumen no cambia.",
            })
        if s["sinTrabajo"]:
            descartados_energia.append({
                "termino": "trabajo de eje",
                "latex": r"\dot W_s",
                "supuesto": "sinTrabajo",
                "motivo": "No hay maquina que intercambie trabajo de eje.",
            })
        if s["sinMovimiento"]:
            descartados_energia.append({
                "termino": "energia cinetica y potencial",
                "latex": r"e_k + e_p",
                "supuesto": "sinMovimiento",
                "motivo": "Las contribuciones cinetica y potencial se desprecian "
                          "frente a la entalpia.",
            })
        if s["adiabatico"]:
            descartados_energia.append({
                "termino": "calor",
                "latex": r"\dot Q",
                "supuesto": "adiabatico",
                "motivo": "El supuesto adiabatico anula el intercambio de calor.",
            })

        terminos_q = [] if s["adiabatico"] else [f"\\dot Q_{{{numero[c['desde']]}}}"
                                                 for c in calores]
        latex_activo = (" + ".join(terminos_q + [f"F_{{{ji}}} h_{{{ji}}}"])
                        + f" = F_{{{jo}}} h_{{{jo}}}")
        variables_energia = [e_in["F"].id, e_in["h"].id, e_out["F"].id, e_out["h"].id]
        variables_energia += [f"{c['desde']}.Q" for c in calores] if not s["adiabatico"] else []

        m.relaciones.append(Relacion(
            id=f"{bid}:energia",
            tipo="balance",
            titulo=f"Conservacion de energia · {nombre}",
            latex_general=(r"\frac{dE_{CV}}{dt} = \dot Q - \dot W_s "
                           r"+ \sum_{in} F(h + e_k + e_p) - \sum_{out} F(h + e_k + e_p)"),
            latex_activo=latex_activo,
            terminos_descartados=descartados_energia,
            origen_bloques=[bid, entrada, salida] + [c["desde"] for c in calores],
            origen_conexiones=cx + [c["id"] for c in calores],
            variables=variables_energia,
            unidad="W",
            cuenta_como_ecuacion=True,
            metodo="pendiente de resolver",
            alcance=None,
            nota=None,
        ))

        # Ni fuente de calor ni supuesto adiabatico: el montaje no declara
        # intercambio termico. NO se supone Q=0 -- el contrato lo prohibe
        # expresamente y tiene razon: con Q=0 supuesto, un volumen al que
        # se le pide subir 10 K daria un sistema incompatible sin
        # explicacion; declarandolo indeterminado, el diagnostico dice
        # exactamente que falta.
        if not calores and not s["adiabatico"]:
            m.avisar(
                codigos.LAB_FALTA_ESPECIFICACION, "error",
                f"El volumen {nombre!r} no declara intercambio termico: no tiene "
                "fuente de calor conectada y el montaje no es adiabatico.",
                "Conecta una fuente de calor o marca el supuesto adiabatico. La "
                "ausencia de la pieza no significa Q = 0: significa que el balance "
                "de energia le falta un termino.",
                bloques=[bid],
                variables=[e_out["T"].id, e_out["h"].id],
            )
        if len(calores) > 1:
            m.avisar(
                codigos.LAB_TOPOLOGIA_NO_SOPORTADA, "error",
                f"El volumen {nombre!r} tiene {len(calores)} fuentes de calor.",
                "Con varias fuentes, el balance determina su SUMA y cada una por "
                "separado queda indeterminada. Usa una sola, o impon todas menos una.",
                categoria="modelo", bloques=[bid] + [c["desde"] for c in calores],
                conexiones=[c["id"] for c in calores],
            )

    # --- la verificacion global ------------------------------------
    # No es una ecuacion independiente: es la SUMA de los balances de los
    # volumenes. Pero es la unica comprobacion de verdad del resultado, y
    # su residuo se mide.
    if m.volumenes:
        primero, ultimo = m.volumenes[0], m.volumenes[-1]
        entrada = m._entradas_de[primero][0]["desde"]
        salida = m._salidas_de[ultimo][0]["hacia"]
        todos_los_calores = [c["desde"] for c in m._fuentes
                             if bloques[c["desde"]]["tipo"] == "calor"]
        m.relaciones.append(Relacion(
            id="global:energia",
            tipo="verificacion",
            titulo="Cierre global de energia",
            latex_general=r"\sum_j \dot Q_j = F\,(h_{salida} - h_{entrada})",
            origen_bloques=[entrada, salida] + todos_los_calores + list(m.volumenes),
            variables=([f"{q}.Q" for q in todos_los_calores]
                       + [m.estados[entrada]["h"].id, m.estados[salida]["h"].id]),
            unidad="W",
            escala="relativa al calor total intercambiado",
            # NO cuenta: es combinacion lineal de los balances por volumen.
            # Contarla daria una ecuacion de regalo y los grados de
            # libertad saldrian mal.
            cuenta_como_ecuacion=False,
            nota=(
                "Combinacion lineal de los balances por volumen, asi que no anade "
                "informacion al sistema. Se mide porque es la comprobacion "
                "independiente del resultado."
                if len(m.volumenes) >= 2 else
                "Con un solo volumen esta igualdad ES su balance de energia, la "
                "ecuacion de la que se despejo Q. Medirla daria el error de "
                "redondeo, y presentarlo como una verificacion seria presentar una "
                "tautologia como evidencia. Se queda sin ejecutar a proposito."
            ),
        ))


def _comprobar_modos(m, bloques):
    """
    Que cada volumen tenga exactamente una especificacion termica.

    La alternativa es excluyente por una razon estructural, no por gusto:
    el balance de energia del volumen es UNA ecuacion con dos incognitas
    posibles (la T de salida y la Q de su fuente). Fijar una determina la
    otra; fijar las dos deja la ecuacion sobrante y normalmente violada;
    no fijar ninguna la deja indeterminada.
    """
    for bid in m.volumenes:
        nombre = bloques[bid].get("nombre") or bid
        salida = m._salidas_de[bid][0]["hacia"]
        v_T = m.estados[salida]["T"]
        calores = [c for c in m._fuentes
                   if c["hacia"] == bid and bloques[c["desde"]]["tipo"] == "calor"]
        qs = [m.variable(f"{c['desde']}.Q") for c in calores]
        qs = [q for q in qs if q is not None]

        T_impuesta = v_T.impuesta
        q_impuestas = [q for q in qs if q.impuesta]

        if T_impuesta and q_impuestas:
            m.avisar(
                codigos.LAB_ESPECIFICACION_EXCLUYENTE, "error",
                f"{nombre!r}: estan impuestas a la vez la temperatura de salida "
                f"({v_T.valor:g} K) y el calor ({q_impuestas[0].valor:g} W).",
                "El balance de energia es una ecuacion con esas dos incognitas: fija "
                "una y el motor calcula la otra. Impuestas las dos, la ecuacion "
                "sobra y en general no se cumple.",
                bloques=[bid, salida] + [q.id.split(".")[0] for q in q_impuestas],
                variables=[v_T.id] + [q.id for q in q_impuestas],
            )
        elif not T_impuesta and not q_impuestas:
            m.avisar(
                codigos.LAB_FALTA_ESPECIFICACION, "error",
                f"{nombre!r}: no se impuso ni la temperatura de salida ni el calor.",
                "Fija una de las dos. Sin ninguna, el balance de energia tiene dos "
                "incognitas y una sola ecuacion.",
                bloques=[bid, salida],
                variables=[v_T.id] + [q.id for q in qs],
            )
        else:
            m._modo = getattr(m, "_modo", {})
            m._modo[bid] = "temperatura" if T_impuesta else "calor"


# =====================================================================
# Analisis estructural
# =====================================================================

def analizar(m):
    """
    El recuento del sistema, y lo que NO se afirma de el.

        grados_libertad = incognitas - ecuaciones_independientes

    `incognitas` son las variables sin imponer. `ecuaciones_independientes`
    cuenta solo las relaciones marcadas como tales -- balances y
    constitutivas -- y deja fuera condiciones, convenciones, cierres por
    parametrizacion y la verificacion global. Que la verificacion no cuente
    es importante: es la suma de los balances de los volumenes, y contarla
    regalaria una ecuacion.

    Sobre `rango`: se da el rango ESTRUCTURAL y se dice de donde sale. Para
    esta topologia el sistema es triangular -- cada volumen depende solo de
    lo que tiene aguas arriba -- y de ahi se sigue que las ecuaciones son
    independientes, por el orden y no por un Jacobiano. No se calcula un
    rango numerico local ni se presenta uno: el contrato advierte justo
    contra eso, y con razon, porque la independencia en un punto no es la
    independencia global.
    """
    incognitas = [v for v in m.variables.values() if not v.impuesta]
    ecuaciones = [r for r in m.relaciones if r.cuenta_como_ecuacion]
    impuestas = [v for v in m.variables.values() if v.impuesta]

    triangular = bool(m.volumenes) and not m.hay_errores
    return {
        "variables_totales": len(m.variables),
        "impuestas": len(impuestas),
        "incognitas": len(incognitas),
        "ecuaciones_independientes": len(ecuaciones),
        "grados_libertad": len(incognitas) - len(ecuaciones),
        "rango": len(ecuaciones) if triangular else None,
        "rango_origen": (
            "estructural: el sistema es triangular por el orden aguas abajo, asi que "
            "cada ecuacion introduce una variable nueva y ninguna es combinacion de "
            "las anteriores. No es el rango numerico de un Jacobiano en un punto, "
            "que no se calcula ni se presenta como independencia global."
            if triangular else
            "no se determina: el montaje no llego a ensamblarse."
        ),
        "metodo": None,      # lo rellena resolver(); validar() no lo inventa
        "alcance": None,
        "orden_resolucion": list(m.volumenes),
        "no_contadas": {
            "condicion": sum(1 for r in m.relaciones if r.tipo == "condicion"),
            "convencion": sum(1 for r in m.relaciones if r.tipo == "convencion"),
            "cierre": sum(1 for r in m.relaciones if r.tipo == "cierre"),
            "verificacion": sum(1 for r in m.relaciones if r.tipo == "verificacion"),
        },
        "nota_no_contadas":
            "Las especificaciones reducen las incognitas; no aumentan las ecuaciones. "
            "Las convenciones de signo no son ecuaciones. El cierre de composicion se "
            "satisface por la parametrizacion. La verificacion global es combinacion "
            "lineal de los balances.",
    }


# =====================================================================
# Resolucion
# =====================================================================

def _estado_completo(m, bloque_id, T, x):
    """
    El estado termodinamico en (T, p, x), con la fase DETERMINADA.

    No se supone liquido. El flash isotermico ubica el punto frente al
    punto de burbuja y al de rocio, asi que la fase sale como consecuencia
    de (T, p, x) y la entalpia es la correcta en los tres casos. El caso
    comun -- liquido subenfriado -- se corta en la comprobacion de burbuja
    y cuesta una sola llamada a UNIFAC.
    """
    z = np.array([x, 1.0 - x], dtype=float)
    return m.flash.isotermico(float(T), m.presion, z)


def resolver(peticion):
    """
    Ensambla y resuelve. Devuelve el diccionario completo de la respuesta.

    El algoritmo es una MARCHA AGUAS ABAJO, y se declara como tal. Para
    cada volumen, en orden:

        F, x y p se propagan (balances de materia, algebraicos)
        si T de salida esta impuesta:  h_sal = h(T,p,x);  Q = F (h_sal - h_ent)
        si Q esta impuesto:            h_sal = h_ent + Q/F;  T de invertir h

    El primer caso es evaluacion directa y el segundo una inversion
    escalar con brentq. No hay sistema acoplado y no se declara ninguno.
    """
    m = ensamblar(peticion)
    analisis = analizar(m)

    if m.hay_errores:
        estado = "no_soportado" if not m.soportado else "invalido"
        return _respuesta(m, analisis, estado, convergencia=None)

    modos = getattr(m, "_modo", {})
    alcances = set()
    iteraciones_totales = 0
    residuos = []

    try:
        for bid in m.volumenes:
            nombre = m._bloques[bid].get("nombre") or bid
            entrada = m._entradas_de[bid][0]["desde"]
            salida = m._salidas_de[bid][0]["hacia"]
            e_in, e_out = m.estados[entrada], m.estados[salida]

            # --- el estado de entrada
            if e_in["h"].valor is None:
                T_in, x_in = e_in["T"].valor, e_in["x"].valor
                if T_in is None or x_in is None or e_in["F"].valor is None:
                    raise ErrorDeDatos(
                        f"La corriente que entra a {nombre!r} no tiene su estado "
                        "completo (F, T y x).",
                        codigo=codigos.LAB_FALTA_ESPECIFICACION,
                    )
                r_in = _estado_completo(m, entrada, T_in, x_in)
                e_in["h"].valor = r_in["h"]
                e_in["h"].procedencia = (
                    f"h({T_in:.6g} K, {m.presion:.6g} Pa, x={x_in:.6g}) con "
                    f"{m.modelo}; fase {r_in['fase']}"
                )
                _marcar_entalpia(m, entrada, r_in)

            F = e_in["F"].valor
            h_in = e_in["h"].valor

            # --- balances de materia: propagacion algebraica
            e_out["F"].valor = F
            e_out["F"].procedencia = f"balance de materia de {nombre!r}"
            e_out["x"].valor = e_in["x"].valor
            e_out["x"].procedencia = f"balance por especie de {nombre!r}"
            _relacion(m, f"{bid}:materia_total").ejecutar(
                nota="F se propaga: una entrada, una salida y sin reaccion.")
            _relacion(m, f"{bid}:materia_especie").ejecutar(
                nota="Con F conservado, la composicion de salida iguala la de entrada.")

            modo = modos.get(bid)
            calores = [c for c in m._fuentes
                       if c["hacia"] == bid and m._bloques[c["desde"]]["tipo"] == "calor"]
            v_Q = m.variable(f"{calores[0]['desde']}.Q") if calores else None
            rel_energia = _relacion(m, f"{bid}:energia")

            if modo == "temperatura":
                # Evaluacion directa: ninguna iteracion, ningun residuo.
                T_out = e_out["T"].valor
                r_out = _estado_completo(m, salida, T_out, e_out["x"].valor)
                e_out["h"].valor = r_out["h"]
                e_out["h"].procedencia = (
                    f"h({T_out:.6g} K, {m.presion:.6g} Pa, x={e_out['x'].valor:.6g}) "
                    f"con {m.modelo}; fase {r_out['fase']}"
                )
                _marcar_entalpia(m, salida, r_out)
                Q = F * (r_out["h"] - h_in)
                if v_Q is not None:
                    v_Q.valor = Q
                    v_Q.procedencia = (
                        f"balance de energia de {nombre!r}: Q = F (h_salida - h_entrada)"
                    )
                rel_energia.metodo = "evaluacion algebraica directa"
                rel_energia.alcance = "algebraico_directo"
                rel_energia.ejecutar(
                    nota="Se despeja Q de la ecuacion, asi que se satisface por "
                         "construccion: no hay residuo que medir ni iteracion que "
                         "contar. Presentar un residuo de 1e-11 aqui seria presentar "
                         "el error de redondeo como si fuera una convergencia.",
                )
                alcances.add("algebraico_directo")

            elif modo == "calor":
                # Inversion escalar: h objetivo conocido, se busca T.
                Q = v_Q.valor
                h_objetivo = h_in + Q / F
                try:
                    r_out = m.flash.a_entalpia(
                        m.presion,
                        np.array([e_out["x"].valor, 1.0 - e_out["x"].valor], dtype=float),
                        h_objetivo,
                    )
                except ValueError as e:
                    raise ErrorFisico(
                        f"{nombre!r}: con Q = {Q:g} W y F = {F:g} mol/s la entalpia "
                        f"de salida ({h_objetivo:.6g} J/mol) cae fuera del dominio "
                        f"del modelo. {e}",
                        codigo=codigos.LAB_FUERA_DE_DOMINIO_TERMODINAMICO,
                        equipo=bid,
                    ) from e
                T_out = r_out["T"]
                e_out["T"].valor = T_out
                e_out["T"].procedencia = (
                    f"inversion de h(T) en {nombre!r}: h_salida = h_entrada + Q/F"
                )
                e_out["h"].valor = r_out["h"]
                e_out["h"].procedencia = f"h_entrada + Q/F en {nombre!r}"
                _marcar_entalpia(m, salida, r_out)

                # El residuo de la inversion, MEDIDO: la entalpia del
                # estado encontrado frente a la que se buscaba.
                residuo = abs(r_out["h"] - h_objetivo)
                escala = max(abs(h_objetivo), abs(h_in), 1.0)
                relativo = residuo / escala
                residuos.append(relativo)
                if relativo > TOLERANCIA_INVERSION:
                    # Medir un residuo y no actuar sobre el es la mitad
                    # del trabajo, y es la mitad que no protege de nada.
                    raise ErrorNumerico(
                        f"{nombre!r}: la inversion de h(T) quedo con un residuo "
                        f"relativo de {relativo:.3e}, por encima de la tolerancia "
                        f"de {TOLERANCIA_INVERSION:.0e}. brentq para cuando la "
                        "temperatura deja de moverse, y donde h(T) es muy empinada "
                        "eso no garantiza que la entalpia haya cuadrado.",
                        codigo=codigos.LAB_SIN_CONVERGENCIA,
                        equipo=bid,
                    )
                rel_energia.metodo = "brentq sobre h(T) a composicion y presion fijas"
                rel_energia.alcance = "inversion_escalar"
                rel_energia.escala = "relativo a la entalpia molar de la corriente"
                rel_energia.ejecutar(
                    residuo=residuo / escala,
                    nota="Q impuesto: la ecuacion fija h de salida y la temperatura "
                         "sale de invertir h(T). El residuo es la diferencia entre la "
                         "entalpia del estado encontrado y la buscada.",
                )
                alcances.add("inversion_escalar")
                iteraciones_totales += 1
            else:
                raise ErrorDeDatos(
                    f"{nombre!r} no tiene modo termico resuelto.",
                    codigo=codigos.LAB_FALTA_ESPECIFICACION,
                )

            m.avisar(
                codigos.LAB_INFO_FASE, "informacion",
                f"{nombre!r}: la corriente de salida sale en fase "
                f"{_fase_legible(m, salida)} a {e_out['T'].valor:.4f} K"
                + (f", con beta = {m.estados[salida]['beta']:.6g}"
                   if m.estados[salida].get("fase") == "bifasico" else "")
                + ".",
                None, categoria="informacion",
                bloques=[bid, salida], variables=[e_out["T"].id],
            )

            # Un calor negativo en una pieza llamada "fuente de calor" no
            # es un error: la convencion define el signo y negativo
            # significa que se RETIRA. Pero hay que decirlo, porque la
            # pieza se llama fuente y quien la dibujo esperaba calentar.
            if v_Q is not None and v_Q.valor is not None and v_Q.valor < 0:
                m.avisar(
                    codigos.LAB_INFO_FASE, "informacion",
                    f"{nombre!r}: el calor sale negativo ({v_Q.valor:.4g} W). Con la "
                    "convencion de positivo hacia el volumen, eso significa que esta "
                    "pieza RETIRA calor en vez de aportarlo.",
                    "Si la intencion era calentar, revisa las temperaturas: la de "
                    "salida impuesta esta por debajo de la de entrada.",
                    categoria="informacion",
                    bloques=[bid, v_Q.id.split(".")[0]], variables=[v_Q.id],
                )

    except (ErrorDeDatos, ErrorFisico, ErrorNumerico) as e:
        datos = e.como_diccionario() if hasattr(e, "como_diccionario") else {}
        m.avisar(
            datos.get("codigo") or codigos.SIN_CLASIFICAR, "error", str(e),
            "El calculo se detuvo aqui: los valores parciales NO se presentan como "
            "resueltos.",
            categoria=datos.get("categoria", "desconocido"),
            bloques=[datos["equipo"]] if datos.get("equipo") else [],
        )
        estado = ("no_convergente"
                  if datos.get("categoria") == "numerica" else "invalido")
        return _respuesta(m, analisis, estado, convergencia=None)

    # --- la comprobacion global, con su residuo medido -------------
    convergencia = _cerrar(m, analisis, alcances, iteraciones_totales, residuos)
    # El cierre global puede haber anadido un error DESPUES de calcular. Si
    # lo hizo, el estado no es 'resuelto': los numeros estan ahi pero no se
    # sostienen, y presentarlos como resueltos seria el fallo que todo este
    # modulo trata de evitar.
    if m.hay_errores:
        return _respuesta(m, analisis, "no_convergente", convergencia)
    return _respuesta(m, analisis, "resuelto", convergencia)


def _relacion(m, id):
    for r in m.relaciones:
        if r.id == id:
            return r
    raise KeyError(id)


def _marcar_entalpia(m, bloque_id, resultado_flash):
    """Marca la constitutiva como ejecutada y guarda la fase medida."""
    rel = _relacion(m, f"{bloque_id}:entalpia")
    rel.ejecutar(
        nota=(f"fase determinada: {resultado_flash['fase']} "
              f"(beta = {resultado_flash['beta']:.6g}); evaluacion directa, sin "
              "residuo que medir."),
        iteraciones=resultado_flash.get("iteraciones") or None,
    )
    m.estados[bloque_id]["fase"] = resultado_flash["fase"]
    m.estados[bloque_id]["beta"] = float(resultado_flash["beta"])


def _fase_legible(m, bloque_id):
    return m.estados[bloque_id].get("fase", "sin determinar")


def _cerrar(m, analisis, alcances, iteraciones, residuos):
    """
    El cierre global de energia y la declaracion del metodo.

    El cierre SE MIDE. No es una ecuacion del sistema -- es la suma de los
    balances por volumen -- pero por eso mismo es la unica comprobacion
    independiente que queda: si los balances se resolvieron bien, la suma
    de los calores tiene que igualar F (h_final - h_inicial).
    """
    rel = next((r for r in m.relaciones if r.id == "global:energia"), None)
    residuo_global = None
    # Con un solo volumen no se mide: ver la nota de la relacion.
    if rel is not None and len(m.volumenes) >= 2:
        primero, ultimo = m.volumenes[0], m.volumenes[-1]
        entrada = m._entradas_de[primero][0]["desde"]
        salida = m._salidas_de[ultimo][0]["hacia"]
        F = m.estados[entrada]["F"].valor
        suma_Q = sum(v.valor for v in m.variables.values()
                     if v.magnitud == "Q" and v.valor is not None)
        esperado = F * (m.estados[salida]["h"].valor - m.estados[entrada]["h"].valor)
        escala = max(abs(suma_Q), abs(esperado), 1.0)
        residuo_global = abs(suma_Q - esperado) / escala
        rel.ejecutar(
            residuo=residuo_global,
            nota=(f"suma de calores {suma_Q:.6f} W frente a F (h_salida - h_entrada) "
                  f"= {esperado:.6f} W"),
        )
        if residuo_global > TOLERANCIA_CIERRE:
            # Un cierre que no cuadra no es un problema de los datos: los
            # balances por volumen se resolvieron cada uno por su cuenta y
            # su suma TIENE que dar la diferencia de entalpias. Si no da,
            # el fallo esta en el ensamblador, y hay que decirlo en vez de
            # publicar el numero y seguir.
            m.avisar(
                codigos.LAB_CIERRE_GLOBAL, "error",
                f"El cierre global de energia no cuadra: residuo relativo "
                f"{residuo_global:.3e} frente a una tolerancia de "
                f"{TOLERANCIA_CIERRE:.0e}. {rel.nota}",
                "Esto no se arregla cambiando los datos: la suma de los balances "
                "por volumen tiene que dar la diferencia de entalpias por "
                "construccion. Es un fallo del motor; informalo con el modelo_id.",
                categoria="numerica",
                bloques=[entrada, salida] + list(m.volumenes),
                variables=list(rel.variables),
            )
        else:
            m.avisar(
                codigos.LAB_INFO_CIERRE_GLOBAL, "informacion",
                f"Cierre global de energia comprobado: residuo relativo "
                f"{residuo_global:.3e}, por debajo de {TOLERANCIA_CIERRE:.0e}.",
                None, categoria="informacion",
                bloques=[entrada, salida],
                variables=[rel.variables[0]] if rel.variables else [],
            )

    if alcances == {"algebraico_directo"}:
        alcance = "algebraico_directo"
        metodo = ("marcha aguas abajo con evaluacion algebraica directa por volumen; "
                  "sin iteracion")
    elif alcances == {"inversion_escalar"}:
        alcance = "inversion_escalar"
        metodo = ("marcha aguas abajo con una inversion escalar h(T) por volumen "
                  "(brentq)")
    else:
        alcance = "mixto"
        metodo = ("marcha aguas abajo: evaluacion directa donde la temperatura esta "
                  "impuesta, e inversion escalar h(T) con brentq donde lo esta el calor")

    analisis["metodo"] = metodo
    analisis["alcance"] = alcance
    analisis["nota_metodo"] = (
        "No es un sistema acoplado ni un Newton: el sistema es triangular por el "
        "orden aguas abajo, asi que cada volumen se resuelve con el estado del "
        "anterior ya determinado. Declararlo como Newton sugeriria un coste y un "
        "condicionamiento que no son los de este calculo."
    )

    itera = alcance != "algebraico_directo"
    return {
        "metodo": metodo,
        "alcance": alcance,
        "itera": itera,
        # Cuantas inversiones escalares se hicieron: una por volumen en
        # modo calor. NO son iteraciones de brentq.
        "inversiones_escalares": iteraciones if itera else None,
        # Las iteraciones de brentq no se reportan porque no se conocen:
        # ni el flash ni la calculadora de entalpia las devuelven. Poner
        # aqui el numero de inversiones invitaria a leer "converge en 1
        # iteracion", que es falso.
        "iteraciones": None,
        "motivo_sin_iteraciones": (
            "El lazo lo lleva brentq dentro de la inversion de h(T) y no publica su "
            "contador; lo que se cuenta aqui son las inversiones realizadas, en "
            "'inversiones_escalares'."
            if itera else
            "No hubo lazo: ver 'motivo_sin_convergencia'."
        ),
        "tolerancia": ("1e-10 K en la inversion de h(T) (xtol de brentq)"
                       if itera else None),
        "residuo_escalado": max(residuos) if residuos else None,
        "escala_residuo": ("maximo residuo relativo de las inversiones h(T), "
                           "adimensional" if residuos else None),
        # `convergio` solo tiene sentido si hubo algo que converger.
        "convergio": (bool(residuos) and max(residuos) < 1e-8) if itera else None,
        "motivo_sin_convergencia": (
            None if itera else
            "No hubo iteracion: con la temperatura impuesta en cada volumen, el calor "
            "se despeja del balance en una sola evaluacion. No hay convergencia que "
            "declarar ni residuo que medir."
        ),
        "cierre_global": {
            "residuo_relativo": residuo_global,
            "escala": "relativo al mayor de |suma de Q| y |F dh|",
            "nota": "Comprobacion independiente: no es una ecuacion del sistema, "
                    "sino la suma de los balances por volumen.",
        },
    }


def _respuesta(m, analisis, estado, convergencia):
    """La respuesta completa, con los diagnosticos ordenados por severidad."""
    orden = {"error": 0, "advertencia": 1, "informacion": 2}
    diagnosticos = sorted(m.diagnosticos,
                          key=lambda d: (orden.get(d.severidad, 3), d.codigo))
    estados = {}
    for bid, estado_bloque in m.estados.items():
        estados[bid] = {
            "fase": estado_bloque.get("fase"),
            "beta": estado_bloque.get("beta"),
            **{k: estado_bloque[k].valor for k in ("F", "T", "p", "x", "h")},
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "estado": estado,
        "componentes": list(m.componentes),
        "modelo_termodinamico": m.modelo,
        "referencia_entalpia": m.referencia,
        "presion_sistema": m.presion,
        "variables": [v.como_diccionario() for v in m.variables.values()],
        "ecuaciones": [r.como_diccionario() for r in m.relaciones],
        "diagnosticos": [d.como_diccionario() for d in diagnosticos],
        "analisis": analisis,
        "convergencia": convergencia,
        "estados_por_bloque": estados,
    }


def validar(peticion):
    """
    Valida sin resolver, que es lo que el contrato pide de /validar.

    No se llama al solver: se ensambla, se cuenta y se devuelven las
    relaciones con `ejecutada = false` y sin residuos, que es la verdad --
    no se ejecuto nada. El proveedor SI se construye, porque "este
    componente no existe para este modelo" es una validacion de datos.
    """
    m = ensamblar(peticion)
    analisis = analizar(m)
    if m.hay_errores:
        estado = "no_soportado" if not m.soportado else "invalido"
    else:
        estado = "valido"
    # Sin resolver, `estados_por_bloque` trae los valores impuestos y None
    # en todo lo demas, y las relaciones salen con ejecutada=false y sin
    # residuo. Esa es la verdad: no se ejecuto nada.
    return _respuesta(m, analisis, estado, convergencia=None)


def capacidades():
    """
    Lo que este ensamblador admite de verdad, para que la interfaz no
    ofrezca lo que no hay.

    Se declara explicitamente lo NO soportado. Un cliente que solo reciba
    la lista de lo admitido tiene que adivinar el resto, y adivinara que
    algo funciona.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "modelos_termodinamicos": list(MODELOS_DISPONIBLES),
        "referencias_entalpia": list(REFERENCIAS_DISPONIBLES),
        "componentes": "cualquier par admitido por el proveedor UNIFAC "
                       "(consulta /componentes/buscar)",
        "numero_de_componentes": 2,
        "piezas": dict(PIEZAS),
        "variables_por_pieza": {k: list(v) for k, v in VARIABLES_POR_PIEZA.items()},
        "unidades": {
            **{k: sorted(v) for k, v in UNIDADES.items()},
            "T": sorted(UNIDADES_TEMPERATURA),
        },
        "especificaciones": {
            "preferente": "especificaciones: [{bloque_id, variable, valor, unidad}] "
                          "-- la unidad es obligatoria",
            "compatibilidad": "bloques[].datos tambien se admite, con las unidades "
                              "implicitas que documenta la mesa",
            "unidades_implicitas_de_datos": dict(UNIDADES_DATOS_LOCALES),
            "aviso": "En un dato local, Q se lee en kW; en una especificacion "
                     "explicita, en la unidad que esta declare. Es la misma letra "
                     "con dos escalas, y la respuesta dice en 'procedencia' de donde "
                     "salio cada valor.",
            "colisiones": "Un dato local y una especificacion explicita sobre la "
                          "misma variable son un error, tambien si coinciden.",
        },
        "topologias": [
            "una alimentacion, uno o dos volumenes de control en serie, una salida",
            "una corriente intermedia entre dos volumenes, con estado unico compartido",
            "una fuente de calor por volumen",
        ],
        "especificacion_termica": {
            "modos": ["temperatura de salida impuesta", "calor impuesto"],
            "excluyentes": True,
            "motivo": "El balance de energia del volumen es una ecuacion con esas dos "
                      "incognitas: fijar una determina la otra.",
        },
        "supuestos_exigidos": {
            "estacionario": True, "sinTrabajo": True,
            "sinReaccion": True, "sinMovimiento": True,
            "adiabatico": "libre, pero incompatible con una fuente de calor conectada",
        },
        "fases": ["liquido", "bifasico", "vapor"],
        "nota_fases": "La fase se determina con el punto de burbuja y el de rocio; no "
                      "se supone liquida.",
        "no_soportado": [
            "regimen transitorio (dE/dt, dn_i/dt)",
            "reaccion quimica en el ensamblador de varios volumenes",
            "trabajo de eje",
            "energias cinetica y potencial",
            "mas de una alimentacion o mas de una salida por volumen",
            "mas de dos volumenes",
            "reciclos y ciclos",
            "caida de presion entre volumenes (la presion es uniforme)",
            "mezclas de mas de dos componentes",
            "mallado, CFD y dinamica espacial",
        ],
        "tolerancias": {
            "inversion_h_T": TOLERANCIA_INVERSION,
            "cierre_global": TOLERANCIA_CIERRE,
            "nota": "La del cierre global es mas holgada porque es una suma de "
                    "resultados y acumula el redondeo de los dos balances. "
                    "Excederla no significa datos malos: significa un fallo del "
                    "motor, y sale como error con estado 'no_convergente'.",
        },
        "metodos": {
            "temperatura impuesta": "evaluacion algebraica directa, sin iteracion",
            "calor impuesto": "inversion escalar de h(T) con brentq, xtol 1e-10 K",
            "topologia": "marcha aguas abajo; el sistema es triangular y no se "
                         "resuelve como sistema acoplado",
        },
    }
