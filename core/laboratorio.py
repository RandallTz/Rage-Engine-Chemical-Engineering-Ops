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
import re

import numpy as np

from core import errores as codigos
from core import cinetica as cin
from core import estequiometria as est
from core.errores import ErrorDeDatos, ErrorFisico, ErrorNumerico
from core.flash import EvaluadorFlash
from thermodynamics.elv import CalculadoraELV
from thermodynamics.entalpia import entalpia_de
from thermodynamics.reaccion import GestorReaccion
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

# Que sabe cada referencia de si misma.
#
# `incluye_formacion` es el campo que decide si el balance de energia
# lleva el termino de calor de reaccion. Con una referencia SENSIBLE las
# entalpias de formacion no estan en h, asi que el termino es obligatorio;
# con una que las incluyera, el termino ya esta dentro y sumarlo lo
# contaria dos veces. Esta en una tabla y no en un comentario para que
# anadir una referencia obligue a declarar en que lado cae.
REFERENCIAS = {
    "sensible_liquido_298.15K": {
        "incluye_formacion": False,
        "T_ref": 298.15,
        "fase_ref": "liquido",
        "descripcion": "Entalpia sensible de cada especie referida a su liquido "
                       "puro a 298.15 K. No incluye entalpias de formacion, asi "
                       "que un balance con reaccion necesita el termino de calor "
                       "de reaccion explicito.",
    },
}
REFERENCIAS_DISPONIBLES = tuple(REFERENCIAS)

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

# Tolerancia de la conservacion de elementos y masa, medida sobre los
# caudales resueltos. Excederla no es un problema de los datos -- la
# estequiometria ya se valido -- sino del motor al aplicar el balance.
TOLERANCIA_CONSERVACION = 1e-10

PRESION_POR_OMISION = 101325.0

# Tope de especies. No es un limite fisico sino del servicio: cada especie
# anade una variable por corriente y una ecuacion por volumen, y una
# peticion con cien especies no merece un diagnostico, merece un no.
MAX_COMPONENTES = 8

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
    "V": {"m3": 1.0, "L": 1e-3, "dm3": 1e-3, "cm3": 1e-6, "mL": 1e-6},
}
UNIDADES_TEMPERATURA = {"K": 0.0, "degC": 273.15, "C": 273.15, "°C": 273.15}

# ---------------------------------------------------------------------
# Unidades de las tasas de reaccion.
#
# La UNIDAD decide la base, que es lo menos ambiguo posible: 'mol/s' es
# una tasa INTEGRADA sobre el volumen y 'mol/(m3*s)' es VOLUMETRICA, y no
# hay forma de confundirlas leyendo. El contrato pide distinguirlas
# explicitamente, y esta es la forma que no depende de que nadie rellene
# un campo 'base' correctamente.
#
# Una tasa volumetrica necesita el volumen del reactor para integrarse. Si
# no se da, no se supone 1 m3: se diagnostica.
# ---------------------------------------------------------------------
UNIDADES_TASA_INTEGRADA = {
    "mol/s": 1.0, "mol/h": 1.0 / 3600.0,
    "kmol/s": 1000.0, "kmol/h": 1000.0 / 3600.0,
}
UNIDADES_TASA_VOLUMETRICA = {
    "mol/(m3*s)": 1.0, "mol/(m3*h)": 1.0 / 3600.0,
    "kmol/(m3*s)": 1000.0, "kmol/(m3*h)": 1000.0 / 3600.0,
    "mol/(L*s)": 1000.0, "mol/(dm3*s)": 1000.0,
    "mol/(cm3*s)": 1e6,
}

# La unidad canonica de cada variable, que es la que viaja en la respuesta.
UNIDAD_SI = {"F": "mol/s", "T": "K", "p": "Pa", "x": "mol/mol",
             "h": "J/mol", "Q": "W", "W": "W", "V": "m3"}

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

# ---------------------------------------------------------------------
# Nombres de las fracciones molares.
#
# La composicion de una corriente de n especies son n variables con
# nombre: `x0`, `x1`, ... `x{n-1}`, en el orden en que se declararon los
# componentes. El indice es parte del NOMBRE, no de la magnitud: la unidad
# y el dominio de `x7` son los de `x`, asi que las tablas se consultan por
# magnitud y los nombres se traducen con `magnitud_de`.
#
# `x` a secas se admite como alias de `x0`, y SOLO en mezclas binarias.
# Con tres especies, "x" no identifica ninguna: aceptarlo obligaria a
# adivinar, y adivinar aqui silencia un dato puesto en el sitio
# equivocado.
# ---------------------------------------------------------------------
_RE_COMPOSICION = re.compile(r"^x(\d+)$")


def nombres_composicion(n):
    return tuple(f"x{i}" for i in range(n))


def magnitud_de(nombre):
    """'x3' -> 'x'. Cualquier otro nombre se devuelve igual."""
    return "x" if _RE_COMPOSICION.match(str(nombre)) else nombre


def indice_composicion(nombre):
    """El indice de una fraccion, o None si el nombre no es una fraccion."""
    coincide = _RE_COMPOSICION.match(str(nombre))
    return int(coincide.group(1)) if coincide else None


# Variables que una especificacion puede fijar, y sobre que pieza. Depende
# de n porque las fracciones son n, asi que es una funcion y no una tabla.
def variables_de_pieza(tipo, n):
    base = {
        "entrada": ("F", "T", "p"),
        "salida": ("p",),
        "corriente": ("p",),
        # En un volumen, 'T' significa la temperatura de SU SALIDA. No es
        # la de la alimentacion: el contrato lo subraya porque
        # confundirlas convierte un calentamiento en una identidad.
        "recipiente": ("T",),
        # El reactor admite ademas su volumen, que hace falta cuando una
        # tasa viene en base volumetrica. Es un dato geometrico, no un
        # estado: si no hay ninguna tasa volumetrica, no hace falta.
        "reactor": ("T", "V"),
        "calor": ("Q",),
        "trabajo": ("W",),
    }.get(tipo, ())
    if tipo == "entrada":
        base = base + nombres_composicion(n) + (("x",) if n == 2 else ())
    return base

# Dominio fisico de cada variable. Fuera de esto no se calcula: no son
# limites del adaptador sino del significado (un caudal negativo no es un
# caudal pequeno).
# (minimo, maximo, minimo_incluido, descripcion)
#
# La inclusividad del minimo es EXPLICITA porque no es la misma para todas
# las magnitudes, y tratarlas igual fue un error real: un caudal de cero no
# es un caudal pequeno --es la ausencia de corriente-- pero una fraccion
# molar de cero es perfectamente fisica y significa que esa especie no
# esta. Con tres especies y una alimentacion pura, x = 0 es lo normal.
DOMINIO = {
    "F": (0.0, None, False, "estrictamente positivo"),
    "T": (0.0, None, False, "estrictamente positivo en kelvin"),
    "p": (0.0, None, False, "presion absoluta estrictamente positiva"),
    "x": (0.0, 1.0, True, "fraccion molar en [0, 1]; cero es valido y significa "
                          "que la especie no esta"),
    "Q": (None, None, True, "cualquier signo; positivo hacia el volumen"),
    "W": (None, None, True, "cualquier signo; positivo hacia el exterior"),
    "V": (0.0, None, False, "volumen estrictamente positivo"),
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
        self.unidad = UNIDAD_SI[magnitud_de(magnitud)]
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
    if magnitud_de(magnitud) == "T":
        if unidad not in UNIDADES_TEMPERATURA:
            raise ErrorDeDatos(
                f"Unidad de temperatura no admitida: {unidad!r}. "
                f"Admitidas: {', '.join(sorted(UNIDADES_TEMPERATURA))}.",
                codigo=codigos.LAB_UNIDAD_INCOMPATIBLE,
            )
        # Afin: factor 1 y desplazamiento. Por eso no esta en UNIDADES.
        return valor + UNIDADES_TEMPERATURA[unidad]
    magnitud = magnitud_de(magnitud)
    tabla = UNIDADES["Q"] if magnitud == "W" else UNIDADES.get(magnitud)
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
    minimo, maximo, minimo_incluido, descripcion = DOMINIO[magnitud_de(magnitud)]
    if minimo is not None:
        fuera = valor < minimo if minimo_incluido else valor <= minimo
        if fuera:
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
        self.n = 0
        self.reacciones = []
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

    def composicion(self, bloque_id):
        """Las n variables de fraccion de una corriente, en orden."""
        estado = self.estados[bloque_id]
        return [estado[nombre] for nombre in nombres_composicion(self.n)]

    def composicion_valores(self, bloque_id):
        """
        Las n fracciones como array, o None si alguna falta.

        None y no ceros: una fraccion que no se conoce no vale cero, y
        rellenarla asi daria una composicion que suma menos de uno sin
        que nadie se entere.
        """
        valores = [v.valor for v in self.composicion(bloque_id)]
        if any(v is None for v in valores):
            return None
        return np.array(valores, dtype=float)

    def fijar_composicion(self, bloque_id, valores, procedencia):
        for v, valor in zip(self.composicion(bloque_id), np.asarray(valores)):
            v.valor = float(valor)
            v.procedencia = procedencia

    def _nueva_variable(self, bloque_id, magnitud, bloque_ids=None,
                        conexion_ids=(), compartida=False, simbolo=None):
        vid = f"{bloque_id}.{magnitud}"
        numero = self._numero.get(bloque_id, "?")
        indice = indice_composicion(magnitud)
        if simbolo is None and indice is not None:
            # Dos subindices: la especie y la pieza. Con uno solo no se
            # distingue "la fraccion del componente 2" de "la fraccion en
            # la pieza 2", y en un reactor las dos cosas aparecen juntas.
            simbolo = f"x_{{{indice + 1},{numero}}}"
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
    if len(componentes) < 2:
        m.avisar(
            codigos.LAB_NUMERO_DE_COMPONENTES, "error",
            f"Hacen falta al menos dos componentes y se dieron {len(componentes)}.",
            "Declara los componentes en orden: 'x0' es la fraccion del primero.",
            categoria="modelo",
        )
        m.soportado = False
    elif len(componentes) > MAX_COMPONENTES:
        m.avisar(
            codigos.LAB_NUMERO_DE_COMPONENTES, "error",
            f"Esta entrega admite hasta {MAX_COMPONENTES} componentes y se dieron "
            f"{len(componentes)}.",
            "No es un limite fisico sino del servicio.",
            categoria="modelo",
        )
        m.soportado = False
    if len(componentes) != len(set(componentes)):
        repetidos = sorted({c for c in componentes if componentes.count(c) > 1})
        m.avisar(
            codigos.LAB_NUMERO_DE_COMPONENTES, "error",
            f"Hay componentes repetidos: {', '.join(repetidos)}.",
            "Cada especie aparece una vez; su posicion define cual es su fraccion.",
            categoria="modelo",
        )
        m.soportado = False
    m.componentes = componentes
    m.n = len(componentes)

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
        for magnitud in ("F", "T", "p", "h") + nombres_composicion(m.n):
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

    # --- 5b. las reacciones ----------------------------------------
    # Despues de las especificaciones porque una tasa en base volumetrica
    # necesita el volumen del reactor, y el volumen llega como
    # especificacion.
    m.reacciones = _leer_reacciones(m, peticion, bloques)
    if m.hay_errores:
        return m

    # Un reactor sin reaccion y sin el supuesto que la anule no declara
    # nada: el termino de transformacion se conserva en el balance y no
    # hay quien lo determine. Es el mismo razonamiento que con el calor --
    # la ausencia de un dato no es un supuesto.
    # El supuesto dice que PUEDE haber reaccion y ningun volumen es un
    # reactor. No invalida nada -- un recipiente no lleva termino de
    # transformacion -- pero el montaje declara una intencion que su
    # topologia no recoge, y callarlo deja al usuario creyendo que algo
    # reacciona.
    if not supuestos["sinReaccion"] and not any(
            bloques[bid]["tipo"] == "reactor" for bid in m.volumenes):
        m.avisar(
            codigos.LAB_SIN_REACCION_DECLARADA, "advertencia",
            "El montaje no marca 'sinReaccion' pero ningun volumen es un reactor, "
            "asi que no hay ningun termino de transformacion en los balances.",
            "Si esperabas reaccion, cambia el volumen a 'reactor' y declara la "
            "reaccion. Si no, marca 'sinReaccion' para dejarlo dicho.",
            bloques=list(m.volumenes),
        )

    for bid in m.volumenes:
        if bloques[bid]["tipo"] != "reactor":
            continue
        if any(r.bloque_id == bid for r in m.reacciones):
            continue
        if supuestos["sinReaccion"]:
            continue
        m.avisar(
            codigos.LAB_SIN_REACCION_DECLARADA, "error",
            f"El reactor {bloques[bid].get('nombre') or bid!r} no declara ninguna "
            "reaccion y el montaje no marca 'sinReaccion'.",
            "Declara la reaccion con su estequiometria y su tasa, o marca "
            "'sinReaccion' si de verdad no hay transformacion. La ausencia de una "
            "reaccion declarada no significa que no haya reaccion: significa que "
            "al balance por especie le falta un termino.",
            bloques=[bid],
        )

    # --- 6. las relaciones -----------------------------------------
    _construir_relaciones(m, bloques)

    # --- 7. modos excluyentes por volumen --------------------------
    _comprobar_modos(m, bloques)

    return m


def _convertir_tasa(etiqueta, campo, dato):
    """
    Una tasa en SI, con su base, o un ErrorDeDatos.

    Devuelve (valor, base, unidad). La base sale de la unidad, no de un
    campo aparte: un campo 'base' que contradiga la unidad habria que
    resolverlo adivinando, y aqui no se adivina.
    """
    if not isinstance(dato, dict):
        raise ErrorDeDatos(
            f"{etiqueta}: {campo} tiene que ser un objeto con 'valor' y 'unidad'.",
            codigo=codigos.LAB_TASA_AMBIGUA,
        )
    valor, unidad = dato.get("valor"), dato.get("unidad")
    if valor is None:
        raise ErrorDeDatos(
            f"{etiqueta}: falta el valor de {campo}. Un campo vacio llega como "
            "null, y null no es cero.",
            codigo=codigos.LAB_FALTA_ESPECIFICACION,
        )
    valor = float(valor)
    if not math.isfinite(valor):
        raise ErrorDeDatos(
            f"{etiqueta}: {campo} no es un numero finito ({valor!r}).",
            codigo=codigos.LAB_VALOR_NO_FINITO,
        )
    if unidad in UNIDADES_TASA_INTEGRADA:
        return valor * UNIDADES_TASA_INTEGRADA[unidad], "integrada", unidad
    if unidad in UNIDADES_TASA_VOLUMETRICA:
        return valor * UNIDADES_TASA_VOLUMETRICA[unidad], "volumetrica", unidad
    raise ErrorDeDatos(
        f"{etiqueta}: unidad de tasa no admitida para {campo}: {unidad!r}. "
        f"Integradas: {', '.join(sorted(UNIDADES_TASA_INTEGRADA))}. "
        f"Volumetricas: {', '.join(sorted(UNIDADES_TASA_VOLUMETRICA))}. "
        "La unidad es la que declara la base: 'mol/s' se integra sobre el volumen "
        "y 'mol/(m3*s)' hay que integrarla.",
        codigo=codigos.LAB_UNIDAD_INCOMPATIBLE,
    )


def _leer_ley(m, etiqueta, dato, nu, n, componentes, base_tasa_esperada=None):
    """
    Una LeyDeVelocidad a partir de su declaracion, o un ErrorDeDatos.

    Los ORDENES son explicitos. Si no se declaran se usa |nu| de los
    reactivos --accion de masas consistente con la estequiometria-- y la
    respuesta dice que ese fue el defecto. Un orden NO es un coeficiente
    estequiometrico: la ley sale de un mecanismo y la estequiometria de un
    balance, y coinciden solo en una reaccion elemental. Ponerlos iguales
    en silencio seria elegir un mecanismo por el usuario.
    """
    if not isinstance(dato, dict):
        raise ErrorDeDatos(
            f"{etiqueta}: la ley tiene que ser un objeto.",
            codigo=codigos.LAB_LEY_INVALIDA,
        )

    base = dato.get("base_actividad") or "actividad"
    if base not in cin.BASES_ACTIVIDAD:
        raise ErrorDeDatos(
            f"{etiqueta}: base de actividad no admitida: {base!r}. Admitidas: "
            f"{', '.join(sorted(cin.BASES_ACTIVIDAD))}. La base en concentracion "
            "no esta: necesitaria el volumen molar de la mezcla, que es otra "
            "decision de modelo y no se toma por tu cuenta.",
            codigo=codigos.LAB_BASE_ACTIVIDAD_NO_SOPORTADA,
        )

    # La constante, con su unidad, que es la que declara la base de la tasa.
    k_dato = dato.get("k_ref") if dato.get("k_ref") is not None else dato.get("A")
    forma = "referenciada" if dato.get("k_ref") is not None else "arrhenius_clasico"
    if k_dato is None:
        raise ErrorDeDatos(
            f"{etiqueta}: falta la constante. Da 'k_ref' con su 'T_ref' (forma "
            "referenciada, mejor condicionada) o 'A' (Arrhenius clasico).",
            codigo=codigos.LAB_LEY_INVALIDA,
        )
    k_valor, base_tasa, unidad_k = _convertir_tasa(etiqueta, "la constante", k_dato)
    if k_valor < 0:
        raise ErrorDeDatos(
            f"{etiqueta}: la constante cinetica sale {k_valor:g} y no puede ser "
            "negativa: es una velocidad. El signo lo lleva el coeficiente "
            "estequiometrico.",
            codigo=codigos.LAB_TASA_NEGATIVA,
        )
    if base_tasa_esperada is not None and base_tasa != base_tasa_esperada:
        raise ErrorDeDatos(
            f"{etiqueta}: la constante esta en base {base_tasa} y la otra ley de "
            f"la misma reaccion en base {base_tasa_esperada}. Las dos tienen que "
            "estar en la misma base para poder restarse.",
            codigo=codigos.LAB_UNIDAD_INCOMPATIBLE,
        )

    Ea = dato.get("Ea")
    if Ea is None:
        Ea = 0.0
    Ea = float(Ea)
    if not math.isfinite(Ea):
        raise ErrorDeDatos(f"{etiqueta}: Ea no es un numero finito.",
                           codigo=codigos.LAB_VALOR_NO_FINITO)

    T_ref = dato.get("T_ref")
    if forma == "referenciada":
        if T_ref is None:
            raise ErrorDeDatos(
                f"{etiqueta}: 'k_ref' necesita 'T_ref'. Una constante referenciada "
                "sin su temperatura de referencia no dice a que temperatura vale.",
                codigo=codigos.LAB_LEY_INVALIDA,
            )
        T_ref = convertir("T", T_ref.get("valor") if isinstance(T_ref, dict)
                          else T_ref,
                          T_ref.get("unidad") if isinstance(T_ref, dict) else "K")
        if T_ref <= 0:
            raise ErrorDeDatos(f"{etiqueta}: T_ref = {T_ref:g} K no es fisica.",
                               codigo=codigos.LAB_VALOR_FUERA_DE_DOMINIO)
    else:
        T_ref = cin.T_REFERENCIA_POR_OMISION

    # Los ordenes.
    declarados = dato.get("ordenes")
    orden_por_omision = False
    if declarados is None:
        ordenes = np.where(nu < 0, -nu, 0.0)
        orden_por_omision = True
    elif isinstance(declarados, dict):
        desconocidos = [c for c in declarados if c not in componentes]
        if desconocidos:
            raise ErrorDeDatos(
                f"{etiqueta}: los ordenes mencionan componentes que no estan en la "
                f"mezcla: {', '.join(desconocidos)}.",
                codigo=codigos.LAB_ORDEN_INVALIDO,
            )
        ordenes = np.array([float(declarados.get(c, 0.0)) for c in componentes])
    else:
        ordenes = np.asarray(declarados, dtype=float)
        if ordenes.shape != (n,):
            raise ErrorDeDatos(
                f"{etiqueta}: hay {ordenes.size} ordenes y {n} componentes. Da uno "
                "por componente en el mismo orden, o un objeto "
                "{componente: orden}.",
                codigo=codigos.LAB_ORDEN_INVALIDO,
            )
    if not np.all(np.isfinite(ordenes)):
        raise ErrorDeDatos(f"{etiqueta}: hay ordenes no finitos.",
                           codigo=codigos.LAB_VALOR_NO_FINITO)
    if np.any(ordenes < 0):
        # Un orden negativo es fisicamente posible (inhibicion) pero hace
        # que la tasa explote cuando la especie se agota, y con una
        # alimentacion sin esa especie la ley no esta definida. Se
        # rechaza con el motivo en vez de dar un infinito.
        raise ErrorDeDatos(
            f"{etiqueta}: hay ordenes negativos "
            f"({[float(v) for v in ordenes]}). Un orden negativo modela "
            "inhibicion y hace que la tasa diverja cuando esa especie se agota; "
            "este motor no lo admite porque no puede garantizar un resultado "
            "acotado.",
            codigo=codigos.LAB_ORDEN_INVALIDO,
        )

    ley = cin.LeyDeVelocidad(
        k_ref=k_valor, Ea=Ea, ordenes=ordenes, T_ref=T_ref, base=base,
        forma=forma, unidad_k=unidad_k, base_tasa=base_tasa,
    )
    ley.orden_por_omision = orden_por_omision
    return ley, base_tasa


def _leer_reacciones(m, peticion, bloques):
    """
    Pasa `reacciones` de la peticion a objetos Reaccion validados.

    Lo que se comprueba, y el orden importa: primero que la reaccion
    PERTENEZCA a un reactor, luego que la estequiometria sea una reaccion
    (elementos y masa), luego que las tasas esten declaradas sin
    ambiguedad, y al final que la base volumetrica tenga su volumen.

    Comprobar las tasas de una estequiometria que no conserva los
    elementos seria perder el tiempo del usuario en el problema pequeno.
    """
    declaradas = peticion.get("reacciones") or []
    if not declaradas:
        return []

    if m._supuestos.get("sinReaccion"):
        m.avisar(
            codigos.LAB_SUPUESTO_INCOHERENTE, "error",
            f"Hay {len(declaradas)} reaccion(es) declarada(s) y el supuesto "
            "'sinReaccion' las anula.",
            "Quita el supuesto o quita las reacciones: tal como esta, el montaje "
            "declara dos cosas incompatibles. 'sinReaccion' elimina a la vez la "
            "produccion, el consumo y los cierres cineticos.",
            bloques=sorted({r.get("bloque_id") for r in declaradas
                            if r.get("bloque_id") in bloques}),
        )
        return []

    try:
        elementos, A = est.matriz_elemental(m.proveedor)
        mw = est.masas_molares(m.proveedor)
    except ErrorDeDatos as e:
        m.avisar(e.codigo, "error", str(e),
                 "Sin composicion elemental no se puede comprobar la "
                 "estequiometria, y una estequiometria sin comprobar es un dato en "
                 "el que no se puede confiar.",
                 categoria="modelo")
        return []
    m._elementos, m._A, m._mw = elementos, A, mw

    reacciones, vistos = [], set()
    for i, d in enumerate(declaradas):
        rid = d.get("id") or f"reaccion[{i}]"
        etiqueta = f"reacciones[{i}] ({rid})"
        bid = d.get("bloque_id")

        if rid in vistos:
            m.avisar(
                codigos.LAB_ID_DUPLICADO, "error",
                f"Hay mas de una reaccion con el identificador {rid!r}.",
                "Cada reaccion necesita un identificador unico: los avances se "
                "reportan por id.",
            )
            continue
        vistos.add(rid)

        if bid not in bloques:
            m.avisar(
                codigos.LAB_REFERENCIA_INEXISTENTE, "error",
                f"{etiqueta}: el bloque {bid!r} no existe.",
                "Una reaccion pertenece a un volumen del montaje.",
                bloques=[bid] if bid else [],
            )
            continue
        if bloques[bid]["tipo"] != "reactor":
            m.avisar(
                codigos.LAB_REACCION_EN_NO_REACTOR, "error",
                f"{etiqueta}: {bid!r} es de tipo {bloques[bid]['tipo']!r} y una "
                "reaccion pertenece a un reactor.",
                "Cambia la pieza a 'reactor'. La produccion y la desaparicion "
                "quimica pertenecen al volumen donde ocurren, no son "
                "alimentaciones ficticias.",
                bloques=[bid],
            )
            continue

        # --- el camino CINETICO: la tasa se calcula, no se da.
        if d.get("ley_directa") is not None or d.get("ley_inversa") is not None:
            tiene_tasas = [k for k in ("tasa", "tasa_directa", "tasa_inversa",
                                       "tasa_neta") if d.get(k) is not None]
            try:
                if tiene_tasas:
                    raise ErrorDeDatos(
                        f"{etiqueta}: se declaro una ley de velocidad y ademas "
                        f"{', '.join(tiene_tasas)}. Una reaccion tiene la tasa "
                        "DADA o CALCULADA, no las dos: con las dos habria que "
                        "elegir cual manda y la eleccion no es del motor.",
                        codigo=codigos.LAB_TASA_AMBIGUA,
                    )
                if d.get("ley_inversa") is not None and d.get("ley_directa") is None:
                    raise ErrorDeDatos(
                        f"{etiqueta}: hay 'ley_inversa' y no 'ley_directa'. Una "
                        "reaccion que solo va hacia atras se escribe invirtiendo "
                        "los signos de nu.",
                        codigo=codigos.LAB_LEY_INVALIDA,
                    )

                nu = np.asarray(d.get("nu"), dtype=float) if d.get("nu") is not None \
                    else np.zeros(m.n)
                directa, base_tasa = _leer_ley(
                    m, f"{etiqueta}.ley_directa", d["ley_directa"], nu, m.n,
                    m.componentes)

                inversa, desde_equilibrio = None, False
                declarada = d.get("ley_inversa")
                if isinstance(declarada, dict) and declarada.get(
                        "desde_equilibrio"):
                    # La inversa derivada de K_eq(T). Es la restriccion que
                    # impone la termodinamica, y por eso es el unico modo
                    # en que una reversible es consistente sin dos juegos
                    # de datos cineticos independientes.
                    desde_equilibrio = True
                elif declarada is not None:
                    inversa, _ = _leer_ley(
                        m, f"{etiqueta}.ley_inversa", declarada, nu, m.n,
                        m.componentes, base_tasa_esperada=base_tasa)

                # La base volumetrica necesita el volumen, igual que con
                # una tasa dada.
                volumen = None
                if base_tasa == "volumetrica":
                    v_V = m.variable(f"{bid}.V")
                    if v_V is None or v_V.valor is None:
                        raise ErrorDeDatos(
                            f"{etiqueta}: la constante esta en base volumetrica "
                            f"y {bid!r} no declara su volumen.",
                            codigo=codigos.LAB_FALTA_VOLUMEN_REACTOR,
                        )
                    volumen = v_V.valor
                    directa.k_ref *= volumen
                    if inversa is not None:
                        inversa.k_ref *= volumen

                reaccion = cin.ReaccionCinetica(
                    rid, bid, nu, directa, ley_inversa=inversa,
                    inversa_desde_equilibrio=desde_equilibrio, volumen=volumen,
                )
                est.validar_estequiometria(reaccion, elementos, A, mw,
                                           m.componentes)
                reacciones.append(reaccion)
            except ErrorDeDatos as e:
                datos = e.como_diccionario()
                m.avisar(
                    datos.get("codigo") or codigos.LAB_LEY_INVALIDA, "error",
                    str(e), "Revisa la ley de velocidad.", bloques=[bid],
                )
            continue

        if d.get("cinetica") is not None or d.get("A") is not None \
                or d.get("Ea") is not None:
            m.avisar(
                codigos.LAB_LEY_INVALIDA, "error",
                f"{etiqueta}: se dieron parametros cineticos sueltos "
                "('cinetica', 'A' o 'Ea') sin una ley.",
                "Una ley de velocidad se declara en 'ley_directa' (y opcionalmente "
                "'ley_inversa'), con su constante, su Ea, su T_ref y sus ordenes. "
                "Sueltos no dicen de que ley son parametros.",
                bloques=[bid],
            )
            continue

        # --- las tasas DADAS, sin ambiguedad
        tiene = {k: d.get(k) for k in
                 ("tasa", "tasa_directa", "tasa_inversa", "tasa_neta")}
        try:
            if tiene["tasa"] is not None:
                if any(tiene[k] is not None for k in
                       ("tasa_directa", "tasa_inversa", "tasa_neta")):
                    raise ErrorDeDatos(
                        f"{etiqueta}: 'tasa' se dio junto con otras. Elige UNA "
                        "forma: 'tasa' (irreversible), 'tasa_directa' mas "
                        "'tasa_inversa' (reversible, con brutas), o 'tasa_neta' "
                        "(solo el neto).",
                        codigo=codigos.LAB_TASA_AMBIGUA,
                    )
                valor, base, unidad = _convertir_tasa(etiqueta, "tasa", tiene["tasa"])
                modo, r_dir, r_inv, r_net = "irreversible", valor, None, None
            elif tiene["tasa_directa"] is not None or tiene["tasa_inversa"] is not None:
                if tiene["tasa_neta"] is not None:
                    raise ErrorDeDatos(
                        f"{etiqueta}: no se puede dar 'tasa_neta' junto con las "
                        "direccionales. Con las direccionales el neto se calcula.",
                        codigo=codigos.LAB_TASA_AMBIGUA,
                    )
                if tiene["tasa_directa"] is None or tiene["tasa_inversa"] is None:
                    falta = ("tasa_inversa" if tiene["tasa_directa"] is not None
                             else "tasa_directa")
                    raise ErrorDeDatos(
                        f"{etiqueta}: falta {falta}. Una reaccion reversible "
                        "necesita las dos tasas, y con una sola no se sabe si la "
                        "otra es cero o si simplemente no se dio -- que son dos "
                        "situaciones fisicas distintas. Si la reaccion es "
                        "irreversible, usa 'tasa'.",
                        codigo=codigos.LAB_TASA_AMBIGUA,
                    )
                v_dir, base_dir, u_dir = _convertir_tasa(
                    etiqueta, "tasa_directa", tiene["tasa_directa"])
                v_inv, base_inv, u_inv = _convertir_tasa(
                    etiqueta, "tasa_inversa", tiene["tasa_inversa"])
                if base_dir != base_inv:
                    raise ErrorDeDatos(
                        f"{etiqueta}: la tasa directa esta en base {base_dir} "
                        f"({u_dir}) y la inversa en {base_inv} ({u_inv}). Las dos "
                        "tienen que estar en la misma base para poder restarse.",
                        codigo=codigos.LAB_UNIDAD_INCOMPATIBLE,
                    )
                modo, base, unidad = "reversible_bruta", base_dir, f"{u_dir} / {u_inv}"
                r_dir, r_inv, r_net = v_dir, v_inv, None
            elif tiene["tasa_neta"] is not None:
                valor, base, unidad = _convertir_tasa(
                    etiqueta, "tasa_neta", tiene["tasa_neta"])
                modo, r_dir, r_inv, r_net = "neta", None, None, valor
            else:
                raise ErrorDeDatos(
                    f"{etiqueta}: no se declaro ninguna tasa. Hace falta 'tasa', o "
                    "'tasa_directa' mas 'tasa_inversa', o 'tasa_neta'.",
                    codigo=codigos.LAB_TASA_AMBIGUA,
                )

            # Las tasas BRUTAS son no negativas por definicion: el signo va
            # en el coeficiente estequiometrico, no en la velocidad. Una
            # tasa directa negativa es una reaccion que va hacia atras, y
            # eso se escribe con la tasa inversa.
            for nombre_tasa, v in (("tasa_directa", r_dir), ("tasa_inversa", r_inv)):
                if v is not None and v < 0:
                    raise ErrorDeDatos(
                        f"{etiqueta}: {nombre_tasa} = {v:g} mol/s es negativa. Las "
                        "tasas brutas son velocidades y no pueden serlo: el signo "
                        "lo lleva el coeficiente estequiometrico (negativo "
                        "reactivo, positivo producto). Una reaccion que avanza al "
                        "reves se declara con 'tasa_inversa'.",
                        codigo=codigos.LAB_TASA_NEGATIVA,
                    )
            if modo == "irreversible" and r_dir is not None and r_dir < 0:
                raise ErrorDeDatos(
                    f"{etiqueta}: 'tasa' = {r_dir:g} mol/s es negativa. Para una "
                    "reaccion que avanza al reves, invierte los signos de nu o usa "
                    "'tasa_directa' y 'tasa_inversa'.",
                    codigo=codigos.LAB_TASA_NEGATIVA,
                )

            # --- la base volumetrica necesita el volumen
            volumen = None
            if base == "volumetrica":
                v_V = m.variable(f"{bid}.V")
                if v_V is None or v_V.valor is None:
                    raise ErrorDeDatos(
                        f"{etiqueta}: la tasa esta en base volumetrica ({unidad}) y "
                        f"{bid!r} no declara su volumen.",
                        codigo=codigos.LAB_FALTA_VOLUMEN_REACTOR,
                    )
                volumen = v_V.valor
                factor = volumen
                r_dir = None if r_dir is None else r_dir * factor
                r_inv = None if r_inv is None else r_inv * factor
                r_net = None if r_net is None else r_net * factor

            reaccion = est.Reaccion(
                rid, bid, d.get("nu"), modo, r_directa=r_dir, r_inversa=r_inv,
                r_neta=r_net, base=base, unidad=unidad, volumen=volumen,
            )
            est.validar_estequiometria(reaccion, elementos, A, mw, m.componentes)
            reacciones.append(reaccion)

        except ErrorDeDatos as e:
            datos = e.como_diccionario()
            m.avisar(
                datos.get("codigo") or codigos.LAB_ESTEQUIOMETRIA_INVALIDA, "error",
                str(e),
                "Revisa la declaracion de la reaccion.",
                bloques=[bid],
            )
            continue

    return reacciones


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
            if clave not in variables_de_pieza(tipo, m.n):
                m.avisar(
                    codigos.LAB_VARIABLE_DESCONOCIDA, "error",
                    f"{bid!r}: lleva un dato local {clave!r} y una pieza de tipo "
                    f"{tipo!r} no tiene esa variable.",
                    f"En {tipo!r} se puede fijar: "
                    f"{', '.join(variables_de_pieza(tipo, m.n)) or 'nada'}. "
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
        admitidas = variables_de_pieza(tipo, m.n)
        if variable not in admitidas:
            # Un 'x' a secas en una mezcla de tres o mas no identifica
            # ninguna fraccion. Aceptarlo obligaria a adivinar, y adivinar
            # aqui silencia un dato puesto en el sitio equivocado.
            if variable == "x" and tipo == "entrada" and m.n > 2:
                m.avisar(
                    codigos.LAB_VARIABLE_DESCONOCIDA, "error",
                    f"{etiqueta}: 'x' a secas solo vale en una mezcla binaria, y hay "
                    f"{m.n} componentes.",
                    f"Usa el nombre con indice: "
                    f"{', '.join(nombres_composicion(m.n))}, en el orden en que "
                    "declaraste los componentes.",
                    bloques=[bid],
                )
                continue
            m.avisar(
                codigos.LAB_VARIABLE_DESCONOCIDA, "error",
                f"{etiqueta}: {variable!r} no es una variable que se pueda fijar en "
                f"una pieza de tipo {tipo!r}.",
                f"En {tipo!r} se puede fijar: {', '.join(admitidas) or 'nada'}.",
                bloques=[bid],
            )
            continue
        # 'x' en un binario es alias de 'x0'. Se traduce aqui, una sola
        # vez, para que todo lo demas hable un unico idioma.
        if variable == "x":
            variable = "x0"

        try:
            valor = convertir(variable, e.get("valor"), e.get("unidad"))
        except ErrorDeDatos as err:
            m.avisar(err.codigo, "error", f"{etiqueta}: {err}",
                     "Da el valor con una unidad admitida.", bloques=[bid])
            continue

        fuente = (f"dato local de {bid!r} (unidad implicita "
                  f"{UNIDADES_DATOS_LOCALES.get(magnitud_de(variable))})"
                  if e.get("_origen") else f"especificacion explicita en {bid!r} "
                  f"({e.get('unidad')})")

        motivo = _en_dominio(variable, valor)
        if motivo:
            m.avisar(
                codigos.LAB_FRACCION_INVALIDA if magnitud_de(variable) == "x"
                else codigos.LAB_VALOR_FUERA_DE_DOMINIO,
                "error",
                f"{etiqueta}: {variable} = {valor:g} "
                f"{UNIDAD_SI[magnitud_de(variable)]} esta fuera del dominio fisico "
                f"({motivo}).",
                "No es un limite del adaptador sino del significado de la magnitud.",
                bloques=[bid],
            )
            continue

        # A que variable canonica apunta. La unica traduccion no trivial
        # es la 'T' de un volumen, que es la de su corriente de salida.
        if tipo == "reactor" and variable == "V":
            # El volumen es geometria del reactor, no estado de ninguna
            # corriente. Se crea aqui, solo si se da: una variable que
            # nadie usa y nadie determina ensuciaria el recuento.
            v = m.variable(f"{bid}.V") or m._nueva_variable(bid, "V")
            if f"{bid}.V" in vistas:
                anterior, valor_anterior = vistas[f"{bid}.V"]
                m.avisar(
                    codigos.LAB_ESPECIFICACION_DUPLICADA, "error",
                    f"El volumen de {bid!r} se fija dos veces: {valor_anterior:g} m3 "
                    f"desde {anterior}, y {valor:g} m3 desde {etiqueta}.",
                    "Una variable canonica se fija una sola vez.",
                    bloques=[bid], variables=[v.id],
                )
                continue
            v.imponer(valor, f"{fuente}: volumen del reactor")
            vistas[f"{bid}.V"] = (etiqueta, valor)
            continue

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
                f"{UNIDAD_SI[magnitud_de(variable)]} desde {anterior}, y {valor:g} "
                f"{UNIDAD_SI[magnitud_de(variable)]} desde {etiqueta}."
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

        impuestas = [mag for mag in ("F", "T", "p") + nombres_composicion(m.n)
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

        # El cierre de composicion. Con las n fracciones como variables
        # explicitas, el cierre SI determina una de ellas -- la que no se
        # dio -- asi que SI es una ecuacion.
        #
        # Antes no lo era, y no es que el criterio haya cambiado: el
        # criterio es el mismo de siempre, **una relacion cuenta si y solo
        # si determina algo**. Con una sola fraccion en el estado, la
        # segunda no era una variable sino una expresion, y el cierre no
        # determinaba nada. Ahora si. Los grados de libertad dan lo mismo
        # porque han subido a la vez una variable y una ecuacion.
        nombres_x = nombres_composicion(m.n)
        # Cuenta como ecuacion solo si DETERMINA una fraccion. Con las n
        # dadas no calcula nada: comprueba. Contarla entonces daria grados
        # de libertad negativos en un sistema bien planteado, que es justo
        # el error que este modulo denuncia en otros sitios.
        todas_dadas = all(estado[nx].impuesta for nx in nombres_x)
        m.relaciones.append(Relacion(
            id=f"{bid}:cierre",
            tipo="cierre",
            titulo=f"Cierre de composicion en {b.get('nombre') or bid}",
            latex_general=r"\sum_{i=1}^{" + str(m.n) + "} x_{i," + str(j) + "} = 1",
            latex_activo=(r"\sum_{i=1}^{" + str(m.n) + "} x_{i," + str(j) + "} = 1"),
            origen_bloques=[bid],
            variables=[estado[nx].id for nx in nombres_x],
            cuenta_como_ecuacion=not todas_dadas,
            metodo="propagacion algebraica",
            alcance="algebraico_directo",
            escala="adimensional" if todas_dadas else None,
            nota=(
                "Se dieron las n fracciones, asi que el cierre no calcula nada: "
                "comprueba. Es una redundancia, no una ecuacion independiente, y "
                "por eso no cuenta. Su residuo SI se mide: una redundancia que no "
                "cuadra es un dato contradictorio."
                if todas_dadas else
                f"Determina la fraccion que no se dio, de las {m.n} que tiene la "
                "corriente."
            ),
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
            variables=([estado[k].id for k in ("T", "p", "h")]
                       + [estado[nx].id for nx in nombres_composicion(m.n)]),
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
                "motivo": "Sin reaccion no hay transformacion de especies: el "
                          "supuesto elimina a la vez la produccion, el consumo y "
                          "los cierres cineticos.",
            })

        reacciones_aqui = [r for r in m.reacciones if r.bloque_id == bid]
        ids_reaccion = [r.id for r in reacciones_aqui]
        nombres_x = nombres_composicion(m.n)

        # --- n balances por especie. Son LAS ecuaciones de materia.
        for i, comp in enumerate(m.componentes):
            termino_reaccion = ""
            if reacciones_aqui:
                partes = []
                for r in reacciones_aqui:
                    coef = r.nu[i]
                    if abs(coef) < 1e-15:
                        continue
                    signo = "+" if coef > 0 else "-"
                    magnitud_coef = (
                        "" if abs(abs(coef) - 1.0) < 1e-12 else f"{abs(coef):g}\\,")
                    partes.append(
                        f" {signo} {magnitud_coef}\\dot\\xi_{{{r.id}}}")
                termino_reaccion = "".join(partes)

            m.relaciones.append(Relacion(
                id=f"{bid}:materia_especie_{i}",
                tipo="balance",
                titulo=f"Conservacion de {comp} · {nombre}",
                latex_general=(r"\frac{dn_i}{dt} = \sum_{in} F x_i "
                               r"- \sum_{out} F x_i + \sum_r \nu_{ir}\dot\xi_r"),
                latex_activo=(f"F_{{{jo}}} x_{{{i + 1},{jo}}} = "
                              f"F_{{{ji}}} x_{{{i + 1},{ji}}}{termino_reaccion}"),
                terminos_descartados=descartados_materia,
                origen_bloques=[bid, entrada, salida],
                origen_conexiones=cx,
                variables=[e_in["F"].id, e_in[nombres_x[i]].id,
                           e_out["F"].id, e_out[nombres_x[i]].id],
                unidad="mol/s",
                cuenta_como_ecuacion=True,
                metodo="propagacion algebraica",
                alcance="algebraico_directo",
                nota=(
                    f"Una ecuacion por especie. El avance de "
                    f"{', '.join(ids_reaccion)} entra con su coeficiente "
                    "estequiometrico: positivo produce, negativo consume."
                    if reacciones_aqui else
                    "Una ecuacion por especie. Sin reaccion, junto con el cierre, "
                    "da la composicion de salida igual a la de entrada."
                ),
            ))

        # --- el balance TOTAL, que NO es independiente.
        #
        # Es la suma de los n balances por especie. Contarlo como ecuacion
        # regalaria una ecuacion -- el mismo error que contar la
        # verificacion global de energia. Y como suma, sirve de
        # comprobacion: si los n se aplicaron bien, el total cuadra.
        suma_nu = ([f" + {s_:g}\\,\\dot\\xi_{{{r.id}}}"
                    for r, s_ in ((r, float(r.nu.sum())) for r in reacciones_aqui)
                    if abs(s_) > 1e-15])
        m.relaciones.append(Relacion(
            id=f"{bid}:materia_total",
            tipo="verificacion",
            titulo=f"Conservacion de materia total · {nombre}",
            latex_general=(r"\frac{dn}{dt} = \sum_{in} F - \sum_{out} F "
                           r"+ \sum_r \left(\sum_i \nu_{ir}\right)\dot\xi_r"),
            latex_activo=f"F_{{{jo}}} = F_{{{ji}}}" + "".join(suma_nu),
            terminos_descartados=descartados_materia,
            origen_bloques=[bid, entrada, salida],
            origen_conexiones=cx,
            variables=[e_in["F"].id, e_out["F"].id],
            unidad="mol/s",
            escala="relativa al caudal de entrada",
            cuenta_como_ecuacion=False,
            nota=(
                "Suma de los balances por especie, asi que no anade informacion al "
                "sistema. Se mide porque es la comprobacion de que se aplicaron "
                "bien. OJO: el caudal molar total PUEDE cambiar con reaccion -- "
                "sum(nu) no tiene por que ser cero -- y eso no viola nada; lo que "
                "no cambia nunca es la masa."
            ),
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
        # El calor de reaccion. Entra EXPLICITAMENTE porque la referencia
        # de entalpia de este motor es sensible: no incluye las entalpias
        # de formacion. Si algun dia hubiera una referencia que si las
        # incluyera, el termino NO debe aparecer -- estaria ya dentro de
        # h -- y por eso la decision cuelga de la referencia y no de que
        # haya reaccion.
        incluye_formacion = REFERENCIAS[m.referencia]["incluye_formacion"]
        termino_rxn = ""
        if reacciones_aqui and not incluye_formacion:
            termino_rxn = "".join(
                f" - \\dot\\xi_{{{r.id}}}\\,\\Delta H_{{rxn,{r.id}}}"
                for r in reacciones_aqui)
        latex_activo = (" + ".join(terminos_q + [f"F_{{{ji}}} h_{{{ji}}}"])
                        + termino_rxn
                        + f" = F_{{{jo}}} h_{{{jo}}}")
        variables_energia = [e_in["F"].id, e_in["h"].id, e_out["F"].id, e_out["h"].id]
        variables_energia += [f"{c['desde']}.Q" for c in calores] if not s["adiabatico"] else []

        if reacciones_aqui and incluye_formacion:
            descartados_energia.append({
                "termino": "calor de reaccion explicito",
                "latex": r"\sum_r \dot\xi_r \Delta H_{rxn,r}",
                "supuesto": f"referencia {m.referencia}",
                "motivo": "La referencia de entalpia YA incluye las entalpias de "
                          "formacion, asi que el calor de reaccion esta dentro de h. "
                          "Sumarlo aparte lo contaria dos veces.",
            })

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
            latex_general=(
                r"\sum_j \dot Q_j = F_{salida} h_{salida} - F_{entrada} h_{entrada}"
                r" + \sum_r \dot\xi_r \Delta H_{rxn,r}"),
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

        # El supuesto adiabatico SI es una especificacion termica: dice
        # Q = 0, y entonces la temperatura es la incognita. Que no haya
        # fuente de calor no significa que falte el dato -- significa que
        # el dato lo puso el supuesto.
        #
        # Es el mismo razonamiento de la entrega anterior en el otro
        # sentido: la AUSENCIA de una fuente no es Q = 0, pero la
        # PRESENCIA del supuesto si lo es.
        adiabatico = m._supuestos.get("adiabatico") and not calores
        if adiabatico:
            if T_impuesta:
                m.avisar(
                    codigos.LAB_ESPECIFICACION_EXCLUYENTE, "error",
                    f"{nombre!r}: el supuesto adiabatico ya impone Q = 0, y "
                    f"ademas se impuso la temperatura de salida "
                    f"({v_T.valor:g} K).",
                    "Con Q = 0 el balance de energia determina la temperatura. "
                    "Impuestas las dos, la ecuacion sobra y en general no se "
                    "cumple: quita una.",
                    bloques=[bid, salida], variables=[v_T.id],
                )
            else:
                m._modo = getattr(m, "_modo", {})
                m._modo[bid] = "adiabatico"
            continue

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
                "Fija una de las dos, o marca el supuesto adiabatico y retira la "
                "fuente, que equivale a imponer Q = 0. Sin ninguna, el balance de "
                "energia tiene dos incognitas y una sola ecuacion.",
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
    z = np.asarray(x, dtype=float)
    return m.flash.isotermico(float(T), m.presion, z)


def _dH_de(m):
    """Las entalpias de reaccion, calculadas una vez y cacheadas."""
    if not hasattr(m, "_dH_rxn"):
        m._dH_rxn = est.entalpias_de_reaccion(m.proveedor, m.reacciones)
    return m._dH_rxn


def _K_eq_de(m):
    """
    K_eq(T) de cada reaccion, para las inversas derivadas del equilibrio.

    Se construye un GestorReaccion con la estequiometria del montaje y se
    le piden sus K: reutiliza la maquinaria de van't Hoff ya validada en
    thermodynamics/reaccion.py en vez de reescribirla.

    OJO con lo que esto significa y lo que no: van't Hoff supone dH_rxn
    CONSTANTE con la temperatura. Es una aproximacion, se declara como tal
    en la respuesta, y lejos de T_std se nota.
    """
    if hasattr(m, "_gestor_K"):
        return m._gestor_K

    necesitan = [r for r in m.reacciones
                 if getattr(r, "inversa_desde_equilibrio", False)]
    if not necesitan:
        m._gestor_K = None
        return None

    NU = np.array([r.nu for r in necesitan], dtype=float)
    try:
        gestor = GestorReaccion(m.proveedor, NU, A=1.0, Ea=0.0)
    except Exception as e:
        raise ErrorDeDatos(
            f"No se puede calcular K_eq para las reacciones que la piden: {e}. "
            "Hace falta la energia de Gibbs de formacion de todas las especies; "
            "consultala en /laboratorio/sustancias/buscar antes de usar "
            "'desde_equilibrio'.",
            codigo=codigos.LAB_EQUILIBRIO_NO_UTILIZABLE,
        ) from e

    indices = {r.id: j for j, r in enumerate(necesitan)}

    def K_de(reaccion_id, T):
        return float(gestor.K_eq_de_cada_una(float(T))[indices[reaccion_id]])

    m._gestor_K = K_de
    return K_de


def _resolver_volumen_cinetico(m, bid, nombre, cineticas, F_i_in, F_in, h_in,
                               e_in, e_out, modo, bloques_calor):
    """
    Resuelve los avances de un volumen con leyes de velocidad.

    AQUI SE ROMPE LA TRIANGULARIDAD, Y SOLO AQUI. La marcha aguas abajo
    entre volumenes sigue valiendo --la entrada de cada uno es la salida
    del anterior, ya determinada-- pero DENTRO del volumen la tasa depende
    de la composicion de salida, que es lo que el balance calcula. Eso es
    un sistema implicito y se resuelve como tal.

    Dos caminos, segun si la temperatura esta impuesta:

      isotermo      T dada: se resuelven solo los avances. Con una
                    reaccion es una raiz escalar ACOTADA por la
                    estequiometria; con varias, un sistema.
      acoplado      T incognita (adiabatico o Q impuesto): los avances y
                    la temperatura se cierran A LA VEZ, porque k(T) decide
                    el avance y el avance decide el calor que decide T.
                    Resolver uno y luego el otro daria la respuesta de
                    otro problema.
    """
    calculadora = entalpia_de(m.proveedor)
    K_de = _K_eq_de(m)

    def entalpia(T, x):
        return m.flash.isotermico(float(T), m.presion,
                                  np.asarray(x, dtype=float))["h"]

    try:
        if modo == "temperatura":
            T_out = e_out["T"].valor
            resultado = cin.resolver_cinetica_isoterma(
                m.proveedor, cineticas, F_i_in, T_out, m.n, K_eq_de=K_de)
        else:
            # Adiabatico (Q = 0) o Q impuesto: la temperatura entra en el
            # sistema.
            Q = 0.0
            if modo == "calor":
                v_Q = m.variable(f"{bloques_calor[0]['desde']}.Q")
                Q = v_Q.valor
            dH = _dH_de(m)
            # Los limites de temperatura salen de la TABLA de entalpia,
            # no de un numero elegido: es el dominio donde el modelo
            # existe, y es lo que impide que el solver busque donde no hay
            # nada.
            resultado = cin.resolver_cinetica_con_energia(
                m.proveedor, cineticas, F_i_in, e_in["T"].valor, h_in, m.n,
                entalpia_de=entalpia, dH_de=lambda rid: dH[rid], Q=Q,
                K_eq_de=K_de, T_inicial=e_in["T"].valor,
                T_limites=(calculadora.T_min, calculadora.T_max),
            )
            e_out["T"].valor = float(resultado.T)
            e_out["T"].procedencia = (
                f"sistema acoplado de {nombre!r}: los avances y la temperatura "
                "se cierran a la vez"
                + (" con Q = 0 (adiabatico)" if modo == "adiabatico"
                   else f" con Q = {Q:g} W impuesto")
            )
    except (ValueError, ArithmeticError) as e:
        raise ErrorNumerico(
            f"{nombre!r}: el sistema cinetico no se pudo resolver: {e}",
            codigo=codigos.LAB_IMPLICITO_SIN_CONVERGENCIA, equipo=bid,
        ) from e

    if not resultado.convergio:
        raise ErrorNumerico(
            f"{nombre!r}: el sistema cinetico no convergio. Residuo escalado "
            f"{resultado.residuo:.3e} frente a una tolerancia de "
            f"{cin.TOLERANCIA_IMPLICITA:.0e}. {resultado.motivo or ''}",
            codigo=codigos.LAB_IMPLICITO_SIN_CONVERGENCIA, equipo=bid,
        )

    # La factibilidad, COMPROBADA. Con una reaccion el intervalo ya la
    # garantiza; con varias no se puede imponer y por eso se mira aqui.
    NU = np.array([r.nu for r in cineticas], dtype=float)
    F_i_out = np.asarray(F_i_in, dtype=float) + NU.T @ resultado.xi
    escala = max(float(np.sum(F_i_in)), 1.0)
    negativas = [i for i in range(m.n) if F_i_out[i] < -1e-9 * escala]
    if negativas:
        detalle = ", ".join(
            f"{m.componentes[i]}: {F_i_out[i]:.6g} mol/s" for i in negativas)
        raise ErrorFisico(
            f"{nombre!r}: la solucion del sistema cinetico deja caudales "
            f"negativos ({detalle}). Las leyes y la alimentacion no son "
            "compatibles: revisa constantes, ordenes y composicion de entrada.",
            codigo=codigos.LAB_CAUDAL_ESPECIE_NEGATIVO, equipo=bid,
        )

    m.avisar(
        codigos.LAB_INFO_CINETICA, "informacion",
        f"{nombre!r}: sistema cinetico resuelto con {resultado.metodo}; residuo "
        f"escalado {resultado.residuo:.3e} en {resultado.evaluaciones} "
        "evaluaciones de la ley.",
        None, categoria="informacion",
        bloques=[bid], variables=[e_out["T"].id],
    )
    return resultado


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
    implicitos = []

    try:
        for bid in m.volumenes:
            nombre = m._bloques[bid].get("nombre") or bid
            entrada = m._entradas_de[bid][0]["desde"]
            salida = m._salidas_de[bid][0]["hacia"]
            e_in, e_out = m.estados[entrada], m.estados[salida]

            # --- el estado de entrada
            if e_in["h"].valor is None:
                T_in = e_in["T"].valor
                x_in = _cerrar_composicion(m, entrada)
                if T_in is None or x_in is None or e_in["F"].valor is None:
                    raise ErrorDeDatos(
                        f"La corriente que entra a {nombre!r} no tiene su estado "
                        "completo (F, T y la composicion).",
                        codigo=codigos.LAB_FALTA_ESPECIFICACION,
                    )
                r_in = _estado_completo(m, entrada, T_in, x_in)
                e_in["h"].valor = r_in["h"]
                e_in["h"].procedencia = (
                    f"h({T_in:.6g} K, {m.presion:.6g} Pa, "
                    f"x={_fmt_x(x_in)}) con {m.modelo}; fase {r_in['fase']}"
                )
                _marcar_entalpia(m, entrada, r_in)

            F_in = e_in["F"].valor
            h_in = e_in["h"].valor
            # Ya cerrada arriba si hizo falta; _cerrar_composicion es
            # idempotente, asi que esto solo lee.
            x_in = _cerrar_composicion(m, entrada)
            if x_in is None:
                raise ErrorDeDatos(
                    f"La corriente que entra a {nombre!r} no tiene su composicion "
                    "determinada.",
                    codigo=codigos.LAB_FALTA_ESPECIFICACION,
                )
            F_i_in = F_in * x_in

            # --- los balances por especie, CON reaccion
            #
            # Se trabaja con caudales por especie y no con fracciones,
            # porque el balance es lineal en F_i y no en x_i: con reaccion
            # el caudal total cambia, y una ecuacion escrita en fracciones
            # arrastraria ese cambio a todos los terminos.
            reacciones_aqui = [r for r in m.reacciones if r.bloque_id == bid]
            cineticas = [r for r in reacciones_aqui
                         if isinstance(r, cin.ReaccionCinetica)]
            if cineticas and len(cineticas) != len(reacciones_aqui):
                raise ErrorDeDatos(
                    f"{nombre!r}: mezcla reacciones de tasa dada con reacciones "
                    "cineticas. Las primeras se propagan y las segundas exigen "
                    "resolver un sistema implicito; combinarlas en un mismo "
                    "volumen necesita un solver que incluya las dos, y este "
                    "ensamblador aun no lo hace.",
                    codigo=codigos.LAB_TOPOLOGIA_NO_SOPORTADA,
                    equipo=bid,
                )

            modo = modos.get(bid)
            if cineticas:
                implicito = _resolver_volumen_cinetico(
                    m, bid, nombre, cineticas, F_i_in, F_in, h_in, e_in, e_out,
                    modo, bloques_calor=[
                        c for c in m._fuentes
                        if c["hacia"] == bid
                        and m._bloques[c["desde"]]["tipo"] == "calor"])
                implicitos.append((bid, implicito))
                alcances.add(implicito.alcance)

            avance = np.zeros(m.n, dtype=float)
            for r in reacciones_aqui:
                avance = avance + r.fuente_neta()
            F_i_out = F_i_in + avance

            # Un caudal de especie negativo significa que la tasa consume
            # mas de lo que entra. No es un error numerico: es un dato
            # imposible, y presentarlo como resultado daria composiciones
            # negativas que parecen numeros.
            negativas = [i for i in range(m.n) if F_i_out[i] < -1e-12 * max(F_in, 1.0)]
            if negativas:
                detalle = ", ".join(
                    f"{m.componentes[i]}: entra {F_i_in[i]:.6g} y la reaccion "
                    f"consume {-avance[i]:.6g} mol/s"
                    for i in negativas)
                raise ErrorFisico(
                    f"{nombre!r}: la tasa especificada consume mas de lo que entra "
                    f"({detalle}). El avance no cabe en la alimentacion.",
                    codigo=codigos.LAB_CAUDAL_ESPECIE_NEGATIVO,
                    equipo=bid,
                )

            F_out = float(np.sum(F_i_out))
            if F_out <= 0:
                raise ErrorFisico(
                    f"{nombre!r}: el caudal de salida sale {F_out:.6g} mol/s.",
                    codigo=codigos.LAB_CAUDAL_ESPECIE_NEGATIVO, equipo=bid,
                )
            x_out = F_i_out / F_out

            e_out["F"].valor = F_out
            e_out["F"].procedencia = (
                f"suma de los balances por especie de {nombre!r}"
                + (f" (el avance de {', '.join(r.id for r in reacciones_aqui)} "
                   f"cambia el caudal total en {F_out - F_in:+.6g} mol/s)"
                   if reacciones_aqui else "")
            )
            m.fijar_composicion(
                salida, x_out,
                f"balances por especie de {nombre!r}"
                + (" con el avance de la reaccion" if reacciones_aqui else ""))
            # El cierre de la salida lo satisface la normalizacion
            # x_i = F_i / sum(F_j). Se marca aqui, donde de verdad ocurre:
            # dejarlo sin ejecutar diria que el sistema tiene una ecuacion
            # que no se uso.
            _relacion(m, f"{salida}:cierre").ejecutar(
                nota=f"lo satisface la normalizacion x_i = F_i / {F_out:.6g}: la "
                     "composicion sale de los balances por especie, asi que suma 1 "
                     "por construccion y no hay residuo que medir",
            )
            for i in range(m.n):
                _relacion(m, f"{bid}:materia_especie_{i}").ejecutar(
                    nota=(f"F_{i} de salida = {F_i_out[i]:.6g} mol/s "
                          f"(entra {F_i_in[i]:.6g}, reaccion {avance[i]:+.6g})")
                    if reacciones_aqui else
                    "Sin reaccion, el caudal de esta especie se propaga.")

            # El balance total: SUMA de los por especie, asi que se MIDE
            # en vez de resolverse.
            residuo_total = abs(F_out - (F_in + float(np.sum(avance))))
            escala_total = max(abs(F_in), abs(F_out), 1.0)
            _relacion(m, f"{bid}:materia_total").ejecutar(
                residuo=residuo_total / escala_total,
                nota=(f"F pasa de {F_in:.6g} a {F_out:.6g} mol/s; la suma de los "
                      f"coeficientes por el avance da {float(np.sum(avance)):+.6g} "
                      "mol/s"),
            )
            F = F_in

            calores = [c for c in m._fuentes
                       if c["hacia"] == bid and m._bloques[c["desde"]]["tipo"] == "calor"]
            v_Q = m.variable(f"{calores[0]['desde']}.Q") if calores else None
            rel_energia = _relacion(m, f"{bid}:energia")

            # El calor de reaccion. Se suma SOLO si la referencia de
            # entalpia no incluye las entalpias de formacion -- si las
            # incluyera, ya estaria dentro de h y sumarlo lo contaria dos
            # veces. La decision cuelga de la referencia, no de que haya
            # reaccion.
            calor_rxn = 0.0
            if reacciones_aqui and not REFERENCIAS[m.referencia]["incluye_formacion"]:
                if not hasattr(m, "_dH_rxn"):
                    try:
                        m._dH_rxn = est.entalpias_de_reaccion(m.proveedor, m.reacciones)
                    except ErrorDeDatos as e:
                        raise ErrorDeDatos(
                            str(e), codigo=e.codigo, equipo=bid) from e
                calor_rxn = est.calor_de_reaccion(reacciones_aqui, m._dH_rxn)
                m.avisar(
                    codigos.LAB_INFO_CALOR_REACCION, "informacion",
                    f"{nombre!r}: el calor de reaccion aporta {-calor_rxn:+.6g} W al "
                    f"balance (suma de xi dH_rxn = {calor_rxn:+.6g} W). La referencia "
                    f"{m.referencia!r} es SENSIBLE: no incluye las entalpias de "
                    "formacion, asi que el termino va explicito y no esta duplicado.",
                    None, categoria="informacion",
                    bloques=[bid], variables=[e_out["h"].id],
                )

            if modo == "temperatura":
                # Evaluacion directa: ninguna iteracion, ningun residuo.
                T_out = e_out["T"].valor
                r_out = _estado_completo(m, salida, T_out, x_out)
                e_out["h"].valor = r_out["h"]
                e_out["h"].procedencia = (
                    f"h({T_out:.6g} K, {m.presion:.6g} Pa, x={_fmt_x(x_out)}) "
                    f"con {m.modelo}; fase {r_out['fase']}"
                )
                _marcar_entalpia(m, salida, r_out)
                Q = F_out * r_out["h"] - F_in * h_in + calor_rxn
                if v_Q is not None:
                    v_Q.valor = Q
                    v_Q.procedencia = (
                        f"balance de energia de {nombre!r}: "
                        "Q = F_sal h_sal - F_ent h_ent"
                        + (" + sum(xi dH_rxn)" if calor_rxn else "")
                    )
                rel_energia.metodo = "evaluacion algebraica directa"
                rel_energia.alcance = "algebraico_directo"
                rel_energia.ejecutar(
                    nota="Se despeja Q de la ecuacion, asi que se satisface por "
                         "construccion: no hay residuo que medir ni iteracion que "
                         "contar. Presentar un residuo de 1e-11 aqui seria presentar "
                         "el error de redondeo como si fuera una convergencia."
                         + (f" El calor de reaccion aporta {calor_rxn:+.6g} W."
                            if calor_rxn else ""),
                )
                alcances.add("algebraico_directo")

            elif cineticas and modo in ("calor", "adiabatico"):
                # La temperatura ya salio del sistema acoplado, junto con
                # los avances. Volver a invertir h(T) aqui resolveria dos
                # veces la misma ecuacion, y la segunda sin la cinetica,
                # que es justo lo que la acopla.
                Q = 0.0 if modo == "adiabatico" else v_Q.valor
                T_out = e_out["T"].valor
                r_out = _estado_completo(m, salida, T_out, x_out)
                e_out["h"].valor = r_out["h"]
                e_out["h"].procedencia = (
                    f"h({T_out:.6g} K, {m.presion:.6g} Pa, x={_fmt_x(x_out)}) "
                    f"con {m.modelo}; fase {r_out['fase']}"
                )
                _marcar_entalpia(m, salida, r_out)
                if v_Q is not None:
                    v_Q.valor = Q
                    v_Q.procedencia = (
                        f"impuesto en {nombre!r}" if modo == "calor" else
                        f"cero: {nombre!r} es adiabatico"
                    )
                rel_energia.metodo = (
                    "resuelto dentro del sistema cinetico acoplado: los avances y "
                    "la temperatura se cierran a la vez")
                rel_energia.alcance = "sistema_acoplado"
                rel_energia.escala = (
                    "residuo de energia relativo a F h de entrada")
                implicito_aqui = next(
                    (res for b, res in implicitos if b == bid), None)
                rel_energia.ejecutar(
                    residuo=(implicito_aqui.residuo if implicito_aqui else None),
                    nota=(
                        "Con cinetica, k(T) decide el avance y el avance decide el "
                        "calor que decide T: las dos cosas se cierran juntas. El "
                        "residuo es el maximo del sistema, que incluye esta "
                        "ecuacion."
                        + (f" El calor de reaccion aporta {calor_rxn:+.6g} W."
                           if calor_rxn else "")
                    ),
                )
                alcances.add("sistema_acoplado")

            elif modo in ("calor", "adiabatico"):
                # Inversion escalar: h objetivo conocido, se busca T.
                # El adiabatico es este mismo caso con Q = 0, asi que se
                # resuelve por el mismo camino en vez de duplicarlo.
                Q = 0.0 if modo == "adiabatico" else v_Q.valor
                if modo == "adiabatico" and v_Q is not None:
                    v_Q.valor = 0.0
                # Con reaccion, F de salida NO es F de entrada, asi que la
                # entalpia objetivo se divide por el caudal que de verdad
                # sale. Usar el de entrada daria una temperatura
                # plausible y equivocada.
                h_objetivo = (F_in * h_in + Q - calor_rxn) / F_out
                try:
                    r_out = m.flash.a_entalpia(m.presion, x_out, h_objetivo)
                except ValueError as e:
                    raise ErrorFisico(
                        f"{nombre!r}: con Q = {Q:g} W"
                        + (" (adiabatico)" if modo == "adiabatico" else "")
                        + f" y F = {F_out:g} mol/s la entalpia de salida "
                        f"({h_objetivo:.6g} J/mol) cae fuera del dominio del "
                        f"modelo. {e}",
                        codigo=codigos.LAB_FUERA_DE_DOMINIO_TERMODINAMICO,
                        equipo=bid,
                    ) from e
                T_out = r_out["T"]
                e_out["T"].valor = T_out
                e_out["T"].procedencia = (
                    f"inversion de h(T) en {nombre!r}: la entalpia de salida sale "
                    "del balance de energia"
                    + (" con Q = 0 (adiabatico)" if modo == "adiabatico"
                       else " con el Q impuesto")
                )
                e_out["h"].valor = r_out["h"]
                e_out["h"].procedencia = (
                    f"(F_ent h_ent + Q"
                    + (" - sum(xi dH_rxn)" if calor_rxn else "")
                    + f") / F_sal en {nombre!r}"
                )
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

            # --- las fuentes del volumen: G, C y el neto por especie.
            #
            # Se DERIVAN de la estequiometria y de las tasas. No son dos
            # incognitas mas por especie: con n especies serian 2n
            # variables nuevas y el problema quedaria indeterminado.
            if reacciones_aqui:
                m._fuentes_por_volumen = getattr(m, "_fuentes_por_volumen", {})
                m._fuentes_por_volumen[bid] = est.fuentes_del_volumen(
                    reacciones_aqui, m.n, m.componentes)

                # Y la conservacion, MEDIDA sobre los caudales resueltos.
                # Es independiente de haber validado la estequiometria:
                # aquello comprueba que la reaccion tenga sentido, esto
                # que el balance se haya aplicado bien.
                medida = est.conservacion_medida(
                    F_i_in, F_i_out, m._elementos, m._A, m._mw)
                m._conservacion = getattr(m, "_conservacion", {})
                m._conservacion[bid] = medida
                peor = max(medida["residuo_elemental_maximo"],
                           medida["masa"]["residuo_relativo"])
                if peor > TOLERANCIA_CONSERVACION:
                    raise ErrorNumerico(
                        f"{nombre!r}: el balance no conserva los elementos o la "
                        f"masa (residuo relativo {peor:.3e}, tolerancia "
                        f"{TOLERANCIA_CONSERVACION:.0e}). La estequiometria se "
                        "valido, asi que el fallo esta en como se aplico el "
                        "balance -- es un fallo del motor, no de los datos.",
                        codigo=codigos.LAB_CONSERVACION_NO_MEDIDA,
                        equipo=bid,
                    )
                m.avisar(
                    codigos.LAB_INFO_CONSERVACION, "informacion",
                    f"{nombre!r}: elementos y masa conservados (residuo relativo "
                    f"maximo {peor:.3e}). El caudal molar pasa de "
                    f"{medida['caudal_molar']['entra_mol_s']:.6g} a "
                    f"{medida['caudal_molar']['sale_mol_s']:.6g} mol/s"
                    + (" -- cambia, y eso es correcto: sum(nu) no es cero."
                       if medida["caudal_molar"]["cambia"] else "."),
                    None, categoria="informacion",
                    bloques=[bid, entrada, salida],
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
    convergencia = _cerrar(m, analisis, alcances, iteraciones_totales, residuos,
                           implicitos)
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


def _fmt_x(x):
    """La composicion para un mensaje, corta y legible."""
    return "[" + ", ".join(f"{v:.6g}" for v in np.asarray(x)) + "]"


def _cerrar_composicion(m, bloque_id):
    """
    Las n fracciones de una corriente, cerrando la que falte.

    Tres caminos, y la diferencia entre ellos esta en si el valor fue
    IMPUESTO o CALCULADO -- no en si esta presente. Confundir las dos
    cosas llevaba a medir el residuo de 1 - (1 - x), que es cero por
    construccion y no comprueba nada.

      * ya resuelta antes: se devuelven los valores y no se vuelve a
        tocar la relacion. La funcion es idempotente a proposito, porque
        el solver mira la entrada de cada volumen y una corriente
        intermedia es entrada de uno y salida de otro.
      * las n IMPUESTAS: el cierre no calcula, comprueba. El residuo se
        mide y una suma que no da 1 es un dato contradictorio.
      * una sin imponer: el cierre la determina. Sin residuo, porque se
        satisface por construccion.

    Si faltan dos o mas por imponer y nadie las ha calculado, no hay nada
    que cerrar: se devuelve None. Repartir la diferencia a partes iguales
    seria inventar una composicion.
    """
    variables = m.composicion(bloque_id)
    rel = _relacion(m, f"{bloque_id}:cierre")

    if rel.ejecutada:
        valores = [v.valor for v in variables]
        if any(v is None for v in valores):
            return None
        return np.array(valores, dtype=float)

    sin_imponer = [v for v in variables if not v.impuesta]

    if not sin_imponer:
        # Las n dadas: el cierre comprueba en vez de calcular, y por eso
        # SI tiene residuo. Es la unica rama donde medirlo significa algo.
        suma = sum(v.valor for v in variables)
        if abs(suma - 1.0) > 1e-9:
            raise ErrorDeDatos(
                f"Las {len(variables)} fracciones de {bloque_id!r} suman "
                f"{suma:.9g} y no 1. Al darlas todas, el cierre deja de calcular "
                "y pasa a comprobar; esta comprobacion no la pasa.",
                codigo=codigos.LAB_DATOS_COMPOSICION_INCOMPATIBLE,
                equipo=bloque_id,
            )
        rel.ejecutar(
            residuo=abs(suma - 1.0),
            nota="se dieron las n fracciones, asi que el cierre comprueba en vez "
                 "de calcular; el residuo es lo que le sobra a la suma",
        )
        return np.array([v.valor for v in variables], dtype=float)

    if len(sin_imponer) > 1:
        # Nadie las ha calculado todavia y faltan varias por imponer.
        if any(v.valor is None for v in variables):
            return None
        # Las calculo otro paso (los balances por especie de un volumen
        # aguas arriba). El cierre se satisface por la normalizacion.
        rel.ejecutar(
            nota="la composicion sale de los balances por especie, normalizada por "
                 "el caudal total: el cierre se satisface por construccion y no "
                 "hay residuo que medir",
        )
        return np.array([v.valor for v in variables], dtype=float)

    # Exactamente una sin imponer: el cierre la determina.
    pendiente = sin_imponer[0]
    resto = sum(v.valor for v in variables if v is not pendiente)
    valor = 1.0 - resto
    if valor < -1e-9 or valor > 1.0 + 1e-9:
        raise ErrorFisico(
            f"El cierre de composicion de {bloque_id!r} da "
            f"{pendiente.id} = {valor:.6g}, fuera de [0, 1]: las fracciones "
            f"dadas suman {resto:.6g}.",
            codigo=codigos.LAB_FRACCION_INVALIDA, equipo=bloque_id,
        )
    pendiente.valor = min(max(valor, 0.0), 1.0)
    pendiente.procedencia = (
        f"cierre de composicion: 1 menos la suma de las otras {len(variables) - 1}"
    )
    rel.ejecutar(nota=f"determina {pendiente.id} = {pendiente.valor:.6g}")
    return np.array([v.valor for v in variables], dtype=float)


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


def _cerrar(m, analisis, alcances, iteraciones, residuos, implicitos=()):
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
        suma_Q = sum(v.valor for v in m.variables.values()
                     if v.magnitud == "Q" and v.valor is not None)
        # El transporte, con los caudales de VERDAD: con reaccion el de
        # salida no es el de entrada, asi que no hay un F que multiplique
        # a las dos entalpias.
        transporte = (m.estados[salida]["F"].valor * m.estados[salida]["h"].valor
                      - m.estados[entrada]["F"].valor * m.estados[entrada]["h"].valor)
        # Y el calor de reaccion de TODO el montaje. Al sumar los balances
        # por volumen los estados intermedios se cancelan --la salida de
        # uno es la entrada del siguiente, y es LA MISMA variable-- pero
        # los terminos de reaccion no: se acumulan.
        calor_rxn_total = 0.0
        if m.reacciones and not REFERENCIAS[m.referencia]["incluye_formacion"]:
            calor_rxn_total = est.calor_de_reaccion(m.reacciones, m._dH_rxn)
        esperado = transporte + calor_rxn_total
        escala = max(abs(suma_Q), abs(esperado), abs(transporte), 1.0)
        residuo_global = abs(suma_Q - esperado) / escala
        rel.ejecutar(
            residuo=residuo_global,
            nota=(f"suma de calores {suma_Q:.6f} W frente a "
                  f"F_sal h_sal - F_ent h_ent = {transporte:.6f} W"
                  + (f" mas el calor de reaccion de todo el montaje "
                     f"{calor_rxn_total:+.6f} W" if calor_rxn_total else "")
                  + f", total esperado {esperado:.6f} W"),
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
    elif alcances & {"sistema_acoplado", "raiz_escalar_acotada"}:
        # Con cinetica la topologia SIGUE siendo una marcha aguas abajo
        # --la entrada de cada volumen es la salida del anterior, ya
        # determinada-- y lo implicito esta DENTRO de cada volumen. Son
        # dos cosas distintas y la declaracion las separa: decir "sistema
        # acoplado" a secas sugeriria que todo el montaje se resuelve a la
        # vez, y no es asi.
        alcance = ("sistema_acoplado" if "sistema_acoplado" in alcances
                   else "raiz_escalar_acotada")
        metodo = (
            "marcha aguas abajo entre volumenes, y DENTRO de cada volumen "
            "cinetico un sistema implicito: "
            + " y ".join(sorted(
                {"raiz_escalar_acotada": "brentq sobre el avance, acotado por la "
                                         "estequiometria",
                 "sistema_acoplado": "root/hybr sobre los avances (y la temperatura "
                                     "cuando no esta impuesta)",
                 "algebraico_directo": "evaluacion directa donde no hay cinetica",
                 "inversion_escalar": "inversion escalar h(T) con brentq",
                 }[a] for a in alcances))
        )
    else:
        alcance = "mixto"
        metodo = ("marcha aguas abajo: evaluacion directa donde la temperatura esta "
                  "impuesta, e inversion escalar h(T) con brentq donde lo esta el "
                  "calor")

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
        # Lo que cada sistema implicito hizo de verdad, por volumen. No
        # se agrega en un solo numero: dos volumenes pueden resolverse con
        # algoritmos distintos, y promediar sus residuos no significaria
        # nada.
        "sistemas_implicitos": [
            {"bloque_id": bid, **res.como_diccionario()}
            for bid, res in implicitos
        ],
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
    nombres_x = nombres_composicion(m.n)
    for bid, estado_bloque in m.estados.items():
        F = estado_bloque["F"].valor
        fracciones = [estado_bloque[nx].valor for nx in nombres_x]
        # Los caudales por especie. El contrato los pide y son DERIVADOS:
        # F_i = F x_i. No son variables del sistema -- declararlos como
        # tales anadiria n incognitas y n ecuaciones que se cancelan y
        # ensuciaria el recuento -- pero si son lo que hace falta para
        # comprobar la conservacion de elementos y de masa.
        por_especie = [
            {
                "componente": m.componentes[i],
                "x": fracciones[i],
                "F_i": (None if F is None or fracciones[i] is None
                        else float(F * fracciones[i])),
                "unidad_F_i": "mol/s",
            }
            for i in range(m.n)
        ]
        estados[bid] = {
            "fase": estado_bloque.get("fase"),
            "beta": estado_bloque.get("beta"),
            "F": F,
            "T": estado_bloque["T"].valor,
            "p": estado_bloque["p"].valor,
            "h": estado_bloque["h"].valor,
            # 'x' se conserva en los binarios por compatibilidad: es la
            # fraccion del primer componente, igual que antes.
            "x": fracciones[0] if m.n == 2 else None,
            "composicion": fracciones,
            "por_especie": por_especie,
            "nota_F_i": "F_i = F x_i, derivado. No es una variable del sistema: "
                        "declararlo como tal anadiria n incognitas y n ecuaciones "
                        "que se cancelan.",
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "estado": estado,
        "componentes": list(m.componentes),
        "reacciones": [r.como_diccionario(m.componentes) for r in m.reacciones],
        "fuentes_por_volumen": getattr(m, "_fuentes_por_volumen", {}),
        "conservacion": getattr(m, "_conservacion", {}),
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
        "referencias_entalpia": {
            nombre: dict(datos) for nombre, datos in REFERENCIAS.items()
        },
        "aviso_referencia": (
            "`incluye_formacion` decide si el balance de energia lleva el termino de "
            "calor de reaccion. Con una referencia SENSIBLE las entalpias de "
            "formacion no estan en h, asi que el termino va explicito; con una que "
            "las incluyera, ya estaria dentro y sumarlo lo contaria dos veces. La "
            "respuesta dice en `terminos_descartados` cual de los dos casos aplico."
        ),
        "componentes": "los que el proveedor UNIFAC admita. Consultalos en "
                       "/laboratorio/sustancias/buscar, que ademas dice si la "
                       "sustancia sirve para REACCION (hace falta entalpia de "
                       "formacion, y hay especies que tienen grupos UNIFAC y no la "
                       "tienen) y avisa cuando la consulta era una FORMULA, que no "
                       "identifica una sustancia",
        "numero_de_componentes": {
            "minimo": 2, "maximo": MAX_COMPONENTES,
            "nota": "El orden importa: 'x0' es la fraccion del primero. 'x' a secas "
                    "se admite como alias de 'x0' SOLO en binarios, porque con tres "
                    "especies no identifica ninguna.",
        },
        "piezas": dict(PIEZAS),
        "variables_por_pieza": {
            tipo: {
                "binario": list(variables_de_pieza(tipo, 2)),
                "n_componentes": list(variables_de_pieza(tipo, 3)) + ["... x{n-1}"]
                if tipo == "entrada" else list(variables_de_pieza(tipo, 3)),
            }
            for tipo in PIEZAS
        },
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
            "una alimentacion, uno o dos volumenes en serie, una salida",
            "una corriente intermedia entre dos volumenes, con estado unico compartido",
            "una fuente de calor por volumen",
            "volumenes de tipo 'recipiente' (sin reaccion) o 'reactor' (con una o "
            "varias reacciones de tasa especificada)",
        ],
        "reaccion": {
            "donde": "En un bloque de tipo 'reactor'. La produccion y la "
                     "desaparicion quimica pertenecen al volumen donde ocurren: no "
                     "son alimentaciones ficticias.",
            "convencion_nu": "positivo producto, negativo reactivo. Un mismo evento "
                             "produce unos componentes y consume otros, y por eso el "
                             "signo va en el coeficiente y no en la tasa.",
            "formas_de_declarar_la_tasa": {
                "tasa": "DADA, irreversible. Las brutas se conocen.",
                "tasa_directa + tasa_inversa": "DADA, reversible. Las brutas se "
                                               "conocen. Las dos son >= 0.",
                "tasa_neta": "DADA, solo el neto. Las brutas NO se conocen y se "
                             "devuelven como null.",
                "ley_directa (+ ley_inversa)": "CALCULADA por una ley de accion de "
                                               "masas. Las brutas se conocen: cada "
                                               "ley da la velocidad de su sentido "
                                               "por definicion.",
            },
            "cinetica": {
                "ley": "r = k(T) prod_i a_i^(orden_i)",
                "ordenes": "EXPLICITOS. Un orden no es un coeficiente "
                           "estequiometrico: la ley sale de un mecanismo y la "
                           "estequiometria de un balance, y coinciden solo en una "
                           "reaccion elemental. Sin declararlos se usa |nu| de los "
                           "reactivos y la respuesta lo dice. Los negativos se "
                           "rechazan: modelan inhibicion y hacen que la tasa "
                           "diverja cuando la especie se agota.",
                "arrhenius": {
                    "referenciada": "k = k_ref exp(-Ea/R (1/T - 1/T_ref)). "
                                    "Preferible: k_ref esta a escala humana y el "
                                    "exponente ronda cero cerca de T_ref.",
                    "clasica": "k = A exp(-Ea/(R T)). Se admite porque los datos de "
                               "la literatura vienen asi, pero A tiene magnitudes "
                               "absurdas y la expresion resta numeros enormes.",
                },
                "bases_de_actividad": dict(cin.BASES_ACTIVIDAD),
                "base_concentracion": "NO admitida: necesitaria el volumen molar de "
                                      "la mezcla, que es otra decision de modelo.",
                "unidades_de_k": "Las actividades son adimensionales en las dos "
                                 "bases, asi que k lleva las unidades de la tasa y "
                                 "no dependen del orden global. Su unidad declara "
                                 "la base (integrada o volumetrica), igual que en "
                                 "una tasa dada.",
                "inversa_desde_equilibrio": "k_inv = k_dir / K_eq(T). Es la "
                                            "restriccion que impone la "
                                            "termodinamica, y el unico modo en que "
                                            "una reversible es consistente sin dos "
                                            "juegos de datos cineticos. Usa van't "
                                            "Hoff, que supone dH_rxn constante con "
                                            "T: es una aproximacion y se declara.",
                "lo_que_cambia": "Con una ley, la tasa depende de la composicion de "
                                 "SALIDA, que es lo que el balance calcula: el "
                                 "sistema del volumen se vuelve IMPLICITO. La "
                                 "marcha aguas abajo entre volumenes sigue valiendo; "
                                 "lo implicito esta dentro de cada volumen.",
                "no_soportado": [
                    "mezclar en un mismo volumen reacciones de tasa dada con "
                    "reacciones cineticas",
                    "ordenes negativos (inhibicion)",
                    "equilibrio quimico calculado: el motor no obtiene el avance a "
                    "partir de K",
                    "regimen transitorio o lote",
                ],
            },
            "bases": {
                "integrada": sorted(UNIDADES_TASA_INTEGRADA),
                "volumetrica": sorted(UNIDADES_TASA_VOLUMETRICA),
                "nota": "La UNIDAD declara la base, que es lo menos ambiguo posible. "
                        "Una tasa volumetrica necesita el volumen del reactor ('V' "
                        "como especificacion); si no se da, no se supone 1 m3: se "
                        "diagnostica.",
            },
            "brutas_frente_a_neto": (
                "La fuente neta NO determina la generacion y el consumo brutos. En "
                "el equilibrio de una reaccion reversible r+ = r- > 0: el neto es "
                "cero y las brutas son POSITIVAS. Si solo se da la tasa neta, "
                "`generacion_bruta` y `consumo_bruto` salen null con su motivo, y "
                "nunca se rellenan con max(neto, 0) -- eso daria cero generacion en "
                "una reaccion que esta funcionando a toda velocidad. La "
                "`descomposicion_neta` SI se ofrece, en un campo aparte y etiquetada "
                "como lo que es: la descomposicion del neto, no el intercambio bruto."
            ),
            "derivadas_no_libres": (
                "G_i y C_i se DERIVAN de la estequiometria y de las tasas. No son "
                "dos incognitas mas por especie: con n especies serian 2n variables "
                "nuevas y el problema quedaria indeterminado."
            ),
            "conservacion": (
                "La estequiometria se valida contra la matriz elemental de 'thermo' "
                "(A @ nu = 0) y contra la masa (MW @ nu = 0) ANTES de resolver, y "
                "elementos y masa se MIDEN sobre los caudales resueltos despues. El "
                "caudal molar total SI puede cambiar: sum(nu) no tiene por que ser "
                "cero. La masa no cambia nunca."
            ),
        },
        "especificacion_termica": {
            "modos": [
                "temperatura de salida impuesta (Q incognita)",
                "calor impuesto (T incognita)",
                "adiabatico: el supuesto ES la especificacion, dice Q = 0, y la "
                "temperatura es la incognita",
            ],
            "excluyentes": True,
            "motivo": "El balance de energia del volumen es una ecuacion con esas dos "
                      "incognitas: fijar una determina la otra. El supuesto "
                      "adiabatico cuenta como fijar Q, asi que marcarlo Y ademas "
                      "imponer la temperatura sobra.",
            "con_cinetica": "Cuando la temperatura es incognita Y hay cinetica, las "
                            "dos cosas se cierran A LA VEZ: k(T) decide el avance y "
                            "el avance decide el calor que decide T. Resolver una y "
                            "luego la otra daria la respuesta de otro problema.",
        },
        "supuestos_exigidos": {
            "estacionario": True, "sinTrabajo": True, "sinMovimiento": True,
            "adiabatico": "libre, pero incompatible con una fuente de calor conectada",
            "sinReaccion": "libre. En true anula a la vez la produccion, el consumo "
                           "y los cierres cineticos, y es incompatible con una "
                           "reaccion declarada. En false exige que cada reactor "
                           "declare su reaccion: la ausencia de una reaccion "
                           "declarada no significa que no haya reaccion, significa "
                           "que al balance por especie le falta un termino.",
        },
        "fases": ["liquido", "bifasico", "vapor"],
        "nota_fases": "La fase se determina con el punto de burbuja y el de rocio; no "
                      "se supone liquida.",
        "no_soportado": [
            "regimen transitorio y lote (dE/dt, dn_i/dt, integracion en el tiempo)",
            "equilibrio quimico calculado: el motor no obtiene el avance a partir "
            "de K. OJO: imponer r+ = r- NO demuestra equilibrio termodinamico, solo "
            "describe un estado estacionario con esas dos tasas",
            "trabajo de eje",
            "energias cinetica y potencial",
            "mas de una alimentacion o mas de una salida por volumen",
            f"mas de dos volumenes, o mas de {MAX_COMPONENTES} componentes",
            "reciclos y ciclos",
            "caida de presion entre volumenes (la presion es uniforme)",
            "entropia, exergia y potenciales quimicos",
            "conduccion en solidos, difusion y balances de momento",
            "mallado, CFD y dinamica espacial",
        ],
        "tolerancias": {
            "inversion_h_T": TOLERANCIA_INVERSION,
            "cierre_global": TOLERANCIA_CIERRE,
            "conservacion_elementos_y_masa": TOLERANCIA_CONSERVACION,
            "sistema_cinetico_implicito": cin.TOLERANCIA_IMPLICITA,
            "nota": "La del cierre global es mas holgada porque es una suma de "
                    "resultados y acumula el redondeo de los dos balances. "
                    "Excederla no significa datos malos: significa un fallo del "
                    "motor, y sale como error con estado 'no_convergente'.",
        },
        "metodos": {
            "temperatura impuesta": "evaluacion algebraica directa, sin iteracion",
            "calor impuesto o adiabatico": "inversion escalar de h(T) con brentq, "
                                           "xtol 1e-10 K",
            "cinetica isoterma, una reaccion": "brentq sobre el avance, ACOTADO por "
                                               "el intervalo estequiometrico. El "
                                               "cambio de signo esta garantizado",
            "cinetica isoterma, varias reacciones": "scipy.optimize.root con hybr "
                                                    "sobre el vector de avances. Sin "
                                                    "intervalo que acote un sistema, "
                                                    "la factibilidad se comprueba "
                                                    "despues",
            "cinetica con T incognita": "arranque por sustituciones sucesivas (dos "
                                        "problemas escalares acotados, alternados) y "
                                        "despues scipy.optimize.least_squares con "
                                        "trf y limites. El arranque hace falta "
                                        "porque least_squares minimiza el cuadrado "
                                        "del residuo y puede pararse en un minimo "
                                        "local que no es raiz",
            "materia": "propagacion algebraica de los caudales por especie; con "
                       "reaccion se suma nu_i xi, que es un dato y no una incognita",
            "topologia": "marcha aguas abajo; el sistema es triangular -- tambien "
                         "con reaccion, porque la tasa esta especificada y no "
                         "depende de la salida -- y no se resuelve como sistema "
                         "acoplado",
        },
    }
