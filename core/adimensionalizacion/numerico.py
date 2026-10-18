"""
Evaluacion numerica de la forma canonica (Poli) del nucleo.

Es la unica pieza que convierte expresiones exactas en numeros. Se usa
solo en los estudios (`estudio.py`): nunca decide una transformacion ni un
certificado, que siguen siendo exactos.

  - Los valores pueden ser escalares o arreglos de numpy, reales o
    complejos (el paso complejo da derivadas exactas a precision de maquina
    para funciones analiticas).
  - Una derivada se resuelve con la funcion `derivadas(atomo)` que aporta
    quien evalua (diferencias finitas en una malla, cero en un estado
    homogeneo...). Sin ella, una derivada es un error explicito.
  - Una funcion declarada (llamada opaca) no tiene definicion numerica: se
    publica como no evaluable, nunca se sustituye por 1.
"""

import math

import numpy as np

from . import algebra as A


class NoEvaluable(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def _real_si_puede(x):
    return x


def evaluar_poli(P, valores, derivadas=None):
    """Valor de P con `valores`: id de simbolo -> numero o arreglo."""
    total = 0
    for m, c in P.t.items():
        termino = float(c)
        for a, e in m:
            termino = termino * _potencia(evaluar_atomo(a, valores, derivadas), e)
        total = total + termino
    return total


def _potencia(x, e):
    if e == 1:
        return x
    if e.denominator == 1:
        n = e.numerator
        if n > 0:
            return x ** n
        return 1.0 / (x ** (-n))
    # Exponente fraccionario: rama principal. Una base negativa real con
    # exponente fraccionario no tiene valor real; se publica como tal.
    if np.iscomplexobj(x):
        return np.power(x, float(e))
    if np.any(np.asarray(x) < 0):
        raise NoEvaluable("rama_compleja", "potencia fraccionaria de una base negativa: sin valor real")
    return np.power(x, float(e))


def evaluar_atomo(a, valores, derivadas=None):
    tipo = a[0]
    if tipo == "s":
        if a[1] not in valores:
            raise NoEvaluable("valor_faltante", f"falta el valor de {a[1]}")
        return valores[a[1]]
    if tipo == "n":
        return float(a[1])
    if tipo == "b":
        return evaluar_poli(a[1], valores, derivadas)
    if tipo == "p":
        base = evaluar_poli(a[1], valores, derivadas)
        expo = evaluar_poli(a[2], valores, derivadas)
        return np.power(base, expo)
    if tipo == "f":
        args = [evaluar_poli(p, valores, derivadas) for p in a[2]]
        nombre = a[1]
        if nombre == "exp":
            return np.exp(args[0])
        if nombre == "log":
            x = args[0]
            if not np.iscomplexobj(x) and np.any(np.asarray(x) <= 0):
                raise NoEvaluable("fuera_de_dominio", "logaritmo de un valor no positivo")
            return np.log(x)
        if nombre == "sin":
            return np.sin(args[0])
        if nombre == "cos":
            return np.cos(args[0])
        if nombre == "tan":
            return np.tan(args[0])
        if nombre == "tanh":
            return np.tanh(args[0])
        if nombre == "sinh":
            return np.sinh(args[0])
        if nombre == "cosh":
            return np.cosh(args[0])
        if nombre == "atan":
            return np.arctan(args[0])
        if nombre == "erf":
            from scipy.special import erf
            return erf(args[0])
        if nombre == "abs":
            x = args[0]
            if np.iscomplexobj(x):
                # |x| con paso complejo: derivada de |re| (valida fuera de 0).
                return x * np.sign(x.real)
            return np.abs(x)
        if nombre == "min":
            r = args[0]
            for x in args[1:]:
                r = np.minimum(r, x) if not np.iscomplexobj(r) else np.where(r.real <= x.real, r, x)
            return r
        if nombre == "max":
            r = args[0]
            for x in args[1:]:
                r = np.maximum(r, x) if not np.iscomplexobj(r) else np.where(r.real >= x.real, r, x)
            return r
        raise NoEvaluable("funcion", f"funcion sin evaluacion numerica: {nombre}")
    if tipo == "c":
        raise NoEvaluable("funcion_declarada", f"la funcion declarada {a[1]} no tiene definicion numerica")
    if tipo in ("d", "o"):
        if derivadas is None:
            raise NoEvaluable("derivada", "una derivada no se evalua sin malla ni estado")
        return derivadas(a)
    raise NoEvaluable("atomo", f"atomo no evaluable: {tipo}")


def evaluar_ast(e, ctx, valores, modo="expandir", derivadas=None):
    return evaluar_poli(A.canonica(e, ctx, modo), valores, derivadas)


def finito(x):
    try:
        return bool(np.all(np.isfinite(x)))
    except TypeError:
        return False


def numero_json(x):
    """Float finito para JSON, o None."""
    try:
        v = complex(x)
    except (TypeError, ValueError):
        return None
    if abs(v.imag) > 1e-12 * max(1.0, abs(v.real)):
        return None
    v = v.real
    return v if math.isfinite(v) else None
