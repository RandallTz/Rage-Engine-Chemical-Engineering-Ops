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
]

EJEMPLOS_LABORATORIO_POR_ID = {e["id"]: e for e in EJEMPLOS_LABORATORIO}
