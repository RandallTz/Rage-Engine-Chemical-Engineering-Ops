"""
Forma canonica de expresiones del contrato v1 (AST JSON).

Una expresion se lleva a un polinomio generalizado: suma de monomios con
coeficiente racional exacto, cada monomio un producto de ATOMOS con
exponentes racionales. Los atomos son simbolos, factores primos con
exponente fraccionario, funciones, llamadas a funciones declaradas,
derivadas parciales, operadores vectoriales y potencias que no se pueden
desarrollar.

Solo se aplican identidades validas bajo los supuestos que se publican:

  - asociatividad, conmutatividad y distributividad de suma y producto;
  - a^p * a^q = a^(p+q) (valida con la rama principal para cualquier a);
  - (a*b)^q = a^q * b^q solo si q es entero o los factores son positivos
    (escalas, parametros declarados positivos, |.|, exp, numeros > 0);
  - linealidad de derivadas y operadores: se extraen los factores
    constantes respecto de la variable y se reparte sobre sumas;
  - d/dx(x) = 1 y d^m/dx^m(d^n f/dx^n) = d^(m+n) f/dx^(m+n);
  - un parametro declarado negativo p se representa como -|p|.

NO se aplican la regla del producto, identidades de exp/log/trig ni el
intercambio de derivadas mixtas. Si dos expresiones tienen la misma forma
canonica son iguales bajo esos supuestos; si no la tienen, no se concluye
nada (de ahi el estado 'no_demostrada').

Tres modos:
  - 'conservar': gradiente, divergencia y laplaciano quedan como atomos
    (presentacion: se conserva la estructura div(D(c) grad c));
  - 'cartesiano': se reducen a derivadas parciales en coordenadas
    cartesianas;
  - 'expandir': cartesiano y ademas las derivadas se desarrollan con las
    reglas del producto, de la potencia y de la cadena (exp, log, sin, cos,
    potencias). Las derivadas de funciones declaradas, abs, min y max quedan
    como atomos. Es el modo del certificado y el de los cambios de variable
    no lineales, que generan terminos adicionales.

En modo 'expandir' tambien se usan log(exp(y)) = y (y real) y
exp(log(y)) = y solo si y es positivo con los signos declarados.
"""

import functools
import itertools
from fractions import Fraction

from .racional import factorizar, fraccion, numero_json, raiz_exacta

INDEPENDIENTES = ("tiempo", "coordenada")
MAX_POTENCIA_DESARROLLADA = 8
MAX_MONOMIOS = 4000


class ErrorAlgebraico(Exception):
    """Operacion indefinida (division por cero) o fuera del alcance."""

    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


class Contexto:
    """Lo que el algebra necesita saber de cada simbolo: rol, constancia,
    dependencias y signo. Las escalas son constantes y positivas."""

    def __init__(self, simbolos, funciones):
        # simbolos: id -> {"rol", "constante", "dependeDe": set, "signo"}
        # funciones: id -> {"dependeDe": set}
        self.simbolos = simbolos
        self.funciones = funciones
        self.expandir = False
        # Dimensiones opcionales (id -> {base: Fraction}); con ellas una suma
        # interna solo cede escalas si eso la deja adimensional.
        self.dimensiones = None
        self.funciones_dim = None

    def _info(self, sid):
        return self.simbolos.get(sid)

    def independiente(self, sid):
        i = self._info(sid)
        return bool(i) and i["rol"] in INDEPENDIENTES

    def constante_respecto(self, sid, var):
        i = self._info(sid)
        if i is None or sid == var:
            return False
        if i["rol"] in INDEPENDIENTES:
            return sid != var
        if i["constante"]:
            return True
        if i["dependeDe"]:
            return var not in i["dependeDe"]
        # Sin dependencias declaradas y no constante: se supone que puede
        # depender de todo (conservador: no se extrae de la derivada).
        return False

    def constante_total(self, sid):
        i = self._info(sid)
        return bool(i) and i["rol"] not in INDEPENDIENTES and i["rol"] != "campo" and i["constante"]

    def signo(self, sid):
        i = self._info(sid)
        return i["signo"] if i else "desconocido"

    def funcion_depende(self, fid):
        f = self.funciones.get(fid)
        return f["dependeDe"] if f else set()


# --- Claves canonicas --------------------------------------------------------

@functools.lru_cache(maxsize=None)
def clave_atomo(a):
    partes = []
    for x in a:
        if isinstance(x, Poli):
            partes.append(x.clave)
        elif isinstance(x, tuple):
            partes.append("(" + ",".join(p.clave if isinstance(p, Poli) else repr(p) for p in x) + ")")
        else:
            partes.append(repr(x))
    return "<" + "|".join(partes) + ">"


def clave_monomio(m):
    return "*".join(f"{clave_atomo(a)}^{e}" for a, e in m)


class Poli:
    """Suma de monomios: {monomio: coeficiente}. Monomio = tupla ordenada
    de (atomo, exponente racional no nulo)."""

    __slots__ = ("t", "clave")

    def __init__(self, terminos):
        self.t = {m: c for m, c in terminos.items() if c != 0}
        if len(self.t) > MAX_MONOMIOS:
            raise ErrorAlgebraico("complejidad", "la expresion desarrollada supera el limite de monomios")
        self.clave = "{" + " + ".join(f"{c}*[{clave_monomio(m)}]" for m, c in self.ordenados()) + "}"

    def ordenados(self):
        return sorted(self.t.items(), key=lambda mc: clave_monomio(mc[0]))

    def __eq__(self, otro):
        return isinstance(otro, Poli) and self.clave == otro.clave

    def __hash__(self):
        return hash(self.clave)

    def __lt__(self, otro):
        return self.clave < otro.clave

    def __repr__(self):
        return self.clave

    @property
    def es_cero(self):
        return not self.t

    def constante_numerica(self):
        """Fraction si es un numero (sin atomos), si no None."""
        if not self.t:
            return Fraction(0)
        if len(self.t) == 1 and () in self.t:
            return self.t[()]
        return None

    def monomio_unico(self):
        """(coeficiente, monomio) si tiene un solo monomio, si no None."""
        if len(self.t) == 1:
            (m, c), = self.t.items()
            return c, m
        return None


CERO = Poli({})
UNO = Poli({(): Fraction(1)})


def numero(q):
    return Poli({(): fraccion(q)})


def _normalizar(exps):
    """Monomio canonico desde {atomo: exponente}; los factores primos con
    exponente entero pasan al coeficiente. Devuelve (coef, monomio)."""
    coef = Fraction(1)
    items = []
    for a, e in exps.items():
        if e == 0:
            continue
        if a[0] == "n":
            entero = e.numerator // e.denominator
            coef *= Fraction(a[1]) ** entero
            e = e - entero
            if e == 0:
                continue
        items.append((a, e))
    items.sort(key=lambda ae: clave_atomo(ae[0]))
    return coef, tuple(items)


def monomio(coef, exps):
    c, m = _normalizar(exps)
    return Poli({m: fraccion(coef) * c})


def atomo(a, e=Fraction(1)):
    return monomio(1, {a: Fraction(e)})


def sumar(*polis):
    r = {}
    for p in polis:
        for m, c in p.t.items():
            r[m] = r.get(m, 0) + c
    return Poli(r)


def multiplicar(*polis):
    r = UNO
    for p in polis:
        acc = {}
        for (m1, c1), (m2, c2) in itertools.product(r.t.items(), p.t.items()):
            exps = dict(m1)
            for a, e in m2:
                exps[a] = exps.get(a, 0) + e
            f, m = _normalizar(exps)
            acc[m] = acc.get(m, 0) + c1 * c2 * f
        r = Poli(acc)
    return r


def negar(p):
    return Poli({m: -c for m, c in p.t.items()})


def restar(a, b):
    return sumar(a, negar(b))


# --- Signos de atomos --------------------------------------------------------

def atomo_positivo(a, ctx):
    tipo = a[0]
    if tipo == "s":
        return ctx.signo(a[1]) == "positivo"
    if tipo == "n":
        return True
    if tipo == "f":
        return a[1] in ("exp", "abs", "cosh")
    return False


def poli_positivo(p, ctx):
    """Positivo con los signos declarados (todos sus monomios lo son)."""
    return bool(p.t) and all(signo_monomio(c, m, ctx) == 1 for m, c in p.t.items())


def signo_monomio(c, m, ctx):
    """+1/-1 si el signo del monomio esta determinado, si no None."""
    if c == 0:
        return 0
    if all(atomo_positivo(a, ctx) for a, _ in m):
        return 1 if c > 0 else -1
    return None


# --- Constructores canonicos -------------------------------------------------

def _simbolo_crudo(sid):
    return atomo(("s", sid))


def simbolo(sid, ctx):
    if ctx.signo(sid) == "negativo":
        # p < 0 se escribe -|p|: el resto del algebra solo ve atomos
        # positivos y el signo queda en el coeficiente.
        return monomio(-1, {("f", "abs", (_simbolo_crudo(sid),)): Fraction(1)})
    return _simbolo_crudo(sid)


def _potencia_numerica(c, q):
    """c^q para racional c > 0 y q fraccionario: exacto si se puede, si no
    como producto de primos con exponente fraccionario."""
    raiz = raiz_exacta(c, q.denominator)
    if raiz is not None:
        return numero(raiz ** q.numerator)
    fn, fd = factorizar(c.numerator), factorizar(c.denominator)
    if fn is None or fd is None:
        return atomo(("b", numero(c)), q)
    exps = {}
    for p, k in fn.items():
        exps[("n", p)] = exps.get(("n", p), 0) + k * q
    for p, k in fd.items():
        exps[("n", p)] = exps.get(("n", p), 0) - k * q
    return monomio(1, exps)


def potencia(p, q, ctx):
    q = fraccion(q)
    if q == 0:
        if p.es_cero:
            raise ErrorAlgebraico("indefinido", "0^0 indefinido")
        return UNO
    if p.es_cero:
        if q > 0:
            return CERO
        raise ErrorAlgebraico("division_por_cero", "division por cero")
    unico = p.monomio_unico()
    if unico:
        c, m = unico
        if q.denominator == 1:
            return monomio(c ** q.numerator, {a: e * q for a, e in m})
        positivos = {a: e for a, e in m if atomo_positivo(a, ctx)}
        resto = {a: e for a, e in m if not atomo_positivo(a, ctx)}
        r = monomio(1, {a: e * q for a, e in positivos.items()})
        if c > 0:
            r = multiplicar(r, _potencia_numerica(c, q))
        if resto or c < 0:
            if c > 0 and len(resto) == 1 and list(resto.values())[0] == 1:
                # a^q con a de signo desconocido: es la propia definicion.
                r = multiplicar(r, atomo(list(resto)[0], q))
            else:
                base = monomio(c if c < 0 else 1, resto)
                r = multiplicar(r, atomo(("b", base), q))
        return r
    if q.denominator == 1 and 0 < q <= MAX_POTENCIA_DESARROLLADA:
        r = UNO
        for _ in range(q.numerator):
            r = multiplicar(r, p)
        return r
    factor, base = _extraer_escalas(p, ctx)
    return multiplicar(potencia(factor, q, ctx), atomo(("b", base), q))


def _extraer_escalas(p, ctx):
    """Saca de una suma interna la parte de escalas del monomio que tiene la
    variable de menor clave: (K + C u) = C (K/C + u). Valido siempre porque
    las escalas son positivas; deja los grupos internos a la vista."""
    candidatos = []
    for m, c in p.t.items():
        nucleo = tuple((a, e) for a, e in m if not atomo_constante_total(a, ctx))
        if nucleo:
            candidatos.append((clave_monomio(nucleo), clave_monomio(m), m))
    if not candidatos:
        return UNO, p
    _, _, m = min(candidatos)
    escalas = {a: e for a, e in m if a[0] == "s" and ctx.simbolos.get(a[1], {}).get("rol") == "escala"}
    if not escalas:
        return UNO, p
    if ctx.dimensiones is not None:
        # Solo se extrae si la suma tiene la dimension del factor: entonces el
        # interior queda adimensional (K + C u = C (K/C + u)). Una suma ya
        # adimensional (1 + K C u) no cede escalas: si no, el nucleo del termino
        # quedaria dimensional y su coeficiente tambien.
        d_suma = _dim_monomio(next(iter(p.t)), ctx)
        d_factor = _dim_monomio(tuple(escalas.items()), ctx)
        if d_suma is None or d_factor is None or d_suma != d_factor:
            return UNO, p
    factor = monomio(1, escalas)
    return factor, multiplicar(p, monomio(1, {a: -e for a, e in escalas.items()}))


def _dim_monomio(m, ctx):
    """Dimension de un monomio con ctx.dimensiones, o None si no se conoce."""
    total = {}
    for a, e in m:
        d = _dim_atomo(a, ctx)
        if d is None:
            return None
        for k, x in d.items():
            total[k] = total.get(k, 0) + e * x
    return {k: x for k, x in total.items() if x != 0}


def _dim_atomo(a, ctx):
    t = a[0]
    if t == "s":
        d = ctx.dimensiones.get(a[1])
        return None if d is None else {k: Fraction(x) for k, x in d.items() if x != 0}
    if t in ("n", "p"):
        return {}
    if t == "f":
        if a[1] in ("exp", "log", "sin", "cos", "tan", "tanh", "sinh", "cosh", "atan", "erf"):
            return {}
        return _dim_monomio(next(iter(a[2][0].t)), ctx) if a[2][0].t else {}
    if t == "b":
        return _dim_monomio(next(iter(a[1].t)), ctx) if a[1].t else {}
    if t == "c":
        f = (ctx.funciones_dim or {}).get(a[1])
        return None if f is None or f.get("salida") is None else {k: Fraction(x) for k, x in f["salida"].items() if x != 0}
    if t == "d":
        di = _dim_monomio(next(iter(a[1].t)), ctx) if a[1].t else {}
        dv = ctx.dimensiones.get(a[2])
        if di is None or dv is None:
            return None
        r = dict(di)
        for k, x in dv.items():
            r[k] = r.get(k, 0) - a[3] * Fraction(x)
        return {k: x for k, x in r.items() if x != 0}
    return None


def funcion(nombre, args, ctx):
    if nombre == "abs":
        p = args[0]
        if p.es_cero:
            return CERO
        unico = p.monomio_unico()
        if unico:
            s = signo_monomio(unico[0], unico[1], ctx)
            if s is not None:
                return p if s > 0 else negar(p)
        return atomo(("f", "abs", (p,)))
    if nombre in ("min", "max"):
        return atomo(("f", nombre, tuple(sorted(args))))
    p = args[0]
    u = p.monomio_unico()
    interior = u[1][0][0] if u and u[0] == 1 and len(u[1]) == 1 and u[1][0][1] == 1 else None
    if nombre == "log" and interior is not None and interior[0] == "f" and interior[1] == "exp":
        return interior[2][0]  # log(exp(y)) = y para y real
    if nombre == "exp" and interior is not None and interior[0] == "f" and interior[1] == "log" and poli_positivo(interior[2][0], ctx):
        return interior[2][0]  # exp(log(y)) = y solo con y > 0
    if nombre == "exp" and p.es_cero:
        return UNO
    if nombre == "log" and p == UNO:
        return CERO
    if nombre in ("sin", "tan", "tanh", "sinh", "atan", "erf") and p.es_cero:
        return CERO
    if nombre in ("cos", "cosh") and p.es_cero:
        return UNO
    return atomo(("f", nombre, (p,)))


def llamada(fid, args):
    return atomo(("c", fid, tuple(args)))


def potencia_general(base, exponente, ctx):
    q = exponente.constante_numerica()
    if q is not None:
        return potencia(base, q, ctx)
    return atomo(("p", base, exponente))


# --- Constancia --------------------------------------------------------------

def _polis_internos(a):
    tipo = a[0]
    if tipo in ("f", "c"):
        return list(a[2])
    if tipo == "b":
        return [a[1]]
    if tipo == "p":
        return [a[1], a[2]]
    if tipo == "d":
        return [a[1]]
    if tipo == "o":
        return [a[2]]
    return []


def atomo_constante_respecto(a, var, ctx):
    tipo = a[0]
    if tipo == "s":
        return ctx.constante_respecto(a[1], var)
    if tipo == "n":
        return True
    if tipo == "c" and var in ctx.funcion_depende(a[1]):
        return False
    return all(poli_constante_respecto(p, var, ctx) for p in _polis_internos(a))


def poli_constante_respecto(p, var, ctx):
    return all(atomo_constante_respecto(a, var, ctx) for m in p.t for a, _ in m)


def atomo_constante_total(a, ctx):
    tipo = a[0]
    if tipo == "s":
        return ctx.constante_total(a[1])
    if tipo == "n":
        return True
    if tipo in ("d", "o"):
        return False
    if tipo == "c" and ctx.funcion_depende(a[1]):
        return False
    return all(poli_constante_total(p, ctx) for p in _polis_internos(a))


def poli_constante_total(p, ctx):
    return all(atomo_constante_total(a, ctx) for m in p.t for a, _ in m)


# --- Operadores diferenciales ------------------------------------------------

def _lineal(p, es_constante, operar):
    """Aplica un operador lineal: extrae factores constantes de cada
    monomio y opera sobre el resto (un monomio constante da cero)."""
    partes = []
    for m, c in p.t.items():
        cons = {a: e for a, e in m if es_constante(a)}
        resto = tuple((a, e) for a, e in m if not es_constante(a))
        if not resto:
            continue
        partes.append(multiplicar(monomio(c, cons), operar(resto)))
    return sumar(*partes) if partes else CERO


def derivada(p, var, orden, ctx):
    if ctx.expandir:
        for _ in range(orden):
            p = derivada_expandida(p, var, ctx)
        return p

    def operar(resto):
        if resto == ((("s", var), Fraction(1)),):
            return UNO if orden == 1 else CERO
        if len(resto) == 1 and resto[0][1] == 1 and resto[0][0][0] == "d" and resto[0][0][2] == var:
            a = resto[0][0]
            return atomo(("d", a[1], var, a[3] + orden))
        return atomo(("d", Poli({resto: Fraction(1)}), var, orden))
    return _lineal(p, lambda a: atomo_constante_respecto(a, var, ctx), operar)


def _atomo_derivado(a, var):
    return atomo(("d", Poli({((a, Fraction(1)),): Fraction(1)}), var, 1))


def derivada_expandida(p, var, ctx):
    """d/dvar con reglas del producto, potencia y cadena (un orden)."""
    partes = []
    for m, c in p.t.items():
        for i, (a, e) in enumerate(m):
            if atomo_constante_respecto(a, var, ctx):
                continue
            da = _derivada_atomo(a, var, ctx)
            if da.es_cero:
                continue
            resto = {b: f for j, (b, f) in enumerate(m) if j != i}
            resto[a] = resto.get(a, 0) + e - 1
            partes.append(multiplicar(monomio(c * e, resto), da))
    return sumar(*partes) if partes else CERO


def _derivada_atomo(a, var, ctx):
    tipo = a[0]
    if tipo == "s":
        return UNO if a[1] == var else _atomo_derivado(a, var)
    if tipo == "f":
        nombre = a[1]
        if nombre in ("exp", "log", "sin", "cos"):
            arg = a[2][0]
            darg = derivada_expandida(arg, var, ctx)
            if nombre == "exp":
                return multiplicar(atomo(a), darg)
            if nombre == "log":
                return multiplicar(darg, potencia(arg, -1, ctx))
            if nombre == "sin":
                return multiplicar(funcion("cos", [arg], ctx), darg)
            return negar(multiplicar(funcion("sin", [arg], ctx), darg))
        if nombre in ("tan", "tanh", "sinh", "cosh", "atan"):
            arg = a[2][0]
            darg = derivada_expandida(arg, var, ctx)
            if nombre == "tan":      # (tan g)' = (1 + tan^2 g) g'
                return multiplicar(sumar(UNO, potencia(atomo(a), 2, ctx)), darg)
            if nombre == "tanh":     # (tanh g)' = (1 - tanh^2 g) g'
                return multiplicar(restar(UNO, potencia(atomo(a), 2, ctx)), darg)
            if nombre == "sinh":
                return multiplicar(funcion("cosh", [arg], ctx), darg)
            if nombre == "cosh":
                return multiplicar(funcion("sinh", [arg], ctx), darg)
            return multiplicar(darg, potencia(sumar(UNO, potencia(arg, 2, ctx)), -1, ctx))  # atan
        return _atomo_derivado(a, var)
    if tipo == "b":
        return derivada_expandida(a[1], var, ctx)
    if tipo == "p":
        base, expo = a[1], a[2]
        termino = sumar(multiplicar(derivada_expandida(expo, var, ctx), funcion("log", [base], ctx)),
                        multiplicar(expo, derivada_expandida(base, var, ctx), potencia(base, -1, ctx)))
        return multiplicar(atomo(a), termino)
    if tipo == "d":
        interior = a[1]
        if a[2] == var:
            return atomo(("d", interior, var, a[3] + 1))
        return _atomo_derivado(a, var)
    return _atomo_derivado(a, var)


def derivar_ast(e, var, ctx):
    """Derivada desarrollada de un AST respecto de var, como AST."""
    previo = ctx.expandir
    ctx.expandir = True
    try:
        return ast(derivada_expandida(_canon(cartesiano(e), ctx), var, ctx))
    finally:
        ctx.expandir = previo


def operador(tipo, p, coords, ctx):
    coords = tuple(coords)

    def operar(resto):
        return atomo(("o", tipo, Poli({resto: Fraction(1)}), coords))
    return _lineal(p, lambda a: all(atomo_constante_respecto(a, x, ctx) for x in coords), operar)


# --- Componentes cartesianas (AST) -------------------------------------------

class NoSoportado(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def es_vectorial(e):
    """Un campo vectorial de varias componentes (gradiente multidimensional
    o algo que lo contiene en un producto, suma o numerador)."""
    t = e["tipo"]
    if t == "gradiente":
        return len(e["coordenadas"]) > 1
    if t in ("producto", "suma"):
        return any(es_vectorial(a) for a in e["argumentos"])
    if t == "cociente":
        return es_vectorial(e["numerador"])
    return False


def componente(e, x, coords):
    """Componente cartesiana x de una expresion vectorial (AST)."""
    t = e["tipo"]
    if t == "gradiente":
        if list(e["coordenadas"]) != list(coords):
            raise NoSoportado("operador_vectorial", "gradiente y divergencia sobre coordenadas distintas")
        return {"tipo": "derivada", "expresion": e["expresion"], "respecto": x, "orden": 1}
    if t == "suma":
        return {"tipo": "suma", "argumentos": [componente(a, x, coords) for a in e["argumentos"]]}
    if t == "producto":
        vec = [i for i, a in enumerate(e["argumentos"]) if es_vectorial(a)]
        if len(vec) != 1:
            raise NoSoportado("operador_vectorial", "producto de dos vectores sin operador definido")
        args = list(e["argumentos"])
        args[vec[0]] = componente(args[vec[0]], x, coords)
        return {"tipo": "producto", "argumentos": args}
    if t == "cociente":
        return {"tipo": "cociente", "numerador": componente(e["numerador"], x, coords), "denominador": e["denominador"]}
    raise NoSoportado("operador_vectorial", f"no se puede tomar la componente de '{t}'")


def cartesiano(e):
    """Reescribe gradiente/divergencia/laplaciano como derivadas parciales
    cartesianas (AST). Supuesto publicado: coordenadas cartesianas."""
    t = e["tipo"]
    if t == "laplaciano":
        f = cartesiano(e["expresion"])
        partes = [{"tipo": "derivada", "expresion": f, "respecto": x, "orden": 2} for x in e["coordenadas"]]
        return partes[0] if len(partes) == 1 else {"tipo": "suma", "argumentos": partes}
    if t == "gradiente":
        if len(e["coordenadas"]) > 1:
            raise NoSoportado("operador_vectorial", "gradiente multidimensional fuera de una divergencia")
        return {"tipo": "derivada", "expresion": cartesiano(e["expresion"]), "respecto": e["coordenadas"][0], "orden": 1}
    if t == "divergencia":
        coords = e["coordenadas"]
        if len(coords) == 1 and not es_vectorial(e["expresion"]):
            return {"tipo": "derivada", "expresion": cartesiano(e["expresion"]), "respecto": coords[0], "orden": 1}
        partes = [{"tipo": "derivada", "expresion": cartesiano(componente(e["expresion"], x, coords)), "respecto": x, "orden": 1} for x in coords]
        return partes[0] if len(partes) == 1 else {"tipo": "suma", "argumentos": partes}
    return mapear_hijos(e, cartesiano)


def mapear_hijos(e, f):
    t = e["tipo"]
    if t in ("numero", "simbolo"):
        return e
    r = dict(e)
    if t in ("suma", "producto", "funcion", "llamada"):
        r["argumentos"] = [f(a) for a in e["argumentos"]]
    elif t == "cociente":
        r["numerador"], r["denominador"] = f(e["numerador"]), f(e["denominador"])
    elif t == "potencia":
        r["base"], r["exponente"] = f(e["base"]), f(e["exponente"])
    else:
        r["expresion"] = f(e["expresion"])
    return r


# --- AST -> forma canonica ---------------------------------------------------

def canonica(e, ctx, modo="conservar"):
    if modo in ("cartesiano", "expandir"):
        e = cartesiano(e)
    previo = ctx.expandir
    ctx.expandir = modo == "expandir"
    try:
        return _canon(e, ctx)
    finally:
        ctx.expandir = previo


def _canon(e, ctx):
    t = e["tipo"]
    if t == "numero":
        return numero(e["valor"])
    if t == "simbolo":
        return simbolo(e["id"], ctx)
    if t == "suma":
        return sumar(*[_canon(a, ctx) for a in e["argumentos"]])
    if t == "producto":
        return multiplicar(*[_canon(a, ctx) for a in e["argumentos"]])
    if t == "cociente":
        return multiplicar(_canon(e["numerador"], ctx), potencia(_canon(e["denominador"], ctx), -1, ctx))
    if t == "potencia":
        return potencia_general(_canon(e["base"], ctx), _canon(e["exponente"], ctx), ctx)
    if t == "funcion":
        return funcion(e["nombre"], [_canon(a, ctx) for a in e["argumentos"]], ctx)
    if t == "llamada":
        return llamada(e["funcionId"], [_canon(a, ctx) for a in e["argumentos"]])
    if t == "derivada":
        return derivada(_canon(e["expresion"], ctx), e["respecto"], e["orden"], ctx)
    if t in ("gradiente", "divergencia", "laplaciano"):
        return operador(t, _canon(e["expresion"], ctx), e["coordenadas"], ctx)
    raise ErrorAlgebraico("operador", f"operador no admitido: {t}")


# --- Forma canonica -> AST ---------------------------------------------------

def ast_numero(q):
    q = fraccion(q)
    v = numero_json(q)
    if v is not None:
        return {"tipo": "numero", "valor": v}
    return {"tipo": "cociente", "numerador": {"tipo": "numero", "valor": q.numerator},
            "denominador": {"tipo": "numero", "valor": q.denominator}}


def _producto(fs):
    plano = []
    for f in fs:
        plano.extend(f["argumentos"] if f["tipo"] == "producto" else [f])
    return plano[0] if len(plano) == 1 else {"tipo": "producto", "argumentos": plano}


def negar_ast(e):
    if e["tipo"] == "numero":
        return {"tipo": "numero", "valor": -e["valor"]}
    if e["tipo"] == "producto" and e["argumentos"][0]["tipo"] == "numero":
        primero = e["argumentos"][0]
        resto = e["argumentos"][1:]
        if primero["valor"] == -1:
            return _producto(resto)
        return _producto([{"tipo": "numero", "valor": -primero["valor"]}] + resto)
    return _producto([{"tipo": "numero", "valor": -1}, e])


def _potencia_ast(base, e):
    if e == 1:
        return base
    return {"tipo": "potencia", "base": base, "exponente": ast_numero(e)}


def ast_atomo(a):
    t = a[0]
    if t == "s":
        return {"tipo": "simbolo", "id": a[1]}
    if t == "n":
        return {"tipo": "numero", "valor": a[1]}
    if t == "f":
        return {"tipo": "funcion", "nombre": a[1], "argumentos": [ast(p) for p in a[2]]}
    if t == "c":
        return {"tipo": "llamada", "funcionId": a[1], "argumentos": [ast(p) for p in a[2]]}
    if t == "d":
        return {"tipo": "derivada", "expresion": ast(a[1]), "respecto": a[2], "orden": a[3]}
    if t == "o":
        return {"tipo": a[1], "expresion": ast(a[2]), "coordenadas": list(a[3])}
    if t == "b":
        return ast(a[1])
    if t == "p":
        return {"tipo": "potencia", "base": ast(a[1]), "exponente": ast(a[2])}
    raise ValueError(t)


def ast_monomio(c, m):
    num, den = [], []
    for a, e in m:
        (num if e > 0 else den).append(_potencia_ast(ast_atomo(a), abs(e)))
    mag = abs(c)
    coef_num, coef_den = Fraction(mag.numerator), Fraction(mag.denominator)
    if coef_num != 1 or not num:
        num.insert(0, ast_numero(coef_num))
    if coef_den != 1:
        den.insert(0, ast_numero(coef_den))
    expr = _producto(num)
    if den:
        expr = {"tipo": "cociente", "numerador": expr, "denominador": _producto(den)}
    return negar_ast(expr) if c < 0 else expr


def ast(p):
    if p.es_cero:
        return {"tipo": "numero", "valor": 0}
    terminos = [ast_monomio(c, m) for m, c in p.ordenados()]
    return terminos[0] if len(terminos) == 1 else {"tipo": "suma", "argumentos": terminos}


def ast_suma(terminos):
    terminos = [t for t in terminos if not (t["tipo"] == "numero" and t["valor"] == 0)]
    if not terminos:
        return {"tipo": "numero", "valor": 0}
    return terminos[0] if len(terminos) == 1 else {"tipo": "suma", "argumentos": terminos}


# --- Sustitucion estructural sobre el AST ------------------------------------

def sustituir(e, simbolos):
    """Reemplaza simbolos por expresiones (AST). Sin evaluar texto."""
    if e["tipo"] == "simbolo":
        return simbolos.get(e["id"], e)
    return mapear_hijos(e, lambda h: sustituir(h, simbolos))


def _expandir_bases(p):
    """Desarrolla las potencias enteras positivas de sumas internas."""
    partes = []
    for m, c in p.t.items():
        resto, factores = {}, []
        for a, e in m:
            if a[0] == "b" and e > 0 and e.denominator == 1 and len(a[1].t) > 1:
                for _ in range(e.numerator):
                    factores.append(a[1])
            else:
                resto[a] = e
        partes.append(multiplicar(monomio(c, resto), *factores))
    return sumar(*partes) if partes else CERO


def es_cero(z, ctx=None, rondas=4):
    """Decide si z es identicamente nulo. Si la forma canonica no lo es, se
    multiplica por las sumas que aparecen con exponente entero negativo
    (denominadores, no nulos porque la expresion original divide por ellos)
    y se desarrolla: z = 0 si y solo si z * D = 0 con D != 0. Esto cancela
    P * P^-1 cuando P aparece una vez como base y otra desarrollada. Si no se
    llega a cero no se concluye nada (el certificado queda 'no_demostrada')."""
    for _ in range(rondas):
        if z.es_cero:
            return True
        denominadores = {}
        for m in z.t:
            for a, e in m:
                if a[0] == "b" and e < 0 and e.denominator == 1 and len(a[1].t) > 1:
                    denominadores[a] = max(denominadores.get(a, 0), -e)
        if not denominadores:
            return False
        z = _expandir_bases(multiplicar(z, monomio(1, denominadores)))
    return z.es_cero


def iguales(a, b, ctx=None):
    return a == b or es_cero(restar(a, b), ctx)


def separar_terminos(p, ctx):
    """Agrupa un polinomio por nucleo (parte que depende de variables).
    Devuelve [(nucleo_monomio, coeficiente_poli)] en orden canonico."""
    grupos = {}
    for m, c in p.t.items():
        cons = {a: e for a, e in m if atomo_constante_total(a, ctx)}
        nucleo = tuple((a, e) for a, e in m if not atomo_constante_total(a, ctx))
        grupos.setdefault(nucleo, []).append(monomio(c, cons))
    return sorted(((n, sumar(*cs)) for n, cs in grupos.items()), key=lambda nc: clave_monomio(nc[0]))
