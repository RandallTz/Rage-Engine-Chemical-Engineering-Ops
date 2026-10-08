"""
Montajes de ejemplo del laboratorio.

Para que sirven, y por que estan en el backend y no en la documentacion.
Un ejemplo escrito a mano en un documento se queda obsoleto en silencio:
nadie lo ejecuta, asi que nadie se entera de que dejo de ser valido. Estos
son peticiones REALES de /laboratorio/resolver, se sirven por
/laboratorio/ejemplos, y la suite de validacion los reenvia al endpoint.

Esa es la idea que ya funciono en `tests/validar_api.py`: encadenar en vez
de inventar cargas. Un preset que la interfaz le ofrece al usuario y que
no se puede resolver es un fallo que se encuentra en el primer clic, y
reenviarlo en la suite lo caza antes.

Zona libre de pint: los valores van con su unidad declarada, como exige el
contrato de /laboratorio/*.
"""

ATM = 101325.0
BINARIO = ["benzene", "toluene"]

SUPUESTOS_BASE = {
    "estacionario": True,
    "adiabatico": False,
    "sinTrabajo": True,
    "sinReaccion": True,
    "sinMovimiento": True,
}


def _cabecera():
    """
    La parte comun. Los montajes reactivos sobreescriben `componentes`,
    `presion_sistema` y `supuestos`: su quimica es otra y su presion de
    trabajo tambien.
    """
    return {
        "version": 1,
        "componentes": list(BINARIO),
        "modelo_termodinamico": "unifac_raoult",
        "referencia_entalpia": "sensible_liquido_298.15K",
        "presion_sistema": {"valor": ATM, "unidad": "Pa"},
        "supuestos": dict(SUPUESTOS_BASE),
    }


def un_volumen_temperatura():
    """
    El montaje minimo: alimentacion, un volumen con fuente de calor, salida.

    Temperatura de salida impuesta y Q incognita. Es el caso que el
    adaptador antiguo ya resolvia por /diagrama/resolver, y da el mismo
    numero: sirve de puente entre los dos servicios.
    """
    return {
        **_cabecera(),
        "bloques": [
            {"id": "in", "tipo": "entrada", "nombre": "Alimentacion"},
            {"id": "cv1", "tipo": "recipiente", "nombre": "Volumen de control"},
            {"id": "heat1", "tipo": "calor", "nombre": "Fuente de calor"},
            {"id": "out", "tipo": "salida", "nombre": "Salida"},
        ],
        "conexiones": [
            {"id": "c1", "desde": "in", "hacia": "cv1", "tipo": "materia"},
            {"id": "c2", "desde": "heat1", "hacia": "cv1", "tipo": "calor"},
            {"id": "c3", "desde": "cv1", "hacia": "out", "tipo": "materia"},
        ],
        "especificaciones": [
            {"bloque_id": "in", "variable": "F", "valor": 100.0, "unidad": "mol/s"},
            {"bloque_id": "in", "variable": "T", "valor": 300.0, "unidad": "K"},
            {"bloque_id": "in", "variable": "x", "valor": 0.5, "unidad": "mol/mol"},
            # En un VOLUMEN, 'T' es la temperatura de su corriente de
            # SALIDA. No es la de la alimentacion: confundirlas convierte
            # el calentamiento en una identidad y Q saldria cero.
            {"bloque_id": "cv1", "variable": "T", "valor": 310.0, "unidad": "K"},
        ],
    }


def dos_volumenes_temperatura():
    """
    EL CASO DE ACEPTACION de esta entrega.

    Dos volumenes en serie unidos por una corriente intermedia con
    identidad unica, cada uno con su fuente de calor, y las dos
    temperaturas de salida impuestas.

    Lo que demuestra: que la corriente compartida es UN estado -- las
    cinco variables (F, T, p, x, h) salen con rol 'compartida' y con los
    dos volumenes y las dos conexiones en su procedencia -- y que
    Q1 + Q2 cuadra con F (h_salida - h_entrada), que es la comprobacion
    independiente del resultado.
    """
    return {
        **_cabecera(),
        "bloques": [
            {"id": "in", "tipo": "entrada", "nombre": "Alimentacion"},
            {"id": "cv1", "tipo": "recipiente", "nombre": "Primer volumen"},
            {"id": "heat1", "tipo": "calor", "nombre": "Primer aporte termico"},
            {"id": "medio", "tipo": "corriente", "nombre": "Corriente compartida"},
            {"id": "cv2", "tipo": "recipiente", "nombre": "Segundo volumen"},
            {"id": "heat2", "tipo": "calor", "nombre": "Segundo aporte termico"},
            {"id": "out", "tipo": "salida", "nombre": "Salida final"},
        ],
        "conexiones": [
            {"id": "c1", "desde": "in", "hacia": "cv1", "tipo": "materia"},
            {"id": "c2", "desde": "heat1", "hacia": "cv1", "tipo": "calor"},
            {"id": "c3", "desde": "cv1", "hacia": "medio", "tipo": "materia"},
            {"id": "c4", "desde": "medio", "hacia": "cv2", "tipo": "materia"},
            {"id": "c5", "desde": "heat2", "hacia": "cv2", "tipo": "calor"},
            {"id": "c6", "desde": "cv2", "hacia": "out", "tipo": "materia"},
        ],
        "especificaciones": [
            {"bloque_id": "in", "variable": "F", "valor": 100.0, "unidad": "mol/s"},
            {"bloque_id": "in", "variable": "T", "valor": 300.0, "unidad": "K"},
            {"bloque_id": "in", "variable": "x", "valor": 0.5, "unidad": "mol/mol"},
            {"bloque_id": "cv1", "variable": "T", "valor": 310.0, "unidad": "K"},
            {"bloque_id": "cv2", "variable": "T", "valor": 320.0, "unidad": "K"},
        ],
    }


def dos_volumenes_calor():
    """
    El mismo montaje con el modo termico invertido en el primer volumen.

    Q1 impuesto y la temperatura intermedia incognita. El valor de Q1 es
    exactamente el que el caso anterior calcula, asi que este montaje
    tiene que devolver 310 K: es la comprobacion de que los dos modos son
    el mismo problema leido en las dos direcciones.

    Y cambia el ALGORITMO: aqui hay una inversion escalar de h(T) con
    brentq donde antes habia una evaluacion directa, y `convergencia` lo
    dice.
    """
    modelo = dos_volumenes_temperatura()
    modelo["especificaciones"] = [
        e for e in modelo["especificaciones"]
        if not (e["bloque_id"] == "cv1" and e["variable"] == "T")
    ] + [
        # El Q que el caso de temperatura calcula, en kW para que se vea
        # que la unidad se declara y se respeta.
        {"bloque_id": "heat1", "variable": "Q",
         "valor": 147.84285147392648, "unidad": "kW"},
    ]
    return modelo


def dos_volumenes_bifasico():
    """
    Un caso que SALE DE LA FASE LIQUIDA, para que no se confunda con el
    unico que el simulador sabe hacer.

    Con 2 MW en el primer volumen la corriente intermedia llega a la
    laguna bifasica: sale a unos 367.5 K con beta ~ 0.30. La fase no se
    supone -- se determina con el punto de burbuja y el de rocio -- y el
    resultado lo demuestra: casi toda la energia va a calor latente y la
    temperatura apenas sube.

    El segundo volumen, con 320 K impuestos, tiene entonces que RETIRAR
    calor: su Q sale negativo. Con la convencion de positivo hacia el
    volumen eso es correcto, y el motor lo avisa en vez de dejarlo pasar.
    """
    modelo = dos_volumenes_temperatura()
    modelo["especificaciones"] = [
        e for e in modelo["especificaciones"]
        if not (e["bloque_id"] == "cv1" and e["variable"] == "T")
    ] + [
        {"bloque_id": "heat1", "variable": "Q", "valor": 2.0, "unidad": "MW"},
    ]
    return modelo


def mesa_con_datos_locales():
    """
    El montaje tal como lo exporta HOY la mesa del frontend: sin
    especificaciones, con los valores dentro de cada pieza.

    Se admite por compatibilidad, y da el mismo resultado. La diferencia
    esta en las unidades: en `datos` son IMPLICITAS, y en particular Q se
    lee en **kW** porque es lo que documenta la mesa. En una
    especificacion explicita la unidad es obligatoria, y por eso ese es el
    camino preferente.
    """
    modelo = dos_volumenes_temperatura()
    modelo["especificaciones"] = []
    valores = {
        "in": {"F": 100.0, "T": 300.0, "p": ATM, "x": 0.5},
        "cv1": {"T": 310.0},
        "cv2": {"T": 320.0},
    }
    modelo["bloques"] = [
        {**b, **({"datos": valores[b["id"]]} if b["id"] in valores else {})}
        for b in modelo["bloques"]
    ]
    return modelo


def incompatible_t_y_q():
    """
    Un montaje que el motor RECHAZA, para que la interfaz pueda probar su
    camino de error sin inventarse una respuesta.

    Impone la temperatura de salida del primer volumen Y el calor de su
    fuente. El balance de energia es una ecuacion con esas dos incognitas:
    fijar una determina la otra, y fijar las dos deja la ecuacion sobrante
    y en general violada.
    """
    modelo = dos_volumenes_temperatura()
    modelo["especificaciones"] = modelo["especificaciones"] + [
        {"bloque_id": "heat1", "variable": "Q", "valor": 100.0, "unidad": "kW"},
    ]
    return modelo


# ---------------------------------------------------------------------
# Los montajes con reaccion.
#
# Dos sistemas reales, elegidos porque el proveedor tiene de los dos TODO
# lo que hace falta --grupos UNIFAC, entalpia de formacion liquida y
# composicion elemental-- y porque su estequiometria cuadra exacta:
#
#   n-butano -> isobutano          isomerizacion, sum(nu) = 0, F constante
#   2 isobuteno <-> diisobutileno  dimerizacion,  sum(nu) = -1, F baja
#
# La presion se sube por encima de 1 atm a proposito: estas especies
# hierven muy por debajo de la temperatura de trabajo, y a presion
# atmosferica saldrian en fase vapor. El flash lo detectaria y lo diria
# --la fase se determina, no se supone-- pero el ejemplo se entiende mejor
# en liquido.
# ---------------------------------------------------------------------

def reactor_isomerizacion():
    """
    A -> B: n-butano a isobutano, con la tasa especificada.

    El caso mas simple con reaccion. Lo que demuestra: que el consumo de A
    y la generacion de B son exactamente el avance, que con sum(nu) = 0 el
    caudal molar NO cambia, y que los elementos y la masa se conservan --
    medidos sobre los caudales resueltos, no supuestos.
    """
    return {
        **_cabecera(),
        "componentes": ["n-butane", "isobutane"],
        "presion_sistema": {"valor": 500000.0, "unidad": "Pa"},
        "supuestos": {**SUPUESTOS_BASE, "sinReaccion": False},
        "bloques": [
            {"id": "in", "tipo": "entrada", "nombre": "Alimentacion de n-butano"},
            {"id": "rx", "tipo": "reactor", "nombre": "Reactor de isomerizacion"},
            {"id": "heat", "tipo": "calor", "nombre": "Aporte termico"},
            {"id": "out", "tipo": "salida", "nombre": "Salida"},
        ],
        "conexiones": [
            {"id": "c1", "desde": "in", "hacia": "rx", "tipo": "materia"},
            {"id": "c2", "desde": "heat", "hacia": "rx", "tipo": "calor"},
            {"id": "c3", "desde": "rx", "hacia": "out", "tipo": "materia"},
        ],
        "especificaciones": [
            {"bloque_id": "in", "variable": "F", "valor": 100.0, "unidad": "mol/s"},
            {"bloque_id": "in", "variable": "T", "valor": 300.0, "unidad": "K"},
            {"bloque_id": "in", "variable": "x0", "valor": 1.0, "unidad": "mol/mol"},
            {"bloque_id": "rx", "variable": "T", "valor": 310.0, "unidad": "K"},
        ],
        "reacciones": [
            {"id": "iso", "bloque_id": "rx", "nu": [-1.0, 1.0],
             "tasa": {"valor": 20.0, "unidad": "mol/s"}},
        ],
    }


def reactor_volumetrico():
    """
    La misma isomerizacion con la tasa en BASE VOLUMETRICA.

    4 mol/(m3 s) en 5 m3 son 20 mol/s, asi que el resultado es identico al
    del ejemplo anterior. Esta aqui para que se vea la distincion que el
    contrato pide: la UNIDAD declara la base, y una tasa volumetrica
    necesita el volumen del reactor. Si no se da, no se supone 1 m3.
    """
    modelo = reactor_isomerizacion()
    modelo["reacciones"] = [
        {"id": "iso", "bloque_id": "rx", "nu": [-1.0, 1.0],
         "tasa": {"valor": 4.0, "unidad": "mol/(m3*s)"}},
    ]
    modelo["especificaciones"] = modelo["especificaciones"] + [
        {"bloque_id": "rx", "variable": "V", "valor": 5.0, "unidad": "m3"},
    ]
    return modelo


def reactor_a_dos_b():
    """
    A -> 2B: diisobutileno a isobuteno. El caudal molar CAMBIA.

    Con sum(nu) = +1 y un avance de 10 mol/s, el caudal pasa de 100 a 110.
    Y la masa no se mueve ni un gramo: es la distincion que el contrato
    subraya, porque un caudal molar que cambia parece un balance roto y no
    lo es.
    """
    modelo = reactor_isomerizacion()
    modelo["componentes"] = ["isobutene", "diisobutylene"]
    modelo["presion_sistema"] = {"valor": 1000000.0, "unidad": "Pa"}
    modelo["bloques"] = [
        {**b, "nombre": "Alimentacion de diisobutileno"} if b["id"] == "in"
        else ({**b, "nombre": "Reactor de craqueo"} if b["id"] == "rx" else b)
        for b in modelo["bloques"]
    ]
    modelo["especificaciones"] = [
        {"bloque_id": "in", "variable": "F", "valor": 100.0, "unidad": "mol/s"},
        {"bloque_id": "in", "variable": "T", "valor": 320.0, "unidad": "K"},
        # x0 es el isobuteno: entra a cero, porque la alimentacion es
        # dimero puro. Cero es una fraccion perfectamente valida y
        # significa que esa especie no esta.
        {"bloque_id": "in", "variable": "x0", "valor": 0.0, "unidad": "mol/mol"},
        {"bloque_id": "rx", "variable": "T", "valor": 330.0, "unidad": "K"},
    ]
    modelo["reacciones"] = [
        {"id": "crack", "bloque_id": "rx", "nu": [2.0, -1.0],
         "tasa": {"valor": 10.0, "unidad": "mol/s"}},
    ]
    return modelo


def reactor_reversible():
    """
    Reversible con la direccion INVERSA dominante.

    r+ = 2 y r- = 8, asi que el avance neto es -6: el dimero se craquea
    neto. Lo que demuestra: que la direccion inversa intercambia
    produccion y consumo correctamente. El isobuteno se genera a 16 mol/s
    (2 x r-) y se consume a 4 (2 x r+); el dimero se genera a 2 y se
    consume a 8.
    """
    modelo = reactor_a_dos_b()
    modelo["especificaciones"] = [
        e if e["variable"] != "x0" else {**e, "valor": 0.5}
        for e in modelo["especificaciones"]
    ]
    modelo["reacciones"] = [
        {"id": "dim", "bloque_id": "rx", "nu": [-2.0, 1.0],
         "tasa_directa": {"valor": 2.0, "unidad": "mol/s"},
         "tasa_inversa": {"valor": 8.0, "unidad": "mol/s"}},
    ]
    return modelo


def reactor_en_equilibrio():
    """
    EL CASO QUE EL CONTRATO EXIGE: r+ = r- > 0.

    La fuente neta de cada especie es CERO y la generacion y el consumo
    brutos son POSITIVOS. Las moleculas no estan quietas: estan yendo y
    viniendo a la misma velocidad.

    Es el ejemplo que desmonta la tentacion de derivar las brutas del
    neto. Un neto de cero es compatible con una reaccion PARADA
    (r+ = r- = 0) y con este equilibrio DINAMICO, y nada en la tasa neta
    distingue los dos casos. Comparalo con `reactor_solo_neta`.
    """
    modelo = reactor_reversible()
    modelo["reacciones"] = [
        {"id": "dim", "bloque_id": "rx", "nu": [-2.0, 1.0],
         "tasa_directa": {"valor": 5.0, "unidad": "mol/s"},
         "tasa_inversa": {"valor": 5.0, "unidad": "mol/s"}},
    ]
    return modelo


def reactor_solo_neta():
    """
    La misma situacion declarada SOLO con la tasa neta.

    El avance neto es cero, igual que en el equilibrio, y la composicion
    de salida es identica. Pero `generacion_bruta` y `consumo_bruto` salen
    **null**, con su motivo, porque con este dato no se pueden saber.

    Esta aqui para que la interfaz pueda probar ese camino: null no es
    cero, y mostrar un cero donde el motor dice "no lo se" seria afirmar
    que la reaccion esta parada cuando puede estar a toda velocidad.
    """
    modelo = reactor_en_equilibrio()
    modelo["reacciones"] = [
        {"id": "dim", "bloque_id": "rx", "nu": [-2.0, 1.0],
         "tasa_neta": {"valor": 0.0, "unidad": "mol/s"}},
    ]
    return modelo


def dos_reactores_en_serie():
    """
    Dos reactores que comparten una corriente intermedia, con reaccion.

    Es el caso 4 de la aceptacion: el estado intermedio NO se duplica. Las
    seis variables de la corriente (F, T, p, x0, x1 y h) salen con rol
    'compartida' y citan los dos reactores.

    Y el cierre global de energia incluye el calor de reaccion de TODO el
    montaje: al sumar los balances por volumen los estados intermedios se
    cancelan --son la MISMA variable-- pero los terminos de reaccion se
    acumulan.
    """
    return {
        **_cabecera(),
        "componentes": ["isobutene", "diisobutylene"],
        "presion_sistema": {"valor": 1000000.0, "unidad": "Pa"},
        "supuestos": {**SUPUESTOS_BASE, "sinReaccion": False},
        "bloques": [
            {"id": "in", "tipo": "entrada", "nombre": "Alimentacion"},
            {"id": "rx1", "tipo": "reactor", "nombre": "Primer reactor"},
            {"id": "h1", "tipo": "calor", "nombre": "Primer aporte termico"},
            {"id": "medio", "tipo": "corriente", "nombre": "Corriente compartida"},
            {"id": "rx2", "tipo": "reactor", "nombre": "Segundo reactor"},
            {"id": "h2", "tipo": "calor", "nombre": "Segundo aporte termico"},
            {"id": "out", "tipo": "salida", "nombre": "Salida final"},
        ],
        "conexiones": [
            {"id": "c1", "desde": "in", "hacia": "rx1", "tipo": "materia"},
            {"id": "c2", "desde": "h1", "hacia": "rx1", "tipo": "calor"},
            {"id": "c3", "desde": "rx1", "hacia": "medio", "tipo": "materia"},
            {"id": "c4", "desde": "medio", "hacia": "rx2", "tipo": "materia"},
            {"id": "c5", "desde": "h2", "hacia": "rx2", "tipo": "calor"},
            {"id": "c6", "desde": "rx2", "hacia": "out", "tipo": "materia"},
        ],
        "especificaciones": [
            {"bloque_id": "in", "variable": "F", "valor": 100.0, "unidad": "mol/s"},
            {"bloque_id": "in", "variable": "T", "valor": 320.0, "unidad": "K"},
            {"bloque_id": "in", "variable": "x0", "valor": 1.0, "unidad": "mol/mol"},
            {"bloque_id": "rx1", "variable": "T", "valor": 330.0, "unidad": "K"},
            {"bloque_id": "rx2", "variable": "T", "valor": 340.0, "unidad": "K"},
        ],
        "reacciones": [
            {"id": "dim1", "bloque_id": "rx1", "nu": [-2.0, 1.0],
             "tasa": {"valor": 10.0, "unidad": "mol/s"}},
            {"id": "dim2", "bloque_id": "rx2", "nu": [-2.0, 1.0],
             "tasa": {"valor": 15.0, "unidad": "mol/s"}},
        ],
    }


def estequiometria_invalida():
    """
    Una estequiometria que NO conserva los elementos, para probar el
    camino de error contra un error de verdad.

    nu = [-1, +2] con n-butano e isobutano: salen 8 carbonos de donde
    entraron 4. Eso no es una reaccion quimica, es un dato mal puesto, y
    el motor lo dice con el descuadre de cada elemento.
    """
    modelo = reactor_isomerizacion()
    modelo["reacciones"] = [
        {"id": "mala", "bloque_id": "rx", "nu": [-1.0, 2.0],
         "tasa": {"valor": 1.0, "unidad": "mol/s"}},
    ]
    return modelo


# ---------------------------------------------------------------------
# Los montajes CINETICOS: la tasa se calcula, no se da.
#
# Sistema: isomerizacion n-butano -> isobutano, que es una reaccion real,
# tiene balance elemental exacto y propiedades completas. A **20 bar**, no
# a una atmosfera, y eso no es un capricho: a 5 bar la mezcla cruza la
# frontera de fase al reaccionar --la presion de burbuja pasa de 456 a 545
# kPa-- y la entalpia da un salto de 18 kJ/mol. El motor lo resuelve
# igual y lo reporta, pero un ejemplo que se entienda conviene que se
# quede en liquido. La isomerizacion de butano se opera bajo presion por
# ese mismo motivo.
# ---------------------------------------------------------------------

BUTANOS = ["n-butane", "isobutane"]
P_BUTANOS = 2000000.0

LEY_ISOMERIZACION = {
    "k_ref": {"valor": 50.0, "unidad": "mol/s"},
    "T_ref": {"valor": 320.0, "unidad": "K"},
    "Ea": 50000.0,
    "base_actividad": "actividad",
    # Explicitos a proposito. Un orden NO es un coeficiente
    # estequiometrico, y dejarlo al defecto habria sido elegir un
    # mecanismo sin decirlo.
    "ordenes": {"n-butane": 1.0},
}


def _reactor_cinetico(nombre_reactor="Reactor de isomerizacion", con_fuente=True,
                      adiabatico=False):
    bloques = [
        {"id": "in", "tipo": "entrada", "nombre": "Alimentacion de n-butano"},
        {"id": "rx", "tipo": "reactor", "nombre": nombre_reactor},
        {"id": "out", "tipo": "salida", "nombre": "Salida"},
    ]
    conexiones = [
        {"id": "c1", "desde": "in", "hacia": "rx", "tipo": "materia"},
        {"id": "c3", "desde": "rx", "hacia": "out", "tipo": "materia"},
    ]
    if con_fuente:
        bloques.insert(2, {"id": "heat", "tipo": "calor",
                           "nombre": "Aporte termico"})
        conexiones.insert(1, {"id": "c2", "desde": "heat", "hacia": "rx",
                              "tipo": "calor"})
    return {
        **_cabecera(),
        "componentes": list(BUTANOS),
        "presion_sistema": {"valor": P_BUTANOS, "unidad": "Pa"},
        "supuestos": {**SUPUESTOS_BASE, "sinReaccion": False,
                      "adiabatico": adiabatico},
        "bloques": bloques,
        "conexiones": conexiones,
        "especificaciones": [
            {"bloque_id": "in", "variable": "F", "valor": 100.0, "unidad": "mol/s"},
            {"bloque_id": "in", "variable": "T", "valor": 320.0, "unidad": "K"},
            {"bloque_id": "in", "variable": "x0", "valor": 1.0, "unidad": "mol/mol"},
        ],
        "reacciones": [],
    }


def cinetica_isoterma():
    """
    Una ley de velocidad con la temperatura impuesta.

    Lo que demuestra: que la tasa se CALCULA. El balance del volumen pasa
    a ser implicito --la tasa depende de la composicion de salida, que es
    lo que el balance calcula-- y el motor lo resuelve con brentq sobre el
    avance, ACOTADO por la estequiometria. El cambio de signo esta
    garantizado: en avance cero el residuo vale -r y en el limite el
    reactivo se agota, la tasa cae y el residuo vale el avance.
    """
    modelo = _reactor_cinetico()
    modelo["especificaciones"] = modelo["especificaciones"] + [
        {"bloque_id": "rx", "variable": "T", "valor": 330.0, "unidad": "K"},
    ]
    modelo["reacciones"] = [
        {"id": "iso", "bloque_id": "rx", "nu": [-1.0, 1.0],
         "ley_directa": dict(LEY_ISOMERIZACION)},
    ]
    return modelo


def cinetica_adiabatica():
    """
    EL CASO DE ENERGIA ACOPLADA: adiabatico, con la temperatura incognita.

    Aqui la temperatura no es un dato: es una consecuencia de la quimica.
    k(T) decide el avance y el avance decide el calor que decide T, asi
    que las dos cosas se cierran A LA VEZ. Resolver una y luego la otra
    daria la respuesta de otro problema.

    El supuesto adiabatico SI es una especificacion termica --dice Q = 0--
    y por eso este montaje no lleva fuente de calor y aun asi esta
    completo.

    El resultado se puede comprobar sin el motor: la reaccion libera
    xi (-dH) = 818 710 W y el calentamiento sensible de 320 a 369.5 K vale
    lo mismo.
    """
    modelo = _reactor_cinetico(nombre_reactor="Reactor adiabatico",
                               con_fuente=False, adiabatico=True)
    modelo["reacciones"] = [
        {"id": "iso", "bloque_id": "rx", "nu": [-1.0, 1.0],
         "ley_directa": dict(LEY_ISOMERIZACION)},
    ]
    return modelo


def cinetica_reversible():
    """
    Reversible con DOS leyes, una por sentido.

    Asi las tasas brutas se conocen por construccion, que es lo que el
    contrato exige: cada ley da la velocidad de su sentido por definicion.
    Lo que no da las brutas es una ley neta escrita como una sola
    expresion.
    """
    modelo = cinetica_isoterma()
    modelo["reacciones"] = [
        {"id": "rev", "bloque_id": "rx", "nu": [-1.0, 1.0],
         "ley_directa": dict(LEY_ISOMERIZACION),
         "ley_inversa": {
             "k_ref": {"valor": 12.0, "unidad": "mol/s"},
             "T_ref": {"valor": 320.0, "unidad": "K"},
             "Ea": 60000.0,
             "base_actividad": "actividad",
             "ordenes": {"isobutane": 1.0},
         }},
    ]
    return modelo


def cinetica_desde_equilibrio():
    """
    La inversa DERIVADA del equilibrio: k_inv = k_dir / K_eq(T).

    Es la restriccion que impone la termodinamica --en el equilibrio
    r+ = r- obliga a que la razon de las constantes sea K_eq-- y es el
    unico modo en que una reversible es consistente sin dos juegos de
    datos cineticos independientes.

    Dos avisos que la respuesta declara: K_eq sale de van't Hoff, que
    supone dH_rxn constante con la temperatura; y con este modo la ley
    directa usa los exponentes de la ESTEQUIOMETRIA, porque mezclar
    ordenes libres con una inversa derivada del equilibrio romperia esa
    consistencia.
    """
    modelo = cinetica_isoterma()
    modelo["reacciones"] = [
        {"id": "rev", "bloque_id": "rx", "nu": [-1.0, 1.0],
         "ley_directa": dict(LEY_ISOMERIZACION),
         "ley_inversa": {"desde_equilibrio": True}},
    ]
    return modelo


def cinetica_volumetrica():
    """
    La constante en base VOLUMETRICA, integrada con el volumen del reactor.

    10 mol/(m3 s) en 5 m3 son 50 mol/s, la misma constante que
    `cinetica_isoterma`, asi que el resultado es identico. La UNIDAD
    declara la base, igual que con una tasa dada.
    """
    modelo = cinetica_isoterma()
    modelo["reacciones"] = [
        {"id": "iso", "bloque_id": "rx", "nu": [-1.0, 1.0],
         "ley_directa": {**LEY_ISOMERIZACION,
                         "k_ref": {"valor": 10.0, "unidad": "mol/(m3*s)"}}},
    ]
    modelo["especificaciones"] = modelo["especificaciones"] + [
        {"bloque_id": "rx", "variable": "V", "valor": 5.0, "unidad": "m3"},
    ]
    return modelo


def cinetica_orden_negativo():
    """
    Un orden negativo, que se rechaza con el motivo.

    Modela inhibicion y es fisicamente posible, pero hace que la tasa
    DIVERJA cuando esa especie se agota, y con una alimentacion sin ella
    la ley no esta definida. Se rechaza en vez de devolver un infinito.
    """
    modelo = cinetica_isoterma()
    modelo["reacciones"] = [
        {"id": "iso", "bloque_id": "rx", "nu": [-1.0, 1.0],
         "ley_directa": {**LEY_ISOMERIZACION,
                         "ordenes": {"n-butane": 1.0, "isobutane": -1.0}}},
    ]
    return modelo


EJEMPLOS_LABORATORIO = [
    {
        "id": "un-volumen-temperatura",
        "nombre": "Un volumen, temperatura impuesta",
        "descripcion": "El montaje minimo. Da el mismo Q que el adaptador antiguo "
                       "de /diagrama/resolver para el mismo problema.",
        "estado_esperado": "resuelto",
        "modelo": un_volumen_temperatura(),
    },
    {
        "id": "dos-volumenes-temperatura",
        "nombre": "Dos volumenes en serie, temperaturas impuestas",
        "descripcion": "El caso de aceptacion. La corriente intermedia es UN estado "
                       "compartido, y Q1 + Q2 cuadra con F (h_salida - h_entrada).",
        "estado_esperado": "resuelto",
        "modelo": dos_volumenes_temperatura(),
    },
    {
        "id": "dos-volumenes-calor",
        "nombre": "Dos volumenes, el primero con calor impuesto",
        "descripcion": "El mismo problema al reves: con el Q que el caso anterior "
                       "calcula, recupera 310 K. Y cambia el algoritmo a una "
                       "inversion escalar con brentq.",
        "estado_esperado": "resuelto",
        "modelo": dos_volumenes_calor(),
    },
    {
        "id": "dos-volumenes-bifasico",
        "nombre": "Dos volumenes con vaporizacion parcial",
        "descripcion": "2 MW llevan la corriente intermedia a la laguna bifasica: "
                       "beta ~ 0.30 a unos 367.5 K. La fase se determina, no se "
                       "supone, y el segundo volumen RETIRA calor.",
        "estado_esperado": "resuelto",
        "modelo": dos_volumenes_bifasico(),
    },
    {
        "id": "mesa-con-datos-locales",
        "nombre": "El montaje como lo exporta la mesa hoy",
        "descripcion": "Sin especificaciones, con los valores en bloques[].datos. "
                       "Mismo resultado, pero con unidades implicitas: Q en kW.",
        "estado_esperado": "resuelto",
        "modelo": mesa_con_datos_locales(),
    },
    {
        "id": "incompatible-t-y-q",
        "nombre": "Temperatura y calor impuestos a la vez (se rechaza)",
        "descripcion": "Para probar el camino de error: devuelve 200 con "
                       "estado 'invalido' y LAB_ESPECIFICACION_EXCLUYENTE.",
        "estado_esperado": "invalido",
        "modelo": incompatible_t_y_q(),
    },
    # --- los reactivos
    {
        "id": "reactor-isomerizacion",
        "nombre": "A -> B: isomerizacion de n-butano",
        "descripcion": "El caso reactivo mas simple. Consumo de A y generacion de B "
                       "iguales al avance; con sum(nu) = 0 el caudal molar no "
                       "cambia; elementos y masa conservados y MEDIDOS.",
        "estado_esperado": "resuelto",
        "modelo": reactor_isomerizacion(),
    },
    {
        "id": "reactor-volumetrico",
        "nombre": "La misma reaccion con la tasa en base volumetrica",
        "descripcion": "4 mol/(m3 s) en 5 m3 son 20 mol/s: resultado identico al "
                       "anterior. La UNIDAD declara la base, y una tasa volumetrica "
                       "necesita el volumen del reactor.",
        "estado_esperado": "resuelto",
        "modelo": reactor_volumetrico(),
    },
    {
        "id": "reactor-a-dos-b",
        "nombre": "A -> 2B: el caudal molar cambia y la masa no",
        "descripcion": "Craqueo de diisobutileno. El caudal pasa de 100 a 110 mol/s "
                       "y la masa no se mueve ni un gramo: un caudal molar que "
                       "cambia parece un balance roto y no lo es.",
        "estado_esperado": "resuelto",
        "modelo": reactor_a_dos_b(),
    },
    {
        "id": "reactor-reversible",
        "nombre": "Reversible con la direccion inversa dominante",
        "descripcion": "r+ = 2 y r- = 8, avance neto -6. La inversa intercambia "
                       "produccion y consumo: el isobuteno se genera a 16 y se "
                       "consume a 4 mol/s.",
        "estado_esperado": "resuelto",
        "modelo": reactor_reversible(),
    },
    {
        "id": "reactor-en-equilibrio",
        "nombre": "Equilibrio dinamico: neto cero, brutas POSITIVAS",
        "descripcion": "r+ = r- = 5. La fuente neta es cero y las brutas valen 10 y "
                       "5 mol/s. Es el caso que desmonta derivar las brutas del "
                       "neto; comparalo con 'reactor-solo-neta'.",
        "estado_esperado": "resuelto",
        "modelo": reactor_en_equilibrio(),
    },
    {
        "id": "reactor-solo-neta",
        "nombre": "La misma situacion con solo la tasa neta (brutas NULL)",
        "descripcion": "Misma composicion de salida que el equilibrio, pero "
                       "generacion_bruta y consumo_bruto salen null con su motivo. "
                       "null no es cero: el dato no esta.",
        "estado_esperado": "resuelto",
        "modelo": reactor_solo_neta(),
    },
    {
        "id": "dos-reactores-en-serie",
        "nombre": "Dos reactores compartiendo la corriente intermedia",
        "descripcion": "El caso 4 de la aceptacion: el estado intermedio no se "
                       "duplica. Y el cierre global incluye el calor de reaccion de "
                       "todo el montaje.",
        "estado_esperado": "resuelto",
        "modelo": dos_reactores_en_serie(),
    },
    {
        "id": "estequiometria-invalida",
        "nombre": "Estequiometria que no conserva los elementos (se rechaza)",
        "descripcion": "nu = [-1, +2]: salen 8 carbonos de donde entraron 4. "
                       "Devuelve 200 con estado 'invalido' y "
                       "LAB_ELEMENTOS_NO_CONSERVADOS, diciendo que elemento "
                       "descuadra y en cuanto.",
        "estado_esperado": "invalido",
        "modelo": estequiometria_invalida(),
    },
    # --- los cineticos
    {
        "id": "cinetica-isoterma",
        "nombre": "Ley de velocidad con temperatura impuesta",
        "descripcion": "La tasa se CALCULA, asi que el balance es implicito. Se "
                       "resuelve con brentq sobre el avance, acotado por la "
                       "estequiometria.",
        "estado_esperado": "resuelto",
        "modelo": cinetica_isoterma(),
    },
    {
        "id": "cinetica-adiabatica",
        "nombre": "Reactor adiabatico: la temperatura es una consecuencia",
        "descripcion": "Energia acoplada. k(T) decide el avance y el avance decide "
                       "el calor que decide T: se cierran a la vez. El supuesto "
                       "adiabatico ES la especificacion termica (Q = 0).",
        "estado_esperado": "resuelto",
        "modelo": cinetica_adiabatica(),
    },
    {
        "id": "cinetica-reversible",
        "nombre": "Reversible con dos leyes, una por sentido",
        "descripcion": "Las tasas brutas se conocen por construccion: cada ley da "
                       "la velocidad de su sentido por definicion.",
        "estado_esperado": "resuelto",
        "modelo": cinetica_reversible(),
    },
    {
        "id": "cinetica-desde-equilibrio",
        "nombre": "Inversa derivada de K_eq(T)",
        "descripcion": "k_inv = k_dir / K_eq(T), la restriccion que impone la "
                       "termodinamica. La respuesta declara la aproximacion de "
                       "van't Hoff y que la directa pasa a usar los exponentes de "
                       "la estequiometria.",
        "estado_esperado": "resuelto",
        "modelo": cinetica_desde_equilibrio(),
    },
    {
        "id": "cinetica-volumetrica",
        "nombre": "Constante en base volumetrica",
        "descripcion": "10 mol/(m3 s) en 5 m3 son 50 mol/s: identico al isotermo. "
                       "La unidad declara la base.",
        "estado_esperado": "resuelto",
        "modelo": cinetica_volumetrica(),
    },
    {
        "id": "cinetica-orden-negativo",
        "nombre": "Orden negativo (se rechaza)",
        "descripcion": "Modela inhibicion y hace que la tasa diverja cuando la "
                       "especie se agota. Devuelve 200 con estado 'invalido' y "
                       "LAB_ORDEN_INVALIDO.",
        "estado_esperado": "invalido",
        "modelo": cinetica_orden_negativo(),
    },
]

EJEMPLOS_LABORATORIO_POR_ID = {e["id"]: e for e in EJEMPLOS_LABORATORIO}
