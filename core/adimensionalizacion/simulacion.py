"""
Simulacion de la formulacion adimensional publicada (la del usuario, no un
modelo de ejemplo), por el metodo de lineas.

  - Una coordenada activa (o ninguna: sistema de EDO). Nodos uniformes en el
    dominio transformado, extremos incluidos.
  - Derivadas espaciales de orden 1 y 2 con diferencias centradas de segundo
    orden. El numero de nodos por omision es el recomendado por el analisis de
    escalas (Peclet de celda <= 2 y 10 nodos por longitud interna), de modo que
    las diferencias centradas no oscilen.
  - Condiciones de frontera: las condiciones declaradas, en el extremo que
    indica su ubicacion (documento v2) o `simulacion.fronteras`. En cada
    evaluacion se resuelven, por Newton con jacobiano de paso complejo, las
    incognitas de cada extremo: el valor del campo si la condicion no tiene
    derivada (Dirichlet: el nodo sale del estado) o un nodo fantasma si la
    tiene (flujo, Robin).
  - Frontera periodica (`simulacion.periodica`): N nodos en [a, b), el nodo
    b coincide con a; no admite condiciones de extremo declaradas.
  - Condicion inicial: la condicion `inicial` de cada campo, despejada (debe
    ser lineal en el campo; puede depender de xi).
  - Tiempo final: `tFinal` en tiempo adimensional o `tFinalSI` en segundos,
    convertido con la inversa publicada del mapa del tiempo.
  - Integracion BDF de orden variable (scipy) con patron de dispersion del
    jacobiano. Tolerancias publicadas.
  - Verificacion: se repite con la malla refinada (2N - 1 nodos, que contiene
    los nodos originales) y se publica la diferencia relativa al final: es una
    estimacion del error espacial, no una cota.
"""

import math

import numpy as np
from scipy.integrate import solve_ivp
from scipy.sparse import lil_matrix

from . import dinamica
from .estudio import clave_derivada, estado, requiere
from .numerico import NoEvaluable, evaluar_poli, numero_json

H = 1e-30
MAX_NODOS = 801


def _residuo(terminos, vals, derivadas):
    total = 0.0
    for t in terminos:
        total = total + t.signo * t.coef * evaluar_poli(t.P, vals, derivadas)
    return total


class _Problema:
    def __init__(self, cx, sistema, N, coord, periodica=False):
        self.cx, self.sistema, self.coord = cx, sistema, coord
        self.campos = [item["campo"] for item in sistema.evolucion]
        self.n = len(self.campos)
        self.N = N
        self.periodica = bool(coord) and periodica
        if coord:
            dom = sistema.dominios[coord]
            self.xi = np.linspace(dom["desde"], dom["hasta"], N, endpoint=not self.periodica)
            self.h = self.xi[1] - self.xi[0]
        else:
            self.xi, self.h = None, None
        self.ordenes = {}
        for item in sistema.evolucion:
            self.ordenes[item["campo"]] = max((t.clase["ordenEspacial"] for t in item["resto"]), default=0)

    # --- fronteras --------------------------------------------------------
    def preparar_fronteras(self, ubicaciones):
        """Asigna condiciones a extremos e incognitas a cada extremo."""
        self.extremos = {"desde": [], "hasta": []}
        if self.periodica:
            sobran = [c["id"] for c in self.sistema.condiciones if c["tipo"] != "inicial"]
            if sobran:
                raise _Falta("con frontera periodica no se declaran condiciones de extremo; sobran " + ", ".join(sobran))
            self.incognitas = {"desde": [], "hasta": []}
            self.dirichlet = {"desde": set(), "hasta": set()}
            self.indices = {u: (k * self.N, list(range(self.N))) for k, u in enumerate(self.campos)}
            self.tam = self.n * self.N
            self.previo = {"desde": np.zeros(0), "hasta": np.zeros(0)}
            return
        for c in self.sistema.condiciones:
            if c["tipo"] == "inicial":
                continue
            lado = ubicaciones.get(c["id"])
            if lado is None:
                raise _Falta(f"la condicion {c['id']} no tiene ubicacion: declare su extremo (documento v2 o simulacion.fronteras)")
            self.extremos[lado].append(c)
        self.incognitas = {}
        self.dirichlet = {"desde": set(), "hasta": set()}
        for lado in ("desde", "hasta"):
            conds = self.extremos[lado]
            con_derivada = set()
            sin_derivada = set()
            for c in conds:
                tiene = any(t.clase["ordenEspacial"] for t in c["terminos"])
                campos = {f for t in c["terminos"] for f in t.clase["campos"]}
                (con_derivada if tiene else sin_derivada).update(campos)
            requeridos = [u for u in self.campos if self.ordenes[u] == 2]
            incogs = []
            for u in self.campos:
                if u in con_derivada:
                    incogs.append(("fantasma", u))
                elif u in sin_derivada:
                    incogs.append(("valor", u))
                    self.dirichlet[lado].add(u)
            faltan = [u for u in requeridos if all(x[1] != u for x in incogs)]
            if faltan:
                raise _Falta(f"en el extremo '{lado}' falta una condicion para {', '.join(faltan)} (difusion de segundo orden)")
            if len(conds) != len(incogs):
                raise _Falta(f"en el extremo '{lado}' hay {len(conds)} condiciones para {len(incogs)} incognitas de frontera")
            self.incognitas[lado] = incogs
        # Estado: todos los nodos de cada campo menos los de Dirichlet.
        self.indices = {}
        k = 0
        for u in self.campos:
            nodos = [i for i in range(self.N)
                     if not ((i == 0 and u in self.dirichlet["desde"]) or (i == self.N - 1 and u in self.dirichlet["hasta"]))]
            self.indices[u] = (k, nodos)
            k += len(nodos)
        self.tam = k
        self.previo = {lado: np.zeros(len(self.incognitas[lado])) for lado in ("desde", "hasta")}

    def _arreglos(self, y, t):
        """Campos en todos los nodos + fantasmas resolviendo las fronteras."""
        U = {}
        for u in self.campos:
            k, nodos = self.indices[u]
            arr = np.empty(self.N, dtype=y.dtype)
            arr[nodos] = y[k:k + len(nodos)]
            # Provisional para un nodo de Dirichlet: lo fija la condicion abajo.
            if 0 not in nodos:
                arr[0] = arr[1]
            if self.N - 1 not in nodos:
                arr[-1] = arr[-2]
            U[u] = arr
        fantasmas = {}
        for lado in ("desde", "hasta"):
            incogs = self.incognitas[lado]
            if not incogs:
                continue
            x = self._resolver_extremo(lado, U, t, self.previo[lado])
            self.previo[lado] = x
            for (tipo, u), v in zip(incogs, x):
                if tipo == "valor":
                    U[u] = U[u].copy()
                    U[u][0 if lado == "desde" else -1] = v
                else:
                    fantasmas[(u, lado)] = v
        ext = {}
        if self.periodica:
            for u in self.campos:
                ext[u] = np.concatenate([U[u][-1:], U[u], U[u][:1]])
            return U, ext
        for u in self.campos:
            arr = U[u]
            izq = fantasmas.get((u, "desde"))
            der = fantasmas.get((u, "hasta"))
            if izq is None:
                izq = 2 * arr[0] - arr[1] if self.ordenes[u] else arr[0]
            if der is None:
                der = 2 * arr[-1] - arr[-2] if self.ordenes[u] else arr[-1]
            ext[u] = np.concatenate([[izq], arr, [der]])
        return U, ext

    def _derivadas_en(self, ext, idx):
        """Callback de derivadas en los nodos idx (indices de nodo)."""
        h = self.h
        coord, campos = self.coord, set(self.campos)

        def derivadas(a):
            clave = clave_derivada(a, campos)
            if clave is None or clave[1] != coord:
                raise NoEvaluable("derivada", "derivada no admitida en la simulacion (funcion declarada, mixta o de otra variable)")
            u, _, orden = clave
            e = ext[u]
            i = np.asarray(idx) + 1
            if orden == 1:
                return (e[i + 1] - e[i - 1]) / (2 * h)
            if orden == 2:
                return (e[i + 1] - 2 * e[i] + e[i - 1]) / h ** 2
            raise NoEvaluable("orden", "derivadas de orden mayor que 2 no se discretizan")
        return derivadas

    def _resolver_extremo(self, lado, U, t, x0):
        incogs = self.incognitas[lado]
        nodo = 0 if lado == "desde" else self.N - 1
        conds = self.extremos[lado]

        def residuos(x):
            V = {u: U[u].astype(complex if np.iscomplexobj(x) else U[u].dtype).copy() for u in self.campos}
            fant = {}
            for (tipo, u), v in zip(incogs, x):
                if tipo == "valor":
                    V[u][nodo] = v
                else:
                    fant[u] = v
            vals = dict(self.cx.valores)
            vals.update({u: V[u][nodo] for u in self.campos})
            vals[self.coord] = self.xi[nodo]
            if self.cx.tiempo:
                vals[self.cx.tiempo] = t
            h = self.h

            def derivadas(a):
                clave = clave_derivada(a, set(self.campos))
                if clave is None or clave[1] != self.coord or clave[2] != 1:
                    raise NoEvaluable("derivada", "una condicion de frontera solo admite derivadas primeras de los campos")
                u = clave[0]
                arr = V[u]
                if lado == "desde":
                    g = fant.get(u, 2 * arr[0] - arr[1])
                    return (arr[1] - g) / (2 * h)
                g = fant.get(u, 2 * arr[-1] - arr[-2])
                return (g - arr[-2]) / (2 * h)
            return np.array([_residuo(c["terminos"], vals, derivadas) for c in conds])

        x = np.array(x0, dtype=float)
        for _ in range(30):
            r = residuos(x)
            if np.max(np.abs(r)) < 1e-13 * max(1.0, np.max(np.abs(x))):
                break
            J = self._jac_extremo(residuos, x)
            dx = np.linalg.solve(J, -r)
            x = x + dx
            if np.max(np.abs(dx)) < 1e-14 * max(1.0, np.max(np.abs(x))):
                break
        return x

    @staticmethod
    def _jac_extremo(residuos, x):
        n = len(x)
        J = np.zeros((n, n))
        for j in range(n):
            z = np.array(x, dtype=complex)
            z[j] += 1j * H
            J[:, j] = np.imag(residuos(z)) / H
        return J

    # --- miembro derecho --------------------------------------------------------
    def rhs(self, t, y):
        U, ext = self._arreglos(y, t)
        dy = np.empty(self.tam, dtype=y.dtype)
        for item in self.sistema.evolucion:
            u = item["campo"]
            k, nodos = self.indices[u]
            vals = dict(self.cx.valores)
            vals.update({c: U[c][nodos] for c in self.campos})
            if self.coord:
                vals[self.coord] = self.xi[nodos]
            if self.cx.tiempo:
                vals[self.cx.tiempo] = t
            derivadas = self._derivadas_en(ext, nodos) if self.coord else _sin_derivadas
            total = 0.0
            for term in item["resto"]:
                total = total - term.signo * term.coef * evaluar_poli(term.P, vals, derivadas)
            dy[k:k + len(nodos)] = np.broadcast_to(total / self.sistema.masa(item), (len(nodos),))
        return dy

    def patron(self):
        S = lil_matrix((self.tam, self.tam))
        posicion = {}
        for u in self.campos:
            k, nodos = self.indices[u]
            for j, i in enumerate(nodos):
                posicion[(u, i)] = k + j
        for u in self.campos:
            k, nodos = self.indices[u]
            for j, i in enumerate(nodos):
                fila = k + j
                for v in self.campos:
                    for d in range(-2, 3):
                        p = posicion.get((v, (i + d) % self.N if self.periodica else i + d))
                        if p is not None:
                            S[fila, p] = 1
                    # Los nodos cercanos a un extremo dependen del extremo entero.
                    if i <= 2 or i >= self.N - 3:
                        for d in range(0, 3):
                            for extremo in (d, self.N - 1 - d):
                                p = posicion.get((v, extremo))
                                if p is not None:
                                    S[fila, p] = 1
        return S


class _Falta(Exception):
    pass


def _sin_derivadas(a):
    raise NoEvaluable("derivada", "derivada espacial sin coordenada")


def _iniciales(cx, sistema, prob):
    """u_j(xi, 0) despejando la condicion inicial (lineal en el campo)."""
    U0 = {}
    for c in sistema.condiciones:
        if c["tipo"] != "inicial":
            continue
        campos = sorted({f for t in c["terminos"] for f in t.clase["campos"]})
        if len(campos) != 1 or any(t.clase["ordenEspacial"] or t.clase["ordenTemporal"] for t in c["terminos"]):
            raise NoEvaluable("inicial", f"la condicion inicial {c['id']} debe contener un solo campo y ninguna derivada")
        u = campos[0]
        vals = dict(cx.valores)
        if prob.coord:
            vals[prob.coord] = prob.xi
        if cx.tiempo:
            vals[cx.tiempo] = 0.0
        r = []
        for x in (0.0, 1.0, 2.0):
            vals[u] = np.full(prob.N if prob.coord else 1, x)
            r.append(np.asarray(_residuo(c["terminos"], vals, None), dtype=float) * np.ones(prob.N if prob.coord else 1))
        if np.max(np.abs(r[2] - 2 * r[1] + r[0])) > 1e-10 * max(1.0, np.max(np.abs(r[1]))):
            raise NoEvaluable("inicial", f"la condicion inicial {c['id']} no es lineal en {u}")
        pendiente = r[1] - r[0]
        if np.any(pendiente == 0):
            raise NoEvaluable("inicial", f"la condicion inicial {c['id']} no determina {u}")
        U0[u] = -r[0] / pendiente
    faltan = [u for u in prob.campos if u not in U0]
    if faltan:
        raise _Falta("falta la condicion inicial de " + ", ".join(faltan))
    return U0


def _integrar(cx, sistema, N, coord, tf, muestras, rtol, atol, ubicaciones, periodica=False):
    prob = _Problema(cx, sistema, N, coord, periodica)
    if coord:
        prob.preparar_fronteras(ubicaciones)
    else:
        prob.indices = {u: (i, [0]) for i, u in enumerate(prob.campos)}
        prob.tam = prob.n
        prob.incognitas = {"desde": [], "hasta": []}
        prob.previo = {"desde": np.zeros(0), "hasta": np.zeros(0)}
    U0 = _iniciales(cx, sistema, prob)
    y0 = np.zeros(prob.tam)
    for u in prob.campos:
        k, nodos = prob.indices[u]
        y0[k:k + len(nodos)] = np.broadcast_to(U0[u], (prob.N if coord else 1,))[nodos]
    ts = np.linspace(0.0, tf, muestras)
    opciones = {"method": "BDF", "t_eval": ts, "rtol": rtol, "atol": atol}
    if coord:
        opciones["jac_sparsity"] = prob.patron()
    with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
        try:
            sol = solve_ivp(prob.rhs, (0.0, tf), y0, **opciones)
        except FloatingPointError as e:
            return prob, None, f"desbordamiento numerico: {e}"
    if not sol.success:
        return prob, sol, sol.message
    return prob, sol, None


def _perfiles(prob, sol):
    series = {u: [] for u in prob.campos}
    for j in range(sol.y.shape[1]):
        U, _ = prob._arreglos(sol.y[:, j], sol.t[j])
        for u in prob.campos:
            series[u].append(np.asarray(U[u], dtype=float))
    return series


def simular(cx, sistema):
    if sistema.evolucion is None:
        return estado("no_soportado", "la formulacion no esta en forma de evolucion: " + "; ".join(sistema.problemas[:3]))
    falta = requiere(sistema)
    if falta:
        return falta
    op = cx.opciones.get("simulacion", {}) or {}
    coords = [c for c in cx.coordenadas if any(c in {v for v, o, _ in _derivs(t)} for item in sistema.evolucion for t in item["resto"])]
    if len(coords) > 1:
        return estado("no_soportado", "la simulacion admite una coordenada activa; hay " + ", ".join(coords))
    coord = coords[0] if coords else None
    if coord and (coord not in sistema.dominios or sistema.dominios[coord]["desde"] is None):
        return estado("requiere_datos", f"falta el dominio de {coord}")
    if any(o > 2 for o in (max((t.clase["ordenEspacial"] for t in item["resto"]), default=0) for item in sistema.evolucion)):
        return estado("no_soportado", "derivadas espaciales de orden mayor que 2")
    ubicaciones = {c["id"]: c["lugar"]["extremo"] for c in sistema.condiciones if c.get("lugar")}
    for x in op.get("fronteras", []):
        ubicaciones[x["condicionId"]] = x["extremo"]
    N = op.get("nodos")
    nota_malla = None
    if coord and N is None:
        try:
            esc = dinamica.escalas(cx, sistema)
            rec = next((c.get("malla", {}).get("nodosRecomendados") for c in esc.get("coordenadas", []) if c.get("coordenada") == coord), None)
        except NoEvaluable:
            rec = None
        N = rec or 101
        if N > MAX_NODOS:
            nota_malla = f"la malla recomendada ({N} nodos) supera el maximo de {MAX_NODOS}: el Peclet de celda puede superar 2 y producir oscilaciones"
            N = MAX_NODOS
    N = int(N or 1)
    periodica = bool(coord) and bool(op.get("periodica"))
    if "tFinalSI" in op:
        try:
            tf = _tau_de(cx, float(op["tFinalSI"]))
        except NoEvaluable as e:
            return estado("requiere_datos", "no se puede convertir tFinalSI al tiempo adimensional: " + e.mensaje)
        if not (tf > 0 and math.isfinite(tf)):
            return estado("requiere_datos", "tFinalSI no corresponde a un tiempo adimensional positivo")
    else:
        tf = float(op.get("tFinal", 1.0))
    muestras = int(op.get("muestras", 41))
    rtol, atol = float(op.get("rtol", 1e-6)), float(op.get("atol", 1e-9))
    try:
        prob, sol, error = _integrar(cx, sistema, N, coord, tf, muestras, rtol, atol, ubicaciones, periodica)
    except _Falta as e:
        return estado("requiere_datos", str(e))
    if error:
        return estado("no_convergente", f"la integracion se detuvo: {error}")
    series = _perfiles(prob, sol)
    r = {"estado": "calculado",
         "motivo": "metodo de lineas: diferencias centradas de segundo orden, condiciones declaradas resueltas en cada evaluacion, integracion BDF",
         "metodo": {"integrador": "BDF (scipy.solve_ivp)", "rtol": rtol, "atol": atol, "nodos": N, "evaluaciones": int(sol.nfev),
                    "jacobianos": int(sol.njev), "tFinal": tf, **({"frontera": "periodica"} if periodica else {})},
         "coordenada": coord, "xi": prob.xi.tolist() if coord else None, "tiempos": sol.t.tolist(),
         "campos": {u: [x.tolist() for x in series[u]] for u in prob.campos}}
    if nota_malla:
        r["avisoMalla"] = nota_malla
    fino_N = 2 * N if periodica else 2 * N - 1
    if coord and op.get("verificarMalla", True) and fino_N <= MAX_NODOS * 2:
        try:
            prob2, sol2, error2 = _integrar(cx, sistema, fino_N, coord, tf, 2, rtol, atol, ubicaciones, periodica)
        except (_Falta, NoEvaluable):
            error2 = "no se pudo repetir con la malla refinada"
            sol2 = None
        if error2 is None and sol2 is not None:
            fino = _perfiles(prob2, sol2)
            dif, escala = 0.0, 0.0
            for u in prob.campos:
                a = series[u][-1]
                b = fino[u][-1][::2]
                dif = max(dif, float(np.max(np.abs(a - b))))
                escala = max(escala, float(np.max(np.abs(b))))
            r["verificacionMalla"] = {"nodosRefinados": fino_N, "diferenciaMaxima": dif,
                                      "diferenciaRelativa": dif / escala if escala else None,
                                      "nota": "diferencia en tau final entre la malla y su refinamiento en los nodos comunes: estimacion del error espacial"}
        else:
            r["verificacionMalla"] = {"estado": "no_calculada", "motivo": error2}
    r["fisico"] = _restitucion(cx, prob, sol, series)
    r["resultados"] = _conjunto(cx, prob, sol, series, r["fisico"], r.get("estado"))
    try:
        r["codigoPython"] = codigo_python(cx, sistema, prob, tf, muestras, rtol, atol)
    except NoEvaluable as e:
        r["codigoPython"] = None
        r["codigoMotivo"] = e.mensaje
    return r


# --- Exportacion: script de Python autonomo ---------------------------------------

def _py_poli(P, nombre, derivada):
    """Expresion de Python (numpy) de una forma canonica."""
    from fractions import Fraction
    terminos = []
    for m, c in P.ordenados():
        factores = [repr(float(c))]
        for a, e in m:
            base = _py_atomo(a, nombre, derivada)
            if e == 1:
                factores.append(base)
            elif Fraction(e).denominator == 1:
                factores.append(f"({base})**{int(e)}")
            else:
                factores.append(f"({base})**({float(e)!r})")
        terminos.append("*".join(factores))
    return "(" + " + ".join(terminos) + ")" if terminos else "0.0"


def _py_atomo(a, nombre, derivada):
    t = a[0]
    if t == "s":
        return nombre(a[1])
    if t == "n":
        return repr(float(a[1]))
    if t == "b":
        return _py_poli(a[1], nombre, derivada)
    if t == "p":
        return f"np.power({_py_poli(a[1], nombre, derivada)}, {_py_poli(a[2], nombre, derivada)})"
    if t == "f":
        args = [_py_poli(p, nombre, derivada) for p in a[2]]
        fn = {"exp": "np.exp", "log": "np.log", "sin": "np.sin", "cos": "np.cos", "tan": "np.tan", "tanh": "np.tanh",
              "sinh": "np.sinh", "cosh": "np.cosh", "atan": "np.arctan", "erf": "erf", "abs": "np.abs"}.get(a[1])
        if fn:
            return f"{fn}({args[0]})"
        if a[1] in ("min", "max"):
            r = args[0]
            for x in args[1:]:
                r = f"np.{'minimum' if a[1] == 'min' else 'maximum'}({r}, {x})"
            return r
    if t == "d":
        return derivada(a)
    raise NoEvaluable("exportacion", f"atomo sin traduccion a Python: {t} (por ejemplo, una funcion declarada sin definicion)")


def codigo_python(cx, sistema, prob, tf, muestras, rtol, atol):
    """Script autonomo (numpy + scipy) que repite la misma discretizacion."""
    campos = prob.campos
    parametros = {k: v for k, v in cx.valores.items() if isinstance(v, (int, float))}

    def nombre(sid):
        if sid in campos:
            return f"U[{sid!r}]"
        if sid == prob.coord:
            return "XI"
        if sid == cx.tiempo:
            return "T"
        if sid in parametros:
            return f"P[{sid!r}]"
        raise NoEvaluable("exportacion", f"simbolo sin valor: {sid}")
    claves = {}

    def derivada(a):
        clave = clave_derivada(a, set(campos))
        if clave is None:
            raise NoEvaluable("exportacion", "derivada no exportable (funcion declarada o derivada mixta)")
        k = "|".join(str(x) for x in clave)
        claves[k] = clave
        return f"D({k!r})"
    rhs = []
    for item in sistema.evolucion:
        partes = []
        for t in item["resto"]:
            partes.append(f"- ({t.signo * t.coef!r}) * {_py_poli(t.P, nombre, derivada)}")
        rhs.append((item["campo"], sistema.masa(item), " ".join(partes) or "0.0"))
    condiciones = []
    if prob.coord:
        for lado in ("desde", "hasta"):
            for c in prob.extremos[lado]:
                partes = [f"({t.signo * t.coef!r}) * {_py_poli(t.P, nombre, derivada)}" for t in c["terminos"]]
                condiciones.append((lado, c["id"], " + ".join(partes) or "0.0"))
    iniciales = []
    for c in sistema.condiciones:
        if c["tipo"] == "inicial":
            partes = [f"({t.signo * t.coef!r}) * {_py_poli(t.P, nombre, derivada)}" for t in c["terminos"]]
            u = sorted({f for t in c["terminos"] for f in t.clase["campos"]})[0]
            iniciales.append((u, " + ".join(partes)))
    L = []
    L.append('"""')
    L.append(f"Simulacion de la formulacion adimensional exportada por el nucleo de adimensionalizacion.")
    L.append("Metodo de lineas: diferencias centradas de segundo orden, condiciones declaradas")
    L.append("resueltas en cada evaluacion (Newton) e integracion BDF. Misma discretizacion que el")
    L.append("estudio del nucleo; los valores de los parametros estan en SI.")
    L.append('"""')
    L.append("import numpy as np")
    L.append("from scipy.integrate import solve_ivp")
    L.append("from scipy.special import erf")
    L.append("")
    L.append(f"P = {parametros!r}")
    L.append(f"CAMPOS = {campos!r}")
    L.append(f"DERIVADAS = {dict((k, v) for k, v in claves.items())!r}")
    if prob.coord:
        L.append(f"N = {prob.N}")
        L.append(f"PERIODICA = {prob.periodica!r}")
        fin = float(prob.xi[0] + prob.N * prob.h) if prob.periodica else float(prob.xi[-1])
        L.append(f"XI_TODOS = np.linspace({float(prob.xi[0])!r}, {fin!r}, N, endpoint=not PERIODICA)")
        L.append("H = XI_TODOS[1] - XI_TODOS[0]")
        L.append(f"INCOGNITAS = {prob.incognitas!r}")
        L.append(f"DIRICHLET = {{'desde': {sorted(prob.dirichlet['desde'])!r}, 'hasta': {sorted(prob.dirichlet['hasta'])!r}}}")
        L.append(f"ORDENES = {prob.ordenes!r}")
    L.append("")
    L.append("def rhs_campo(campo, U, XI, T, D):")
    for campo, masa, expr in rhs:
        L.append(f"    if campo == {campo!r}:")
        L.append(f"        return ({expr}) / {masa!r}")
    L.append("")
    if prob.coord:
        L.append("def residuos_extremo(lado, U, XI, T, D):")
        L.append("    r = []")
        for lado, cid, expr in condiciones:
            L.append(f"    if lado == {lado!r}:")
            L.append(f"        r.append({expr})  # condicion {cid}")
        L.append("    return np.array(r, dtype=complex if any(np.iscomplexobj(v) for v in U.values()) else float)")
        L.append(_MOTOR_1D)
    else:
        L.append(_MOTOR_0D)
    L.append("def condicion_inicial():")
    L.append("    U0 = {}")
    L.append("    XI = XI_TODOS if 'XI_TODOS' in globals() else 0.0")
    L.append("    T = 0.0")
    L.append("    D = lambda clave: 0.0")
    for u, expr in iniciales:
        L.append(f"    r = []")
        L.append(f"    for x in (0.0, 1.0):")
        L.append(f"        U = {{{u!r}: x * np.ones_like(np.atleast_1d(XI), dtype=float)}}")
        L.append(f"        r.append(np.atleast_1d({expr}) * np.ones_like(np.atleast_1d(XI), dtype=float))")
        L.append(f"    U0[{u!r}] = -r[0] / (r[1] - r[0])")
    L.append("    return U0")
    L.append("")
    L.append(f"TF, MUESTRAS = {tf!r}, {muestras!r}")
    L.append("sol = integrar(TF, MUESTRAS)")
    L.append("if __name__ == '__main__':")
    L.append("    print('estado:', sol.message)")
    L.append("    for c, perfil in perfiles(sol).items():")
    L.append("        print(c, 'en tau final:', np.round(perfil[-1], 6))")
    return "\n".join(L) + "\n"


_MOTOR_0D = '''
def rhs(t, y):
    U = {c: y[i] for i, c in enumerate(CAMPOS)}
    def D(clave):
        raise ValueError("derivada espacial sin coordenada")
    return np.array([rhs_campo(c, U, 0.0, t, D) for c in CAMPOS], dtype=float)

def integrar(tf, muestras):
    U0 = condicion_inicial()
    y0 = np.array([float(np.atleast_1d(U0[c])[0]) for c in CAMPOS])
    return solve_ivp(rhs, (0.0, tf), y0, method="BDF", t_eval=np.linspace(0.0, tf, muestras), rtol=1e-6, atol=1e-9)

def perfiles(sol):
    return {c: [np.array([sol.y[i, j]]) for j in range(sol.y.shape[1])] for i, c in enumerate(CAMPOS)}
'''

_MOTOR_1D = '''
INDICES = {}
_k = 0
for _c in CAMPOS:
    _nodos = [i for i in range(N) if not ((i == 0 and _c in DIRICHLET["desde"]) or (i == N - 1 and _c in DIRICHLET["hasta"]))]
    INDICES[_c] = (_k, _nodos)
    _k += len(_nodos)
TAM = _k
PREVIO = {"desde": np.zeros(len(INCOGNITAS["desde"])), "hasta": np.zeros(len(INCOGNITAS["hasta"]))}

def _resolver_extremo(lado, U, t):
    incogs = INCOGNITAS[lado]
    nodo = 0 if lado == "desde" else N - 1
    def residuos(x):
        V = {c: U[c].astype(complex if np.iscomplexobj(x) else float).copy() for c in CAMPOS}
        fant = {}
        for (tipo, c), v in zip(incogs, x):
            if tipo == "valor":
                V[c][nodo] = v
            else:
                fant[c] = v
        def D(clave):
            c = DERIVADAS[clave][0]
            arr = V[c]
            if lado == "desde":
                g = fant.get(c, 2 * arr[0] - arr[1])
                return (arr[1] - g) / (2 * H)
            g = fant.get(c, 2 * arr[-1] - arr[-2])
            return (g - arr[-2]) / (2 * H)
        return residuos_extremo(lado, {c: V[c][nodo] for c in CAMPOS}, XI_TODOS[nodo], t, D)
    x = PREVIO[lado].astype(float)
    for _ in range(30):
        r = residuos(x)
        if np.max(np.abs(r)) < 1e-13 * max(1.0, np.max(np.abs(x))):
            break
        J = np.zeros((len(x), len(x)))
        for j in range(len(x)):
            z = x.astype(complex)
            z[j] += 1e-30j
            J[:, j] = np.imag(residuos(z)) / 1e-30
        x = x + np.linalg.solve(J, -r)
    PREVIO[lado] = x
    return x

def _arreglos(y, t):
    U = {}
    for c in CAMPOS:
        k, nodos = INDICES[c]
        arr = np.empty(N)
        arr[nodos] = y[k:k + len(nodos)]
        if 0 not in nodos:
            arr[0] = arr[1]
        if N - 1 not in nodos:
            arr[-1] = arr[-2]
        U[c] = arr
    fantasmas = {}
    for lado in ("desde", "hasta"):
        if not INCOGNITAS[lado]:
            continue
        x = _resolver_extremo(lado, U, t)
        for (tipo, c), v in zip(INCOGNITAS[lado], x):
            if tipo == "valor":
                U[c][0 if lado == "desde" else -1] = v
            else:
                fantasmas[(c, lado)] = v
    ext = {}
    for c in CAMPOS:
        arr = U[c]
        if PERIODICA:
            ext[c] = np.concatenate([arr[-1:], arr, arr[:1]])
            continue
        izq = fantasmas.get((c, "desde"), 2 * arr[0] - arr[1] if ORDENES[c] else arr[0])
        der = fantasmas.get((c, "hasta"), 2 * arr[-1] - arr[-2] if ORDENES[c] else arr[-1])
        ext[c] = np.concatenate([[izq], arr, [der]])
    return U, ext

def rhs(t, y):
    U, ext = _arreglos(y, t)
    dy = np.empty(TAM)
    for c in CAMPOS:
        k, nodos = INDICES[c]
        idx = np.asarray(nodos) + 1
        def D(clave):
            campo, _, orden = DERIVADAS[clave]
            e = ext[campo]
            if orden == 1:
                return (e[idx + 1] - e[idx - 1]) / (2 * H)
            return (e[idx + 1] - 2 * e[idx] + e[idx - 1]) / H ** 2
        dy[k:k + len(nodos)] = rhs_campo(c, {d: U[d][nodos] for d in CAMPOS}, XI_TODOS[nodos], t, D)
    return dy

def integrar(tf, muestras):
    U0 = condicion_inicial()
    y0 = np.zeros(TAM)
    for c in CAMPOS:
        k, nodos = INDICES[c]
        y0[k:k + len(nodos)] = np.broadcast_to(U0[c], (N,))[nodos]
    return solve_ivp(rhs, (0.0, tf), y0, method="BDF", t_eval=np.linspace(0.0, tf, muestras), rtol=1e-6, atol=1e-9)

def perfiles(sol):
    r = {c: [] for c in CAMPOS}
    for j in range(sol.y.shape[1]):
        U, _ = _arreglos(sol.y[:, j], sol.t[j])
        for c in CAMPOS:
            r[c].append(U[c].copy())
    return r
'''


def _derivs(t):
    from .estudio import _atomos_derivada
    return _atomos_derivada(t.P)


def _conjunto(cx, prob, sol, series, fis, estado):
    """La misma trayectoria en el formato común de resultados (core/resultados):
    la formulación adimensional (ejes tau y xi, unidad 1) y, si las escalas
    tienen valor, las variables originales en SI con su dimensión."""
    from core import resultados as res
    from core import unidades as un
    ejes = [res.eje("tau", cx.tiempo or "tau", "tiempo", "1", sol.t)]
    if prob.coord:
        ejes.append(res.eje("xi", prob.coord, "coordenada", "1", prob.xi))
    dom = ["tau"] + (["xi"] if prob.coord else [])

    def valores(filas):
        return [[float(v) for v in f] for f in filas] if prob.coord else [float(f[0]) for f in filas]
    ser = [res.serie(u, u, "1", dom, valores(series[u]), propietarioId="formulacion") for u in prob.campos]

    def unidad(sid):
        d = cx._dimension_de(sid)
        return None if d is None else un.unidad_SI(d)
    t_si = fis.get("tiempo", {})
    u_t = unidad(t_si.get("variableId")) if t_si.get("variableId") else None
    fisico_ok = t_si.get("valoresSI") is not None and u_t is not None
    if fisico_ok and prob.coord:
        c = fis.get("coordenada") or {}
        u_x = unidad(c.get("variableId")) if c.get("variableId") else None
        fisico_ok = c.get("valoresSI") is not None and u_x is not None
    if fisico_ok:
        ejes.append(res.eje("t", t_si["variableId"], "tiempo", u_t, t_si["valoresSI"]))
        dom_f = ["t"]
        if prob.coord:
            ejes.append(res.eje("x", fis["coordenada"]["variableId"], "coordenada", u_x, fis["coordenada"]["valoresSI"]))
            dom_f.append("x")
        usados = {s_["id"] for s_ in ser}
        for vid, filas in fis["campos"].items():
            u_v = unidad(vid)
            if filas is None or u_v is None:
                continue
            ident = vid if vid not in usados else f"{vid}.SI"
            ser.append(res.serie(ident, vid, u_v, dom_f, filas if prob.coord else [f[0] for f in filas], propietarioId="modelo"))
    return res.conjunto("simulacion", "Simulación de la formulación", "resuelto",
                        {"motor": "adimensionalizacion.simulacion", "metodo": "BDF (metodo de lineas)", "firma": None},
                        ejes, ser)


def _tau_de(cx, t_si):
    """Tiempo adimensional de un tiempo fisico (s) por la inversa publicada."""
    from . import algebra as A
    if not cx.tiempo:
        raise NoEvaluable("tiempo", "el sistema no tiene variable de tiempo")
    m = next((m for m in cx.cuerpo.get("transformaciones") or [] if m["nuevoId"] == cx.tiempo), None)
    if m is None:
        return t_si
    vals = dict(cx.valores)
    vals[m["variableId"]] = t_si
    return float(np.real(evaluar_poli(A.canonica(m["inversa"], cx.ctx), vals)))


def _restitucion(cx, prob, sol, series):
    """Variables originales con las escalas numericas: v = g(v') del mapa."""
    from . import algebra as A
    mapas = {m["nuevoId"]: m for m in cx.cuerpo.get("transformaciones") or []}
    salida = {"campos": {}, "faltan": []}

    def aplicar(nuevo, valores_nuevos):
        m = mapas.get(nuevo)
        if m is None:
            return valores_nuevos, nuevo
        vals = dict(cx.valores)
        vals[nuevo] = np.asarray(valores_nuevos, dtype=float)
        try:
            return evaluar_poli(A.canonica(m["directa"], cx.ctx), vals) * np.ones_like(vals[nuevo]), m["variableId"]
        except NoEvaluable as e:
            salida["faltan"].append(e.mensaje)
            return None, m["variableId"]
    t, tid = aplicar(cx.tiempo, sol.t) if cx.tiempo else (None, None)
    salida["tiempo"] = {"variableId": tid, "valoresSI": t.tolist() if t is not None else None}
    if prob.coord:
        x, xid = aplicar(prob.coord, prob.xi)
        salida["coordenada"] = {"variableId": xid, "valoresSI": x.tolist() if x is not None else None}
    for u in prob.campos:
        filas = []
        vid = u
        for fila in series[u]:
            v, vid = aplicar(u, fila)
            if v is None:
                filas = None
                break
            filas.append(v.tolist())
        salida["campos"][vid] = filas
    salida["nota"] = "variables originales en SI con v = g(v') y las escalas numericas"
    _ = (math, numero_json)
    return salida
