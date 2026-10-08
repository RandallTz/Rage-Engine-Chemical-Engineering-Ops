"""
Balanceo estequiometrico EXACTO: el espacio nulo de la matriz elemental.

QUE RESUELVE
------------
Dadas unas especies, encontrar los coeficientes nu que conservan los
elementos:

    A @ nu = 0

donde A es la matriz elemental (filas = elementos, columnas = especies).
Es el problema que el prototipo del frontend llama "balanceo racional", y
aqui se hace con aritmetica EXACTA -- `fractions.Fraction` y eliminacion
de Gauss sobre los racionales -- en vez de con floats.

POR QUE EXACTA Y NO NUMERICA
----------------------------
Porque la respuesta correcta son numeros enteros pequenos, y un metodo
numerico los devuelve como 0.9999999999999998. Con SVD se obtiene una base
del espacio nulo en floats y luego hay que "reconocer" los enteros, que es
adivinar: 0.333333 puede ser 1/3 o puede ser el redondeo de otra cosa. Con
Fraction no hay nada que reconocer -- los coeficientes SON racionales y se
escalan al minimo entero dividiendo por el maximo comun divisor.

LAS TRES RESPUESTAS POSIBLES, Y LAS TRES IMPORTAN
-------------------------------------------------
    dimension 0   No hay reaccion. Estas especies no se pueden combinar
                  conservando los elementos, y decirlo es la respuesta.
    dimension 1   Hay UNA reaccion, unica salvo escala y signo. Es el caso
                  que el usuario espera.
    dimension > 1 Hay VARIAS reacciones independientes. El sistema no
                  determina una: determina un subespacio. Devolver una
                  cualquiera seria elegir por el usuario, asi que se
                  devuelve la base entera y se dice cuantas son.

EL SIGNO NO LO DECIDE LA CONSERVACION
-------------------------------------
A @ nu = 0 tiene la misma solucion con nu y con -nu: la conservacion de
elementos no sabe que es reactivo y que es producto. Asi que se admite una
pista -- cuales son los reactivos -- y, sin ella, se orienta por
convencion y se DICE que es una convencion. Suponer una direccion en
silencio es como una reaccion sale escrita al reves sin que nadie se
entere.

Zona libre de pint: adimensional en todo (coeficientes estequiometricos).
"""

from fractions import Fraction
from math import gcd

import numpy as np

from core import errores as codigos
from core.errores import ErrorDeDatos

# Tope de especies. Mas que un limite fisico es de servicio: la
# eliminacion exacta es O(n^3) sobre racionales y los denominadores crecen.
MAX_ESPECIES = 24


def _a_fracciones(A):
    """La matriz elemental como Fractions, para no perder exactitud."""
    return [[Fraction(int(round(valor))) for valor in fila] for fila in A]


def _escalonar(M):
    """
    Forma escalonada reducida por filas, en aritmetica exacta.

    Devuelve (M_reducida, columnas_pivote). Sin pivoteo por magnitud
    porque con racionales no hay error de redondeo que mitigar: se pivota
    por el primer no nulo, que es mas simple y aqui es igual de estable.
    """
    M = [fila[:] for fila in M]
    filas, columnas = len(M), len(M[0]) if M else 0
    pivotes = []
    fila_actual = 0
    for col in range(columnas):
        # el primer no nulo en esta columna, de fila_actual hacia abajo
        objetivo = next((f for f in range(fila_actual, filas) if M[f][col] != 0),
                        None)
        if objetivo is None:
            continue
        M[fila_actual], M[objetivo] = M[objetivo], M[fila_actual]
        pivote = M[fila_actual][col]
        M[fila_actual] = [v / pivote for v in M[fila_actual]]
        for f in range(filas):
            if f != fila_actual and M[f][col] != 0:
                factor = M[f][col]
                M[f] = [a - factor * b for a, b in zip(M[f], M[fila_actual])]
        pivotes.append(col)
        fila_actual += 1
        if fila_actual == filas:
            break
    return M, pivotes


def _enteros_minimos(vector):
    """
    Un vector de Fractions escalado al menor vector de enteros.

    Se multiplica por el minimo comun multiplo de los denominadores y se
    divide por el maximo comun divisor de los numeradores. El resultado es
    el unico vector de enteros proporcional sin factor comun, que es la
    forma en la que una reaccion se escribe.
    """
    denominadores = [f.denominator for f in vector]
    mcm = 1
    for d in denominadores:
        mcm = mcm * d // gcd(mcm, d)
    enteros = [int(f * mcm) for f in vector]
    divisor = 0
    for v in enteros:
        divisor = gcd(divisor, abs(v))
    if divisor > 1:
        enteros = [v // divisor for v in enteros]
    return enteros


def espacio_nulo_exacto(A):
    """
    Una base del espacio nulo de A, con coeficientes enteros minimos.

    Cada vector de la base es una reaccion independiente. La dimension del
    espacio es cuantas reacciones independientes hay entre esas especies, y
    es el dato que decide si el problema tiene una respuesta o un
    subespacio de respuestas.
    """
    if not A or not A[0]:
        return []
    M, pivotes = _escalonar(_a_fracciones(A))
    columnas = len(A[0])
    libres = [c for c in range(columnas) if c not in pivotes]

    base = []
    for libre in libres:
        vector = [Fraction(0)] * columnas
        vector[libre] = Fraction(1)
        for fila, pivote in enumerate(pivotes):
            vector[pivote] = -M[fila][libre]
        base.append(_enteros_minimos(vector))
    return base


def _orientar(nu, indices_reactivos, especies):
    """
    El signo de la reaccion, con la pista del usuario o por convencion.

    La conservacion de elementos no distingue reactivo de producto: nu y
    -nu la cumplen igual. Asi que o lo dice el usuario, o es una
    convencion -- y en ese caso se declara como tal.
    """
    nu = list(nu)
    if indices_reactivos:
        # Los reactivos tienen que salir NEGATIVOS. Se mira el primero que
        # tenga coeficiente no nulo.
        for i in indices_reactivos:
            if i < len(nu) and nu[i] != 0:
                if nu[i] > 0:
                    nu = [-v for v in nu]
                return nu, (
                    f"orientada con la pista del usuario: {especies[i]} es "
                    "reactivo, asi que su coeficiente es negativo"
                )
        return nu, (
            "no se pudo orientar con la pista: ninguno de los reactivos "
            "indicados participa en esta reaccion. El signo es una convencion."
        )
    # Convencion: el PRIMER coeficiente no nulo sale negativo, de forma que
    # la primera especie que participe sea un reactivo.
    primero = next((i for i, v in enumerate(nu) if v != 0), None)
    if primero is not None and nu[primero] > 0:
        nu = [-v for v in nu]
    return nu, (
        "el signo es una CONVENCION: la conservacion de elementos no "
        "distingue reactivo de producto, y A @ nu = 0 se cumple igual con nu "
        f"y con -nu. Se orienta para que {especies[primero]} salga como "
        "reactivo. Da 'reactivos' si quieres otra direccion."
        if primero is not None else "reaccion nula"
    )


def balancear(especies, atomos_por_especie, reactivos=None):
    """
    Las reacciones que conservan los elementos entre estas especies.

    `atomos_por_especie` es una lista de diccionarios {elemento: cuenta},
    uno por especie, en el mismo orden. `reactivos` es una lista opcional
    de nombres o indices para orientar el signo.

    Devuelve un diccionario con la base de reacciones, su dimension y la
    matriz elemental, mas el diagnostico de los tres casos posibles.
    """
    if len(especies) < 2:
        raise ErrorDeDatos(
            f"Hacen falta al menos dos especies para balancear una reaccion y se "
            f"dieron {len(especies)}.",
            codigo=codigos.LAB_ESTEQUIOMETRIA_INVALIDA,
        )
    if len(especies) > MAX_ESPECIES:
        raise ErrorDeDatos(
            f"Esta entrega balancea hasta {MAX_ESPECIES} especies y se dieron "
            f"{len(especies)}. No es un limite fisico sino del servicio: la "
            "eliminacion exacta crece con el cubo del numero de especies y los "
            "denominadores con ella.",
            codigo=codigos.LAB_NUMERO_DE_COMPONENTES,
        )
    if len(atomos_por_especie) != len(especies):
        raise ErrorDeDatos(
            f"Hay {len(especies)} especies y {len(atomos_por_especie)} "
            "composiciones elementales. Hace falta una por especie.",
            codigo=codigos.LAB_ESTEQUIOMETRIA_INVALIDA,
        )

    sin_atomos = [especies[i] for i, a in enumerate(atomos_por_especie) if not a]
    if sin_atomos:
        raise ErrorDeDatos(
            f"No hay composicion elemental de: {', '.join(sin_atomos)}. Sin ella "
            "no se puede balancear: el balanceo ES la conservacion de los atomos.",
            codigo=codigos.LAB_COMPONENTE_NO_DISPONIBLE,
        )

    elementos = sorted({e for a in atomos_por_especie for e in a})
    A = [[int(a.get(e, 0)) for a in atomos_por_especie] for e in elementos]

    # Los indices de los reactivos, si se dieron por nombre o por posicion.
    indices_reactivos = []
    for r in (reactivos or []):
        if isinstance(r, int):
            indices_reactivos.append(r)
        elif r in especies:
            indices_reactivos.append(especies.index(r))
        else:
            raise ErrorDeDatos(
                f"La pista de reactivos menciona {r!r}, que no esta entre las "
                f"especies ({', '.join(especies)}).",
                codigo=codigos.LAB_ESTEQUIOMETRIA_INVALIDA,
            )

    base = espacio_nulo_exacto(A)
    orientadas, notas = [], []
    for nu in base:
        nu_or, nota = _orientar(nu, indices_reactivos, especies)
        orientadas.append(nu_or)
        notas.append(nota)

    dimension = len(orientadas)
    if dimension == 0:
        diagnostico = {
            "caso": "sin_reaccion",
            "mensaje": (
                "No hay ninguna combinacion de estas especies que conserve los "
                "elementos. No es que el balanceo haya fallado: es que estas "
                "especies no reaccionan entre si. Revisa si falta alguna."
            ),
        }
    elif dimension == 1:
        diagnostico = {
            "caso": "unica",
            "mensaje": "Hay una sola reaccion independiente, unica salvo escala. "
                       "Los coeficientes son los enteros minimos.",
        }
    else:
        diagnostico = {
            "caso": "subespacio",
            "mensaje": (
                f"Hay {dimension} reacciones INDEPENDIENTES entre estas especies, "
                "asi que la conservacion de elementos no determina una: determina "
                "un subespacio. Se devuelve la base entera. Cualquier combinacion "
                "lineal de ellas tambien conserva los elementos, y elegir una por "
                "ti seria decidir que quimica ocurre."
            ),
        }

    # La comprobacion, medida: A @ nu tiene que ser exactamente cero.
    residuos = []
    for nu in orientadas:
        fila = {}
        for k, e in enumerate(elementos):
            fila[e] = int(sum(A[k][i] * nu[i] for i in range(len(nu))))
        residuos.append(fila)

    return {
        "especies": list(especies),
        "elementos": elementos,
        "matriz_elemental": A,
        "dimension_del_espacio": dimension,
        "reacciones": [
            {
                "nu": nu,
                "nu_por_especie": {especies[i]: nu[i] for i in range(len(nu))},
                "orientacion": nota,
                "residuo_elemental": residuo,
                "conserva": all(v == 0 for v in residuo.values()),
                "latex": _latex_de(especies, nu),
            }
            for nu, nota, residuo in zip(orientadas, notas, residuos)
        ],
        "diagnostico": diagnostico,
        "aritmetica": "exacta (fractions.Fraction y eliminacion de Gauss sobre "
                      "los racionales). Los coeficientes son enteros minimos, no "
                      "floats redondeados.",
        "convencion_nu": "positivo producto, negativo reactivo",
    }


def _latex_de(especies, nu):
    """La reaccion escrita, para que se lea en vez de contarse."""
    izquierda, derecha = [], []
    for i, coef in enumerate(nu):
        if coef == 0:
            continue
        magnitud = "" if abs(coef) == 1 else f"{abs(coef)}\\,"
        termino = magnitud + r"\mathrm{" + str(especies[i]).replace("_", r"\_") + "}"
        (izquierda if coef < 0 else derecha).append(termino)
    return " + ".join(izquierda) + r" \longrightarrow " + " + ".join(derecha)


def comprobar_nu(nu, atomos_por_especie, especies):
    """
    Si una nu DADA conserva los elementos, y cuanto descuadra si no.

    Es el complemento del balanceo: ahi se busca nu, aqui se juzga una. Lo
    usa el laboratorio para validar lo que llega en la peticion (ver
    `core/estequiometria.validar_estequiometria`), y se expone aparte para
    que el frontend pueda juzgar una nu editada a mano sin resolver nada.
    """
    nu = [int(round(v)) if abs(v - round(v)) < 1e-12 else float(v) for v in nu]
    elementos = sorted({e for a in atomos_por_especie for e in a})
    A = [[int(a.get(e, 0)) for a in atomos_por_especie] for e in elementos]
    residuo = {e: sum(A[k][i] * nu[i] for i in range(len(nu)))
               for k, e in enumerate(elementos)}
    escala = max(
        (sum(abs(A[k][i] * nu[i]) for i in range(len(nu)))
         for k in range(len(elementos))), default=0) or 1
    descuadre = {e: v for e, v in residuo.items() if abs(v) > 1e-9 * escala}
    return {
        "especies": list(especies),
        "nu": nu,
        "elementos": elementos,
        "residuo_elemental": {e: float(v) + 0.0 for e, v in residuo.items()},
        "conserva": not descuadre,
        "descuadre": {e: float(v) + 0.0 for e, v in descuadre.items()},
        "mensaje": (
            "Conserva los elementos."
            if not descuadre else
            "NO conserva los elementos: "
            + ", ".join(f"{e} {v:+g}" for e, v in sorted(descuadre.items()))
            + ". Eso no es una reaccion quimica, es un dato mal puesto."
        ),
    }
