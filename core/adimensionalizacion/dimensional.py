"""
A1: analisis dimensional del AST del contrato v1.

Una dimension es un vector de exponentes racionales sobre bases declaradas
(los nombres de base son los del documento: 'T', 'L', 'N', o los que el
usuario elija). Las dimensiones pendientes (`null`) son incognitas: cada
regla del lenguaje genera restricciones lineales racionales y se resuelven
de forma exacta. El resultado distingue

  - compatible: todo determinado y sin contradicciones;
  - incompatible: alguna restriccion contradice a las anteriores (se
    publica la ruta del termino y los simbolos implicados);
  - indeterminado: no hay contradiccion, pero quedan dimensiones que las
    ecuaciones no fijan.

Reglas: una suma exige sumandos de igual dimension; el numero 0 es
compatible con cualquier dimension (no se fabrica una unidad para
justificarlo) y cualquier otro numero es adimensional; exp/log/sin/cos
exigen argumento adimensional; abs conserva la dimension; min/max exigen
argumentos iguales; un exponente no numerico exige base y exponente
adimensionales; una llamada exige las dimensiones de entrada declaradas;
derivadas y operadores restan la dimension de la variable.

Unidades: el texto de unidad se interpreta con pint y se proyecta sobre
las bases SI L, M, T, I, Theta, N, J. Una unidad con desplazamiento (degC,
degF) marca una temperatura ABSOLUTA afin: nunca admite una escala
multiplicativa. Dos unidades equivalentes producen la misma dimension.
"""

import functools
from fractions import Fraction

from .racional import SistemaRacional, combinar, escalar, fraccion, limpiar

BASES_SI = {"[length]": "L", "[mass]": "M", "[time]": "T", "[current]": "I",
            "[temperature]": "Theta", "[substance]": "N", "[luminosity]": "J"}

_UREG = None


def _registro():
    global _UREG
    if _UREG is None:
        import pint
        _UREG = pint.UnitRegistry()
    return _UREG


@functools.lru_cache(maxsize=None)
def interpretar_unidad(texto):
    """{'dimension': {...}, 'afin': bool, 'factorSI': float} o None."""
    alias = {"adimensional": "dimensionless", "-": "dimensionless", "1": "dimensionless"}
    try:
        q = _registro().Quantity(1.0, alias.get(texto, texto))
    except Exception:
        return None
    dim = {}
    for base, exp in dict(q.dimensionality).items():
        if base not in BASES_SI:
            return None
        dim[BASES_SI[base]] = fraccion(exp) if not isinstance(exp, float) else Fraction(exp).limit_denominator(1000)
    afin = not q._is_multiplicative
    factor = None
    if not afin:
        factor = float(q.to_base_units().magnitude)
    return {"dimension": limpiar(dim), "afin": afin, "factorSI": factor}


def cantidad_SI(valor, unidad):
    """(magnitud SI, texto de unidad SI) de una cantidad multiplicativa."""
    q = _registro().Quantity(valor, unidad).to_base_units()
    return float(q.magnitude), f"{q.units:~}" or "1"


def dim_desde_json(d):
    if d is None:
        return None
    return limpiar({k: Fraction(v["n"], v["d"]) for k, v in d.items()})


def dim_a_json(d):
    if d is None:
        return None
    return {k: {"n": v.numerator, "d": v.denominator} for k, v in sorted(limpiar(d).items())}


def dim_texto(d):
    if d is None:
        return "pendiente"
    d = limpiar(d)
    if not d:
        return "1"
    return " ".join(k if v == 1 else f"{k}^{v}" for k, v in sorted(d.items()))


class Afin:
    """Dimension afin: constante + combinacion lineal de incognitas."""

    __slots__ = ("const", "inc")

    def __init__(self, const=None, inc=None):
        self.const = limpiar(const or {})
        self.inc = limpiar(inc or {})

    def mas(self, otro, f=Fraction(1)):
        return Afin(combinar(self.const, otro.const, f), combinar(self.inc, otro.inc, f))

    def por(self, f):
        return Afin(escalar(self.const, f), escalar(self.inc, f))


UNO = Afin()


class Analizador:
    """Recorre igualdades y expresiones generando restricciones."""

    def __init__(self, simbolos, funciones):
        # simbolos: id -> {"dimension": dict|None, "rol": ...}
        # funciones: id -> {"entradas": [dict|None], "salida": dict|None}
        self.simbolos = simbolos
        self.funciones = funciones
        # Orden de pivote: los comodines del 0 primero (no aportan datos), luego
        # parametros, funciones y por ultimo variables. Asi las columnas libres
        # que quedan son DATOS que el usuario puede dar (preferentemente de
        # variables, que suele conocer) y bastan para determinar el resto.
        def prioridad(col):
            tipo, _, sid = col.partition(":")
            if tipo == "cero":
                return (0, col)
            if tipo == "s":
                rol = (simbolos.get(sid) or {}).get("rol")
                return (1 if rol in ("parametro", "constante") else 3, col)
            return (2, col)
        self.sistema = SistemaRacional(prioridad=prioridad)
        self.diagnosticos = []
        self.usados = set()
        self.comodines = 0
        self.rango_errores = []

    # incognitas: "s:<id>", "fe:<fid>:<i>", "fs:<fid>", "cero:<n>"
    def _simbolo(self, sid):
        self.usados.add(sid)
        d = self.simbolos[sid]["dimension"]
        return Afin(const=d) if d is not None else Afin(inc={"s:" + sid: Fraction(1)})

    def _entrada(self, fid, i):
        d = self.funciones[fid]["entradas"][i]
        return Afin(const=d) if d is not None else Afin(inc={f"fe:{fid}:{i}": Fraction(1)})

    def _salida(self, fid):
        d = self.funciones[fid]["salida"]
        return Afin(const=d) if d is not None else Afin(inc={f"fs:{fid}": Fraction(1)})

    def igual(self, a, b, ruta, motivo):
        dif = a.mas(b, Fraction(-1))
        estado, origen, rhs = self.sistema.agregar(dif.inc, escalar(dif.const, Fraction(-1)), ruta)
        if estado == "incompatible":
            implicadas = sorted(k.split(":", 1)[1] for k in dif.inc if k.startswith("s:"))
            if dif.inc:
                mensaje = (f"{motivo}: contradice las dimensiones ya inferidas"
                           + (f" para {', '.join(implicadas)}" if implicadas else ""))
            else:
                mensaje = f"{motivo}: {dim_texto(a.const)} frente a {dim_texto(b.const)}"
            self.diagnosticos.append({"ruta": ruta, "codigo": "dimension_incompatible",
                                      "severidad": "error", "mensaje": mensaje,
                                      "simbolos": implicadas})

    def adimensional(self, a, ruta, motivo):
        self.igual(a, UNO, ruta, motivo)

    def _rango(self, ruta, mensaje):
        self.diagnosticos.append({"ruta": ruta, "codigo": "rango", "severidad": "error", "mensaje": mensaje})

    def expresion(self, e, ruta):
        """Devuelve (Afin, rango) con rango None (escalar) o tupla de coordenadas."""
        t = e["tipo"]
        if t == "numero":
            if e["valor"] == 0:
                self.comodines += 1
                return Afin(inc={f"cero:{self.comodines}": Fraction(1)}), None
            return UNO, None
        if t == "simbolo":
            return self._simbolo(e["id"]), None
        if t == "suma":
            args = [self.expresion(a, f"{ruta}.argumentos[{i}]") for i, a in enumerate(e["argumentos"])]
            for i, (d, r) in enumerate(args[1:], 1):
                self.igual(d, args[0][0], f"{ruta}.argumentos[{i}]", "suma de dimensiones distintas")
                if r != args[0][1]:
                    self._rango(f"{ruta}.argumentos[{i}]", "suma de un escalar y un vector")
            return args[0]
        if t == "producto":
            total, rango = UNO, None
            for i, a in enumerate(e["argumentos"]):
                d, r = self.expresion(a, f"{ruta}.argumentos[{i}]")
                total = total.mas(d)
                if r is not None:
                    if rango is not None:
                        self._rango(f"{ruta}.argumentos[{i}]", "producto de dos vectores sin operador definido")
                    rango = r
            return total, rango
        if t == "cociente":
            n, rn = self.expresion(e["numerador"], ruta + ".numerador")
            d, rd = self.expresion(e["denominador"], ruta + ".denominador")
            if rd is not None:
                self._rango(ruta + ".denominador", "division por un vector")
            return n.mas(d, Fraction(-1)), rn
        if t == "potencia":
            b, rb = self.expresion(e["base"], ruta + ".base")
            if rb is not None:
                self._rango(ruta + ".base", "potencia de un vector")
            q = exponente_numerico(e["exponente"])
            if q is not None:
                return b.por(q), None
            x, _ = self.expresion(e["exponente"], ruta + ".exponente")
            self.adimensional(x, ruta + ".exponente", "un exponente no numerico debe ser adimensional")
            self.adimensional(b, ruta + ".base", "con exponente no numerico la base debe ser adimensional")
            return UNO, None
        if t == "funcion":
            args = []
            for i, a in enumerate(e["argumentos"]):
                d, r = self.expresion(a, f"{ruta}.argumentos[{i}]")
                if r is not None:
                    self._rango(f"{ruta}.argumentos[{i}]", "una funcion escalar no admite un vector")
                args.append(d)
            if e["nombre"] in ("exp", "log", "sin", "cos", "tan", "tanh", "sinh", "cosh", "atan", "erf"):
                self.adimensional(args[0], ruta + ".argumentos[0]", f"el argumento de {e['nombre']} debe ser adimensional")
                return UNO, None
            for i, d in enumerate(args[1:], 1):
                self.igual(d, args[0], f"{ruta}.argumentos[{i}]", f"argumentos de {e['nombre']} con dimensiones distintas")
            return args[0], None
        if t == "llamada":
            fid = e["funcionId"]
            for i, a in enumerate(e["argumentos"]):
                d, r = self.expresion(a, f"{ruta}.argumentos[{i}]")
                if r is not None:
                    self._rango(f"{ruta}.argumentos[{i}]", "una funcion declarada no admite un vector")
                self.igual(d, self._entrada(fid, i), f"{ruta}.argumentos[{i}]", f"entrada {i + 1} de {fid}")
            return self._salida(fid), None
        if t == "derivada":
            d, r = self.expresion(e["expresion"], ruta + ".expresion")
            return d.mas(self._simbolo(e["respecto"]), Fraction(-e["orden"])), r
        if t in ("gradiente", "divergencia", "laplaciano"):
            coords = e["coordenadas"]
            d, r = self.expresion(e["expresion"], ruta + ".expresion")
            base = self._simbolo(coords[0])
            for i, x in enumerate(coords[1:], 1):
                self.igual(self._simbolo(x), base, f"{ruta}.coordenadas[{i}]", "coordenadas de un operador con dimensiones distintas")
            vector = tuple(coords) if len(coords) > 1 else None
            if t == "gradiente":
                if r is not None:
                    self._rango(ruta, "gradiente de un vector (tensor) fuera del alcance")
                return d.mas(base, Fraction(-1)), vector
            if t == "divergencia":
                if len(coords) > 1 and r != tuple(coords):
                    self._rango(ruta, "la divergencia requiere un vector en las mismas coordenadas")
                return d.mas(base, Fraction(-1)), None
            if r is not None:
                self._rango(ruta, "laplaciano de un vector fuera del alcance")
            return d.mas(base, Fraction(-2)), None
        raise ValueError(t)

    def igualdad(self, eq, ruta):
        i, ri = self.expresion(eq["izquierda"], ruta + ".izquierda")
        d, rd = self.expresion(eq["derecha"], ruta + ".derecha")
        self.igual(d, i, ruta + ".derecha", "los dos lados de la igualdad tienen dimensiones distintas")
        if ri is not None or rd is not None:
            self._rango(ruta, "igualdad vectorial: solo se admiten ecuaciones escalares")
        return i

    # --- resultados ---
    def valor(self, incognita):
        """Dimension determinada de una incognita, o None."""
        piv = self.sistema.pivotes()
        fila = piv.get(incognita)
        if fila is None or len(fila["coef"]) != 1:
            return None
        return dict(fila["rhs"])

    def dimension(self, afin):
        """Valor de una dimension afin si sus incognitas estan determinadas."""
        total = dict(afin.const)
        for k, f in afin.inc.items():
            v = self.valor(k)
            if v is None:
                return None
            total = combinar(total, v, f)
        return total


def exponente_numerico(e):
    """Fraction si el exponente es una expresion solo de numeros."""
    t = e["tipo"]
    if t == "numero":
        return fraccion(e["valor"])
    if t == "producto":
        r = Fraction(1)
        for a in e["argumentos"]:
            q = exponente_numerico(a)
            if q is None:
                return None
            r *= q
        return r
    if t == "suma":
        r = Fraction(0)
        for a in e["argumentos"]:
            q = exponente_numerico(a)
            if q is None:
                return None
            r += q
        return r
    if t == "cociente":
        n, d = exponente_numerico(e["numerador"]), exponente_numerico(e["denominador"])
        if n is None or d is None or d == 0:
            return None
        return n / d
    return None


def analizar_modelo(modelo):
    """Analisis dimensional completo del modelo. Devuelve un dict con estado,
    dimensiones de simbolos (con su origen), diagnosticos y el analizador."""
    diagnosticos = []
    simbolos = {}
    origen = {}
    unidades = {}
    for i, s in enumerate(modelo["simbolos"]):
        d = dim_desde_json(s["dimension"])
        origen[s["id"]] = "declarada" if d is not None else None
        if s["unidad"] is not None:
            u = interpretar_unidad(s["unidad"])
            unidades[s["id"]] = u
            ruta = f"simbolos[{i}].unidad"
            if u is None:
                diagnosticos.append({"ruta": ruta, "codigo": "unidad_no_reconocida", "severidad": "aviso",
                                     "mensaje": f"unidad '{s['unidad']}' no reconocida; no se usa para inferir ni comprobar"})
            elif d is None:
                d = dict(u["dimension"])
                origen[s["id"]] = "unidad"
            elif set(d) <= set(BASES_SI.values()):
                if limpiar(d) != u["dimension"]:
                    diagnosticos.append({"ruta": ruta, "codigo": "dimension_incompatible", "severidad": "error",
                                         "mensaje": f"la unidad '{s['unidad']}' tiene dimension {dim_texto(u['dimension'])} y se declaro {dim_texto(d)}",
                                         "simbolos": [s["id"]]})
            else:
                diagnosticos.append({"ruta": ruta, "codigo": "unidad_no_comparable", "severidad": "aviso",
                                     "mensaje": "la dimension declarada usa bases no SI; la unidad no se compara"})
        simbolos[s["id"]] = {"dimension": d, "rol": s["rol"]}
    funciones = {f["id"]: {"entradas": [dim_desde_json(x) for x in f["entradas"]],
                           "salida": dim_desde_json(f["salida"])} for f in modelo["funciones"]}
    an = Analizador(simbolos, funciones)
    for i, eq in enumerate(modelo["ecuaciones"]):
        an.igualdad(eq, f"ecuaciones[{i}]")
    for i, dom in enumerate(modelo["dominios"]):
        var = an._simbolo(dom["variableId"])
        for lado in ("desde", "hasta"):
            d, r = an.expresion(dom[lado], f"dominios[{i}].{lado}")
            an.igual(d, var, f"dominios[{i}].{lado}", "el extremo del dominio no tiene la dimension de su variable")
    for i, c in enumerate(modelo["condiciones"]):
        an.igualdad(c["ecuacion"], f"condiciones[{i}].ecuacion")
    for i, f in enumerate(modelo["funciones"]):
        if "escala" in f:
            # v2: f = S fhat con fhat adimensional, luego [S] = [salida de f].
            an.igual(an._simbolo(f["escala"]["simboloId"]), an._salida(f["id"]), f"funciones[{i}].escala.simboloId",
                     f"la escala de {f['id']} debe tener la dimension de su salida")
    diagnosticos.extend(an.diagnosticos)

    resultado_simbolos = []
    indeterminados = []
    for s in modelo["simbolos"]:
        sid = s["id"]
        d = simbolos[sid]["dimension"]
        o = origen[sid]
        if d is None:
            d = an.valor("s:" + sid)
            o = "inferida" if d is not None else "indeterminada"
            if d is None and sid in an.usados:
                indeterminados.append(sid)
        entrada = {"id": sid, "dimension": dim_a_json(d), "origen": o if sid in an.usados or o != "indeterminada" else "sin_uso"}
        if sid in unidades and unidades[sid] is not None:
            entrada["unidad"] = {"texto": s["unidad"], "dimension": dim_a_json(unidades[sid]["dimension"]),
                                 "afin": unidades[sid]["afin"]}
        resultado_simbolos.append(entrada)
        simbolos[sid]["dimension_final"] = d
    resultado_funciones = []
    for f in modelo["funciones"]:
        fid = f["id"]
        entradas = []
        for i, x in enumerate(funciones[fid]["entradas"]):
            v = x if x is not None else an.valor(f"fe:{fid}:{i}")
            entradas.append(dim_a_json(v))
            if v is None:
                indeterminados.append(f"{fid}.entrada[{i}]")
        salida = funciones[fid]["salida"]
        if salida is None:
            salida = an.valor(f"fs:{fid}")
            if salida is None:
                indeterminados.append(f"{fid}.salida")
        resultado_funciones.append({"id": fid, "entradas": entradas, "salida": dim_a_json(salida)})
        funciones[fid]["entradas_finales"] = [dim_desde_json(x) for x in entradas]
        funciones[fid]["salida_final"] = dim_desde_json(dim_a_json(salida))
    for sid in indeterminados:
        diagnosticos.append({"ruta": f"simbolos.{sid}", "codigo": "dimension_indeterminada", "severidad": "aviso",
                             "mensaje": f"las ecuaciones no determinan la dimension de {sid}"})
    # Datos indispensables: incognitas de datos que no pivotan. Las filas de un
    # pivote de datos solo contienen columnas libres de datos (los comodines
    # pivotan antes), asi que dar estas dimensiones determina todas las demas.
    pivotes = an.sistema.pivotes()
    faltantes = []
    for s in modelo["simbolos"]:
        col = "s:" + s["id"]
        if s["id"] in an.usados and simbolos[s["id"]]["dimension"] is None and col not in pivotes:
            faltantes.append(s["id"])
    for f in modelo["funciones"]:
        fid = f["id"]
        for i, x in enumerate(funciones[fid]["entradas"]):
            if x is None and f"fe:{fid}:{i}" not in pivotes and any(f"fe:{fid}:{i}" in fila["coef"] for fila in an.sistema.filas):
                faltantes.append(f"{fid}.entrada[{i}]")
        if funciones[fid]["salida"] is None and f"fs:{fid}" not in pivotes and any(f"fs:{fid}" in fila["coef"] for fila in an.sistema.filas):
            faltantes.append(f"{fid}.salida")
    if faltantes and indeterminados:
        diagnosticos.append({"ruta": "modelo", "codigo": "datos_indispensables", "severidad": "aviso", "simbolos": faltantes,
                             "mensaje": "basta declarar la dimension de " + ", ".join(faltantes) + " para determinar todas las demas"})
    errores = [d for d in diagnosticos if d["severidad"] == "error"]
    rango = [d for d in errores if d["codigo"] == "rango"]
    estado = "incompatible" if any(d["codigo"] == "dimension_incompatible" for d in errores) else (
        "indeterminado" if indeterminados else "compatible")
    return {"estado": estado, "simbolos": resultado_simbolos, "funciones": resultado_funciones,
            "faltantes": faltantes if indeterminados else [],
            "diagnosticos": diagnosticos, "errores_rango": bool(rango),
            "dimensiones": {sid: v["dimension_final"] for sid, v in simbolos.items()},
            "funciones_dim": funciones, "unidades": unidades}


def dimension_de(e, dimensiones, funciones):
    """Dimension de una expresion con todos los datos conocidos, o None si
    es incompatible o indeterminada. `funciones`: id -> {entradas, salida}."""
    simbolos = {k: {"dimension": v, "rol": None} for k, v in dimensiones.items()}
    an = Analizador(simbolos, funciones)
    d, _ = an.expresion(e, "expresion")
    if any(x["severidad"] == "error" for x in an.diagnosticos):
        return None
    return an.dimension(d)
