"""
Simetrias de escala y de traslacion de la formulacion adimensional, y
reduccion exacta a EDO.

Dilataciones. Se buscan exponentes racionales (a, b_i, c_j) tales que
tau -> lambda^a tau, xi_i -> lambda^(b_i) xi_i, u_j -> lambda^(c_j) u_j
deje invariante cada ecuacion (los parametros quedan fijos). Cada monomio de
la forma canonica tiene un peso lineal en esos exponentes:

    simbolo de variable: su exponente; d^n f / dv^n: peso(f) - n peso(v);
    exp, log, sin, cos y funciones declaradas: argumento de peso 0;
    abs, min, max y potencias: el peso de su base (homogenea).

La invariancia exige el mismo peso en todos los monomios de cada ecuacion y
peso cero dentro de las funciones. El espacio nulo racional de esas
restricciones son los generadores (exacto).

Reduccion de semejanza (un tiempo y una coordenada). Con un generador con
a != 0: eta = xi tau^(-q), u_j = tau^(p_j) F_j(eta), q = b/a, p_j = c_j/a.
Las derivadas se sustituyen con  d/dxi = tau^(-q) d/deta  y
d/dtau|_xi = d/dtau|_eta - q eta tau^(-1) d/deta.  La reduccion solo se
publica si TODOS los monomios de cada ecuacion quedan con la misma potencia
de tau (se comprueba): entonces se divide y queda una EDO en eta.

Onda viajera. Si ni tau ni xi aparecen explicitamente, u_j = F_j(z),
z = xi - c tau, con d/dxi = d/dz y d/dtau = -c d/dz.
"""

from fractions import Fraction

from . import algebra as A
from .estudio import _explicitos, estado
from .racional import entero_primitivo, espacio_nulo


class _Pesos:
    def __init__(self, columnas, var_col):
        self.columnas = columnas
        self.var_col = var_col  # id -> columna
        self.restricciones = []

    def atomo(self, a):
        t = a[0]
        if t == "s":
            c = self.var_col.get(a[1])
            return {c: Fraction(1)} if c else {}
        if t == "n":
            return {}
        if t == "d":
            w = self.homogeneo(a[1])
            c = self.var_col.get(a[2])
            if c:
                w = dict(w)
                w[c] = w.get(c, 0) - a[3]
            return _limpio(w)
        if t == "f":
            if a[1] in ("exp", "log", "sin", "cos", "tan", "tanh", "sinh", "cosh", "atan", "erf"):
                self.cero(a[2][0])
                return {}
            pesos = [self.homogeneo(p) for p in a[2]]
            for w in pesos[1:]:
                self.igual(w, pesos[0])
            return pesos[0]
        if t == "c":
            for p in a[2]:
                self.cero(p)
            return {}
        if t == "b":
            return self.homogeneo(a[1])
        if t == "p":
            self.cero(a[1])
            self.cero(a[2])
            return {}
        if t == "o":
            raise A.NoSoportado("operador", "operador sin desarrollar")
        return {}

    def monomio(self, m):
        w = {}
        for a, e in m:
            for c, x in self.atomo(a).items():
                w[c] = w.get(c, 0) + e * x
        return _limpio(w)

    def homogeneo(self, P):
        pesos = [self.monomio(m) for m in P.t]
        if not pesos:
            return {}
        for w in pesos[1:]:
            self.igual(w, pesos[0])
        return pesos[0]

    def cero(self, P):
        for m in P.t:
            w = self.monomio(m)
            if w:
                self.restricciones.append(w)

    def igual(self, w1, w2):
        d = dict(w1)
        for c, x in w2.items():
            d[c] = d.get(c, 0) - x
        d = _limpio(d)
        if d:
            self.restricciones.append(d)


def _limpio(w):
    return {k: v for k, v in w.items() if v != 0}


def _residuos(cx):
    """Residuo canonico (izquierda - derecha) de cada ecuacion publicada."""
    r = []
    for ec in cx.cuerpo["ecuaciones"]:
        ig = ec["igualdad"]
        r.append((ig["id"], A.canonica({"tipo": "suma", "argumentos": [ig["izquierda"], A.negar_ast(ig["derecha"])]}, cx.ctx, "expandir")))
    return r


def _unico(base, ocupados):
    x, k = base, 2
    while x in ocupados:
        x, k = f"{base}{k}", k + 1
    ocupados.add(x)
    return x


def analizar(cx, sistema=None):
    residuos = _residuos(cx)
    variables = ([cx.tiempo] if cx.tiempo else []) + list(cx.coordenadas) + list(cx.campos)
    presentes = set()
    for _, R in residuos:
        presentes |= _variables_en(R, set(variables))
    variables = [v for v in variables if v in presentes]
    columnas = [f"c:{v}" for v in variables if v in cx.campos] + [f"b:{v}" for v in variables if v in cx.coordenadas] + \
               ([f"a:{cx.tiempo}"] if cx.tiempo in variables else [])
    var_col = {v: next(c for c in columnas if c.endswith(":" + v)) for v in variables}
    pesos = _Pesos(columnas, var_col)
    for _, R in residuos:
        pesos.homogeneo(R)
    base, rango = espacio_nulo(pesos.restricciones, columnas)
    generadores = []
    for v in base:
        v = entero_primitivo(v)
        clave_t = f"a:{cx.tiempo}"
        if v.get(clave_t, 0) < 0 or (not v.get(clave_t) and next((x for x in v.values() if x), 1) < 0):
            v = {k: -x for k, x in v.items()}
        generadores.append({"exponentes": {c.split(":", 1)[1]: {"n": int(x.numerator), "d": int(x.denominator)} for c, x in v.items()},
                            "_v": v})
    indep = set(cx.coordenadas) | ({cx.tiempo} if cx.tiempo else set())
    explicitos = set()
    for _, R in residuos:
        explicitos |= _explicitos(R, indep)
    traslaciones = [v for v in ([cx.tiempo] if cx.tiempo else []) + list(cx.coordenadas) if v in presentes and v not in explicitos]
    r = {"estado": "calculado",
         "motivo": "pesos exactos de cada monomio de la forma canonica; espacio nulo racional de las restricciones de invariancia",
         "variables": variables, "generadores": [{"exponentes": g["exponentes"]} for g in generadores],
         "rangoRestricciones": rango, "traslaciones": traslaciones, "reducciones": []}
    lineal = [g for g in generadores if all(not k.startswith(("a:", "b:")) for k in g["_v"])]
    if lineal:
        r["nota"] = "hay escalados solo de los campos (ecuaciones homogeneas en ellos): por linealidad, la potencia de tau del ansatz se puede elegir libremente"
    coords_activas = [c for c in cx.coordenadas if c in presentes]
    if cx.tiempo in presentes and len(coords_activas) == 1:
        xi = coords_activas[0]
        for g in generadores:
            v = g["_v"]
            a = v.get(f"a:{cx.tiempo}", 0)
            if a == 0:
                continue
            q = Fraction(v.get(f"b:{xi}", 0)) / a
            if q == 0:
                continue
            p = {u: Fraction(v.get(f"c:{u}", 0)) / a for u in cx.campos if u in presentes}
            r["reducciones"].append(_semejanza(cx, residuos, xi, q, p))
        if cx.tiempo in traslaciones and xi in traslaciones:
            r["reducciones"].append(_onda(cx, residuos, xi))
    elif cx.tiempo in presentes and len(coords_activas) > 1:
        r["notaReduccion"] = "la reduccion a EDO se publica solo con una coordenada activa"
    return r


def _variables_en(P, variables):
    r = set()
    for m in P.t:
        for a, _ in m:
            r |= _variables_atomo(a, variables)
    return r


def _variables_atomo(a, variables):
    t = a[0]
    if t == "s":
        return {a[1]} & variables
    if t == "d":
        return _variables_en(a[1], variables) | ({a[2]} & variables)
    if t in ("f", "c"):
        return {x for p in a[2] for x in _variables_en(p, variables)}
    if t == "b":
        return _variables_en(a[1], variables)
    if t == "p":
        return _variables_en(a[1], variables) | _variables_en(a[2], variables)
    if t == "o":
        return _variables_en(a[2], variables) | (set(a[3]) & variables)
    return set()


class _Sustitucion:
    """Sustituye campos y derivadas en una forma canonica."""

    def __init__(self, ctx, campo_por, derivar_por, explicitos):
        self.ctx = ctx
        self.campo_por = campo_por        # campo -> Poli
        self.derivar_por = derivar_por    # variable -> funcion(Poli) -> Poli
        self.explicitos = explicitos      # variable independiente -> Poli

    def poli(self, P):
        total = A.CERO
        for m, c in P.t.items():
            t = A.numero(c)
            for a, e in m:
                t = A.multiplicar(t, A.potencia(self.atomo(a), e, self.ctx))
            total = A.sumar(total, t)
        return total

    def atomo(self, a):
        t = a[0]
        if t == "s":
            if a[1] in self.campo_por:
                return self.campo_por[a[1]]
            if a[1] in self.explicitos:
                return self.explicitos[a[1]]
            return A.atomo(a)
        if t == "n":
            return A.atomo(a)
        if t == "d":
            E = self.poli(a[1])
            f = self.derivar_por.get(a[2])
            if f is None:
                raise A.NoSoportado("derivada", f"derivada respecto de {a[2]} fuera de la reduccion")
            for _ in range(a[3]):
                E = f(E)
            return E
        if t == "f":
            return A.funcion(a[1], [self.poli(p) for p in a[2]], self.ctx)
        if t == "c":
            return A.llamada(a[1], [self.poli(p) for p in a[2]])
        if t == "b":
            return self.poli(a[1])
        if t == "p":
            return A.potencia_general(self.poli(a[1]), self.poli(a[2]), self.ctx)
        raise A.NoSoportado("operador", "operador sin desarrollar")


def _contexto_reducido(cx, nuevos_campos, coord, tiempo=None, extras=None):
    simbolos = {k: dict(v) for k, v in cx.ctx.simbolos.items()}
    for f in nuevos_campos:
        simbolos[f] = {"rol": "campo", "constante": False, "dependeDe": {coord}, "signo": "desconocido"}
    simbolos[coord] = {"rol": "coordenada", "constante": False, "dependeDe": set(), "signo": "desconocido"}
    if tiempo:
        simbolos[tiempo] = {"rol": "tiempo", "constante": False, "dependeDe": set(), "signo": "positivo"}
    for k, v in (extras or {}).items():
        simbolos[k] = v
    return A.Contexto(simbolos, dict(cx.ctx.funciones))


def _semejanza(cx, residuos, xi, q, p):
    ocupados = set(cx.ctx.simbolos) | set(cx.campos) | set(cx.coordenadas)
    eta = _unico("eta", ocupados)
    Fs = {u: _unico(f"F_{u}", ocupados) for u in p}
    tau = cx.tiempo
    ctx = _contexto_reducido(cx, list(Fs.values()), eta, tau)
    tau_q = lambda e: A.monomio(1, {("s", tau): Fraction(e)})  # noqa: E731
    deta = lambda E: A.derivada_expandida(E, eta, ctx)  # noqa: E731

    def Dxi(E):
        return A.multiplicar(tau_q(-q), deta(E))

    def Dtau(E):
        parcial = A.derivada_expandida(E, tau, ctx)
        return A.restar(parcial, A.multiplicar(A.monomio(q, {("s", eta): Fraction(1), ("s", tau): Fraction(-1)}), deta(E)))
    campo_por = {u: A.monomio(1, {("s", tau): p[u], ("s", Fs[u]): Fraction(1)}) for u in p}
    sus = _Sustitucion(ctx, campo_por, {xi: Dxi, tau: Dtau}, {xi: A.monomio(1, {("s", eta): Fraction(1), ("s", tau): q})})
    ecuaciones, comprobado = [], True
    for eid, R in residuos:
        try:
            Rs = sus.poli(R)
        except A.NoSoportado as e:
            return {"tipo": "semejanza", "estado": "no_soportado", "motivo": e.mensaje}
        exps = set()
        for m in Rs.t:
            e_tau = sum((e for a, e in m if a == ("s", tau)), Fraction(0))
            otros = any(tau in _variables_atomo(a, {tau}) for a, _ in m if a != ("s", tau))
            if otros:
                comprobado = False
            exps.add(e_tau)
        if len(exps) > 1:
            comprobado = False
        w = next(iter(exps)) if exps else Fraction(0)
        ode = A.multiplicar(Rs, A.monomio(1, {("s", tau): -w}))
        ecuaciones.append({"id": eid, "potenciaTau": {"n": w.numerator, "d": w.denominator},
                           "ecuacion": {"id": eid, "izquierda": A.ast(ode), "derecha": {"tipo": "numero", "valor": 0}}})
    q_ast = A.ast(A.numero(q))
    return {"tipo": "semejanza", "estado": "calculado" if comprobado else "no_demostrada",
            "motivo": "cada monomio de cada ecuacion queda con la misma potencia de tau" if comprobado else "algun monomio conserva tau: el generador no reduce la ecuacion",
            "variable": {"id": eta, "definicion": {"tipo": "producto", "argumentos": [{"tipo": "simbolo", "id": xi},
                                                                                      {"tipo": "potencia", "base": {"tipo": "simbolo", "id": tau}, "exponente": A.negar_ast(q_ast)}]}},
            "perfiles": [{"campo": u, "id": Fs[u], "potenciaTau": {"n": p[u].numerator, "d": p[u].denominator}} for u in p],
            "ecuaciones": ecuaciones}


def _onda(cx, residuos, xi):
    ocupados = set(cx.ctx.simbolos) | set(cx.campos) | set(cx.coordenadas)
    z = _unico("z", ocupados)
    c = _unico("c_onda", ocupados)
    campos = [u for u in cx.campos]
    Fs = {u: _unico(f"F_{u}", ocupados) for u in campos}
    ctx = _contexto_reducido(cx, list(Fs.values()), z, extras={c: {"rol": "parametro", "constante": True, "dependeDe": set(), "signo": "desconocido"}})
    dz = lambda E: A.derivada_expandida(E, z, ctx)  # noqa: E731

    def Dtau(E):
        return A.multiplicar(A.monomio(-1, {("s", c): Fraction(1)}), dz(E))
    sus = _Sustitucion(ctx, {u: A.atomo(("s", Fs[u])) for u in campos}, {xi: dz, cx.tiempo: Dtau}, {})
    ecuaciones = []
    for eid, R in residuos:
        try:
            Rs = sus.poli(R)
        except A.NoSoportado as e:
            return {"tipo": "onda_viajera", "estado": "no_soportado", "motivo": e.mensaje}
        ecuaciones.append({"id": eid, "ecuacion": {"id": eid, "izquierda": A.ast(Rs), "derecha": {"tipo": "numero", "valor": 0}}})
    return {"tipo": "onda_viajera", "estado": "calculado",
            "motivo": "el sistema es autonomo en tau y en la coordenada: u = F(z), z = xi - c tau, con c la velocidad (incognita)",
            "variable": {"id": z, "definicion": {"tipo": "suma", "argumentos": [{"tipo": "simbolo", "id": xi},
                                                                              A.negar_ast({"tipo": "producto", "argumentos": [{"tipo": "simbolo", "id": c}, {"tipo": "simbolo", "id": cx.tiempo}]})]}},
            "velocidad": c, "perfiles": [{"campo": u, "id": Fs[u]} for u in campos], "ecuaciones": ecuaciones}


_ = estado
