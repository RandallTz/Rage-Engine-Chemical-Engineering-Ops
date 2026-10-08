"""
Tipos de error del simulador, para poder CLASIFICAR sin leer el mensaje.

Por que hace falta. Hasta aqui todo lo que iba mal se lanzaba como
`ValueError` o `RuntimeError`, y la unica forma de saber de que tipo de
problema se trataba era leer el texto del mensaje. Eso funciona para una
persona y no funciona para nada mas: un cliente que quiera distinguir
"faltan datos" de "esto es fisicamente imposible" tendria que buscar
subcadenas en castellano, y esa clasificacion se rompe la primera vez que
alguien mejora la redaccion de un mensaje.

Las cuatro categorias son distintas en lo unico que importa, que es QUE
HACER:

  ErrorDeDatos      -> cambia lo que diste. El modelo no tiene nada que
                       decir todavia: los datos se contradicen, faltan, o
                       estan fuera de rango antes de calcular nada.
  ErrorFisico       -> el estado existe como numero pero NO como
                       situacion fisica, o cae fuera del rango donde el
                       modelo vale. No se arregla iterando mas: hay que
                       cambiar las condiciones de operacion o el modelo.
  ErrorNumerico     -> el problema esta bien planteado y el algoritmo no
                       llego. Se arregla con otro arranque, otra
                       tolerancia, o mas iteraciones.
  ErrorDeModelo     -> lo que se pide esta fuera de lo que este simulador
                       implementa (una columna de atajo no tiene perfil
                       de presion, UNIFAC no tiene grupos para ese
                       componente). No es un fallo: es un limite.

TODAS heredan de ValueError o RuntimeError segun lo que ya se lanzaba, a
proposito: el codigo y las suites que hacen `except ValueError` siguen
funcionando sin cambiar una linea. Esto solo ANADE informacion.

Y lo que no esta clasificado se queda sin clasificar. Un `ValueError`
pelado no se adivina mirando su texto -- se reporta como no categorizado,
porque "no lo se" es una respuesta y "lo deduje de una subcadena" es una
invencion.
"""


class ErrorSimulador(Exception):
    """
    Raiz de los errores con categoria.

    `codigo` es un identificador ESTABLE, en mayusculas y sin acentos,
    pensado para que un cliente ramifique sobre el. El mensaje es para
    leer; el codigo es para programar. Si alguna vez hay que cambiar un
    mensaje, el codigo no se toca.
    """

    categoria = "desconocido"
    codigo = "ERROR"

    def __init__(self, mensaje, codigo=None, variables=None, equipo=None):
        super().__init__(mensaje)
        if codigo is not None:
            self.codigo = codigo
        # Las variables del pool implicadas, cuando se saben. Es lo que
        # permite a un cliente senalar el campo concreto en vez de mostrar
        # un mensaje suelto.
        self.variables = tuple(variables or ())
        self.equipo = equipo

    def como_diccionario(self):
        return {
            "categoria": self.categoria,
            "codigo": self.codigo,
            "mensaje": str(self),
            "variables": list(self.variables),
            "equipo": self.equipo,
        }


class ErrorDeDatos(ErrorSimulador, ValueError):
    """Los datos se contradicen, faltan o estan fuera de rango."""

    categoria = "datos"
    codigo = "DATOS"


class ErrorFisico(ErrorSimulador, ValueError):
    """
    El numero existe; la situacion fisica, no.

    Es la categoria mas valiosa del simulador y la razon de ser de medio
    proyecto: un balance se cumple igual de contento con un equipo
    imposible de construir. Ejemplos reales: un tanque de reaccion
    hirviendo cuando el modelo lo supone liquido, un cruce de
    temperaturas en un intercambiador, un reflujo por debajo del minimo,
    una composicion fuera del simplex, una presion de salida negativa.
    """

    categoria = "fisica"
    codigo = "FISICA"


class ErrorNumerico(ErrorSimulador, RuntimeError):
    """El planteamiento es correcto y el algoritmo no llego."""

    categoria = "numerica"
    codigo = "NUMERICA"


class ErrorDeModelo(ErrorSimulador, ValueError):
    """
    Lo pedido esta fuera de lo que este simulador implementa.

    No es un fallo, es un LIMITE, y distinguirlo importa: a un error de
    datos se le busca el dato, a un error de modelo se le busca otra
    herramienta (o se implementa lo que falta). Confundirlos hace perder
    el tiempo buscando en el sitio equivocado.
    """

    categoria = "modelo"
    codigo = "MODELO"


# ---------------------------------------------------------------------
# Codigos estables de los casos que el simulador ya vigilaba.
#
# Estan aqui, juntos, y no repartidos por el codigo, para que se vea de un
# golpe que hay y para que anadir uno obligue a mirar si ya existe algo
# parecido. El valor es la cadena que viaja al cliente.
# ---------------------------------------------------------------------

# Fisica
TANQUE_HIRVIENDO = "FISICA_TANQUE_HIRVIENDO"
CRUCE_TEMPERATURAS = "FISICA_CRUCE_TEMPERATURAS"
REFLUJO_BAJO_MINIMO = "FISICA_REFLUJO_BAJO_MINIMO"
FUERA_DEL_SIMPLEX = "FISICA_FUERA_DEL_SIMPLEX"
PRESION_NO_FISICA = "FISICA_PRESION_NO_FISICA"
CAUDAL_NO_FISICO = "FISICA_CAUDAL_NO_FISICO"
LIMITE_ESTEQUIOMETRICO = "FISICA_LIMITE_ESTEQUIOMETRICO"
FUERA_DE_RANGO_CORRELACION = "FISICA_FUERA_DE_RANGO_CORRELACION"

# Numerica
SIN_CONVERGENCIA = "NUMERICA_SIN_CONVERGENCIA"
RECICLO_SIN_CONVERGENCIA = "NUMERICA_RECICLO_SIN_CONVERGENCIA"
SIN_CAMBIO_DE_SIGNO = "NUMERICA_SIN_CAMBIO_DE_SIGNO"
INTEGRACION_FALLIDA = "NUMERICA_INTEGRACION_FALLIDA"

# Datos
DATOS_INCOMPATIBLES = "DATOS_INCOMPATIBLES"
SOBRE_ESPECIFICADO = "DATOS_SOBRE_ESPECIFICADO"
FALTA_ESPECIFICACION = "DATOS_FALTA_ESPECIFICACION"
REDUNDANCIA = "DATOS_REDUNDANCIA"
RANGO_INVALIDO = "DATOS_RANGO_INVALIDO"

# Modelo
SIN_GRUPOS_UNIFAC = "MODELO_SIN_GRUPOS_UNIFAC"
NO_IMPLEMENTADO = "MODELO_NO_IMPLEMENTADO"
FUERA_DEL_ALCANCE = "MODELO_FUERA_DEL_ALCANCE"

# ---------------------------------------------------------------------
# Laboratorio: el ensamblador de sistemas por bloques.
#
# Llevan prefijo LAB_ porque identifican fallos del MONTAJE, no de la
# fisica ni del algoritmo: el cliente dibuja un grafo y hay muchas formas
# de dibujarlo mal. El codigo tiene que distinguirlas para que la interfaz
# pueda senalar la pieza o la conexion concreta, que es justo lo que un
# mensaje suelto no permite hacer.
#
# La categoria de cada uno la fija quien lo emite (ver core/laboratorio.py):
# la mayoria son 'datos', los de topologia imposible son 'modelo'.
# ---------------------------------------------------------------------

# Estructura del grafo
LAB_ID_DUPLICADO = "LAB_ID_DUPLICADO"
LAB_REFERENCIA_INEXISTENTE = "LAB_REFERENCIA_INEXISTENTE"
LAB_PUERTO_INCOMPATIBLE = "LAB_PUERTO_INCOMPATIBLE"
LAB_PIEZA_AISLADA = "LAB_PIEZA_AISLADA"
LAB_CICLO = "LAB_CICLO"
LAB_TOPOLOGIA_NO_SOPORTADA = "LAB_TOPOLOGIA_NO_SOPORTADA"
LAB_CORRIENTE_MAL_CONECTADA = "LAB_CORRIENTE_MAL_CONECTADA"
LAB_VOLUMEN_SIN_SALIDA = "LAB_VOLUMEN_SIN_SALIDA"
LAB_VOLUMEN_SIN_ENTRADA = "LAB_VOLUMEN_SIN_ENTRADA"

# Especificaciones
LAB_ESPECIFICACION_DUPLICADA = "LAB_ESPECIFICACION_DUPLICADA"
LAB_ESPECIFICACION_EXCLUYENTE = "LAB_ESPECIFICACION_EXCLUYENTE"
LAB_FALTA_ESPECIFICACION = "LAB_FALTA_ESPECIFICACION"
LAB_VARIABLE_DESCONOCIDA = "LAB_VARIABLE_DESCONOCIDA"
LAB_UNIDAD_INCOMPATIBLE = "LAB_UNIDAD_INCOMPATIBLE"

# Valores
LAB_VALOR_NO_FINITO = "LAB_VALOR_NO_FINITO"
LAB_FRACCION_INVALIDA = "LAB_FRACCION_INVALIDA"
LAB_DATOS_COMPOSICION_INCOMPATIBLE = "LAB_DATOS_COMPOSICION_INCOMPATIBLE"
LAB_VALOR_FUERA_DE_DOMINIO = "LAB_VALOR_FUERA_DE_DOMINIO"

# Supuestos y coherencia del montaje
LAB_SUPUESTO_INCOHERENTE = "LAB_SUPUESTO_INCOHERENTE"
LAB_SUPUESTO_NO_SOPORTADO = "LAB_SUPUESTO_NO_SOPORTADO"

# Reaccion y estequiometria
#
# Separados de los de estructura porque fallan por otro motivo: una
# estequiometria que no conserva los elementos no es un error de montaje
# ni de unidades, es un dato que no describe ninguna reaccion quimica.
LAB_REACCION_EN_NO_REACTOR = "LAB_REACCION_EN_NO_REACTOR"
LAB_ESTEQUIOMETRIA_INVALIDA = "LAB_ESTEQUIOMETRIA_INVALIDA"
LAB_ELEMENTOS_NO_CONSERVADOS = "LAB_ELEMENTOS_NO_CONSERVADOS"
LAB_MASA_NO_CONSERVADA = "LAB_MASA_NO_CONSERVADA"
LAB_TASA_AMBIGUA = "LAB_TASA_AMBIGUA"
LAB_TASA_NEGATIVA = "LAB_TASA_NEGATIVA"
LAB_FALTA_VOLUMEN_REACTOR = "LAB_FALTA_VOLUMEN_REACTOR"
LAB_CAUDAL_ESPECIE_NEGATIVO = "LAB_CAUDAL_ESPECIE_NEGATIVO"
LAB_CINETICA_NO_SOPORTADA = "LAB_CINETICA_NO_SOPORTADA"
LAB_SIN_REACCION_DECLARADA = "LAB_SIN_REACCION_DECLARADA"
LAB_ENTALPIA_FORMACION_NO_DISPONIBLE = "LAB_ENTALPIA_FORMACION_NO_DISPONIBLE"
LAB_CONSERVACION_NO_MEDIDA = "LAB_CONSERVACION_NO_MEDIDA"

# Modelo y componentes
LAB_MODELO_NO_DISPONIBLE = "LAB_MODELO_NO_DISPONIBLE"
LAB_COMPONENTE_NO_DISPONIBLE = "LAB_COMPONENTE_NO_DISPONIBLE"
LAB_NUMERO_DE_COMPONENTES = "LAB_NUMERO_DE_COMPONENTES"

# Resultado
LAB_FUERA_DE_DOMINIO_TERMODINAMICO = "LAB_FUERA_DE_DOMINIO_TERMODINAMICO"
LAB_SIN_CONVERGENCIA = "LAB_SIN_CONVERGENCIA"
LAB_CIERRE_GLOBAL = "LAB_CIERRE_GLOBAL"

# Informativos: no invalidan nada, explican lo que el motor hizo.
LAB_INFO_FASE = "LAB_INFO_FASE"
LAB_INFO_CALOR_REACCION = "LAB_INFO_CALOR_REACCION"
LAB_INFO_CONSERVACION = "LAB_INFO_CONSERVACION"
LAB_INFO_CIERRE_GLOBAL = "LAB_INFO_CIERRE_GLOBAL"

# Lo que no se ha clasificado. No se adivina del texto.
SIN_CLASIFICAR = "SIN_CLASIFICAR"


def clasificar(excepcion, equipo=None):
    """
    Un diccionario de categoria y codigo para cualquier excepcion.

    Si la excepcion lleva categoria, se usa la suya. Si no, se reporta
    como SIN_CLASIFICAR -- y eso es deliberado. La alternativa seria
    buscar palabras en el mensaje ("hirviendo", "no convergio"), que
    acierta hasta que alguien reescribe una frase y entonces falla en
    silencio, que es el peor modo de fallo posible para un diagnostico.

    Lo unico que si se mira sin ser una invencion es el TIPO de Python:
    un RuntimeError que nadie clasifico es, por la convencion de este
    proyecto, un fallo de ejecucion y no un dato mal dado. Se reporta como
    numerica sin codigo especifico, que es una afirmacion mas debil y
    honesta que inventarle uno.
    """
    if isinstance(excepcion, ErrorSimulador):
        datos = excepcion.como_diccionario()
        if equipo and not datos.get("equipo"):
            datos["equipo"] = equipo
        return datos
    categoria = "numerica" if isinstance(excepcion, RuntimeError) else "desconocido"
    return {
        "categoria": categoria,
        "codigo": SIN_CLASIFICAR,
        "mensaje": str(excepcion),
        "variables": [],
        "equipo": equipo,
        # Se conserva el tipo de Python porque es el unico dato objetivo
        # que queda cuando no hay categoria, y ayuda a quien tenga que
        # anadirla despues.
        "tipo_python": type(excepcion).__name__,
    }
