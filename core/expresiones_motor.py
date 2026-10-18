"""
Expresiones de datos del motor independiente, del lado servidor.

Misma gramatica que frontend/app/motor/expresionesMotor.ts (numeros, pi, e,
+ - * / ^, parentesis, sin cos exp log sqrt abs min max step), analizada a
un arbol propio: nunca se ejecuta texto con eval. Lo que anade el servidor:

  * derivada simbolica respecto de una variable (dP/dt de una presion
    prescrita), solo para operaciones suaves;
  * `no_suaves(arbol)`: abs, min, max y step tienen derivada discontinua o
    nula a trozos; una presion o un caudal con ellas no es una "funcion
    temporal suave verificada" y se diagnostica en vez de integrarse;
  * forma canonica para la identidad del modelo.

La unica variable admitida en los datos de frontera es t, el tiempo en
segundos (SI), sea cual sea la unidad declarada del dato.
"""

import math
import re

FUNCIONES = {"sin", "cos", "exp", "log", "sqrt", "abs", "min", "max", "step"}
NO_SUAVES = {"abs", "min", "max", "step"}
_TOKEN = re.compile(r"\s*(?:((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)|([A-Za-z][A-Za-z0-9_]*)|([+\-*/^(),]))")


class ErrorExpresion(ValueError):
    pass


def analizar(texto, variables):
    """Arbol: ('num', v) | ('var', nombre) | ('op', op, (args...))."""
    if not isinstance(texto, str) or not texto.strip():
        raise ErrorExpresion("Falta un valor o expresión.")
    if len(texto) > 500:
        raise ErrorExpresion("La expresión es demasiado larga.")
    tokens, pos = [], 0
    while pos < len(texto):
        m = _TOKEN.match(texto, pos)
        if not m:
            if not texto[pos:].strip():
                break
            raise ErrorExpresion(f"Símbolo no permitido en «{texto[pos:pos + 12]}».")
        tokens.append(m.group(0).strip())
        pos = m.end()
    estado = {"i": 0, "nodos": 0}

    def nodo(e):
        estado["nodos"] += 1
        if estado["nodos"] > 200:
            raise ErrorExpresion("Demasiadas operaciones.")
        return e

    def actual():
        return tokens[estado["i"]] if estado["i"] < len(tokens) else None

    def tomar():
        t = actual()
        estado["i"] += 1
        return t

    def atom():
        tok = tomar()
        if tok is None:
            raise ErrorExpresion("Expresión incompleta.")
        if tok == "(":
            e = suma()
            if tomar() != ")":
                raise ErrorExpresion("Falta cerrar el paréntesis.")
            return e
        if re.match(r"^(\d|\.)", tok):
            v = float(tok)
            if not math.isfinite(v):
                raise ErrorExpresion("Número no finito.")
            return nodo(("num", v))
        if tok in ("pi", "e"):
            return nodo(("num", math.pi if tok == "pi" else math.e))
        if tok in FUNCIONES:
            if tomar() != "(":
                raise ErrorExpresion(f"{tok} necesita paréntesis.")
            args = [suma()]
            while actual() == ",":
                tomar()
                args.append(suma())
            if tomar() != ")":
                raise ErrorExpresion("Falta cerrar la función.")
            if (tok not in ("min", "max") and len(args) != 1) or len(args) > 8:
                raise ErrorExpresion("Cantidad de argumentos no admitida.")
            return nodo(("op", tok, tuple(args)))
        if tok not in variables:
            raise ErrorExpresion(f"Variable no admitida: {tok}."
                                 + (f" Usa {', '.join(variables)}." if variables else " Este dato debe ser constante."))
        return nodo(("var", tok))

    def potencia():
        e = atom()
        if actual() == "^":
            tomar()
            return nodo(("op", "^", (e, unario())))
        return e

    def unario():
        if actual() in ("-", "+"):
            op = tomar()
            return nodo(("op", "neg", (unario(),))) if op == "-" else unario()
        return potencia()

    def producto():
        e = unario()
        while actual() in ("*", "/"):
            op = tomar()
            e = nodo(("op", op, (e, unario())))
        return e

    def suma():
        e = producto()
        while actual() in ("+", "-"):
            op = tomar()
            e = nodo(("op", op, (e, producto())))
        return e

    arbol = suma()
    if estado["i"] != len(tokens):
        raise ErrorExpresion("Operación o paréntesis inesperado.")
    return arbol


def evaluar(e, variables):
    if e[0] == "num":
        v = e[1]
    elif e[0] == "var":
        v = variables[e[1]]
    else:
        op, a = e[1], [evaluar(x, variables) for x in e[2]]
        try:
            if op == "+":
                v = a[0] + a[1]
            elif op == "-":
                v = a[0] - a[1]
            elif op == "*":
                v = a[0] * a[1]
            elif op == "/":
                v = a[0] / a[1]
            elif op == "^":
                v = a[0] ** a[1]
            elif op == "neg":
                v = -a[0]
            elif op == "sin":
                v = math.sin(a[0])
            elif op == "cos":
                v = math.cos(a[0])
            elif op == "exp":
                v = math.exp(a[0])
            elif op == "log":
                v = math.log(a[0])
            elif op == "sqrt":
                v = math.sqrt(a[0])
            elif op == "abs":
                v = abs(a[0])
            elif op == "min":
                v = min(a)
            elif op == "max":
                v = max(a)
            elif op == "step":
                v = 1.0 if a[0] >= 0 else 0.0
            else:
                raise ErrorExpresion(f"Operación desconocida {op}.")
        except (ZeroDivisionError, ValueError, OverflowError) as x:
            raise ErrorExpresion(f"La expresión no es evaluable aquí ({x}).")
        if isinstance(v, complex):
            raise ErrorExpresion("La expresión produjo un número complejo.")
    if not math.isfinite(v):
        raise ErrorExpresion("La expresión produjo un valor no finito.")
    return float(v)


def depende_de(e, nombre):
    if e[0] == "var":
        return e[1] == nombre
    if e[0] == "op":
        return any(depende_de(x, nombre) for x in e[2])
    return False


def no_suaves(e):
    if e[0] != "op":
        return set()
    propias = {e[1]} if e[1] in NO_SUAVES else set()
    return propias.union(*[no_suaves(x) for x in e[2]])


def _n(v):
    return ("num", float(v))


def derivada(e, x):
    """Derivada simbolica d e / d x. Solo para arboles sin funciones no
    suaves (ErrorExpresion si las hay)."""
    if not depende_de(e, x):
        return _n(0)
    if e[0] == "var":
        return _n(1)
    op, a = e[1], e[2]
    if op in NO_SUAVES:
        raise ErrorExpresion(f"{op} no es derivable de forma continua.")
    d = [derivada(y, x) for y in a]
    if op == "+":
        return ("op", "+", (d[0], d[1]))
    if op == "-":
        return ("op", "-", (d[0], d[1]))
    if op == "neg":
        return ("op", "neg", (d[0],))
    if op == "*":
        return ("op", "+", (("op", "*", (d[0], a[1])), ("op", "*", (a[0], d[1]))))
    if op == "/":
        return ("op", "/", (("op", "-", (("op", "*", (d[0], a[1])), ("op", "*", (a[0], d[1])))),
                            ("op", "^", (a[1], _n(2)))))
    if op == "^":
        if not depende_de(a[1], x):     # (f^c)' = c f^(c-1) f'
            return ("op", "*", (("op", "*", (a[1], ("op", "^", (a[0], ("op", "-", (a[1], _n(1))))))), d[0]))
        # (f^g)' = f^g (g' log f + g f'/f)
        return ("op", "*", (e, ("op", "+", (("op", "*", (d[1], ("op", "log", (a[0],)))),
                                             ("op", "/", (("op", "*", (a[1], d[0])), a[0]))))))
    if op == "sin":
        return ("op", "*", (("op", "cos", a), d[0]))
    if op == "cos":
        return ("op", "neg", (("op", "*", (("op", "sin", a), d[0])),))
    if op == "exp":
        return ("op", "*", (e, d[0]))
    if op == "log":
        return ("op", "/", (d[0], a[0]))
    if op == "sqrt":
        return ("op", "/", (d[0], ("op", "*", (_n(2), e))))
    raise ErrorExpresion(f"Sin derivada para {op}.")


def canonica(e):
    """Texto canonico (para la identidad del modelo): sin espacios ni
    parentesis redundantes, numeros con repr."""
    if e[0] == "num":
        return repr(e[1])
    if e[0] == "var":
        return e[1]
    return f"{e[1]}({','.join(canonica(x) for x in e[2])})"
