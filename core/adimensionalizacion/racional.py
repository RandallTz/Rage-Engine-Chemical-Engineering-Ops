"""
Aritmetica racional exacta para el nucleo de adimensionalizacion.

Todo lo que decide (dimensiones, exponentes de escalas, rangos, espacios
nulos) se hace con fracciones exactas: un rango calculado con flotantes no
distingue un objetivo redundante de uno casi redundante.
"""

import math
from fractions import Fraction

LIMITE_FACTORIZACION = 10 ** 6


def fraccion(valor):
    """Fraccion exacta desde un numero JSON finito (int o float decimal)."""
    if isinstance(valor, bool):
        raise TypeError("un booleano no es un numero")
    if isinstance(valor, Fraction):
        return valor
    if isinstance(valor, int):
        return Fraction(valor)
    if isinstance(valor, float):
        if not math.isfinite(valor):
            raise ValueError("numero no finito")
        # repr devuelve el decimal mas corto que reproduce el flotante:
        # 0.1 se lee como 1/10, no como su expansion binaria.
        return Fraction(repr(valor))
    raise TypeError(f"no es un numero: {valor!r}")


def numero_json(q):
    """int si es entero; float si el decimal es exacto y reversible; None si no."""
    if q.denominator == 1:
        return int(q.numerator)
    d = q.denominator
    while d % 2 == 0:
        d //= 2
    while d % 5 == 0:
        d //= 5
    if d == 1:
        f = float(q)
        if Fraction(repr(f)) == q:
            return f
    return None


def raiz_entera(n, r):
    """Raiz r-esima entera exacta de n >= 0, o None."""
    if n < 0:
        return None
    if n in (0, 1):
        return n
    x = int(round(n ** (1.0 / r)))
    for c in (x - 1, x, x + 1):
        if c >= 0 and c ** r == n:
            return c
    return None


def raiz_exacta(q, r):
    """Raiz r-esima racional exacta de q > 0, o None."""
    a, b = raiz_entera(q.numerator, r), raiz_entera(q.denominator, r)
    if a is None or b is None:
        return None
    return Fraction(a, b)


def factorizar(n):
    """Factores primos {p: k} de n >= 1, o None si hay un factor grande."""
    factores, p = {}, 2
    while p * p <= n:
        if p > LIMITE_FACTORIZACION:
            return None
        while n % p == 0:
            factores[p] = factores.get(p, 0) + 1
            n //= p
        p += 1 if p == 2 else 2
    if n > 1:
        if n > LIMITE_FACTORIZACION ** 2:
            return None
        factores[n] = factores.get(n, 0) + 1
    return factores


# --- Vectores dispersos {clave: Fraction} -----------------------------------

def limpiar(v):
    return {k: x for k, x in v.items() if x != 0}


def combinar(a, b, f=Fraction(1)):
    """a + f*b."""
    r = dict(a)
    for k, x in b.items():
        r[k] = r.get(k, 0) + f * x
    return limpiar(r)


def escalar(a, f):
    return limpiar({k: f * x for k, x in a.items()})


class SistemaRacional:
    """Eliminacion gaussiana incremental y exacta, en forma escalonada reducida.

    Cada fila es  sum(coef[col] * x[col]) = rhs  donde rhs es un vector
    disperso (por ejemplo, exponentes de dimensiones base o logaritmos de
    parametros). `origen` registra que combinacion de filas originales
    produjo cada fila: con eso se identifican las elecciones responsables
    de una redundancia o de una incompatibilidad.

    `prioridad(col)` decide que columna pivota primero; el orden es parte
    del contrato publicado (no una preferencia oculta).
    """

    def __init__(self, prioridad=None):
        self.filas = []  # dicts: piv, coef, rhs, origen
        self.prioridad = prioridad or (lambda col: (0, str(col)))

    def reducir(self, coef, rhs, origen):
        coef, rhs, origen = limpiar(coef), limpiar(rhs), limpiar(origen)
        for fila in self.filas:
            f = coef.get(fila["piv"])
            if f:
                coef = combinar(coef, fila["coef"], -f)
                rhs = combinar(rhs, fila["rhs"], -f)
                origen = combinar(origen, fila["origen"], -f)
        return coef, rhs, origen

    def agregar(self, coef, rhs, origen_id):
        """Devuelve (estado, origen, rhs_residual); estado en
        'independiente' | 'dependiente' | 'incompatible'."""
        coef, rhs, origen = self.reducir(coef, rhs, {origen_id: Fraction(1)})
        if not coef:
            return ("dependiente" if not rhs else "incompatible"), origen, rhs
        piv = min(coef, key=self.prioridad)
        f = 1 / coef[piv]
        nueva = {"piv": piv, "coef": escalar(coef, f), "rhs": escalar(rhs, f),
                 "origen": escalar(origen, f)}
        for fila in self.filas:
            g = fila["coef"].get(piv)
            if g:
                fila["coef"] = combinar(fila["coef"], nueva["coef"], -g)
                fila["rhs"] = combinar(fila["rhs"], nueva["rhs"], -g)
                fila["origen"] = combinar(fila["origen"], nueva["origen"], -g)
        self.filas.append(nueva)
        return "independiente", origen, rhs

    def pivotes(self):
        return {fila["piv"]: fila for fila in self.filas}

    @property
    def rango(self):
        return len(self.filas)


def espacio_nulo(matriz, columnas):
    """Base racional del espacio nulo de `matriz` (lista de filas {col: q}).

    Devuelve vectores {col: q}; uno por columna libre, con la columna libre
    a 1. El orden de `columnas` decide que columnas pivotan (las primeras).
    """
    orden = {c: i for i, c in enumerate(columnas)}
    sistema = SistemaRacional(prioridad=lambda c: orden[c])
    for i, fila in enumerate(matriz):
        sistema.agregar(fila, {}, i)
    piv = sistema.pivotes()
    base = []
    for libre in columnas:
        if libre in piv:
            continue
        v = {libre: Fraction(1)}
        for col, fila in piv.items():
            g = fila["coef"].get(libre)
            if g:
                v[col] = -g
        base.append(limpiar(v))
    return base, sistema.rango


def entero_primitivo(v):
    """Multiplica un vector racional por el menor factor que lo vuelve entero
    con mcd 1 y primera componente no nula positiva."""
    if not v:
        return v
    mcm = 1
    for x in v.values():
        mcm = mcm * x.denominator // math.gcd(mcm, x.denominator)
    enteros = {k: int(x * mcm) for k, x in v.items()}
    g = 0
    for x in enteros.values():
        g = math.gcd(g, abs(x))
    return {k: Fraction(x, g) for k, x in enteros.items()}
